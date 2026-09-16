"""
Knowledge Consumer — read-only adapter between StoryboardEngine and KnowledgeRegistry.

L-U2 — Knowledge Layer Read-Only Integration.

Purpose
-------
Provides StoryboardEngine (and other pipeline consumers) with typed,
versioned, traceable lookups into the KnowledgeRegistry. This module
is the ONLY place where StoryboardEngine should reference the
knowledge layer. Downstream consumers should NOT import from
`app.knowledge.*` directly — they go through this adapter.

Design principles
----------------
    1. READ-ONLY — this module never calls `register()`, `bump_version()`,
       or any mutating method on KnowledgeRegistry.
    2. Fail-gracefully — if the registry is empty or unavailable,
       this module returns heuristic defaults, never crashes.
    3. Explicit — every lookup documents the domain / tag / status filter.
    4. Deterministic — same query always returns same result.

Usage
-----
    from app.storyboard.knowledge_consumer import KnowledgeConsumer

    consumer = KnowledgeConsumer()          # Uses build_default_registry()
    # or
    consumer = KnowledgeConsumer(registry=custom_registry)

    # Look up camera vocabulary
    shot = consumer.get_camera_shot("wide_shot")
    movement = consumer.get_camera_movement("push_in")

    # Look up visual style rules
    style_rules = consumer.get_style_rules("hand_drawn_doodle")
    constraints = consumer.get_negative_constraints()

    # Look up character reference rules
    char_ref_rules = consumer.get_character_reference_rules()

    # Look up composition rules
    composition_rules = consumer.get_composition_rules()

    # Look up all rules for a specific applicability
    applicable = consumer.get_rules_by_applicability("video_prompt")

    # Build a VisualGrammar for a beat
    grammar = consumer.build_visual_grammar_for_beat(beat, mode="image")

Critical invariant
-----------------
    All lookups are pass-through to KnowledgeRegistry. This module adds
    no business logic — only typed convenience wrappers and fallbacks.
"""

from __future__ import annotations

from typing import Optional

from app.knowledge import (
    CameraMovementType,
    CameraShotType,
    KnowledgeDomain,
    KnowledgeEntry,
    KnowledgeRegistry,
    KnowledgeStatus,
    MotionPattern,
    VisualGrammar,
    VisualStyleProfile,
    build_default_registry,
)
from app.schemas.storyboard import (
    MotionItem,
    StoryboardCameraType,
    StoryboardMotionType,
    VisualBeat,
)


# ============================================================================
# Mapping: StoryboardCameraType → DINO AI Camera vocabulary
# ============================================================================

# StoryboardCameraType is the existing renderer-bound enum.
# CameraShotType is the DINO AI Cinematic Dictionary enum.
# This mapping is explicit so provenance is clear.

STORYBOARD_TO_CAMERA_SHOT: dict[StoryboardCameraType, CameraShotType] = {
    StoryboardCameraType.WIDE: CameraShotType.WIDE_SHOT,
    StoryboardCameraType.MEDIUM: CameraShotType.MEDIUM_SHOT,
    StoryboardCameraType.CLOSE_UP: CameraShotType.CLOSE_UP,
    StoryboardCameraType.EXTREME_CLOSE_UP: CameraShotType.EXTREME_CLOSE_UP,
    StoryboardCameraType.PUSH_IN: CameraShotType.CLOSE_UP,          # push-in targets close-up
    StoryboardCameraType.PULL_OUT: CameraShotType.WIDE_SHOT,        # pull-out targets wide
    StoryboardCameraType.PAN: CameraShotType.MEDIUM_WIDE_SHOT,     # pan typically starts medium-wide
    StoryboardCameraType.PARALLAX: CameraShotType.WIDE_SHOT,       # parallax used in wide establishing
    StoryboardCameraType.ORBIT: CameraShotType.MEDIUM_WIDE_SHOT,    # orbit starts medium-wide
    StoryboardCameraType.STATIC: CameraShotType.MEDIUM_SHOT,        # static defaults to medium
}

STORYBOARD_TO_CAMERA_MOVEMENT: dict[StoryboardCameraType, CameraMovementType] = {
    StoryboardCameraType.WIDE: CameraMovementType.HOLD,
    StoryboardCameraType.MEDIUM: CameraMovementType.HOLD,
    StoryboardCameraType.CLOSE_UP: CameraMovementType.HOLD,
    StoryboardCameraType.EXTREME_CLOSE_UP: CameraMovementType.HOLD,
    StoryboardCameraType.PUSH_IN: CameraMovementType.PUSH_IN,
    StoryboardCameraType.PULL_OUT: CameraMovementType.PULL_OUT,
    StoryboardCameraType.PAN: CameraMovementType.PAN,
    StoryboardCameraType.PARALLAX: CameraMovementType.PARALLAX,
    StoryboardCameraType.ORBIT: CameraMovementType.ORBIT,
    StoryboardCameraType.STATIC: CameraMovementType.HOLD,
}

