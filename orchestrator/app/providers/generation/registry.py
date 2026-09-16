"""
Provider Registry — single source of truth for generation provider metadata.

L-U8 — Provider Adapter Layer.

This module maintains the canonical registry of all known generation providers
(IMAGE_GENERATION, VIDEO_GENERATION).

Registry operations are deterministic and produce the same result for the same inputs.
"""

from __future__ import annotations

from typing import Optional

from app.providers.generation.schemas import (
    ExecutionMode,
    ProviderCapability,
    ProviderDefinition,
    ProviderStatus,
    ProviderType,
    ProviderVerificationStatus,
)


class ProviderRegistry:
    """Canonical registry of generation providers.

    This is a SINGLE SOURCE OF TRUTH for provider metadata.
    Do NOT create duplicate registries (ProviderRegistry2, ProviderCatalog, etc.).
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderDefinition] = {}
        self._capabilities: dict[str, ProviderCapability] = {}

    # ---- Registration ----

    def register(
        self,
        definition: ProviderDefinition,
        capability: Optional[ProviderCapability] = None,
    ) -> None:
        """Register a provider and its primary capability."""
        if definition.provider_id in self._providers:
            raise ValueError(
                f"Provider '{definition.provider_id}' already registered. "
                "Use update() to modify."
            )
        self._providers[definition.provider_id] = definition
        if capability is not None:
            self._capabilities[capability.capability_id] = capability

    def unregister(self, provider_id: str) -> None:
        """Remove a provider and its capabilities."""
        self._providers.pop(provider_id, None)
        # Remove associated capabilities
        to_remove = [
            cid for cid, cap in self._capabilities.items()
            if cap.provider_id == provider_id
        ]
        for cid in to_remove:
            self._capabilities.pop(cid, None)

    # ---- Query ----

    def get(self, provider_id: str) -> Optional[ProviderDefinition]:
        """Get a provider definition by ID."""
        return self._providers.get(provider_id)

    def list_all(self) -> tuple[ProviderDefinition, ...]:
        """List all registered providers."""
        return tuple(self._providers.values())

    def list_by_type(
        self,
        provider_type: ProviderType,
    ) -> tuple[ProviderDefinition, ...]:
        """List all providers of a given type."""
        return tuple(
            p for p in self._providers.values()
            if provider_type in p.provider_type
        )

    def list_active(self) -> tuple[ProviderDefinition, ...]:
        """List all ACTIVE providers (only these may be auto-selected)."""
        return tuple(
            p for p in self._providers.values()
            if p.status == ProviderStatus.ACTIVE
        )

    def list_active_by_type(
        self,
        provider_type: ProviderType,
    ) -> tuple[ProviderDefinition, ...]:
        """List all ACTIVE providers of a given type."""
        return tuple(
            p for p in self._providers.values()
            if p.status == ProviderStatus.ACTIVE
            and provider_type in p.provider_type
        )

    # ---- Capability lookup ----

    def get_capability(
        self,
        capability_id: str,
    ) -> Optional[ProviderCapability]:
        """Get a capability by ID."""
        return self._capabilities.get(capability_id)

    def list_capabilities_for_provider(
        self,
        provider_id: str,
    ) -> tuple[ProviderCapability, ...]:
        """List all capabilities for a provider."""
        return tuple(
            c for c in self._capabilities.values()
            if c.provider_id == provider_id
        )

    # ---- Version lookup ----

    def get_version(self, provider_id: str) -> Optional[str]:
        """Get the version string for a provider."""
        p = self._providers.get(provider_id)
        return p.version if p else None


# ============================================================================
# Default registry with known providers
# ============================================================================


def _build_default_registry() -> ProviderRegistry:
    """Build the default registry with known providers.

    These are DECLARED providers. Runtime verification (VERIFIED) requires
    actual execution.
    """
    registry = ProviderRegistry()

    # ---- Mock Generation Provider ----
    registry.register(
        ProviderDefinition(
            provider_id="mock_gen",
            display_name="Mock Generation Provider",
            provider_type=(ProviderType.IMAGE_GENERATION, ProviderType.VIDEO_GENERATION),
            version="1.0.0",
            execution_mode=ExecutionMode.LOCAL,
            adapter_version="1.0.0",
            status=ProviderStatus.ACTIVE,
            verification=ProviderVerificationStatus.DECLARED,
            requires_api_key=False,
        ),
        ProviderCapability(
            capability_id="mock_gen_image",
            provider_id="mock_gen",
            provider_type=ProviderType.IMAGE_GENERATION,
            supported_prompt_kinds=("image",),
            supported_aspect_ratios=(),
            supported_camera_shots=frozenset({
                "extreme_wide", "wide", "medium_wide", "medium",
                "medium_close", "close", "extreme_close",
                "over_shoulder", "pov", "dutch",
                "birds_eye", "worms_eye", "two_shot",
            }),
            supported_camera_movements=frozenset({
                "hold", "push_in", "pull_out", "pan",
                "tilt", "zoom", "tracking", "shake", "orbit",
            }),
            supported_subject_motions=frozenset({
                "none", "stand", "walk", "run", "point",
                "think", "celebrate", "hide", "sit",
                "enter", "exit", "gesture", "look",
                "turn", "breathing", "idle",
            }),
            supported_motion_patterns=frozenset({
                "frame_by_frame", "loop",
                "rig_pose_interpolation",
                "kinetic_text", "shake_nervous",
            }),
            supported_sound_semantics=frozenset({
                "ambient", "music", "sfx", "environment",
                "narration", "dialogue", "impact", "silence",
            }),
            character_reference_support=True,
            negative_constraint_support=True,
            sound_layers_support=True,
            maximum_characters=None,
            verification=ProviderVerificationStatus.DECLARED,
        ),
    )

    # ---- Google Flow ----
    registry.register(
        ProviderDefinition(
            provider_id="google_flow",
            display_name="Google Flow",
            provider_type=(ProviderType.IMAGE_GENERATION,),
            version="1.0.0",
            execution_mode=ExecutionMode.REMOTE,
            adapter_version="1.0.0",
            status=ProviderStatus.EXPERIMENTAL,
            verification=ProviderVerificationStatus.UNKNOWN,
            requires_api_key=True,
            endpoint="https://labs.google.com/flow",
            default_model=None,
        ),
        ProviderCapability(
            capability_id="google_flow_image",
            provider_id="google_flow",
            provider_type=ProviderType.IMAGE_GENERATION,
            supported_prompt_kinds=("image",),
            supported_aspect_ratios=(),
            supported_camera_shots=frozenset(),
            supported_camera_movements=frozenset(),
            supported_subject_motions=frozenset(),
            supported_motion_patterns=frozenset(),
            supported_sound_semantics=frozenset(),
            character_reference_support=False,
            negative_constraint_support=False,
            sound_layers_support=False,
            verification=ProviderVerificationStatus.UNKNOWN,
        ),
    )

    # ---- DINO (placeholder) ----
    registry.register(
        ProviderDefinition(
            provider_id="dino_ai",
            display_name="DINO AI",
            provider_type=(ProviderType.IMAGE_GENERATION,),
            version="1.0.0",
            execution_mode=ExecutionMode.REMOTE,
            adapter_version="1.0.0",
            status=ProviderStatus.EXPERIMENTAL,
            verification=ProviderVerificationStatus.UNKNOWN,
            requires_api_key=True,
            endpoint=None,
        ),
        ProviderCapability(
            capability_id="dino_ai_image",
            provider_id="dino_ai",
            provider_type=ProviderType.IMAGE_GENERATION,
            supported_prompt_kinds=("image",),
            supported_aspect_ratios=(),
            supported_camera_shots=frozenset(),
            supported_camera_movements=frozenset(),
            supported_subject_motions=frozenset(),
            supported_motion_patterns=frozenset(),
            supported_sound_semantics=frozenset(),
            character_reference_support=False,
            negative_constraint_support=False,
            sound_layers_support=False,
            verification=ProviderVerificationStatus.UNKNOWN,
        ),
    )

    # ---- Video Generation (generic placeholder) ----
    registry.register(
        ProviderDefinition(
            provider_id="generic_video",
            display_name="Generic Video Generation",
            provider_type=(ProviderType.VIDEO_GENERATION,),
            version="1.0.0",
            execution_mode=ExecutionMode.REMOTE,
            adapter_version="1.0.0",
            status=ProviderStatus.EXPERIMENTAL,
            verification=ProviderVerificationStatus.UNKNOWN,
            requires_api_key=True,
            endpoint=None,
        ),
        ProviderCapability(
            capability_id="generic_video_gen",
            provider_id="generic_video",
            provider_type=ProviderType.VIDEO_GENERATION,
            supported_prompt_kinds=("video",),
            supported_aspect_ratios=(),
            supported_camera_shots=frozenset(),
            supported_camera_movements=frozenset(),
            supported_subject_motions=frozenset(),
            supported_motion_patterns=frozenset(),
            supported_sound_semantics=frozenset(),
            character_reference_support=False,
            negative_constraint_support=False,
            sound_layers_support=False,
            maximum_duration_sec=60.0,
            verification=ProviderVerificationStatus.UNKNOWN,
        ),
    )

    return registry


# Module-level singleton (deterministic, no I/O)
_DEFAULT_REGISTRY = _build_default_registry()


def get_registry() -> ProviderRegistry:
    """Get the default provider registry."""
    return _DEFAULT_REGISTRY


def reset_registry() -> ProviderRegistry:
    """Reset the registry to the default state. For testing only."""
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = _build_default_registry()
    return _DEFAULT_REGISTRY


__all__ = [
    "ProviderRegistry",
    "get_registry",
    "reset_registry",
]
