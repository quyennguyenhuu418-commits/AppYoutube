"""
P13 — ShortsCompiler: deterministic short composition planning.

Takes the full pipeline output (scene_definition, captions, render metadata)
and produces a ShortsPlan with intelligent scene selection and crop composition.

Key decisions:
- Scene selection: prefer narration/diagram scenes with emotional content
- Crop composition: center subject based on crop_mode
- Caption repositioning: captions move to lower third for vertical video
- Duration: 15-60s optimal for short-form platforms
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.shorts.schemas import (
    CaptionPositionOverride,
    CropMode,
    SceneCropSpec,
    ShortsAspectRatio,
    ShortsCompilationResult,
    ShortsPlan,
    ShortsQuality,
    ShortsRenderSettings,
    ShortsSourceContext,
    ShortsTargetPlatform,
)


# =============================================================================
# Scene scoring for intelligent selection
# =============================================================================


# Emotional tags that make a scene "triumphant" or engaging for shorts
_HIGH_ENGAGEMENT_TAGS = frozenset({
    "triumphant", "warm", "uplifting", "reveal", "conclusion",
    "dramatic", "climactic", "inspiring", "satisfying",
})

# Tags that are less engaging for shorts (often slower pacing)
_LOW_ENGAGEMENT_TAGS = frozenset({
    "setup", "transition", "b_roll", "silence", "wait",
})


@dataclass(frozen=True)
class _ScoredScene:
    scene_id: str
    scene_label: str
    start_sec: float
    end_sec: float
    kind: str
    emotional_intent: str | None
    has_narration: bool
    has_diagram: bool
    score: float


def _score_scene(scene: dict[str, Any], video_duration: float) -> _ScoredScene:
    """Score a scene for shorts suitability.

    Higher score = better candidate for a short.
    """
    start = float(scene.get("start_sec", 0))
    end = float(scene.get("end_sec", start))
    duration = end - start
    kind = scene.get("kind", "unknown")
    emotional = scene.get("emotional_intent", None)

    score = 0.0

    # Duration: prefer 15-60s (shorts ideal length)
    if 15.0 <= duration <= 60.0:
        score += 10.0
    elif 10.0 <= duration < 15.0:
        score += 5.0
    elif 60.0 < duration <= 90.0:
        score += 5.0  # Can be trimmed

    # Kind: narration and diagram scenes are best
    if kind == "narration":
        score += 20.0
    elif kind == "diagram":
        score += 15.0
    elif kind == "title":
        score -= 10.0  # Title scenes are usually not short-worthy

    # Emotional intent: high-engagement tags boost score
    if emotional:
        if emotional in _HIGH_ENGAGEMENT_TAGS:
            score += 15.0
        elif emotional in _LOW_ENGAGEMENT_TAGS:
            score -= 10.0

    # Position in video: scenes near middle or at climax are better
    midpoint = video_duration / 2
    scene_mid = (start + end) / 2
    dist_from_middle = abs(scene_mid - midpoint) / (video_duration or 1)
    if dist_from_middle < 0.1:
        score += 8.0  # Near the middle
    elif dist_from_middle < 0.25:
        score += 4.0
    elif scene_mid > midpoint:
        score += 6.0  # Slightly favor the climax (second half)

    # Has narration: narration scenes are more engaging
    narration = scene.get("has_narration", scene.get("narration", False))
    if narration:
        score += 5.0

    # Has diagram: diagrams are visual hook
    diagram = scene.get("has_diagram") or scene.get("diagram", False)
    if diagram:
        score += 3.0

    return _ScoredScene(
        scene_id=str(scene.get("id", f"scene_{start:.1f}")),
        scene_label=str(scene.get("label", scene.get("kind", "unknown"))),
        start_sec=start,
        end_sec=end,
        kind=kind,
        emotional_intent=emotional,
        has_narration=bool(narration),
        has_diagram=bool(diagram),
        score=score,
    )


# =============================================================================
# Composition helpers
# =============================================================================


def _compute_crop_center(
    scene: dict[str, Any],
    crop_mode: CropMode,
) -> tuple[float, float]:
    """Compute the crop center (x, y) in normalized 0-1 coordinates.

    For 16:9 -> 9:16 conversion, we need to:
    1. Determine the horizontal center based on subject/focus
    2. Vertical center is typically 0.4-0.5 (subject slightly above center)
    """
    # Check for explicit focus point
    focus_x = scene.get("focus_x")
    focus_y = scene.get("focus_y")
    if focus_x is not None and focus_y is not None:
        return float(focus_x), float(focus_y)

    # Check for character positions (from animation/scene data)
    character_positions = scene.get("character_positions", [])
    if character_positions:
        # Average x position of characters
        avg_x = sum(p.get("x", 0.5) for p in character_positions) / len(character_positions)
        avg_y = sum(p.get("y", 0.5) for p in character_positions) / len(character_positions)
        return avg_x, avg_y

    # Check narration speaker position (if scene has narration)
    speaker_x = scene.get("speaker_x")
    if speaker_x is not None:
        return float(speaker_x), 0.45

    # Default based on crop mode
    if crop_mode == CropMode.RULE_OF_THIRDS:
        return 0.33, 0.4  # Upper left third (classic composition)
    elif crop_mode == CropMode.SMART_FACE:
        return 0.5, 0.4  # Center, slightly above
    else:
        return 0.5, 0.45  # Default center


# =============================================================================
# ShortsCompiler
# =============================================================================


class ShortsCompiler:
    """Compile a ShortsPlan from pipeline output."""

    def __init__(
        self,
        target_aspect_ratio: ShortsAspectRatio = ShortsAspectRatio.ASPECT_9_16,
        target_platform: ShortsTargetPlatform = ShortsTargetPlatform.YOUTUBE_SHORTS,
        render_settings: ShortsRenderSettings | None = None,
        max_shorts: int = 3,
        diversify_scenes: bool = True,
    ) -> None:
        self.target_aspect_ratio = target_aspect_ratio
        self.target_platform = target_platform
        self.render_settings = render_settings or ShortsRenderSettings()
        self.max_shorts = max_shorts
        self.diversify_scenes = diversify_scenes

    def compile(
        self,
        job_id: str,
        source_video_path: str,
        scene_definition: dict[str, Any],
        render_metadata: dict[str, Any] | None = None,
        caption_track: dict[str, Any] | None = None,
    ) -> ShortsPlan:
        """Compile a ShortsPlan from scene definition.

        Parameters:
            job_id: Job identifier
            source_video_path: Path to the final.mp4
            scene_definition: Parsed scene_definition.json
            render_metadata: Optional render metadata (fps, dimensions)
            caption_track: Optional caption track data

        Returns:
            ShortsPlan with one or more ShortsCompilationResult
        """
        render_meta = render_metadata or {}
        scenes = scene_definition.get("scenes", [])
        meta = scene_definition.get("meta", {})
        video_duration = float(meta.get("target_duration_sec", 60.0))

        # Score all candidate scenes
        scored = [_score_scene(s, video_duration) for s in scenes]
        # Filter to narration/diagram scenes with positive score
        candidates = [s for s in scored if s.score > 0 and s.kind in ("narration", "diagram")]
        if not candidates:
            # Fall back to all scenes with any score
            candidates = [s for s in scored if s.score > 0]
        if not candidates:
            # Last resort: use the middle scene
            if scenes:
                candidates = [_score_scene(scenes[len(scenes) // 2], video_duration)]
            else:
                candidates = []

        # Sort by score (highest first)
        candidates.sort(key=lambda s: s.score, reverse=True)

        # Diversify: pick scenes from different parts of the video
        selected = self._diversified_select(candidates, video_duration)

        # Build source context
        fps = float(render_meta.get("fps", 30.0))
        width = int(render_meta.get("width", 1280))
        height = int(render_meta.get("height", 720))
        source = ShortsSourceContext(
            job_id=job_id,
            source_video_path=source_video_path,
            source_duration_sec=video_duration,
            source_width=width,
            source_height=height,
            source_fps=fps,
            source_ar="16:9",
            scenes=tuple(
                SceneCropSpec(
                    scene_id=cs.scene_id,
                    scene_label=cs.scene_label,
                    start_sec=cs.start_sec,
                    end_sec=cs.end_sec,
                    crop_mode=CropMode.SMART_FACE,
                    has_narration=cs.has_narration,
                    has_diagram=cs.has_diagram,
                    emotional_intent=cs.emotional_intent,
                )
                for cs in selected
            ),
            caption_track_id=None,  # TODO: link to caption track
        )

        # Build results
        results: list[ShortsCompilationResult] = []
        for i, cs in enumerate(selected):
            crop_mode = CropMode.SMART_FACE
            center_x, center_y = 0.5, 0.45  # Default center

            # Find the original scene dict for composition hints
            orig_scene = next(
                (s for s in scenes if str(s.get("id")) == cs.scene_id),
                {},
            )
            center_x, center_y = _compute_crop_center(orig_scene, crop_mode)

            # Compute time boundaries
            start = max(0.0, cs.start_sec)
            end = min(cs.end_sec, video_duration)
            # Clamp to max duration
            max_dur = self.render_settings.max_duration_sec
            if end - start > max_dur:
                end = start + max_dur
            duration = end - start

            # Build caption override for vertical
            caption_override = CaptionPositionOverride(
                vertical_position=0.78,  # Lower third
                horizontal_align="center",
                font_scale=1.0,
                max_width_pct=0.9,
            )

            result = ShortsCompilationResult(
                shorts_id=f"short_{job_id}_{i:02d}",
                job_id=job_id,
                source=source,
                selected_scene=SceneCropSpec(
                    scene_id=cs.scene_id,
                    scene_label=cs.scene_label,
                    start_sec=cs.start_sec,
                    end_sec=cs.end_sec,
                    crop_mode=crop_mode,
                    focus_x=center_x,
                    focus_y=center_y,
                    has_narration=cs.has_narration,
                    has_diagram=cs.has_diagram,
                    emotional_intent=cs.emotional_intent,
                ),
                crop_mode=crop_mode,
                aspect_ratio=self.target_aspect_ratio,
                render_settings=self.render_settings,
                caption_override=caption_override,
                clip_start_sec=start,
                clip_end_sec=end,
                clip_duration_sec=duration,
                crop_center_x=center_x,
                crop_center_y=center_y,
                composition_notes=self._composition_note(cs, center_x, center_y),
                output_filename=f"short_{cs.scene_id}.mp4",
            )
            results.append(result)

        return ShortsPlan(
            job_id=job_id,
            shorts_ids=tuple(r.shorts_id for r in results),
            results=tuple(results),
            generate_multiple=len(results) > 1,
            max_shorts=self.max_shorts,
            diversify_scenes=self.diversify_scenes,
            target_platforms=(self.target_platform,),
            render_settings=self.render_settings,
        )

    def _diversified_select(
        self,
        candidates: list[_ScoredScene],
        video_duration: float,
    ) -> list[_ScoredScene]:
        """Select diverse scenes spread across the video."""
        if not candidates:
            return []
        if len(candidates) <= self.max_shorts:
            return candidates[: self.max_shorts]

        # Group by position in video
        selected: list[_ScoredScene] = []
        used_positions: set[int] = set()

        for cs in candidates:
            if len(selected) >= self.max_shorts:
                break
            # Compute which 1/3 of the video this scene is in
            scene_mid = (cs.start_sec + cs.end_sec) / 2
            third = int((scene_mid / video_duration) * 3) if video_duration > 0 else 0
            third = min(third, 2)

            if third not in used_positions or len(selected) < 2:
                selected.append(cs)
                if self.diversify_scenes:
                    used_positions.add(third)

        return selected

    @staticmethod
    def _composition_note(scene: _ScoredScene, cx: float, cy: float) -> str:
        parts = []
        if scene.kind == "narration":
            parts.append("Narration-focused composition")
        elif scene.kind == "diagram":
            parts.append("Diagram-centered framing")
        if scene.emotional_intent:
            parts.append(f"Emotional tone: {scene.emotional_intent}")
        if cx < 0.4:
            parts.append("Subject positioned left (rule of thirds)")
        elif cx > 0.6:
            parts.append("Subject positioned right")
        if not parts:
            parts.append("Center composition")
        return "; ".join(parts)


# =============================================================================
# Fingerprint (deterministic)
# =============================================================================


def shorts_plan_fingerprint(plan: ShortsPlan) -> str:
    """Deterministic fingerprint for a ShortsPlan."""
    parts = [
        plan.job_id,
        str(plan.generate_multiple),
        str(plan.max_shorts),
        str(len(plan.results)),
    ]
    for r in plan.results:
        parts.extend([
            r.selected_scene.scene_id,
            f"{r.clip_start_sec:.3f}",
            f"{r.clip_end_sec:.3f}",
            r.crop_mode.value,
            f"{r.crop_center_x:.3f}",
            f"{r.crop_center_y:.3f}",
        ])
    text = "|".join(parts)
    return hashlib.sha256(text.encode()).hexdigest()[:32]


__all__ = [
    "ShortsCompiler",
    "shorts_plan_fingerprint",
]
