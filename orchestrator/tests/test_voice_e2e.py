"""PROMPT 8 — Real Narration Audio E2E Test (§37, §38, §39, §40, §48, §49).

Vertical flow:

  StoryboardPackage (story unit)
        |
        v
  Script (script unit) <-> StoryboardPackage
        |
        v
  NarrationScript (canonical)
        |
        v
  VoiceResolver + VoiceTTSProvider (MockTTSProvider - deterministic WAV)
        |
        v
  AudioArtifact (canonical, validated)
        |
        v
  SpeechTiming (canonical, word-level timestamps)
        |
        v
  NarrationTimeline (canonical, scene timing)

The audio file is written to disk and verified by:
  * stdlib `wave` (channels, sample_rate, duration)
  * ffprobe (codec, duration, sample_rate, channels)  -- if available

Assertions:
  * Every NarrationUnit produces a canonical AudioArtifact
  * Every AudioArtifact has matching SpeechTiming
  * Word count == token count of narration text
  * Word timestamps are monotone, non-overlapping, non-negative
  * Last word end_sec <= duration + tolerance
  * Audio duration matches reported duration within +- 0.05 s
  * Idempotency: second pipeline run produces identical artifact_ids
  * No credentials leaked into artifacts
  * NarrationTimeline entries cover all units
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from app.schemas.script import Script, ScriptBeat, ScriptSection
from app.voice.audio_artifact import write_audio_artifact
from app.voice.audio_validator import apply_validation_to_artifact, validate_audio_file
from app.voice.cache import VoiceTTSCache
from app.voice.mock_tts import MockTTSProvider, VoiceTTSRequest
from app.voice.narration import build_narration_script
from app.voice.pipeline import run_tts_pipeline
from app.voice.registry import VoiceRegistryManager
from app.voice.resolver import VoiceResolver, VoiceResolutionError
from app.voice.schemas import (
    NarrationUnit,
    NarrationTimeline,
    TtsEnvironment,
    TtsProviderName,
    VoiceDefinition,
    VoiceLifecycleStatus,
    VoiceSettings,
)
from app.voice.timeline import build_timeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_voice_workspace(tmp_path: Path):
    workspace = tmp_path / "voice_audio_e2e"
    workspace.mkdir(parents=True, exist_ok=True)
    yield workspace
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)


def _voice(voice_id: str = "narrator_en", language: str = "en", **kw) -> VoiceDefinition:
    defaults = dict(
        voice_id=voice_id,
        name=voice_id,
        language=language,
        locale=f"{language}-XX",
        provider=TtsProviderName.MOCK,
        style="narrator",
        settings=VoiceSettings(speaking_rate=1.0),
        supported_languages=[language],
        status=VoiceLifecycleStatus.APPROVED,
        version_label="v1",
    )
    defaults.update(kw)
    return VoiceDefinition(**defaults)


def _script() -> Script:
    return Script(
        topic="Rome: Rise and Fall",
        sections=[ScriptSection(name="intro", beats=[
            ScriptBeat(text="Rome fell in 476 AD.", emotional_intent="neutral"),
            ScriptBeat(text="Constantinople rose in 330 AD.", emotional_intent="neutral"),
        ])],
    )


def _build_resolver_and_cache(job_id: str, tmp: Path):
    cache = VoiceTTSCache(job_id=job_id)
    cache._base = tmp / "voice_cache"
    cache._base.mkdir(parents=True, exist_ok=True)
    voices = [_voice("narrator_en")]
    reg = VoiceRegistryManager()
    for v in voices:
        reg.register(v)
    defs = {v.voice_id: v for v in voices}
    resolver = VoiceResolver(
        registry=reg, voice_definitions=defs, voice_instances=[],
        environment=TtsEnvironment.DEVELOPMENT,
        project_default_voice_id="narrator_en",
        fallback_voice_id="narrator_en",
        default_provider=TtsProviderName.MOCK,
    )
    return resolver, cache, voices


# ---------------------------------------------------------------------------
# Vertical pipeline test
# ---------------------------------------------------------------------------

def test_production_narration_end_to_end(tmp_voice_workspace: Path):
    """StoryboardPackage <-> Script <-> NarrationScript -> TTS -> AudioArtifact
    -> SpeechTiming -> NarrationTimeline.
    """
    resolver, cache, _ = _build_resolver_and_cache("job_e2e", tmp_voice_workspace)
    script = _script()
    narration_script = build_narration_script(
        script_id="ns_e2e", job_id="job_e2e", project_id="proj_e2e", script=script,
    )
    assert len(narration_script.units) == 2

    # Run TTS pipeline.
    audio_dir = tmp_voice_workspace / "audio"
    artifacts, timings = run_tts_pipeline(
        script=narration_script, resolver=resolver, cache=cache, output_dir=audio_dir,
    )
    assert len(artifacts) == 2
    assert len(timings) == 2

    # Artifacts validated.
    for narr_id, art in artifacts.items():
        assert art.status.value == "validated", f"{narr_id} status={art.status}"
        assert art.duration_sec > 0
        assert Path(art.absolute_path).exists()
        # Validate explicitly (idempotent).
        apply_validation_to_artifact(art)
        assert "validation_actual_duration_sec" in art.metadata

    # Audio file inspection via stdlib wave.
    for art in artifacts.values():
        with wave.open(str(art.absolute_path), "rb") as w:
            n_channels = w.getnchannels()
            sample_rate = w.getframerate()
            n_frames = w.getnframes()
            computed_duration = n_frames / float(sample_rate)
        assert n_channels == art.channels, f"{art.artifact_id}: channels {n_channels} != {art.channels}"
        assert sample_rate == art.sample_rate, f"{art.artifact_id}: sample_rate {sample_rate} != {art.sample_rate}"
        assert math.isclose(computed_duration, art.duration_sec, abs_tol=0.05), (
            f"duration mismatch: reported={art.duration_sec}, actual={computed_duration}"
        )

    # SpeechTiming: word count matches token count.
    for unit in narration_script.units:
        timing = timings[unit.narration_id]
        tokens = [t for t in unit.text.split() if t.strip()]
        assert len(timing.words) == len(tokens), (
            f"word count mismatch for {unit.narration_id}: "
            f"words={len(timing.words)}, tokens={len(tokens)}"
        )
        # Timestamps monotone non-overlapping.
        prev_end = 0.0
        for w in timing.words:
            assert w.start_sec >= 0.0
            assert w.end_sec > w.start_sec
            assert w.start_sec >= prev_end - 1e-3
            prev_end = w.end_sec
        # Last word <= duration + tolerance.
        assert timing.words[-1].end_sec <= timing.duration_sec + 0.1

    # Idempotency.
    artifacts2, _ = run_tts_pipeline(
        script=narration_script, resolver=resolver, cache=cache, output_dir=audio_dir,
    )
    for narr_id in artifacts:
        assert artifacts[narr_id].artifact_id == artifacts2[narr_id].artifact_id, (
            "cache idempotency broken"
        )

    # NarrationTimeline.
    timeline = build_timeline(
        script=narration_script, artifacts=artifacts, timings=timings, fps=30,
        timeline_id="tl_e2e",
    )
    assert isinstance(timeline, NarrationTimeline)
    assert timeline.fps == 30
    assert timeline.total_duration_sec > 0
    assert len(timeline.entries) == 2
    # Entries cover all units.
    narr_ids_in_timeline = {e.narration_id for e in timeline.entries}
    assert narr_ids_in_timeline == set(artifacts.keys())


# ---------------------------------------------------------------------------
# ffprobe audio verification (§38)
# ---------------------------------------------------------------------------

def _ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


@pytest.mark.skipif(not _ffprobe_available(), reason="ffprobe not installed")
def test_ffprobe_verifies_real_audio_stream(tmp_voice_workspace: Path):
    """ffprobe verifies audio stream metadata for a real WAV."""
    provider = MockTTSProvider()
    audio_path = tmp_voice_workspace / "ffprobe_test.wav"
    voice = _voice("narrator_en")
    req = VoiceTTSRequest(
        text="Hello world.",
        voice=voice,
        language="en",
        locale="en-US",
        pronunciation_hints=[],
        settings_override=None,
        output_path=str(audio_path),
        fingerprint="0123456789abcdef_0123456789abcdef",
    )
    response = provider.synthesize(req)
    assert Path(response.audio_path).exists()
    assert response.duration_sec > 0

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels,duration",
        "-of", "json",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, f"ffprobe failed: {result.stderr}"
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    assert len(streams) >= 1, "no audio stream detected"
    stream = streams[0]
    assert stream.get("codec_name") in (
        "pcm_s16le", "pcm_s16be", "pcm_s24le", "pcm_f32le",
    )
    assert int(stream.get("sample_rate", 0)) > 0
    assert int(stream.get("channels", 0)) >= 1


# ---------------------------------------------------------------------------
# Failure paths (§41)
# ---------------------------------------------------------------------------

def test_invalid_voice_id_rejected(tmp_voice_workspace: Path):
    """VoiceResolutionError when voice_id does not exist."""
    from app.voice.resolver import VoiceResolver as VR
    cache = VoiceTTSCache(job_id="job_invalid")
    cache._base = tmp_voice_workspace / "voice_cache"
    cache._base.mkdir(parents=True, exist_ok=True)
    voice = _voice("narrator_en")
    reg = VoiceRegistryManager()
    reg.register(voice)
    resolver = VR(
        registry=reg,
        voice_definitions={voice.voice_id: voice},
        voice_instances=[],
        environment=TtsEnvironment.DEVELOPMENT,
        project_default_voice_id="narrator_en",
        fallback_voice_id="narrator_en",
        default_provider=TtsProviderName.MOCK,
    )
    unit = NarrationUnit(
        narration_id="n1", scene_id="s1", beat_id="b1",
        speaker_id="narrator", text="hello", language="en",
        voice_id="does_not_exist",
    )
    with pytest.raises(VoiceResolutionError):
        resolver.resolve(unit)


def test_empty_text_rejected():
    """NarrationUnit with empty text is rejected at validation time."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        NarrationUnit(
            narration_id="n1", scene_id="s1", beat_id="b1",
            speaker_id="narrator", text="", language="en",
        )