STORYBOARD_MOTION_TO_PATTERN: dict[StoryboardMotionType, MotionPattern] = {
    StoryboardMotionType.NONE: MotionPattern.LOOP,
    StoryboardMotionType.CHARACTER_ACTION: MotionPattern.RIG_POSE_INTERPOLATION,
    StoryboardMotionType.PARALLAX_DRIFT: MotionPattern.PARALLAX_PAN,
    StoryboardMotionType.OVERLAY_APPEAR: MotionPattern.KINETIC_TEXT,
    StoryboardMotionType.PROP_ROTATE: MotionPattern.LOOP,
    StoryboardMotionType.METAPHOR: MotionPattern.METAPHOR_DROP,
}


# ============================================================================
# KnowledgeConsumer
# ============================================================================

class KnowledgeConsumer:
    """Read-only adapter to the KnowledgeRegistry.

    All lookups delegate to the injected registry. If no registry is
    provided, a default registry is built from the L-U1 seeds.

    This class is intentionally lightweight — it adds convenience wrappers
    but no business logic. The registry owns the knowledge.
    """

    def __init__(
        self,
        registry: Optional[KnowledgeRegistry] = None,
    ) -> None:
        self._registry = registry or build_default_registry()

    # ----- Registry access -----

    @property
    def registry(self) -> KnowledgeRegistry:
        """The underlying registry (read-only)."""
        return self._registry

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Retrieve a single entry by id."""
        return self._registry.get(entry_id)

    def search(self, query: str) -> list[KnowledgeEntry]:
        """Substring search across name + description + tags."""
        return self._registry.search(query)

    def find_by_domain(self, domain: KnowledgeDomain) -> list[KnowledgeEntry]:
        """All entries in a domain, sorted by id."""
        return self._registry.find_by_domain(domain)

    def find_by_tag(self, tag: str) -> list[KnowledgeEntry]:
        """All entries carrying the given tag."""
        return self._registry.find_by_tag(tag)

    def find_by_status(self, status: KnowledgeStatus) -> list[KnowledgeEntry]:
        """All entries with the given status."""
        return self._registry.find_by_status(status)

    def find_by_applicability(self, tag: str) -> list[KnowledgeEntry]:
        """All entries whose `applicability` list contains the tag."""
        return self._registry.find_by_applicability(tag)

    def apply_filters(
        self,
        domain: Optional[KnowledgeDomain] = None,
        status: Optional[KnowledgeStatus] = None,
        tag: Optional[str] = None,
        applicability: Optional[str] = None,
    ) -> list[KnowledgeEntry]:
        """Multi-filter retrieval; all filters are AND-ed together."""
        return self._registry.apply_filters(
            domain=domain,
            status=status,
            tag=tag,
            applicability=applicability,
        )

    # ----- Camera vocabulary lookups -----

    def get_camera_shot(
        self,
        shot_name: str,
    ) -> Optional[CameraShotType]:
        """Resolve a shot name string to CameraShotType, or None.

        Falls back to MEDIUM_SHOT (the safest default).
        """
        try:
            return CameraShotType(shot_name.lower())
        except ValueError:
            # Try StoryboardCameraType → CameraShotType mapping
            for k, v in STORYBOARD_TO_CAMERA_SHOT.items():
                if k.value == shot_name.lower():
                    return v
            return CameraShotType.MEDIUM_SHOT

    def get_camera_movement(
        self,
        movement_name: str,
    ) -> Optional[CameraMovementType]:
        """Resolve a movement name string to CameraMovementType, or None.

        Falls back to HOLD (the safest default).
        """
        try:
            return CameraMovementType(movement_name.lower())
        except ValueError:
            for k, v in STORYBOARD_TO_CAMERA_MOVEMENT.items():
                if k.value == movement_name.lower():
                    return v
            return CameraMovementType.HOLD

    def get_motion_pattern(
        self,
        motion_type_name: str,
    ) -> Optional[MotionPattern]:
        """Resolve a motion type to MotionPattern.

        Falls back to LOOP.
        """
        try:
            return MotionPattern(motion_type_name.lower())
        except ValueError:
            for k, v in STORYBOARD_MOTION_TO_PATTERN.items():
                if k.value == motion_type_name.lower():
                    return v
            return MotionPattern.LOOP

    def get_shot_rules(self) -> list[KnowledgeEntry]:
        """Get all camera shot rules (DINO AI source)."""
        return self._registry.apply_filters(
            domain=KnowledgeDomain.CAMERA,
            status=KnowledgeStatus.EXPLICIT,
        )

    def get_movement_rules(self) -> list[KnowledgeEntry]:
        """Get all camera movement rules (DINO AI source)."""
        return self._registry.apply_filters(
            domain=KnowledgeDomain.CAMERA_MOVEMENT,
            status=KnowledgeStatus.EXPLICIT,
        )

    # ----- Style lookups -----

    def get_style_rules(self, profile_name: str) -> list[KnowledgeEntry]:
        """Get all rules for a visual style profile.

        Args:
            profile_name: e.g. "hand_drawn_doodle", "semi_realistic_2d"
        """
        entries = self._registry.apply_filters(
            domain=KnowledgeDomain.VISUAL_STYLE,
        )
        return [e for e in entries if profile_name.lower() in e.name.lower()]

    def get_default_style_profile(self) -> VisualStyleProfile:
        """Return the default style profile for this project.

        Currently: HAND_DRAWN_DOODLE (per Google Flow reference).
        """
        return VisualStyleProfile.HAND_DRAWN_DOODLE

    # ----- Character reference lookups -----

    def get_character_reference_rules(self) -> list[KnowledgeEntry]:
        """Get all character reference / consistency rules."""
        return self._registry.apply_filters(
            domain=KnowledgeDomain.CHARACTER_CONSISTENCY,
            status=KnowledgeStatus.EXPLICIT,
        )

    def get_reference_sheet_rules(self) -> list[KnowledgeEntry]:
        """Get rules about reference sheet layout (6-panel structure)."""
        return self._registry.find_by_tag("reference_sheet")

    # ----- Image / video prompt lookups -----

    def get_negative_constraints(self) -> list[KnowledgeEntry]:
        """Get all negative constraint rules."""
        return self._registry.find_by_domain(KnowledgeDomain.NEGATIVE_CONSTRAINT)

    def get_image_prompt_rules(self) -> list[KnowledgeEntry]:
        """Get all image prompt structure rules."""
        return self._registry.apply_filters(
            domain=KnowledgeDomain.IMAGE_PROMPT,
            status=KnowledgeStatus.EXPLICIT,
        )

    def get_video_prompt_rules(self) -> list[KnowledgeEntry]:
        """Get all video prompt structure rules."""
        return self._registry.apply_filters(
            domain=KnowledgeDomain.VIDEO_PROMPT,
            status=KnowledgeStatus.EXPLICIT,
        )

    def get_sound_rules(self) -> list[KnowledgeEntry]:
        """Get all sound / audio rules."""
        return self._registry.find_by_domain(KnowledgeDomain.SOUND)

    def get_voice_rules(self) -> list[KnowledgeEntry]:
        """Get voice-specific rules (TTS, loudness, etc.)."""
        return self._registry.apply_filters(
            domain=KnowledgeDomain.SOUND,
            tag="voice",
        )

    # ----- Composition lookups -----

    def get_composition_rules(self) -> list[KnowledgeEntry]:
        """Get all composition rules."""
        return self._registry.find_by_domain(KnowledgeDomain.COMPOSITION)

    def get_format_rules(self) -> list[KnowledgeEntry]:
        """Get all format rules (aspect ratio, medium)."""
        return self._registry.find_by_domain(KnowledgeDomain.FORMAT)

    def get_continuity_rules(self) -> list[KnowledgeEntry]:
        """Get all continuity rules."""
        return self._registry.find_by_domain(KnowledgeDomain.CONTINUITY)

    # ----- Utility -----

    def get_rules_by_applicability(self, applicability: str) -> list[KnowledgeEntry]:
        """Get all rules for a given applicability tag."""
        return self._registry.find_by_applicability(applicability)

    def get_all_explicit_rules(self) -> list[str]:
        """Return a flat list of all EXPLICIT rules across all domains.

        Useful for injecting into LLM prompt context.
        """
        explicit_entries = self._registry.find_by_status(KnowledgeStatus.EXPLICIT)
        rules: list[str] = []
        for entry in explicit_entries:
            rules.extend(entry.rules)
        return rules

    def summary(self) -> dict:
        """Diagnostic summary of the registry."""
        return self._registry.summary()
