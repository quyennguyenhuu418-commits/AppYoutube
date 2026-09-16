"""AudioArtifact writer + fingerprint computation helpers (PROMPT 8 §17, §18).

The writer takes a synthesized provider response, computes the canonical
fingerprint, validates the audio file, and emits the canonical
AudioArtifact.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.voice.audio_validator import apply_validation_to_artifact, validate_audio_file
from app.voice.schemas import (
    AudioArtifact,
    AudioArtifactStatus,
    TtsProviderName,
    VoiceDefinition,
    VoiceSettings,
    compute_audio_fingerprint,
    compute_text_hash,
    compute_voice_config_hash,
)


def compute_sha256(path: str | Path) -> str:
    """SHA-256 hex digest of the bytes of a file."""
    p = Path(path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_id_from_fingerprint(fp: str) -> str:
    """`artifact_id` is exactly the fingerprint (text_hash + voice_config_hash)."""
    return fp


def write_audio_artifact(
    *,
    text: str,
    voice: VoiceDefinition,
    settings_override: VoiceSettings | None,
    provider: TtsProviderName,
    provider_version: str,
    audio_path: str | Path,
    duration_sec: float,
    sample_rate: int,
    channels: int,
    bits_per_sample: int,
    format: str,
    narration_id: str,
    provider_metadata: dict[str, Any] | None = None,
    validate: bool = True,
) -> AudioArtifact:
    """Build + (optionally) validate a canonical AudioArtifact from a
    freshly-synthesized audio file."""
    fingerprint = compute_audio_fingerprint(text, voice, settings_override)
    artifact_id = artifact_id_from_fingerprint(fingerprint)
    src = Path(audio_path)
    byte_size = src.stat().st_size if src.exists() else 0
    checksum = compute_sha256(src) if src.exists() else ""

    artifact = AudioArtifact(
        artifact_id=artifact_id,
        narration_id=narration_id,
        voice_id=voice.voice_id,
        provider=provider,
        provider_version=provider_version,
        source_text_hash=compute_text_hash(text),
        voice_config_hash=compute_voice_config_hash(voice, settings_override),
        format=format.lower(),
        sample_rate=sample_rate,
        channels=channels,
        bits_per_sample=bits_per_sample,
        duration_sec=round(duration_sec, 6),
        uri=str(audio_path) if src.exists() else "",
        absolute_path=str(src.resolve()) if src.exists() else "",
        checksum_sha256=checksum,
        byte_size=byte_size,
        fingerprint=fingerprint,
        status=AudioArtifactStatus.GENERATED,
        metadata=provider_metadata or {},
    )
    if validate:
        artifact = apply_validation_to_artifact(artifact)
    return artifact


__all__ = [
    "write_audio_artifact",
    "compute_sha256",
    "artifact_id_from_fingerprint",
]