def test_corrupt_audio_artifact_rejected(tmp_voice_workspace: Path):
    """AudioValidator rejects a non-audio file masquerading as WAV."""
    fake_path = tmp_voice_workspace / "fake.wav"
    fake_path.write_bytes(b"NOT_A_WAV_FILE")
    result = validate_audio_file(fake_path)
    assert result.valid is False
    assert len(result.issues) > 0


def test_missing_artifact_uri_returns_null(tmp_voice_workspace: Path):
    """An artifact pointing to a non-existent file is detectable."""
    missing = tmp_voice_workspace / "missing.wav"
    result = validate_audio_file(missing)
    assert result.valid is False
    assert any("missing" in e.lower() or "not found" in e.lower() or "exist" in e.lower()
               for e in result.issues)


def test_no_credentials_in_serialized_artifact(tmp_voice_workspace: Path):
    """AudioArtifact JSON must never contain API keys, headers, secrets (§42)."""
    provider = MockTTSProvider()
    voice = _voice("narrator_en")
    req = VoiceTTSRequest(
        text="test", voice=voice, language="en", locale="en-US",
        pronunciation_hints=[], settings_override=None,
        output_path=str(tmp_voice_workspace / "test.wav"),
        fingerprint="0123456789abcdef_0123456789abcdef",
    )
    response = provider.synthesize(req)
    artifact = write_audio_artifact(
        text="test", voice=_voice(), settings_override=None,
        provider=TtsProviderName.MOCK, provider_version="v1",
        audio_path=response.audio_path, duration_sec=response.duration_sec,
        sample_rate=response.sample_rate, channels=response.channels,
        bits_per_sample=response.bits_per_sample, format=response.format,
        narration_id="n_check01",
    )
    serialized = artifact.model_dump(mode="json")
    blob = json.dumps(serialized)
    # Filter out narration_id/voice_id (legitimate IDs we control) before scanning.
    safe_blob = blob.replace("n_check01", "").replace("narrator_en", "")
    for forbidden in ("api_key", "authorization", "elevenlabs_", "secret", "token"):
        assert forbidden.lower() not in safe_blob.lower(), (
            f"forbidden token '{forbidden}' found in serialized artifact"
        )


