"""
Capability Matcher — deterministic matching of generation requirements to provider capabilities.

L-U8 — Provider Adapter Layer.

The matcher receives a GenerationCapabilityRequirement and returns a
CapabilityMatchResult for each candidate capability.

This is NOT a recommendation engine. It does NOT rank providers.
It only determines compatibility.
"""

from __future__ import annotations

from app.providers.generation.schemas import (
    CapabilityCompatibility,
    CapabilityMatchResult,
    GenerationCapabilityRequirement,
    ProviderCapability,
)


def match_capability(
    requirement: GenerationCapabilityRequirement,
    capability: ProviderCapability,
) -> CapabilityMatchResult:
    """Deterministically match a requirement against a capability.

    Returns a CapabilityMatchResult with SUPPORTED / PARTIALLY_SUPPORTED /
    UNSUPPORTED / UNKNOWN.
    """
    unsupported: list[str] = []
    partial: list[str] = []

    # 1. Prompt kind check
    if not capability.supports_prompt_kind(requirement.prompt_kind):
        unsupported.append(f"prompt_kind:{requirement.prompt_kind}")
        return CapabilityMatchResult(
            compatibility=CapabilityCompatibility.UNSUPPORTED,
            capability=capability,
            unsupported_features=tuple(unsupported),
            partially_supported_features=tuple(partial),
        )

    # 2. Aspect ratio check
    if requirement.aspect_ratio is not None:
        if not capability.supports_aspect_ratio(requirement.aspect_ratio):
            partial.append(f"aspect_ratio:{requirement.aspect_ratio}")

    # 3. Duration check (video only)
    if requirement.duration_sec is not None and capability.maximum_duration_sec is not None:
        if requirement.duration_sec > capability.maximum_duration_sec:
            unsupported.append(
                f"duration:{requirement.duration_sec}s "
                f"> max:{capability.maximum_duration_sec}s"
            )

    # 4. Character reference check
    if requirement.requires_character_reference and not capability.character_reference_support:
        unsupported.append("character_reference")

    # 5. Negative constraints check
    if requirement.requires_negative_constraints and not capability.negative_constraint_support:
        unsupported.append("negative_constraints")

    # 6. Sound layers check
    if requirement.requires_sound_layers and not capability.sound_layers_support:
        partial.append("sound_layers")

    # 7. Camera shots check
    if requirement.camera_shots:
        unsupported_shots = requirement.camera_shots - capability.supported_camera_shots
        if unsupported_shots:
            unsupported.append(f"camera_shots:{', '.join(unsupported_shots)}")

    # 8. Camera movements check
    if requirement.camera_movements:
        unsupported_movements = requirement.camera_movements - capability.supported_camera_movements
        if unsupported_movements:
            partial.append(
                f"camera_movements:{', '.join(unsupported_movements)}"
            )

    # 9. Subject motions check
    if requirement.subject_motions:
        unsupported_motions = requirement.subject_motions - capability.supported_subject_motions
        if unsupported_motions:
            partial.append(f"subject_motions:{', '.join(unsupported_motions)}")

    # Determine compatibility
    if unsupported:
        compat = CapabilityCompatibility.UNSUPPORTED
    elif partial:
        compat = CapabilityCompatibility.PARTIALLY_SUPPORTED
    else:
        compat = CapabilityCompatibility.SUPPORTED

    return CapabilityMatchResult(
        compatibility=compat,
        capability=capability,
        unsupported_features=tuple(unsupported),
        partially_supported_features=tuple(partial),
    )


def find_compatible_providers(
    registry: ProviderRegistry,
    requirement: GenerationCapabilityRequirement,
) -> tuple[CapabilityMatchResult, ...]:
    """Find all providers compatible with a given requirement.

    Returns a tuple of CapabilityMatchResult sorted by compatibility.
    No ranking within compatibility tiers.
    """
    results: list[CapabilityMatchResult] = []

    for cap in registry._capabilities.values():
        result = match_capability(requirement, cap)
        results.append(result)

    # Sort by compatibility (unsupported last)
    order = {
        CapabilityCompatibility.SUPPORTED: 0,
        CapabilityCompatibility.PARTIALLY_SUPPORTED: 1,
        CapabilityCompatibility.UNSUPPORTED: 2,
        CapabilityCompatibility.UNKNOWN: 3,
    }
    results.sort(key=lambda r: order.get(r.compatibility, 99))
    return tuple(results)


__all__ = [
    "match_capability",
    "find_compatible_providers",
]
