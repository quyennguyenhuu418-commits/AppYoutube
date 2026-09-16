"""Content-addressed TTS cache (PROMPT 8 §18–§20).

Mirrors the ResearchCache / StoryCache / CharacterCache pattern.

Cache layout:
  workspace/{job_id}/voice_cache/{fingerprint}.json   ← AudioArtifact dict
  workspace/{job_id}/voice_cache/{fingerprint}.wav    ← audio bytes (optional)
  workspace/{job_id}/voice_cache/_index.json          ← summary index

A cache hit short-circuits the provider call, returning the canonical
AudioArtifact and its audio file.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.voice.schemas import AudioArtifact, compute_audio_fingerprint


def _hash16(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


class VoiceTTSCache:
    """Per-job content-addressed cache for AudioArtifacts.

    Cache key: the audio fingerprint (text_hash + voice_config_hash).
    Cache value: AudioArtifact dict + audio file.
    """

    def __init__(self, job_id: str, ttl_seconds: int | None = None):
        self.job_id = job_id
        self._base = settings.workspace_path / job_id / "voice_cache"
        self._base.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl_seconds if ttl_seconds is not None else settings.research_cache_ttl_days * 86400

    # ------------------------------------------------------------------
    # Cache paths
    # ------------------------------------------------------------------

    def _artifact_path(self, fingerprint: str) -> Path:
        return self._base / f"{fingerprint}.json"

    def _audio_path(self, fingerprint: str, fmt: str = "wav") -> Path:
        return self._base / f"{fingerprint}.{fmt}"

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup(
        self,
        text: str,
        voice,                              # VoiceDefinition
        settings_override=None,             # VoiceSettings | None
        format: str = "wav",
    ) -> AudioArtifact | None:
        """Return cached AudioArtifact for the given input, or None."""
        fp = compute_audio_fingerprint(
            text,
            voice,
            settings_override,
        )
        path = self._artifact_path(fp)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > self._ttl:
            self._evict(path)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        try:
            return AudioArtifact.model_validate(data)
        except Exception:
            return None

    def has_audio(self, fingerprint: str, format: str = "wav") -> bool:
        return self._audio_path(fingerprint, format).exists()

    def audio_path(self, fingerprint: str, format: str = "wav") -> Path:
        return self._audio_path(fingerprint, format)

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------

    def store(
        self,
        artifact: AudioArtifact,
        audio_bytes_path: Path | None = None,
    ) -> AudioArtifact:
        """Persist an AudioArtifact + (optionally) its audio bytes.

        Returns the same artifact (with `fingerprint` field populated).
        """
        path = self._artifact_path(artifact.fingerprint)
        path.write_text(
            json.dumps(artifact.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if audio_bytes_path is not None and audio_bytes_path.exists():
            target = self._audio_path(artifact.fingerprint, artifact.format)
            if not target.exists():
                target.write_bytes(audio_bytes_path.read_bytes())
        return artifact

    # ------------------------------------------------------------------
    # Eviction
    # ------------------------------------------------------------------

    def evict(self, fingerprint: str) -> None:
        self._evict(self._artifact_path(fingerprint))
        for fmt in ("wav", "mp3"):
            p = self._audio_path(fingerprint, fmt)
            if p.exists():
                p.unlink(missing_ok=True)

    def _evict(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "base": str(self._base),
            "entries": sum(1 for p in self._base.glob("*.json") if not p.name.startswith("_")),
        }


__all__ = ["VoiceTTSCache"]
