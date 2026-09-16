"""VoiceRegistry — canonical voice management (PROMPT 8 §8).

Mirrors the AssetRegistry / CharacterRegistry pattern: holds the
canonical list of voices with lifecycle bookkeeping, usage tracking,
and lookup helpers.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.voice import lifecycle as voice_lifecycle
from app.voice.schemas import (
    TtsEnvironment,
    VoiceDefinition,
    VoiceLifecycleStatus,
    VoiceRegistry,
    VoiceRegistryEntry,
)


class VoiceNotFoundError(LookupError):
    """Raised when looking up a voice that doesn't exist."""
    def __init__(self, voice_id: str):
        super().__init__(f"Voice not found: {voice_id!r}")
        self.voice_id = voice_id


class DuplicateVoiceError(ValueError):
    """Raised when registering a voice with a duplicate ID."""
    def __init__(self, voice_id: str):
        super().__init__(f"Voice already registered: {voice_id!r}")
        self.voice_id = voice_id


class VoiceRegistryManager:
    """In-memory VoiceRegistry manager.

    Backed by a `VoiceRegistry` model. Suitable for unit tests and the
    pipeline stage (state lives across stages in process memory).

    For persistent storage, callers can serialize the underlying
    `VoiceRegistry` to JSON.
    """

    def __init__(self, registry: VoiceRegistry | None = None):
        self.registry = registry or VoiceRegistry()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, voice: VoiceDefinition, *, replace: bool = False) -> VoiceRegistryEntry:
        """Register a voice. Raises DuplicateVoiceError if voice_id exists
        (unless `replace=True`)."""
        if voice.voice_id in {e.voice_id for e in self.registry.voices}:
            if not replace:
                raise DuplicateVoiceError(voice.voice_id)
            self.registry.voices = [
                e for e in self.registry.voices if e.voice_id != voice.voice_id
            ]
        entry = VoiceRegistryEntry(
            voice_id=voice.voice_id,
            version_label=voice.version_label,
            status=voice.status,
        )
        self.registry.voices.append(entry)
        self.registry.updated_at = datetime.utcnow()
        return entry

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup(self, voice_id: str) -> VoiceRegistryEntry:
        for e in self.registry.voices:
            if e.voice_id == voice_id:
                return e
        raise VoiceNotFoundError(voice_id)

    def has(self, voice_id: str) -> bool:
        return any(e.voice_id == voice_id for e in self.registry.voices)

    def list(self) -> list[VoiceRegistryEntry]:
        return list(self.registry.voices)

    def search(self, predicate) -> list[VoiceRegistryEntry]:
        return [e for e in self.registry.voices if predicate(e)]

    def find_by_language(self, language: str) -> list[VoiceRegistryEntry]:
        """Find voices matching the language code (registry does not carry
        the full VoiceDefinition — callers must supply the lookup map)."""
        # Without a VoiceDefinition map we can only filter by language
        # if the entry has metadata. We expose this hook for callers that
        # have an external voice store; here we return an empty list and
        # log a warning so callers know to supply their own lookup map.
        self.registry.warnings.append(
            "find_by_language requires a voice map; returning empty list"
        )
        return []

    def find_by_status(self, status: VoiceLifecycleStatus) -> list[VoiceRegistryEntry]:
        return [e for e in self.registry.voices if e.status == status]

    def find_approved(self) -> list[VoiceRegistryEntry]:
        return self.find_by_status(VoiceLifecycleStatus.APPROVED)

    def find_active(self) -> list[VoiceRegistryEntry]:
        return self.find_by_status(VoiceLifecycleStatus.ACTIVE)

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def transition(
        self,
        voice_id: str,
        target: VoiceLifecycleStatus,
        *,
        approved_by: str = "",
    ) -> VoiceRegistryEntry:
        entry = self.lookup(voice_id)
        voice_lifecycle.assert_transition(entry.status, target)
        entry.status = target
        self.registry.updated_at = datetime.utcnow()
        if target == VoiceLifecycleStatus.APPROVED:
            entry.approved_by = approved_by or entry.approved_by or "system"
            entry.approved_at = entry.approved_at or datetime.utcnow()
        return entry

    def deprecate(self, voice_id: str, *, reason: str = "") -> VoiceRegistryEntry:
        entry = self.lookup(voice_id)
        voice_lifecycle.assert_transition(entry.status, VoiceLifecycleStatus.DEPRECATED)
        entry.status = VoiceLifecycleStatus.DEPRECATED
        entry.deprecated_reason = reason
        self.registry.updated_at = datetime.utcnow()
        return entry

    # ------------------------------------------------------------------
    # Usage tracking (PROMPT 8 §32)
    # ------------------------------------------------------------------

    def record_usage(self, voice_id: str) -> VoiceRegistryEntry:
        entry = self.lookup(voice_id)
        entry.usage_count += 1
        entry.last_used_at = datetime.utcnow()
        return entry

    # ------------------------------------------------------------------
    # Resolvability check (PROMPT 8 §9)
    # ------------------------------------------------------------------

    def is_resolvable(self, voice_id: str, environment: TtsEnvironment) -> bool:
        try:
            entry = self.lookup(voice_id)
        except VoiceNotFoundError:
            return False
        if environment == TtsEnvironment.PRODUCTION:
            return entry.status in voice_lifecycle.RESOLVABLE_IN_PRODUCTION
        if environment == TtsEnvironment.DEVELOPMENT:
            return entry.status in voice_lifecycle.RESOLVABLE_IN_DEVELOPMENT
        # MOCK environment allows everything (the resolver will still
        # emit an audit event).
        return True

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return self.registry.model_dump(mode="json")


__all__ = [
    "VoiceRegistryManager",
    "VoiceNotFoundError",
    "DuplicateVoiceError",
]
