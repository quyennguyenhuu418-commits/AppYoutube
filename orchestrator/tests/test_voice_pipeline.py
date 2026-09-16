"""TTS pipeline (orchestrator-level) tests (PROMPT 8 §16, §19, §20)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.script import Script, ScriptBeat, ScriptSection
from app.voice.audio_artifact import compute_sha256
from app.voice.cache import VoiceTTSCache
from app.voice.narration import build_narration_script
from app.voice.pipeline import run_tts_pipeline
from app.voice.registry import VoiceRegistryManager
from app.voice.resolver import VoiceResolver
from app.voice.schemas import (
    TtsEnvironment,
    TtsProviderName,
    VoiceDefinition,
    VoiceLifecycleStatus,
)


def _voice(voice_id="narrator_en", **kw) -> VoiceDefinition:
    defaults = dict(
        voice_id=voice_id, name=voice_id, language="en",
        provider=TtsProviderName.MOCK, status=VoiceLifecycleStatus.APPROVED,
    )
    defaults.update(kw)
    return VoiceDefinition(**defaults)


def _script() -> Script:
    return Script(
        topic="Test",
        sections=[ScriptSection(name="intro", beats=[
            ScriptBeat(text="Rome fell in 476 AD.", emotional_intent="neutral"),
            ScriptBeat(text="Constantinople rose in 330 AD.", emotional_intent="neutral"),
        ])],
    )


def _build_resolver_and_cache(job_id: str, tmp_path: Path):
    cache = VoiceTTSCache(job_id=job_id)
    cache._base = tmp_path / "voice_cache"
    cache._base.mkdir(parents=True, exist_ok=True)

    voices = [_voice("narrator_en")]
    reg = VoiceRegistryManager()
    for v in voices:
        reg.register(v)
    defs = {v.voice_id: v for v in voices}
    resolver = VoiceResolver(
        registry=reg,
        voice_definitions=defs,
        voice_instances=[],
        environment=TtsEnvironment.DEVELOPMENT,
        project_default_voice_id="narrator_en",
        fallback_voice_id="narrator_en",
        default_provider=TtsProviderName.MOCK,
    )
    return resolver, cache


# ---------------------------------------------------------------------------
# run_tts_pipeline
# ---------------------------------------------------------------------------

def test_run_tts_pipeline_produces_artifacts_and_timings(tmp_path):
    job_id = "job_test_1"
    resolver, cache = _build_resolver_and_cache(job_id, tmp_path)
    script = _script()
    narration_script = build_narration_script(
        script_id="ns1", job_id=job_id, project_id="proj1", script=script,
    )
    audio_dir = tmp_path / "audio"
    artifacts, timings = run_tts_pipeline(
        script=narration_script, resolver=resolver, cache=cache, output_dir=audio_dir,
    )
    assert len(artifacts) == 2
    assert len(timings) == 2
    for nid, art in artifacts.items():
        # Audio file exists.
        assert Path(art.absolute_path).exists()
        assert art.byte_size > 1000
        # Status is validated.
        assert art.status.value == "validated"
        # Word timestamps present.
        timing = timings[nid]
        assert len(timing.words) > 0


def test_run_tts_pipeline_idempotent(tmp_path):
    job_id = "job_test_2"
    resolver, cache = _build_resolver_and_cache(job_id, tmp_path)
    script = _script()
    narration_script = build_narration_script(
        script_id="ns1", job_id=job_id, project_id="proj1", script=script,
    )
    audio_dir = tmp_path / "audio"

    # Run 1.
    a1, t1 = run_tts_pipeline(
        script=narration_script, resolver=resolver, cache=cache, output_dir=audio_dir,
    )
    # Run 2.
    a2, t2 = run_tts_pipeline(
        script=narration_script, resolver=resolver, cache=cache, output_dir=audio_dir,
    )

    for nid in a1:
        assert a1[nid].artifact_id == a2[nid].artifact_id
        assert a1[nid].checksum_sha256 == a2[nid].checksum_sha256
        assert a1[nid].duration_sec == pytest.approx(a2[nid].duration_sec, abs=1e-3)


def test_run_tts_pipeline_cache_hit_no_regeneration(tmp_path):
    job_id = "job_test_3"
    resolver, cache = _build_resolver_and_cache(job_id, tmp_path)
    script = _script()
    narration_script = build_narration_script(
        script_id="ns1", job_id=job_id, project_id="proj1", script=script,
    )
    audio_dir = tmp_path / "audio"

    # Run 1: synthesize.
    a1, _ = run_tts_pipeline(
        script=narration_script, resolver=resolver, cache=cache, output_dir=audio_dir,
    )
    checksum_1 = a1["n_0001"].checksum_sha256
    bytes_1 = Path(a1["n_0001"].absolute_path).read_bytes()

    # Run 2: cache hit.
    a2, _ = run_tts_pipeline(
        script=narration_script, resolver=resolver, cache=cache, output_dir=audio_dir,
    )
    bytes_2 = Path(a2["n_0001"].absolute_path).read_bytes()
    # Byte-identical audio (deterministic).
    assert bytes_1 == bytes_2
    assert a2["n_0001"].checksum_sha256 == checksum_1


def test_run_tts_pipeline_text_change_invalidates_cache(tmp_path):
    job_id = "job_test_4"
    resolver, cache = _build_resolver_and_cache(job_id, tmp_path)
    audio_dir = tmp_path / "audio"

    script_a = Script(
        topic="x", sections=[ScriptSection(name="intro", beats=[
            ScriptBeat(text="Original text.", emotional_intent="neutral"),
        ])],
    )
    script_b = Script(
        topic="x", sections=[ScriptSection(name="intro", beats=[
            ScriptBeat(text="Different text.", emotional_intent="neutral"),
        ])],
    )
    narration_a = build_narration_script(
        script_id="ns1", job_id=job_id, project_id="proj1", script=script_a,
    )
    narration_b = build_narration_script(
        script_id="ns1", job_id=job_id, project_id="proj1", script=script_b,
    )
    a1, _ = run_tts_pipeline(
        script=narration_a, resolver=resolver, cache=cache, output_dir=audio_dir,
    )
    a2, _ = run_tts_pipeline(
        script=narration_b, resolver=resolver, cache=cache, output_dir=audio_dir,
    )
    # Different text → different artifact identity.
    assert a1["n_0001"].artifact_id != a2["n_0001"].artifact_id


def test_run_tts_pipeline_records_audit(tmp_path):
    job_id = "job_test_5"
    resolver, cache = _build_resolver_and_cache(job_id, tmp_path)
    script = _script()
    narration_script = build_narration_script(
        script_id="ns1", job_id=job_id, project_id="proj1", script=script,
    )
    run_tts_pipeline(
        script=narration_script, resolver=resolver, cache=cache,
        output_dir=tmp_path / "audio",
    )
    assert len(resolver.audit_log) == 2
    # Each entry records the resolution.
    for evt in resolver.audit_log:
        assert evt.resolved_voice_id == "narrator_en"
        assert evt.provider == TtsProviderName.MOCK


def test_run_tts_pipeline_validates_audio(tmp_path):
    """Every artifact must pass audio validation (status=VALIDATED)."""
    job_id = "job_test_6"
    resolver, cache = _build_resolver_and_cache(job_id, tmp_path)
    script = _script()
    narration_script = build_narration_script(
        script_id="ns1", job_id=job_id, project_id="proj1", script=script,
    )
    artifacts, _ = run_tts_pipeline(
        script=narration_script, resolver=resolver, cache=cache,
        output_dir=tmp_path / "audio",
    )
    for art in artifacts.values():
        assert art.status.value == "validated"
        # Validation metadata populated.
        assert "validation_actual_duration_sec" in art.metadata
        assert "validation_actual_sample_rate" in art.metadata
        # SHA-256 set.
        assert len(art.checksum_sha256) == 64
