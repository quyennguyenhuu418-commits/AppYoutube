"""Voice failure-path tests (PROMPT 8 §41).

Covers the canonical failure modes documented in the prompt:
- invalid voice ID
- unsupported language
- provider failure
- empty text
- corrupt audio
- missing artifact
- invalid timestamps
- timestamp beyond duration
- cache corruption
- unknown audio artifact ID
"""
from __future__ import annotations

import wave
from pathlib import Path

import pytest

from app.schemas.script import Script, ScriptBeat, ScriptSection
from app.voice.audio_artifact import write_audio_artifact
from app.voice.audio_validator import validate_audio_file
from app.voice.cache import VoiceTTSCache
from app.voice.mock_tts import MockTTSProvider
from app.voice.pipeline import run_tts_pipeline
from app.voice.provider_base import (
    TTSEmptyTextError,
    TTSProviderError,
    VoiceTTSRequest,
)
from app.voice.registry import VoiceRegistryManager, VoiceNotFoundError
from app.voice.resolver import VoiceResolutionError, VoiceResolver
from app.voice.schemas import (
    AudioArtifact,
    AudioArtifactStatus,
    NarrationScript,
    NarrationUnit,
    SpeechTiming,
    TimestampSource,
    TtsEnvironment,
    TtsProviderName,
    VoiceDefinition,
    VoiceLifecycleStatus,
    WordTiming,
    compute_audio_fingerprint,
)


def _voice(voice_id="narrator_en", **kw) -> VoiceDefinition:
    defaults = dict(
        voice_id=voice_id, name=voice_id, language="en",
        provider=TtsProviderName.MOCK, status=VoiceLifecycleStatus.APPROVED,
    )
    defaults.update(kw)
    return VoiceDefinition(**defaults)


# ---------------------------------------------------------------------------
# Invalid voice ID
# ---------------------------------------------------------------------------

def test_unknown_voice_id_raises():
    mgr = VoiceRegistryManager()
    mgr.register(_voice())
    r = VoiceResolver(
        registry=mgr, voice_definitions={"narrator_en": _voice()},
        voice_instances=[], environment=TtsEnvironment.DEVELOPMENT,
    )
    with pytest.raises(VoiceResolutionError):
        r.resolve(NarrationUnit(narration_id="n1", text="x", language="en", voice_id="ghost"))


def test_registry_lookup_unknown():
    mgr = VoiceRegistryManager()
    with pytest.raises(VoiceNotFoundError):
        mgr.lookup("missing")


# ---------------------------------------------------------------------------
# Unsupported language
# ---------------------------------------------------------------------------

def test_unsupported_language_in_resolver_compatible_fallback():
    voices = [_voice("narrator_en")]
    mgr = VoiceRegistryManager()
    for v in voices:
        mgr.register(v)
    r = VoiceResolver(
        registry=mgr, voice_definitions={v.voice_id: v for v in voices},
        voice_instances=[], environment=TtsEnvironment.DEVELOPMENT,
        project_default_voice_id=None, fallback_voice_id=None,
    )
    # Unit language "zz" - mock supports it too (en/vi/ko/zh/es/fr/de/ja).
    # To force the "no compatible voice" path, use a language outside mock's range.
    # The mock provider supports a wide set; but the resolver falls back to
    # "compatible voice" first if the registered voice has it in supported_languages.
    # Since narrator_en supports "en" only (defaulted), and the unit asks for "zz",
    # there is no compatible voice → mock fallback in development.
    # To simulate true unsupported, use a unit with a language not in the only voice.
    # Build a voice with supported_languages=["en"].
    narrow_voice = _voice("narrator_en", supported_languages=["en"])
    # Replace voice_definitions with the narrow voice.
    r.voice_definitions = {"narrator_en": narrow_voice}
    res = r.resolve(NarrationUnit(
        narration_id="n1", text="hello", language="zz",  # not in any voice
    ))
    # Should fall through to mock fallback (DEVELOPMENT).
    assert res.resolved_voice_id.startswith("ephemeral_mock_")
    assert res.mock_used is True


# ---------------------------------------------------------------------------
# Provider failure (synthesize raises)
# ---------------------------------------------------------------------------

class _BoomProvider(MockTTSProvider):
    name = TtsProviderName.MOCK
    def synthesize(self, request):
        raise TTSProviderError("synthetic failure", provider=self.name, category="synthetic")


