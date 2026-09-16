"""Mock TTS provider tests (PROMPT 8 §21, §37)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.voice.mock_tts import MockTTSProvider
from app.voice.provider_base import (
    TTSEmptyTextError,
    VoiceTTSRequest,
)
from app.voice.schemas import (
    TtsProviderName,
    VoiceDefinition,
    VoiceLifecycleStatus,
    VoiceSettings,
    compute_audio_fingerprint,
)


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


def _request(text: str, voice: VoiceDefinition, output_path: str):
    fp = compute_audio_fingerprint(text, voice)
    return VoiceTTSRequest(
        text=text,
        voice=voice,
        settings_override=None,
        output_path=output_path,
        language=voice.language,
        locale=voice.locale,
        pronunciation_hints=[],
        fingerprint=fp,
    )


# ---------------------------------------------------------------------------
# Synthesis produces a real file
# ---------------------------------------------------------------------------

def test_mock_synthesize_creates_wav(tmp_path: Path):
    p = MockTTSProvider()
    voice = _voice()
    text = "Rome fell in 476 AD"
    out = tmp_path / "audio.wav"
    resp = p.synthesize(_request(text, voice, str(out)))
    assert resp.audio_path == str(out)
    assert out.exists()
    assert out.stat().st_size > 1000  # real PCM data


def test_mock_synthesize_rejects_empty_text(tmp_path: Path):
    p = MockTTSProvider()
    voice = _voice()
    with pytest.raises(TTSEmptyTextError):
        p.synthesize(_request("   ", voice, str(tmp_path / "x.wav")))


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_mock_synthesize_byte_identical_for_same_input(tmp_path: Path):
    p = MockTTSProvider()
    voice = _voice()
    text = "Constantinople rose in 330 AD"
    out_a = tmp_path / "a.wav"
    out_b = tmp_path / "b.wav"
    p.synthesize(_request(text, voice, str(out_a)))
    p.synthesize(_request(text, voice, str(out_b)))
    # Byte-identical WAV content.
    assert out_a.read_bytes() == out_b.read_bytes()


def test_mock_synthesize_different_voice_different_tone(tmp_path: Path):
    p = MockTTSProvider()
    v1 = _voice(voice_id="voice_a")
    v2 = _voice(voice_id="voice_b")
    text = "Hello world"
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    p.synthesize(_request(text, v1, str(a)))
    p.synthesize(_request(text, v2, str(b)))
    # Different voice → different fundamental → different bytes.
    assert a.read_bytes() != b.read_bytes()


def test_mock_synthesize_duration_scales_with_text_length(tmp_path: Path):
    p = MockTTSProvider()
    voice = _voice()
    short = p.synthesize(_request("Hi", voice, str(tmp_path / "short.wav")))
    long = p.synthesize(_request(
        "one two three four five six seven eight nine ten", voice, str(tmp_path / "long.wav"))
    )
    assert long.duration_sec > short.duration_sec


def test_mock_synthesize_rate_changes_duration(tmp_path: Path):
    p = MockTTSProvider()
    voice = _voice()
    text = "one two three four five six"
    out = tmp_path / "x.wav"
    fp = compute_audio_fingerprint(text, voice)
    req = VoiceTTSRequest(
        text=text, voice=voice,
        settings_override=VoiceSettings(speaking_rate=2.0),
        output_path=str(out),
        language=voice.language, locale=voice.locale,
        pronunciation_hints=[], fingerprint=fp,
    )
    fast = p.synthesize(req)
    req2 = VoiceTTSRequest(
        text=text, voice=voice,
        settings_override=VoiceSettings(speaking_rate=0.5),
        output_path=str(out),
        language=voice.language, locale=voice.locale,
        pronunciation_hints=[], fingerprint=fp,
    )
    slow = p.synthesize(req2)
    assert fast.duration_sec < slow.duration_sec


# ---------------------------------------------------------------------------
# Word timestamps
# ---------------------------------------------------------------------------

def test_mock_word_timestamps_uniform():
    p = MockTTSProvider()
    voice = _voice()
    resp = p.synthesize(_request("one two three four", voice, "/tmp/_x.wav"))
    assert len(resp.word_timestamps) == 4
    assert resp.word_timestamps[0]["word"] == "one"
    # Uniform alignment → equal intervals (within sub-millisecond rounding).
    intervals = [w["end_sec"] - w["start_sec"] for w in resp.word_timestamps]
    spread = max(intervals) - min(intervals)
    assert spread < 0.01   # tolerate rounding to 0.001s


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------

def test_mock_capability_declares_supported_languages():
    p = MockTTSProvider()
    assert "en" in p.capability.supported_languages
    assert "vi" in p.capability.supported_languages
    assert p.capability.deterministic is True
    assert p.capability.requires_api_key is False


def test_mock_validate_voice_accepts_supported():
    p = MockTTSProvider()
    voice = _voice(language="en")
    assert p.validate_voice(voice) is True


def test_mock_validate_voice_rejects_unsupported():
    p = MockTTSProvider()
    voice = _voice(language="xx")  # not in supported_languages
    assert p.validate_voice(voice) is False


# ---------------------------------------------------------------------------
# Estimate duration
# ---------------------------------------------------------------------------

def test_estimate_duration_consistent_with_synth():
    p = MockTTSProvider()
    text = "Rome fell in 476 AD"
    s = VoiceSettings(speaking_rate=1.0)
    est = p.estimate_duration(text, s)
    voice = _voice()
    resp = p.synthesize(_request(text, voice, "/tmp/_e.wav"))
    # Estimate and actual within 50% (estimate is coarse).
    assert abs(est - resp.duration_sec) / max(resp.duration_sec, 1e-6) < 0.5


# ---------------------------------------------------------------------------
# Provider fingerprint hash for cache key
# ---------------------------------------------------------------------------

def test_fingerprint_stable_for_same_inputs():
    text = "Rome fell"
    voice = _voice()
    f1 = compute_audio_fingerprint(text, voice)
    f2 = compute_audio_fingerprint(text, voice)
    assert f1 == f2
    assert len(f1) == 33  # 16 + 1 + 16


def test_fingerprint_changes_with_text():
    voice = _voice()
    f1 = compute_audio_fingerprint("Rome fell", voice)
    f2 = compute_audio_fingerprint("Rome did not fall", voice)
    assert f1 != f2
