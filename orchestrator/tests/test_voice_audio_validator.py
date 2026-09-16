"""Audio validation tests (PROMPT 8 §22)."""
from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest

from app.voice.audio_validator import (
    apply_validation_to_artifact,
    parse_timestamps_from_response,
    validate_audio_file,
)
from app.voice.mock_tts import MockTTSProvider
from app.voice.provider_base import VoiceTTSRequest
from app.voice.schemas import (
    AudioArtifact,
    AudioArtifactStatus,
    TtsProviderName,
    TimestampSource,
    VoiceDefinition,
    VoiceLifecycleStatus,
    compute_audio_fingerprint,
)


def _voice() -> VoiceDefinition:
    return VoiceDefinition(
        voice_id="narrator_en", name="Narrator EN", language="en",
        provider=TtsProviderName.MOCK, status=VoiceLifecycleStatus.APPROVED,
    )


def _make_wav(path: Path, sample_rate: int = 22050, duration_sec: float = 1.0,
              channels: int = 1, bits: int = 16, n_samples: int | None = None) -> None:
    if n_samples is None:
        n_samples = int(sample_rate * duration_sec)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(bits // 8)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * n_samples * channels)


# ---------------------------------------------------------------------------
# validate_audio_file
# ---------------------------------------------------------------------------

def test_validate_wav_ok(tmp_path):
    p = tmp_path / "ok.wav"
    _make_wav(p, duration_sec=1.0)
    r = validate_audio_file(p, declared_format="wav", declared_sample_rate=22050,
                            declared_channels=1, declared_bits=16, declared_duration_sec=1.0)
    assert r.valid
    assert r.actual_duration_sec == pytest.approx(1.0, abs=0.1)
    assert r.actual_sample_rate == 22050


def test_validate_wav_missing_file(tmp_path):
    r = validate_audio_file(tmp_path / "missing.wav")
    assert not r.valid
    assert "does not exist" in r.issues[0]


def test_validate_wav_empty_file(tmp_path):
    p = tmp_path / "empty.wav"
    p.write_bytes(b"")
    r = validate_audio_file(p)
    assert not r.valid
    assert any("empty" in i for i in r.issues)


def test_validate_wav_corrupt_file(tmp_path):
    p = tmp_path / "corrupt.wav"
    p.write_bytes(b"not a real WAV")
    r = validate_audio_file(p, declared_format="wav")
    assert not r.valid
    assert any("WAV" in i for i in r.issues)


def test_validate_wav_truncated(tmp_path):
    p = tmp_path / "truncated.wav"
    _make_wav(p, duration_sec=1.0)
    # Truncate file in the middle of the data section.
    data = p.read_bytes()
    p.write_bytes(data[:len(data) // 2])
    r = validate_audio_file(p, declared_format="wav")
    assert not r.valid


def test_validate_wav_channel_mismatch(tmp_path):
    p = tmp_path / "stereo.wav"
    _make_wav(p, channels=2)
    r = validate_audio_file(p, declared_format="wav", declared_channels=1)
    assert not r.valid
    assert any("channel" in i for i in r.issues)


def test_validate_wav_bits_mismatch(tmp_path):
    p = tmp_path / "8bit.wav"
    _make_wav(p, bits=8)
    r = validate_audio_file(p, declared_format="wav", declared_bits=16)
    assert not r.valid
    assert any("bits" in i for i in r.issues)


def test_validate_wav_sample_rate_mismatch(tmp_path):
    p = tmp_path / "8k.wav"
    _make_wav(p, sample_rate=8000)
    r = validate_audio_file(p, declared_format="wav", declared_sample_rate=22050)
    # SR mismatch is a soft issue (resamplable).
    assert any("sample-rate" in i for i in r.issues)


def test_validate_wav_duration_mismatch(tmp_path):
    p = tmp_path / "short.wav"
    _make_wav(p, duration_sec=2.0)
    r = validate_audio_file(p, declared_format="wav", declared_duration_sec=5.0)
    assert not r.valid
    assert any("duration" in i for i in r.issues)


def test_validate_unsupported_format(tmp_path):
    p = tmp_path / "x.ogg"
    p.write_bytes(b"some bytes")
    r = validate_audio_file(p, declared_format="ogg")
    assert not r.valid


# ---------------------------------------------------------------------------
# apply_validation_to_artifact
# ---------------------------------------------------------------------------

def _build_artifact(path: Path) -> AudioArtifact:
    fp = "0123456789abcdef_0123456789abcdef"
    return AudioArtifact(
        artifact_id=fp,
        narration_id="n1",
        voice_id="narrator_en",
        provider=TtsProviderName.MOCK,
        source_text_hash="0123456789abcdef",
        voice_config_hash="0123456789abcdef",
        format="wav",
        sample_rate=22050,
        channels=1,
        bits_per_sample=16,
        duration_sec=1.0,
        uri=str(path),
        absolute_path=str(path),
        fingerprint=fp,
        status=AudioArtifactStatus.GENERATED,
    )


def test_apply_validation_valid(tmp_path):
    p = tmp_path / "ok.wav"
    _make_wav(p, duration_sec=1.0)
    a = _build_artifact(p)
    out = apply_validation_to_artifact(a)
    assert out.status == AudioArtifactStatus.VALIDATED


def test_apply_validation_rejected(tmp_path):
    p = tmp_path / "bad.wav"
    p.write_bytes(b"not a wav")
    a = _build_artifact(p)
    out = apply_validation_to_artifact(a)
    assert out.status == AudioArtifactStatus.REJECTED
    assert "validation_issues" in out.metadata


# ---------------------------------------------------------------------------
# parse_timestamps_from_response
# ---------------------------------------------------------------------------

def test_parse_timestamps_provider_native():
    words, src = parse_timestamps_from_response(
        [
            {"word": "Rome", "start_sec": 0.0, "end_sec": 0.4, "confidence": 0.95},
            {"word": "fell", "start_sec": 0.6, "end_sec": 1.1, "confidence": 0.9},
        ],
        duration_sec=1.5, declared_format="wav",
    )
    assert len(words) == 2
    assert src == TimestampSource.PROVIDER_NATIVE


def test_parse_timestamps_uniform():
    words, src = parse_timestamps_from_response(
        [
            {"word": "Rome", "start_sec": 0.000, "end_sec": 0.500},
            {"word": "fell", "start_sec": 0.500, "end_sec": 1.000},
        ],
        duration_sec=1.0, declared_format="wav",
    )
    assert src == TimestampSource.UNIFORM_ALIGNMENT


def test_parse_timestamps_empty_returns_unavailable():
    words, src = parse_timestamps_from_response(
        [], duration_sec=1.0, declared_format="wav",
    )
    assert src == TimestampSource.UNAVAILABLE
    assert words == []


def test_parse_timestamps_skips_empty_words():
    words, src = parse_timestamps_from_response(
        [
            {"word": "", "start_sec": 0.0, "end_sec": 0.5},
            {"word": "Rome", "start_sec": 0.5, "end_sec": 1.0},
        ],
        duration_sec=1.0, declared_format="wav",
    )
    assert len(words) == 1
    assert words[0].word == "Rome"
