"""High-level TTS pipeline (PROMPT 8 §16).

End-to-end function: NarrationScript → AudioArtifacts + SpeechTimings.

This is what a future s7.5 (or augmented s7) stage would call:

    artifacts, timings = run_tts_pipeline(
        script=narration_script,
        resolver=resolver,
        cache=tts_cache,
        output_dir=job_dir / "voice_audio",
    )
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.voice.audio_artifact import write_audio_artifact
from app.voice.audio_validator import apply_validation_to_artifact
from app.voice.cache import VoiceTTSCache
from app.voice.resolver import VoiceResolver
from app.voice.schemas import (
    AudioArtifact,
    NarrationScript,
    NarrationUnit,
    SpeechTiming,
    TtsEnvironment,
    VoiceDefinition,
    compute_audio_fingerprint,
)
from app.voice.timing import build_speech_timing

log = logging.getLogger(__name__)


def run_tts_pipeline(
    script: NarrationScript,
    resolver: VoiceResolver,
    cache: VoiceTTSCache | None = None,
    output_dir: str | Path | None = None,
    validate: bool = True,
) -> tuple[dict[str, AudioArtifact], dict[str, SpeechTiming]]:
    """Synthesize audio for every narration unit.

    Returns (artifacts_by_narration_id, timings_by_narration_id).
    """
    output_dir_p = Path(output_dir) if output_dir is not None else None
    artifacts: dict[str, AudioArtifact] = {}
    timings: dict[str, SpeechTiming] = {}

    for unit in script.units:
        # Resolve voice.
        resolution = resolver.resolve(unit)
        voice = resolver.voice_definitions.get(resolution.resolved_voice_id)
        if voice is None:
            log.warning(
                "[tts] resolution produced voice_id %s but no definition; skipping",
                resolution.resolved_voice_id,
            )
            continue

        # Compute fingerprint for cache + file paths.
        settings_override = resolver._match_instance(unit)
        settings_override = (
            settings_override.settings_override
            if settings_override is not None
            else None
        )
        fp = compute_audio_fingerprint(unit.text, voice, settings_override)

        # Cache lookup.
        cached = None
        if cache is not None:
            cached = cache.lookup(
                text=unit.text, voice=voice, settings_override=settings_override,
            )
        if cached is not None:
            log.debug("[tts] cache hit: %s (%s)", cached.artifact_id, unit.narration_id)
            artifacts[unit.narration_id] = cached
            timings[unit.narration_id] = build_speech_timing(
                timing_id=f"t_{unit.narration_id}",
                artifact_id=cached.artifact_id,
                narration_id=unit.narration_id,
                provider=cached.provider,
                language=unit.language,
                word_timestamps=[],   # cached path: not re-parsed here
                duration_sec=cached.duration_sec,
            )
            continue

        # Synthesize.
        provider = resolver.select_provider_for(voice, unit)
        if output_dir_p is not None:
            output_dir_p.mkdir(parents=True, exist_ok=True)
            audio_path = output_dir_p / f"{fp}.wav"
        else:
            audio_path = Path(cache.audio_path(fp, voice.provider.value)) if cache is not None else Path(f"{fp}.wav")
            audio_path.parent.mkdir(parents=True, exist_ok=True)
        response = provider.synthesize(_make_request(unit, voice, settings_override, audio_path, fp))

        # Build + validate artifact.
        artifact = write_audio_artifact(
            text=unit.text,
            voice=voice,
            settings_override=settings_override,
            provider=voice.provider,
            provider_version=voice.version_label,
            audio_path=response.audio_path,
            duration_sec=response.duration_sec,
            sample_rate=response.sample_rate,
            channels=response.channels,
            bits_per_sample=response.bits_per_sample,
            format=response.format,
            narration_id=unit.narration_id,
            provider_metadata=response.provider_artifact_meta,
            validate=validate,
        )
        # Re-apply validation explicitly (write_audio_artifact already did).
        artifact = apply_validation_to_artifact(artifact)
        artifacts[unit.narration_id] = artifact

        # Build timing.
        timing = build_speech_timing(
            timing_id=f"t_{unit.narration_id}",
            artifact_id=artifact.artifact_id,
            narration_id=unit.narration_id,
            provider=voice.provider,
            language=unit.language,
            word_timestamps=response.word_timestamps,
            duration_sec=response.duration_sec,
        )
        timings[unit.narration_id] = timing

        # Cache write.
        if cache is not None:
            cache.store(artifact, Path(response.audio_path))

    return artifacts, timings


def _make_request(
    unit: NarrationUnit,
    voice: VoiceDefinition,
    settings_override,
    audio_path,
    fingerprint: str,
):
    from app.voice.provider_base import VoiceTTSRequest
    return VoiceTTSRequest(
        text=unit.text,
        voice=voice,
        settings_override=settings_override,
        output_path=str(audio_path),
        language=unit.language,
        locale=unit.locale,
        pronunciation_hints=unit.pronunciation_hints,
        metadata={"narration_id": unit.narration_id, "speaker_id": unit.speaker_id},
        fingerprint=fingerprint,
    )


__all__ = ["run_tts_pipeline"]