# ---------------------------------------------------------------------------
# Cross-runtime fixture
# ---------------------------------------------------------------------------

def test_serialization_format_matches_typescript_types(tmp_voice_workspace: Path):
    """AudioArtifact serialization uses snake_case + matches TS types (§47)."""
    provider = MockTTSProvider()
    voice = _voice("narrator_en")
    req = VoiceTTSRequest(
        text="cross runtime", voice=voice, language="en", locale="en-US",
        pronunciation_hints=[], settings_override=None,
        output_path=str(tmp_voice_workspace / "x.wav"),
        fingerprint="0123456789abcdef_0123456789abcdef",
    )
    response = provider.synthesize(req)
    art = write_audio_artifact(
        text="cross runtime", voice=_voice(), settings_override=None,
        provider=TtsProviderName.MOCK, provider_version="v1",
        audio_path=response.audio_path, duration_sec=response.duration_sec,
        sample_rate=response.sample_rate, channels=response.channels,
        bits_per_sample=response.bits_per_sample, format=response.format,
        narration_id="n_xr",
    )
    blob = art.model_dump(mode="json")
    # Required TS fields present.
    for f in (
        "artifact_id", "narration_id", "voice_id", "provider", "provider_version",
        "source_text_hash", "voice_config_hash", "format", "sample_rate", "channels",
        "bits_per_sample", "duration_sec", "uri", "absolute_path", "checksum_sha256",
        "byte_size", "status", "fingerprint", "version", "created_at", "metadata",
    ):
        assert f in blob, f"missing field {f}"
    # No camelCase leakage.
    for k in blob.keys():
        assert k == k.lower(), f"non-snake_case key: {k}"
