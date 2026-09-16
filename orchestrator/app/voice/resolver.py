"""VoiceResolver — policy-based voice selection (PROMPT 8 §15, §32, §33).

Resolution order (deterministic):
1. explicit unit voice_id (if approved for environment)
2. project-level default voice (if approved)
3. project-level approved voice with matching language
4. mock fallback (only in MOCK / DEVELOPMENT environments)
5. raise error in PRODUCTION

Every decision is logged into a `ResolutionEvent` audit log. No silent
provider switching in PRODUCTION.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from app.voice import lifecycle as voice_lifecycle
from app.voice.provider_base import (
    TTSProviderError,
    VoiceTTSProvider,
)
from app.voice.provider_factory import select_provider
from app.voice.registry import VoiceRegistryManager
from app.voice.schemas import (
    NarrationUnit,
    ResolutionEvent,
    TtsEnvironment,
    TtsProviderName,
    VoiceDefinition,
    VoiceInstance,
    VoiceLifecycleStatus,
    VoiceRegistry,
    VoiceResolution,
    VoiceSettings,
)

log = logging.getLogger(__name__)


class VoiceResolutionError(Exception):
    """Raised when voice resolution fails (e.g. PRODUCTION fallback)."""


class VoiceResolver:
    """Policy-based voice resolver."""

    def __init__(
        self,
        registry: VoiceRegistryManager,
        voice_definitions: dict[str, VoiceDefinition] | None = None,
        voice_instances: list[VoiceInstance] | None = None,
        environment: TtsEnvironment = TtsEnvironment.DEVELOPMENT,
        project_default_voice_id: str | None = None,
        fallback_voice_id: str | None = None,
        default_provider: TtsProviderName = TtsProviderName.MOCK,
    ):
        self.registry = registry
        # voice_definitions: id -> VoiceDefinition (the registry only carries metadata).
        self.voice_definitions: dict[str, VoiceDefinition] = voice_definitions or {}
        self.voice_instances: list[VoiceInstance] = voice_instances or []
        self.environment = environment
        self.project_default_voice_id = project_default_voice_id
        self.fallback_voice_id = fallback_voice_id
        self.default_provider = default_provider
        self.audit_log: list[ResolutionEvent] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, unit: NarrationUnit) -> VoiceResolution:
        """Resolve a narration unit to a concrete voice + provider."""
        events: list[str] = []
        fallback_used = False
        mock_used = False

        # 1. Explicit voice_id on the unit.
        if unit.voice_id:
            events.append(f"explicit_voice:{unit.voice_id}")
            voice = self._resolve_approved_voice(unit.voice_id, events)
            strategy = "explicit"
        # 2. VoiceInstance matching speaker_id.
        else:
            instance = self._match_instance(unit)
            if instance is not None:
                events.append(f"instance_match:{instance.instance_id}")
                voice = self._resolve_approved_voice(instance.voice_id, events)
                strategy = "instance_match"
            # 3. Project-level default.
            elif self.project_default_voice_id:
                events.append(f"project_default:{self.project_default_voice_id}")
                voice = self._resolve_approved_voice(self.project_default_voice_id, events)
                strategy = "project_default"
            else:
                voice = None
                strategy = "no_match"

        # 4. Fallback chain.
        if voice is None:
            # Try fallback voice (e.g. approved voice with matching language).
            cand = self._find_compatible_voice(unit)
            if cand is not None:
                events.append(f"compatible_voice:{cand.voice_id}")
                voice = cand
                fallback_used = True
                strategy = "compatible_fallback"
            elif self.fallback_voice_id:
                events.append(f"explicit_fallback:{self.fallback_voice_id}")
                voice = self._resolve_approved_voice(self.fallback_voice_id, events)
                fallback_used = True
                strategy = "explicit_fallback"

        # 5. Mock fallback in MOCK / DEVELOPMENT only.
        if voice is None:
            if self.environment in (TtsEnvironment.MOCK, TtsEnvironment.DEVELOPMENT):
                events.append("mock_fallback")
                mock_used = True
                voice = self._make_ephemeral_mock_voice(unit)
                strategy = "mock_fallback"
            else:
                raise VoiceResolutionError(
                    f"No voice found for narration {unit.narration_id!r} in PRODUCTION"
                )

        # Decide provider: voice.provider wins, else default_provider.
        provider_name = voice.provider if voice.provider else self.default_provider
        # PRODUCTION: do not silently downgrade provider.
        if provider_name != voice.provider:
            events.append(f"provider_default_override:{provider_name.value}")

        # Determine settings: voice defaults, then instance override.
        settings = voice.settings
        instance = self._match_instance(unit)
        if instance is not None and instance.settings_override is not None:
            settings = instance.settings_override
            events.append("instance_settings_override")

        resolution_id = f"res_{unit.narration_id}_{uuid.uuid4().hex[:8]}"
        resolution = VoiceResolution(
            resolution_id=resolution_id,
            narration_id=unit.narration_id,
            resolved_voice_id=voice.voice_id,
            resolved_provider=provider_name,
            strategy=strategy,
            settings_used=settings,
            events=events,
            fallback_used=fallback_used,
            mock_used=mock_used,
        )
        # Audit event.
        self.audit_log.append(
            ResolutionEvent(
                event_id=f"evt_{resolution_id}",
                narration_id=unit.narration_id,
                requested_voice_id=unit.voice_id,
                resolved_voice_id=voice.voice_id,
                strategy=strategy,
                provider=provider_name,
                environment=self.environment,
                detail={"fallback_used": fallback_used, "mock_used": mock_used},
            )
        )
        # Record usage.
        try:
            self.registry.record_usage(voice.voice_id)
        except Exception:  # noqa: BLE001
            pass
        return resolution

    # ------------------------------------------------------------------
    # Provider selection
    # ------------------------------------------------------------------

    def select_provider_for(
        self, voice: VoiceDefinition, unit: NarrationUnit
    ) -> VoiceTTSProvider:
        """Select a concrete TTS provider for the given voice.

        Honors the resolver's environment + the voice's provider
        declaration. Returns a `VoiceTTSProvider`.
        """
        try:
            return select_provider(voice.provider, self.environment)
        except TTSProviderError as exc:
            log.warning(
                "Provider selection failed for voice %s (%s): %s",
                voice.voice_id, voice.provider.value, exc,
            )
            if self.environment == TtsEnvironment.PRODUCTION:
                raise
            # Fall back to mock.
            log.warning("[voice] falling back to mock provider (environment=%s)", self.environment.value)
            return select_provider(TtsProviderName.MOCK, self.environment)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_approved_voice(
        self, voice_id: str, events: list[str]
    ) -> VoiceDefinition:
        voice = self.voice_definitions.get(voice_id)
        if voice is None:
            events.append(f"unknown_voice:{voice_id}")
            raise VoiceResolutionError(f"Unknown voice_id: {voice_id!r}")
        if not self.registry.is_resolvable(voice_id, self.environment):
            current = self.registry.lookup(voice_id).status
            events.append(f"unresolvable_status:{current.value}")
            raise VoiceResolutionError(
                f"Voice {voice_id!r} not resolvable in {self.environment.value} "
                f"(status={current.value})"
            )
        return voice

    def _match_instance(self, unit: NarrationUnit) -> VoiceInstance | None:
        # Prefer instance with matching speaker_id + scene_id; else speaker_id-only.
        candidates = [i for i in self.voice_instances if i.speaker_role == unit.speaker_role]
        if not candidates:
            candidates = [i for i in self.voice_instances if i.speaker_id_compatible(unit.speaker_id)]
        if not candidates:
            return None
        scene_match = [i for i in candidates if i.scene_id and i.scene_id == unit.scene_id]
        if scene_match:
            return scene_match[0]
        project_match = [i for i in candidates if not i.scene_id]
        if project_match:
            return project_match[0]
        return candidates[0]

    def _find_compatible_voice(self, unit: NarrationUnit) -> VoiceDefinition | None:
        # Find an APPROVED / ACTIVE voice that supports the unit's language.
        for entry in self.registry.find_active() + self.registry.find_approved():
            voice = self.voice_definitions.get(entry.voice_id)
            if voice is None:
                continue
            if unit.language in voice.supported_languages:
                return voice
        return None

    def _make_ephemeral_mock_voice(self, unit: NarrationUnit) -> VoiceDefinition:
        """Construct a transient mock voice for development/test fallback."""
        voice_id = f"ephemeral_mock_{unit.language}"
        return VoiceDefinition(
            voice_id=voice_id,
            name=f"Ephemeral Mock ({unit.language})",
            language=unit.language,
            locale=unit.locale or f"{unit.language}-XX",
            provider=TtsProviderName.MOCK,
            style="unspecified",
            status=VoiceLifecycleStatus.DRAFT,
            version_label="v1",
        )


__all__ = ["VoiceResolver", "VoiceResolutionError"]
