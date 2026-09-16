"""Voice / TTS / Audio canonical contract tests (C-17).

PROMPT 8 §6–§17: VoiceDefinition, VoiceInstance, VoiceRegistry,
NarrationScript, AudioArtifact, SpeechTiming, NarrationTimeline.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.voice.schemas import (
    AudioArtifact,
    AudioArtifactStatus,
    DurationReconciliationStrategy,
    EmphasisHint,
    NarrationScript,
    NarrationTimeline,
    NarrationTimelineEntry,
    NarrationUnit,
    PronunciationHint,
    SegmentTiming,
    SpeakerRole,
    SpeechTiming,
    TimestampSource,
    TtsProviderName,
    VoiceDefinition,
    VoiceInstance,
    VoiceLifecycleStatus,
    VoiceRegistry,
    VoiceRegistryEntry,
    VoiceResolution,
    VoiceSettings,
    WordTiming,
    compute_audio_fingerprint,
    compute_text_hash,
    compute_voice_config_hash,
)


# ============================================================================
# VoiceDefinition
# ============================================================================

def _voice(**overrides) -> VoiceDefinition:
    defaults = dict(
        voice_id="narrator_en",
        name="Narrator EN",
        language="en",
        provider=TtsProviderName.MOCK,
        status=VoiceLifecycleStatus.APPROVED,
    )
    defaults.update(overrides)
    return VoiceDefinition(**defaults)


def test_voice_definition_basic():
    v = _voice()
    assert v.voice_id == "narrator_en"
    assert v.language == "en"
    assert v.provider == TtsProviderName.MOCK
    assert v.status == VoiceLifecycleStatus.APPROVED
    assert v.supported_languages == ["en"]
    assert v.locale == "en-XX"  # auto-filled


def test_voice_definition_id_must_be_snake_case():
    with pytest.raises(ValidationError):
        _voice(voice_id="BadID!")
    with pytest.raises(ValidationError):
        _voice(voice_id="with spaces")


def test_voice_definition_locale_default():
    v = _voice(language="vi", locale="vi-VN")
    assert v.locale == "vi-VN"
    v2 = _voice(language="ko")
    assert v2.locale == "ko-XX"


def test_voice_definition_serialization_roundtrip():
    v = _voice()
    d = v.to_dict()
    v2 = VoiceDefinition.model_validate(d)
    assert v == v2


def test_voice_settings_bounds():
    s = VoiceSettings(speaking_rate=0.5, pitch=2.0, stability=0.0, similarity=1.0)
    assert s.speaking_rate == 0.5
    assert s.pitch == 2.0
    with pytest.raises(ValidationError):
        VoiceSettings(speaking_rate=0.1)   # < 0.5
    with pytest.raises(ValidationError):
        VoiceSettings(speaking_rate=3.0)   # > 2.0


def test_pronunciation_hint_validation():
    h = PronunciationHint(hint_id="h1", word="Rome", phonetic="roʊm")
    assert h.phonetic == "roʊm"
    with pytest.raises(ValidationError):
        PronunciationHint(hint_id="", word="x")


def test_emphasis_hint_pacing_bounds():
    e = EmphasisHint(hint_id="e1", text="important", intensity=0.8, pacing_change=-0.2)
    assert e.intensity == 0.8
    with pytest.raises(ValidationError):
        EmphasisHint(hint_id="e2", text="x", intensity=2.0)
    with pytest.raises(ValidationError):
        EmphasisHint(hint_id="e3", text="x", pacing_change=1.0)


# ============================================================================
# VoiceInstance
# ============================================================================

def test_voice_instance_basic():
    vi = VoiceInstance(instance_id="inst_1", voice_id="narrator_en", speaker_role="narrator")
    assert vi.voice_id == "narrator_en"


def test_voice_instance_speaker_id_compatible():
    vi = VoiceInstance(instance_id="inst_1", voice_id="narrator_en", speaker_id="narrator")
    assert vi.speaker_id_compatible("narrator")
    assert not vi.speaker_id_compatible("character_a")
    vi2 = VoiceInstance(instance_id="inst_2", voice_id="narrator_en", speaker_id="")
    assert vi2.speaker_id_compatible("anything")  # project-wide


# ============================================================================
# VoiceRegistry / RegistryEntry
# ============================================================================

def test_voice_registry_entry_lifecycle():
    e = VoiceRegistryEntry(voice_id="v1", status=VoiceLifecycleStatus.APPROVED)
    assert e.voice_id == "v1"
    assert e.usage_count == 0


def test_voice_registry_serialization():
    r = VoiceRegistry(project_id="proj_1", voices=[
        VoiceRegistryEntry(voice_id="v1"),
        VoiceRegistryEntry(voice_id="v2", status=VoiceLifecycleStatus.ACTIVE),
    ])
    d = r.to_dict()
    assert len(d["voices"]) == 2


# ============================================================================
# NarrationScript
# ============================================================================

def _unit(**overrides) -> NarrationUnit:
    defaults = dict(
        narration_id="n_0001",
        text="Rome fell in 476 AD",
        speaker_id="narrator",
        language="en",
    )
    defaults.update(overrides)
    return NarrationUnit(**defaults)


def test_narration_unit_basic():
    u = _unit()
    assert u.narration_id == "n_0001"
    assert u.locale == "en-XX"


def test_narration_unit_duplicate_ids_rejected():
    with pytest.raises(ValidationError):
        NarrationScript(script_id="s1", units=[_unit(), _unit()])


def test_narration_script_default_voice_validation():
    NarrationScript(script_id="s1", units=[_unit()], default_voice_id="narrator_en")
    with pytest.raises(ValidationError):
        NarrationScript(script_id="s1", units=[_unit()], default_voice_id="Bad ID!")


def test_narration_script_serialization():
    s = NarrationScript(script_id="s1", units=[_unit(), _unit(narration_id="n_0002", text="Ok.")])
    d = s.to_dict()
    s2 = NarrationScript.model_validate(d)
    assert s == s2


def test_narration_unit_speaker_role_default():
    assert _unit().speaker_role == SpeakerRole.NARRATOR


# ============================================================================
# AudioArtifact
# ============================================================================

def _artifact(**overrides) -> AudioArtifact:
    defaults = dict(
        artifact_id="0123456789abcdef_0123456789abcdef",
        narration_id="n_0001",
        voice_id="narrator_en",
        provider=TtsProviderName.MOCK,
        source_text_hash="0123456789abcdef",
        voice_config_hash="0123456789abcdef",
        format="wav",
        sample_rate=22050,
        channels=1,
        bits_per_sample=16,
        duration_sec=1.234,
        uri="audio.wav",
        absolute_path="/tmp/audio.wav",
        fingerprint="0123456789abcdef_0123456789abcdef",
        status=AudioArtifactStatus.GENERATED,
    )
    defaults.update(overrides)
    return AudioArtifact(**defaults)


def test_audio_artifact_basic():
    a = _artifact()
    assert a.artifact_id == "0123456789abcdef_0123456789abcdef"
    assert a.fingerprint == "0123456789abcdef_0123456789abcdef"


def test_audio_artifact_id_must_be_two_16hex():
    with pytest.raises(ValidationError):
        _artifact(artifact_id="bad")
    with pytest.raises(ValidationError):
        _artifact(artifact_id="0123456789abcdef_0123456789abcde")  # 15 chars


def test_audio_artifact_serializes_clean():
    a = _artifact()
    d = a.to_dict()
    a2 = AudioArtifact.model_validate(d)
    assert a == a2


# ============================================================================
# SpeechTiming
# ============================================================================

def test_word_timing_ordering():
    w = WordTiming(word="Rome", start_sec=0.0, end_sec=0.5)
    assert w.end_sec > w.start_sec
    with pytest.raises(ValidationError):
        WordTiming(word="x", start_sec=1.0, end_sec=0.5)


def test_segment_timing_ordering():
    with pytest.raises(ValidationError):
        SegmentTiming(text="x", start_sec=2.0, end_sec=1.0)


def test_speech_timing_basic():
    t = SpeechTiming(
        timing_id="t1",
        artifact_id="0123456789abcdef_0123456789abcdef",
        narration_id="n_0001",
        language="en",
        timestamp_source=TimestampSource.UNIFORM_ALIGNMENT,
        duration_sec=2.0,
        words=[
            WordTiming(word="Rome", start_sec=0.0, end_sec=1.0),
            WordTiming(word="fell", start_sec=1.0, end_sec=2.0),
        ],
    )
    assert len(t.words) == 2


def test_speech_timing_word_beyond_duration_rejected():
    with pytest.raises(ValidationError):
        SpeechTiming(
            timing_id="t1",
            artifact_id="0123456789abcdef_0123456789abcdef",
            narration_id="n_0001",
            language="en",
            duration_sec=1.0,
            words=[WordTiming(word="x", start_sec=0.0, end_sec=2.0)],  # 2.0 > 1.0+0.5
        )


def test_speech_timing_far_overlap_rejected():
    with pytest.raises(ValidationError):
        SpeechTiming(
            timing_id="t1",
            artifact_id="0123456789abcdef_0123456789abcdef",
            narration_id="n_0001",
            language="en",
            duration_sec=5.0,
            words=[
                WordTiming(word="a", start_sec=0.0, end_sec=1.0),
                WordTiming(word="b", start_sec=0.1, end_sec=0.5),  # 0.1 < 1.0-0.5
            ],
        )


# ============================================================================
# NarrationTimeline
# ============================================================================

def test_narration_timeline_entry_ordering():
    with pytest.raises(ValidationError):
        NarrationTimelineEntry(
            narration_id="n1",
            artifact_id="0123456789abcdef_0123456789abcdef",
            timing_id="t1",
            voice_id="v1",
            audio_start_sec=2.0,
            audio_end_sec=1.0,
            scene_start_sec=0.0,
            scene_end_sec=5.0,
        )


def test_narration_timeline_basic():
    e = NarrationTimelineEntry(
        narration_id="n1",
        artifact_id="0123456789abcdef_0123456789abcdef",
        timing_id="t1",
        voice_id="v1",
        audio_start_sec=0.0,
        audio_end_sec=2.0,
        scene_start_sec=0.0,
        scene_end_sec=2.5,
    )
    t = NarrationTimeline(
        timeline_id="tl1",
        script_id="s1",
        entries=[e],
        strategy=DurationReconciliationStrategy.FOLLOW_AUDIO,
    )
    assert t.total_duration_sec == 0.0
    d = t.to_dict()


# ============================================================================
# VoiceResolution
# ============================================================================

def test_voice_resolution_basic():
    r = VoiceResolution(
        resolution_id="res_1",
        narration_id="n_0001",
        resolved_voice_id="narrator_en",
        resolved_provider=TtsProviderName.MOCK,
        strategy="explicit",
        settings_used=VoiceSettings(),
    )
    assert r.resolved_voice_id == "narrator_en"


# ============================================================================
# Fingerprinting helpers
# ============================================================================

def test_compute_text_hash_deterministic():
    h1 = compute_text_hash("Rome fell in 476 AD")
    h2 = compute_text_hash("  Rome  fell in   476 AD  ")
    assert h1 == h2
    assert len(h1) == 16


def test_compute_voice_config_hash_changes_with_settings():
    v = _voice()
    h1 = compute_voice_config_hash(v)
    s2 = VoiceSettings(speaking_rate=1.2)
    h2 = compute_voice_config_hash(v, s2)
    assert h1 != h2


def test_compute_audio_fingerprint_changes_with_text():
    v = _voice()
    f1 = compute_audio_fingerprint("Rome fell", v)
    f2 = compute_audio_fingerprint("Constantinople rose", v)
    assert f1 != f2


def test_compute_audio_fingerprint_stable_for_same_input():
    v = _voice()
    f1 = compute_audio_fingerprint("Hello world", v)
    f2 = compute_audio_fingerprint("Hello world", v)
    assert f1 == f2