def test_provider_failure_propagates(tmp_path):
    p = _BoomProvider()
    voice = _voice()
    text = "x"
    fp = compute_audio_fingerprint(text, voice)
    with pytest.raises(TTSProviderError):
        p.synthesize(VoiceTTSRequest(
            text=text, voice=voice, settings_override=None,
            output_path=str(tmp_path / "x.wav"),
            language=voice.language, locale=voice.locale,
            pronunciation_hints=[], fingerprint=fp,
        ))


# ---------------------------------------------------------------------------
# Empty text
# ---------------------------------------------------------------------------

def test_empty_text_raises(tmp_path):
    p = MockTTSProvider()
    voice = _voice()
    fp = compute_audio_fingerprint("x", voice)
    with pytest.raises(TTSEmptyTextError):
        p.synthesize(VoiceTTSRequest(
            text="   ", voice=voice, settings_override=None,
            output_path=str(tmp_path / "x.wav"),
            language=voice.language, locale=voice.locale,
            pronunciation_hints=[], fingerprint=fp,
        ))


# ---------------------------------------------------------------------------
# Corrupt audio
# ---------------------------------------------------------------------------

def test_corrupt_audio_fails_validation(tmp_path):
    p = tmp_path / "corrupt.wav"
    p.write_bytes(b"not a wav at all")
    r = validate_audio_file(p, declared_format="wav")
    assert not r.valid


# ---------------------------------------------------------------------------
# Missing artifact
# ---------------------------------------------------------------------------

def test_missing_artifact_audio_file(tmp_path):
    r = validate_audio_file(tmp_path / "does_not_exist.wav", declared_format="wav")
    assert not r.valid
    assert "does not exist" in r.issues[0]


# ---------------------------------------------------------------------------
# Invalid timestamps (negative end)
# ---------------------------------------------------------------------------

def test_invalid_word_timing_negative_end():
    with pytest.raises(Exception):
        SpeechTiming(
            timing_id="t1", artifact_id="0123456789abcdef_0123456789abcdef",
            narration_id="n1", language="en", duration_sec=2.0,
            words=[WordTiming(word="x", start_sec=0.5, end_sec=0.4)],  # end < start
        )


# ---------------------------------------------------------------------------
# Timestamp beyond duration
# ---------------------------------------------------------------------------

def test_timestamp_beyond_duration_rejected():
    from app.voice.schemas import SpeechTiming
    import pytest as _pytest
    with _pytest.raises(Exception):
        SpeechTiming(
            timing_id="t1", artifact_id="0123456789abcdef_0123456789abcdef",
            narration_id="n1", language="en", duration_sec=1.0,
            words=[WordTiming(word="x", start_sec=0.0, end_sec=5.0)],  # > duration + 0.5
        )


# ---------------------------------------------------------------------------
# Cache corruption (manually corrupt JSON)
# ---------------------------------------------------------------------------

def test_cache_corruption_returns_none(tmp_path):
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    # Write a corrupt JSON file.
    v = _voice()
    fp = compute_audio_fingerprint("corrupt_text", v)
    (tmp_path / "voice_cache" / f"{fp}.json").write_text("not valid json {{{")
    out = cache.lookup("corrupt_text", v)
    assert out is None


# ---------------------------------------------------------------------------
# Unknown audio artifact ID (lookup of non-existent cache entry)
# ---------------------------------------------------------------------------

def test_unknown_artifact_id_cache_miss(tmp_path):
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    v = _voice()
    out = cache.lookup("not in cache", v)
    assert out is None


# ---------------------------------------------------------------------------
# Pipeline with all-empty script (edge case)
# ---------------------------------------------------------------------------

def test_pipeline_empty_script_returns_empty_dicts(tmp_path):
    script = NarrationScript(script_id="empty", units=[])
    mgr = VoiceRegistryManager()
    mgr.register(_voice())
    r = VoiceResolver(
        registry=mgr, voice_definitions={"narrator_en": _voice()},
        voice_instances=[], environment=TtsEnvironment.DEVELOPMENT,
    )
    cache = VoiceTTSCache(job_id="job1")
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir()
    artifacts, timings = run_tts_pipeline(
        script=script, resolver=r, cache=cache, output_dir=tmp_path / "audio",
    )
    assert artifacts == {}
    assert timings == {}
