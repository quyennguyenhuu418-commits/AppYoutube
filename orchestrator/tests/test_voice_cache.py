"""TTS cache tests (PROMPT 8 §18, §19, §20)."""
from __future__ import annotations

import pytest

from app.voice.cache import VoiceTTSCache
from app.voice.mock_tts import MockTTSProvider
from app.voice.schemas import (
    AudioArtifact,
    AudioArtifactStatus,
    TtsProviderName,
    VoiceDefinition,
    VoiceLifecycleStatus,
    VoiceSettings,
    compute_audio_fingerprint,
)


def _voice(**kw) -> VoiceDefinition:
    defaults = dict(
        voice_id="narrator_en",
        name="Narrator EN",
        language="en",
        provider=TtsProviderName.MOCK,
        status=VoiceLifecycleStatus.APPROVED,
    )
    defaults.update(kw)
    return VoiceDefinition(**defaults)


def test_cache_lookup_miss(tmp_path):
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    v = _voice()
    out = cache.lookup("hello world", v)
    assert out is None


def test_cache_lookup_hit(tmp_path):
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    v = _voice()
    text = "hello world"
    fp = compute_audio_fingerprint(text, v)
    artifact = AudioArtifact(
        artifact_id=fp,
        narration_id="n1",
        voice_id=v.voice_id,
        provider=v.provider,
        source_text_hash=fp.split("_")[0],
        voice_config_hash=fp.split("_")[1],
        format="wav",
        sample_rate=22050,
        channels=1,
        bits_per_sample=16,
        duration_sec=0.667,
        uri=f"{fp}.wav",
        absolute_path=str(tmp_path / f"{fp}.wav"),
        fingerprint=fp,
        status=AudioArtifactStatus.VALIDATED,
    )
    cache.store(artifact)
    out = cache.lookup(text, v)
    assert out is not None
    assert out.fingerprint == fp
    assert out.duration_sec == pytest.approx(0.667, abs=1e-3)


def test_cache_store_then_lookup_round_trip(tmp_path):
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    v = _voice()
    text = "Test text for round trip"
    fp = compute_audio_fingerprint(text, v)
    a = AudioArtifact(
        artifact_id=fp,
        narration_id="n1",
        voice_id=v.voice_id,
        provider=v.provider,
        source_text_hash=fp.split("_")[0],
        voice_config_hash=fp.split("_")[1],
        format="wav",
        sample_rate=22050,
        channels=1,
        bits_per_sample=16,
        duration_sec=1.0,
        uri=f"{fp}.wav",
        fingerprint=fp,
        status=AudioArtifactStatus.GENERATED,
    )
    cache.store(a)
    out = cache.lookup(text, v)
    assert out is not None
    assert out.narration_id == "n1"


def test_cache_evict_removes_artifact(tmp_path):
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    v = _voice()
    text = "To be evicted"
    fp = compute_audio_fingerprint(text, v)
    a = AudioArtifact(
        artifact_id=fp,
        narration_id="n1",
        voice_id=v.voice_id,
        provider=v.provider,
        source_text_hash=fp.split("_")[0],
        voice_config_hash=fp.split("_")[1],
        format="wav",
        sample_rate=22050,
        channels=1,
        bits_per_sample=16,
        duration_sec=1.0,
        uri=f"{fp}.wav",
        fingerprint=fp,
        status=AudioArtifactStatus.GENERATED,
    )
    cache.store(a)
    assert cache.lookup(text, v) is not None
    cache.evict(fp)
    assert cache.lookup(text, v) is None


def test_cache_stats(tmp_path):
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    stats = cache.stats()
    assert stats["job_id"] == "job1"


def test_cache_text_change_invalidates(tmp_path):
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    v = _voice()
    fp1 = compute_audio_fingerprint("one", v)
    fp2 = compute_audio_fingerprint("two", v)
    a = AudioArtifact(
        artifact_id=fp1,
        narration_id="n1",
        voice_id=v.voice_id,
        provider=v.provider,
        source_text_hash=fp1.split("_")[0],
        voice_config_hash=fp1.split("_")[1],
        format="wav",
        sample_rate=22050,
        channels=1,
        bits_per_sample=16,
        duration_sec=1.0,
        uri=f"{fp1}.wav",
        fingerprint=fp1,
        status=AudioArtifactStatus.GENERATED,
    )
    cache.store(a)
    assert cache.lookup("one", v) is not None
    assert cache.lookup("two", v) is None  # different text → miss
    assert fp1 != fp2


def test_cache_settings_change_invalidates(tmp_path):
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    v = _voice()
    fp1 = compute_audio_fingerprint("hi", v)
    a = AudioArtifact(
        artifact_id=fp1,
        narration_id="n1",
        voice_id=v.voice_id,
        provider=v.provider,
        source_text_hash=fp1.split("_")[0],
        voice_config_hash=fp1.split("_")[1],
        format="wav",
        sample_rate=22050,
        channels=1,
        bits_per_sample=16,
        duration_sec=1.0,
        uri=f"{fp1}.wav",
        fingerprint=fp1,
        status=AudioArtifactStatus.GENERATED,
    )
    cache.store(a)
    # No override.
    assert cache.lookup("hi", v) is not None
    # Different settings → different fingerprint → miss.
    assert cache.lookup("hi", v, settings_override=VoiceSettings(speaking_rate=1.5)) is None


def test_idempotency_two_runs_same_artifact(tmp_path):
    """Run 1 generates; Run 2 should cache-hit with same identity."""
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    v = _voice()
    text = "Rome fell in 476 AD"

    # Run 1: synthesize + store.
    p = MockTTSProvider()
    from app.voice.provider_base import VoiceTTSRequest
    fp = compute_audio_fingerprint(text, v)
    out1 = tmp_path / "run1.wav"
    req = VoiceTTSRequest(
        text=text, voice=v, settings_override=None,
        output_path=str(out1),
        language=v.language, locale=v.locale,
        pronunciation_hints=[], fingerprint=fp,
    )
    resp = p.synthesize(req)
    from app.voice.audio_artifact import write_audio_artifact
    a1 = write_audio_artifact(
        text=text, voice=v, settings_override=None,
        provider=v.provider, provider_version=v.version_label,
        audio_path=resp.audio_path,
        duration_sec=resp.duration_sec,
        sample_rate=resp.sample_rate,
        channels=resp.channels,
        bits_per_sample=resp.bits_per_sample,
        format=resp.format,
        narration_id="n1",
    )
    cache.store(a1, out1)

    # Run 2: same text+voice → cache hit returns identical artifact identity.
    cached = cache.lookup(text, v)
    assert cached is not None
    assert cached.artifact_id == a1.artifact_id
    assert cached.checksum_sha256 == a1.checksum_sha256
    assert cached.duration_sec == pytest.approx(a1.duration_sec, abs=1e-3)
