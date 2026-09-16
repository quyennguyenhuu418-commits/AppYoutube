"""CaptionCompiler (PROMPT 9 §2, §21, §22, §35, §36).

Pure, deterministic compiler. Input is a ``NarrationTimeline`` plus the
per-entry ``SpeechTiming`` map and narration text map. Output is a list
of ``CaptionTrack`` (one per scene).

Pipeline:

    NarrationTimeline
    + SpeechTiming (per narration_id)
    + NarrationUnit text (per narration_id)
    + CaptionStyle
    → SegmentationPolicy
    → CaptionSegmenter
    → LineBreaker
    → TimingQualityScore
    → validate_caption_track
    → CaptionTrack[]

No LLM. No wall-clock. No random IDs (deterministic from inputs).

Scene-level scene_start_sec / scene_end_sec comes from
``NarrationTimelineEntry`` (PROMPT 9 §21). Animation timing is NOT
duplicated here — we only expose timing anchors.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from app.captions.line_breaker import LineBreaker
from app.captions.quality import compute_timing_quality
from app.captions.schemas import (
    CaptionStyle,
    CaptionTrack,
)
from app.captions.segmenter import (
    CaptionSegmenter,
    SegmentationPolicy,
)
from app.captions.validator import validate_caption_track
from app.voice.schemas import (
    NarrationTimeline,
    NarrationTimelineEntry,
    SpeechTiming,
    TimestampSource,
)


def compute_caption_id(
    narration_timeline_id: str, scene_id: str, style_id: str, fps: int,
) -> str:
    """Deterministic caption_id from canonical inputs."""
    payload = f"{narration_timeline_id}|{scene_id}|{style_id}|{fps}"
    return "cap_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class CaptionCompileRequest:
    """One compile request."""
    timeline: NarrationTimeline
    timings: dict[str, SpeechTiming]   # narration_id → SpeechTiming
    text: dict[str, str]               # narration_id → narration text
    style: CaptionStyle
    style_id: str = "default"
    segmenter_policy: SegmentationPolicy | None = None


@dataclass(frozen=True)
class CaptionCompileResult:
    tracks: list[CaptionTrack]
    failures: list[str]
    warnings: list[str]


class CaptionCompiler:
    """Pure deterministic caption compiler."""

    def __init__(self, policy: SegmentationPolicy | None = None) -> None:
        self._policy = policy or SegmentationPolicy()
        self._segmenter = CaptionSegmenter(self._policy)
        self._line_breaker = LineBreaker()

    @property
    def policy(self) -> SegmentationPolicy:
        return self._policy

    def compile(self, request: CaptionCompileRequest) -> CaptionCompileResult:
        timeline = request.timeline
        style = request.style
        style_id = request.style_id
        tracks: list[CaptionTrack] = []
        failures: list[str] = []
        warnings: list[str] = []

        # Group entries by scene.
        by_scene: dict[str, list[NarrationTimelineEntry]] = {}
        for e in timeline.entries:
            if not e.scene_id:
                # Entry has no scene; skip with warning (PROMPT 9 §45).
                warnings.append(
                    f"timeline entry {e.narration_id} has no scene_id; skipping"
                )
                continue
            by_scene.setdefault(e.scene_id, []).append(e)

        for scene_id, entries in by_scene.items():
            track = self._compile_scene(
                scene_id=scene_id,
                entries=entries,
                timeline=timeline,
                timings=request.timings,
                text=request.text,
                style=style,
                style_id=style_id,
                warnings=warnings,
                failures=failures,
            )
            if track is None:
                continue
            tracks.append(track)

        return CaptionCompileResult(
            tracks=tracks,
            failures=failures,
            warnings=warnings,
        )

    def _compile_scene(
        self,
        scene_id: str,
        entries: Sequence[NarrationTimelineEntry],
        timeline: NarrationTimeline,
        timings: dict[str, SpeechTiming],
        text: dict[str, str],
        style: CaptionStyle,
        style_id: str,
        warnings: list[str],
        failures: list[str],
    ) -> CaptionTrack | None:
        if not entries:
            failures.append(f"scene {scene_id} has no entries")
            return None
        # Scene bounds: union of entry bounds.
        scene_start = min(e.scene_start_sec for e in entries)
        scene_end = max(e.scene_end_sec for e in entries)
        # Track-level timestamp_source: if any entry uses UNIFORM, track inherits.
        track_ts_source = None
        # We'll determine track-level source from segment-level sources.

        all_segments = []
        scene_warnings: list[str] = []
        for entry in entries:
            timing = timings.get(entry.narration_id)
            narration_text = text.get(entry.narration_id, "")
            if timing is None:
                failures.append(
                    f"scene {scene_id} narration {entry.narration_id} "
                    f"missing SpeechTiming"
                )
                continue
            if not narration_text:
                failures.append(
                    f"scene {scene_id} narration {entry.narration_id} "
                    f"missing narration text"
                )
                continue

            # Shift words by audio_start_sec so they live on the
            # scene timeline (PROMPT 9 §21 — scene_start is authority).
            shifted_words = [
                type(timing.words[0])(
                    word=w.word,
                    start_sec=round(entry.audio_start_sec + w.start_sec, 6),
                    end_sec=round(entry.audio_start_sec + w.end_sec, 6),
                    confidence=w.confidence,
                )
                for w in timing.words
            ]
            shifted_segments = [
                type(timing.segments[0])(
                    text=s.text,
                    start_sec=round(entry.audio_start_sec + s.start_sec, 6),
                    end_sec=round(entry.audio_start_sec + s.end_sec, 6),
                )
                for s in timing.segments
            ]
            shifted_duration = (
                entry.audio_start_sec + timing.duration_sec
            )
            shifted_timing = SpeechTiming(
                timing_id=timing.timing_id,
                artifact_id=timing.artifact_id,
                narration_id=timing.narration_id,
                language=timing.language,
                timestamp_source=timing.timestamp_source,
                words=shifted_words,
                segments=shifted_segments,
                duration_sec=round(shifted_duration, 6),
                provider=timing.provider,
                metadata=dict(timing.metadata),
            )

            seg_result = self._segmenter.segment(
                speech_timing=shifted_timing,
                timeline_entry=entry,
                narration_text=narration_text,
                artifact_id=entry.artifact_id,
                style=style,
                style_id=style_id,
            )
            scene_warnings.extend(seg_result.warnings)

            # Apply line breaking.
            for seg in seg_result.segments:
                lb = self._line_breaker.break_segment(seg, style=style)
                # Mutate-in-place: assign back the new lines.
                seg.lines = lb.new_lines
                for w in lb.warnings:
                    seg.warnings.append(w)
                if lb.hard_split_used:
                    warnings.append(
                        f"segment {seg.segment_id} used hard split"
                    )

            all_segments.extend(seg_result.segments)

        if not all_segments:
            failures.append(f"scene {scene_id} produced no segments")
            return None

        # Resolve track-level timestamp_source (most conservative wins).
        sources = {s.timestamp_source for s in all_segments}
        if TimestampSource.UNAVAILABLE in sources:
            track_ts_source = "unavailable"  # not used in practice — UNAVAILABLE → UNIFORM
        elif TimestampSource.UNIFORM_ALIGNMENT in sources:
            track_ts_source = "uniform_alignment"
        elif TimestampSource.FORCED_ALIGNMENT in sources:
            track_ts_source = "forced_alignment"
        else:
            track_ts_source = "provider_native"

        # Backfill caption_id on every segment.
        caption_id = compute_caption_id(
            narration_timeline_id=timeline.timeline_id,
            scene_id=scene_id,
            style_id=style_id,
            fps=timeline.fps,
        )
        for s in all_segments:
            s.caption_id = caption_id

        track = CaptionTrack(
            track_id=f"{caption_id}_track",
            caption_id=caption_id,
            project_id=timeline.project_id,
            job_id=timeline.job_id,
            narration_timeline_id=timeline.timeline_id,
            scene_id=scene_id,
            language=entries[0].metadata.get("language", "en")
                if entries[0].metadata.get("language")
                else "en",
            locale=entries[0].metadata.get("locale", "en-US")
                if entries[0].metadata.get("locale")
                else "en-US",
            fps=timeline.fps,
            style=style,
            style_id=style_id,
            segments=all_segments,
            timestamp_source=track_ts_source,
            alignment_provider_id="",
            scene_start_sec=scene_start,
            scene_end_sec=scene_end,
            warnings=list(scene_warnings),
        )

        # Quality score (best-effort, uses the first entry's timing if present).
        first_narration = entries[0].narration_id
        ref_timing = timings.get(first_narration)
        if ref_timing is not None:
            track.quality = compute_timing_quality(ref_timing)

        # Validate.
        val = validate_caption_track(track)
        if not val.ok:
            for e in val.errors:
                failures.append(f"{e.code}: {e.message}")
            return None
        for w in val.warnings:
            track.warnings.append(w)

        # Forward scene warnings to top-level warnings list too.
        warnings.extend(scene_warnings)

        return track


__all__ = [
    "CaptionCompiler",
    "CaptionCompileRequest",
    "CaptionCompileResult",
    "compute_caption_id",
]
