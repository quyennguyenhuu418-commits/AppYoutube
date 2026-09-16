"""NarrationTimeline + DurationReconciliation tests (PROMPT 8 §26, §28, §29)."""
from __future__ import annotations

import pytest

from app.voice.schemas import (
    AudioArtifact,
    DurationReconciliationStrategy,
    NarrationScript,
    NarrationUnit,
    SpeechTiming,
    TimestampSource,
    WordTiming,
)
from app.voice.timeline import build_timeline, reconcile_duration


def _unit(narration_id: str, scene_id: str = "s1", text: str = "Hello world") -> NarrationUnit:
    return NarrationUnit(
        narration_id=narration_id, scene_id=scene_id, text=text, language="en",
    )


def _script() -> NarrationScript:
    return NarrationScript(
        script_id="s1", units=[
            _unit("n_0001", scene_id="s1", text="Rome fell."),
            _unit("n_0002", scene_id="s2", text="Constantinople rose."),
            _unit("n_0003", scene_id="s3", text="The world changed."),
        ],
    )


def _artifact(narration_id: str, voice_id: str = "v1",
               duration: float = 1.0) -> AudioArtifact:
    fp = "0123456789abcdef_0123456789abcdef"
    return AudioArtifact(
        artifact_id=fp, narration_id=narration_id, voice_id=voice_id,
        provider="mock", source_text_hash="0123456789abcdef",
        voice_config_hash="0123456789abcdef",
        format="wav", sample_rate=22050, channels=1, bits_per_sample=16,
        duration_sec=duration, uri=f"{fp}.wav", fingerprint=fp,
    )


def _timing(narration_id: str, duration: float = 1.0) -> SpeechTiming:
    return SpeechTiming(
        timing_id=f"t_{narration_id}", artifact_id="0123456789abcdef_0123456789abcdef",
        narration_id=narration_id, language="en",
        timestamp_source=TimestampSource.UNIFORM_ALIGNMENT,
        words=[WordTiming(word="x", start_sec=0.0, end_sec=duration)],
        duration_sec=duration,
        provider="mock",
    )


# ---------------------------------------------------------------------------
# reconcile_duration
# ---------------------------------------------------------------------------

def test_reconcile_follow_audio():
    r = reconcile_duration(
        audio_duration_sec=2.0, scene_duration_sec=2.5,
        animation_duration_sec=2.5, strategy=DurationReconciliationStrategy.FOLLOW_AUDIO,
    )
    assert r["audio_end_sec"] == 2.0
    assert r["scene_end_sec"] == 2.05  # 2.0 + default_padding 0.05


def test_reconcile_follow_scene():
    r = reconcile_duration(
        audio_duration_sec=3.0, scene_duration_sec=2.0,
        animation_duration_sec=2.0, strategy=DurationReconciliationStrategy.FOLLOW_SCENE,
    )
    assert r["audio_end_sec"] == 2.0
    assert r["scene_end_sec"] == 2.0
    assert r["post_roll_sec"] == 0.0


def test_reconcile_pad_to_scene():
    r = reconcile_duration(
        audio_duration_sec=2.0, scene_duration_sec=3.0,
        animation_duration_sec=3.0, strategy=DurationReconciliationStrategy.PAD_TO_SCENE,
    )
    assert r["audio_end_sec"] == 2.0
    assert r["scene_end_sec"] == 3.0  # max(3.0, 2.05)


def test_reconcile_fail_raises_on_mismatch():
    with pytest.raises(ValueError):
        reconcile_duration(
            audio_duration_sec=2.0, scene_duration_sec=5.0,
            animation_duration_sec=5.0, strategy=DurationReconciliationStrategy.FAIL,
        )


def test_reconcile_auto_maps_to_follow_audio():
    r = reconcile_duration(
        audio_duration_sec=1.0, scene_duration_sec=1.0,
        animation_duration_sec=1.0, strategy=DurationReconciliationStrategy.AUTO,
    )
    assert r["resolution_strategy"] == DurationReconciliationStrategy.FOLLOW_AUDIO.value


