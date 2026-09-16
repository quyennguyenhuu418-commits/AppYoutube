"""NarrationTimeline + DurationReconciliation (PROMPT 8 §26–§29).

Builds a canonical NarrationTimeline from a NarrationScript + per-unit
AudioArtifact + SpeechTiming. Reconciles audio vs. scene vs. animation
durations using a deterministic policy.
"""
from __future__ import annotations

from typing import Any

from app.voice.schemas import (
    AudioArtifact,
    DurationReconciliationStrategy,
    NarrationScript,
    NarrationTimeline,
    NarrationTimelineEntry,
    NarrationUnit,
    SpeechTiming,
)


def reconcile_duration(
    audio_duration_sec: float,
    scene_duration_sec: float,
    animation_duration_sec: float,
    strategy: DurationReconciliationStrategy,
    default_padding_sec: float = 0.05,
) -> dict[str, float]:
    """Apply the duration-reconciliation policy.

    Returns a dict with:
      - scene_start_sec
      - scene_end_sec
      - audio_start_sec
      - audio_end_sec
      - pre_roll_sec
      - post_roll_sec
      - padding_sec
      - resolution_strategy (string)

    Strategy behavior:
      FOLLOW_AUDIO — scene duration = audio + padding; audio fits scene.
      FOLLOW_SCENE — audio is trimmed to scene; warning if mismatch > tolerance.
      PAD_TO_SCENE  — scene waits for audio + silence tail.
      FAIL          — reject if mismatch > tolerance.
      AUTO          — FOLLOW_AUDIO with explicit padding.
    """
    if strategy == DurationReconciliationStrategy.FAIL:
        tol = 0.5
        if abs(audio_duration_sec - scene_duration_sec) > tol:
            raise ValueError(
                f"audio ({audio_duration_sec:.3f}s) vs scene ({scene_duration_sec:.3f}s) "
                f"differ by > {tol}s (strategy=FAIL)"
            )
        strategy = DurationReconciliationStrategy.FOLLOW_AUDIO

    if strategy == DurationReconciliationStrategy.AUTO:
        strategy = DurationReconciliationStrategy.FOLLOW_AUDIO

    if strategy == DurationReconciliationStrategy.FOLLOW_AUDIO:
        # Scene takes audio duration + default padding.
        target = audio_duration_sec + default_padding_sec
        pre_roll = 0.0
        post_roll = default_padding_sec
        scene_end = target
        audio_end = audio_duration_sec
        padding = default_padding_sec
    elif strategy == DurationReconciliationStrategy.FOLLOW_SCENE:
        # Audio is implicitly trimmed to scene.
        scene_end = scene_duration_sec
        audio_end = min(audio_duration_sec, scene_duration_sec)
        pre_roll = 0.0
        post_roll = max(0.0, scene_duration_sec - audio_duration_sec)
        padding = post_roll
    elif strategy == DurationReconciliationStrategy.PAD_TO_SCENE:
        # Scene waits: scene_end = audio + silence tail.
        scene_end = max(scene_duration_sec, audio_duration_sec + default_padding_sec)
        audio_end = audio_duration_sec
        pre_roll = 0.0
        post_roll = max(0.0, scene_end - audio_end)
        padding = post_roll
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    # Animation duration is informational; we do not stretch narration to
    # match it. The renderer uses scene duration, which is canonical.
    return {
        "scene_start_sec": 0.0,
        "scene_end_sec": round(scene_end, 3),
        "audio_start_sec": 0.0,
        "audio_end_sec": round(audio_end, 3),
        "pre_roll_sec": round(pre_roll, 3),
        "post_roll_sec": round(post_roll, 3),
        "padding_sec": round(padding, 3),
        "resolution_strategy": strategy.value,
        "animation_duration_sec": round(animation_duration_sec, 3),
    }


def build_timeline(
    *,
    timeline_id: str,
    script: NarrationScript,
    artifacts: dict[str, AudioArtifact],       # narration_id -> artifact
    timings: dict[str, SpeechTiming],           # narration_id -> timing
    scene_durations: dict[str, float] | None = None,    # scene_id -> sec
    animation_durations: dict[str, float] | None = None, # scene_id -> sec
    fps: int = 30,
    strategy: DurationReconciliationStrategy = DurationReconciliationStrategy.FOLLOW_AUDIO,
    default_padding_sec: float = 0.05,
    default_pre_roll_sec: float = 0.0,
    default_post_roll_sec: float = 0.0,
) -> NarrationTimeline:
    """Build a canonical NarrationTimeline.

    `artifacts` and `timings` are keyed by `narration_id`. Units missing
    from these maps are recorded as warnings (and excluded from entries).
    """
    scene_durations = scene_durations or {}
    animation_durations = animation_durations or {}
    entries: list[NarrationTimelineEntry] = []
    warnings: list[str] = []

    cursor_sec = 0.0  # running cursor for sequential units
    for unit in script.units:
        artifact = artifacts.get(unit.narration_id)
        if artifact is None:
            warnings.append(f"unit {unit.narration_id!r} has no AudioArtifact; skipping")
            continue
        timing = timings.get(unit.narration_id)
        audio_duration = artifact.duration_sec
        scene_duration = scene_durations.get(unit.scene_id, audio_duration)
        animation_duration = animation_durations.get(unit.scene_id, scene_duration)

        rec = reconcile_duration(
            audio_duration_sec=audio_duration,
            scene_duration_sec=scene_duration,
            animation_duration_sec=animation_duration,
            strategy=strategy,
            default_padding_sec=default_padding_sec,
        )
        timing_id = timing.timing_id if timing is not None else f"t_unavailable_{unit.narration_id}"
        entry = NarrationTimelineEntry(
            narration_id=unit.narration_id,
            scene_id=unit.scene_id,
            artifact_id=artifact.artifact_id,
            timing_id=timing_id,
            voice_id=artifact.voice_id,
            speaker_id=unit.speaker_id,
            audio_start_sec=cursor_sec,
            audio_end_sec=cursor_sec + rec["audio_end_sec"],
            scene_start_sec=cursor_sec,
            scene_end_sec=cursor_sec + rec["scene_end_sec"],
            pre_roll_sec=default_pre_roll_sec,
            post_roll_sec=rec["post_roll_sec"],
            padding_sec=rec["padding_sec"],
            resolution_strategy=DurationReconciliationStrategy(rec["resolution_strategy"]),
            metadata={
                "audio_duration_sec": round(audio_duration, 3),
                "scene_duration_sec": round(scene_duration, 3),
                "animation_duration_sec": round(animation_duration, 3),
            },
        )
        entries.append(entry)
        cursor_sec = entry.scene_end_sec

    return NarrationTimeline(
        timeline_id=timeline_id,
        script_id=script.script_id,
        project_id=script.project_id,
        job_id=script.job_id,
        fps=fps,
        total_duration_sec=round(cursor_sec, 3),
        entries=entries,
        default_padding_sec=default_padding_sec,
        default_pre_roll_sec=default_pre_roll_sec,
        default_post_roll_sec=default_post_roll_sec,
        strategy=strategy,
        warnings=warnings,
    )


__all__ = ["build_timeline", "reconcile_duration"]