def test_reconcile_fail_within_tolerance():
    r = reconcile_duration(
        audio_duration_sec=1.0, scene_duration_sec=1.4,
        animation_duration_sec=1.4, strategy=DurationReconciliationStrategy.FAIL,
    )
    assert r["resolution_strategy"] == DurationReconciliationStrategy.FOLLOW_AUDIO.value


# ---------------------------------------------------------------------------
# build_timeline
# ---------------------------------------------------------------------------

def test_build_timeline_basic():
    script = _script()
    artifacts = {u.narration_id: _artifact(u.narration_id, duration=1.5)
                for u in script.units}
    timings = {u.narration_id: _timing(u.narration_id, duration=1.5)
               for u in script.units}
    tl = build_timeline(
        timeline_id="tl1", script=script,
        artifacts=artifacts, timings=timings,
        scene_durations={"s1": 2.0, "s2": 2.0, "s3": 2.0},
    )
    assert len(tl.entries) == 3
    # Entries are sequential.
    assert tl.entries[0].scene_start_sec == 0.0
    assert tl.entries[1].scene_start_sec == pytest.approx(tl.entries[0].scene_end_sec, abs=1e-3)
    # Each entry uses FOLLOW_AUDIO strategy by default.
    for e in tl.entries:
        assert e.resolution_strategy == DurationReconciliationStrategy.FOLLOW_AUDIO


def test_build_timeline_cursor_advances():
    script = _script()
    artifacts = {u.narration_id: _artifact(u.narration_id, duration=1.0)
                for u in script.units}
    timings = {u.narration_id: _timing(u.narration_id, duration=1.0)
               for u in script.units}
    tl = build_timeline(
        timeline_id="tl1", script=script,
        artifacts=artifacts, timings=timings,
    )
    # Each unit is ~1.05s, total ≈ 3.15s.
    assert tl.total_duration_sec == pytest.approx(3.15, abs=0.5)


def test_build_timeline_missing_artifact_recorded():
    script = _script()
    artifacts = {"n_0001": _artifact("n_0001")}
    timings = {"n_0001": _timing("n_0001")}
    tl = build_timeline(
        timeline_id="tl1", script=script, artifacts=artifacts, timings=timings,
    )
    assert len(tl.entries) == 1
    assert any("n_0002" in w or "n_0003" in w for w in tl.warnings)


def test_build_timeline_serialization():
    script = _script()
    artifacts = {u.narration_id: _artifact(u.narration_id, duration=1.0)
                for u in script.units}
    timings = {u.narration_id: _timing(u.narration_id, duration=1.0)
               for u in script.units}
    tl = build_timeline(
        timeline_id="tl1", script=script,
        artifacts=artifacts, timings=timings,
    )
    d = tl.to_dict()
    assert d["timeline_id"] == "tl1"
    assert len(d["entries"]) == 3


def test_build_timeline_respects_strategy():
    script = _script()
    artifacts = {u.narration_id: _artifact(u.narration_id, duration=1.0)
                for u in script.units}
    timings = {u.narration_id: _timing(u.narration_id, duration=1.0)
               for u in script.units}
    tl = build_timeline(
        timeline_id="tl1", script=script,
        artifacts=artifacts, timings=timings,
        scene_durations={"s1": 2.0, "s2": 2.0, "s3": 2.0},
        strategy=DurationReconciliationStrategy.FOLLOW_SCENE,
    )
    for e in tl.entries:
        assert e.resolution_strategy == DurationReconciliationStrategy.FOLLOW_SCENE


def test_build_timeline_padding_configurable():
    script = _script()
    artifacts = {u.narration_id: _artifact(u.narration_id, duration=1.0)
                for u in script.units}
    timings = {u.narration_id: _timing(u.narration_id, duration=1.0)
               for u in script.units}
    tl = build_timeline(
        timeline_id="tl1", script=script,
        artifacts=artifacts, timings=timings,
        default_padding_sec=0.5,
    )
    for e in tl.entries:
        assert e.padding_sec == pytest.approx(0.5, abs=1e-3)
