"""
KnowledgeCharacterAdapter — thin adapter bridging Knowledge Layer to Character System.

L-U4 — Character Reference System Integration.

Purpose
-------
The `KnowledgeCharacterAdapter` is the ONLY integration point between the
Knowledge Layer and the Character System. It translates `KnowledgeResult`
from the canonical `KnowledgeResolver` into character-specific guidance
(`CharacterReferenceSpecification`).

Architecture
------------
    KnowledgeContext (L-U3)
            ↓
    KnowledgeResolver (L-U3)
            ↓
    KnowledgeCharacterAdapter (L-U4 — this module)
            ↓
    CharacterReferenceSpecification (L-U4)
            ↓
    CharacterSystemEngine (produces CharacterDefinition)

Design principles
----------------
1. THIN adapter — all resolution goes through `KnowledgeResolver`.
   No direct registry access.
2. KNOWLEDGE-GUIDANCE separation — the adapter resolves guidance,
   NOT actual character values. Color, head_shape, etc. live in
   `CharacterDefinition`, not here.
3. IDENTITY vs SCENE STATE — the adapter explicitly marks which
   properties are identity-bearing and which are scene-variable.
4. PROVENANCE mandatory — every resolved rule carries its source.
5. OPTIONAL — if no `KnowledgeContext` is provided, returns a
   backward-compatible "no knowledge" spec.

What this adapter does NOT do:
    - Generate actual character values (colors, shapes, etc.)
    - Call image generation providers
    - Generate prompts
    - Modify the KnowledgeRegistry
    - Make decisions about character identity (that is the engine's job)

What this adapter DOES:
    - Consult the Knowledge Layer for character rules
    - Translate results into character-specific guidance
    - Preserve provenance
    - Build a `CharacterReferenceSpecification`
    - Handle conflicts explicitly (never silently)
"""

from __future__ import annotations

from typing import Optional

from app.character.reference_schema import (
    CharacterKnowledgeConflict,
    CharacterReferenceSpecification,
    ExplicitOverride,
    IdentityBearingProperty,
    NegativeConstraint,
    PaletteGuidance,
    ResolvedCharacterRule,
    SceneVariableProperty,
    WardrobeGuidance,
)
from app.knowledge import (
    FallbackPolicy,
    KnowledgeContext,
    KnowledgeDomain,
    KnowledgeQuery,
    KnowledgeRegistry,
    KnowledgeResolver,
    KnowledgeResult,
    KnowledgeStatus,
    default_sources,
)
from app.schemas.storyboard import CharacterRequirement


# ============================================================================
# Tag-to-category mapping (L-U1 convention)
# ============================================================================

# Maps KnowledgeEntry tags → character property categories.
# These are derived from the L-U1 seeds (google_flow character seeds).
_TAG_TO_CATEGORY: dict[str, str] = {
    # Identity-bearing categories
    "reference_sheet": "identity_lock",
    "consistency": "consistency",
    "family": "family_grouping",
    "signature_prop": "signature_prop",
    "style": "style_profile",
    "design": "design_rules",
    "wardrobe": "wardrobe",
    "doodle": "style_doodle",
    # Scene-variable categories
    "image_prompt": "image_prompt",  # not character-specific
    "video_prompt": "video_prompt",  # not character-specific
    "google_flow": "google_flow",
    "dino_ai": "dino_ai",
    "axen": "axen",
}

# Which categories are identity-bearing (locked across scenes)
_IDENTITY_BEARING_CATEGORIES: frozenset[str] = frozenset({
    "identity_lock",
    "consistency",
    "family_grouping",
    "signature_prop",
    "style_profile",
    "design_rules",
    "wardrobe",
})

# Which tags indicate negative constraints
_NEGATIVE_TAGS: frozenset[str] = frozenset({
    "negative",
    "forbid",
})

# Which tags indicate wardrobe guidance
_WARDROBE_TAGS: frozenset[str] = frozenset({
    "wardrobe",
    "clothing",
})

# Which tags indicate style/palette guidance
_PALETTE_TAGS: frozenset[str] = frozenset({
    "color",
    "palette",
    "style",
})


# ============================================================================
# The adapter
# ============================================================================

class KnowledgeCharacterAdapter:
    """Thin adapter: Knowledge Layer → Character Reference Specification.

    Construction:
        # Canonical L-U3 path (preferred):
        ctx = KnowledgeContext.from_registry(registry)
        adapter = KnowledgeCharacterAdapter(context=ctx)

        # Legacy L-U2 path (still supported):
        adapter = KnowledgeCharacterAdapter(registry=registry)

        # No-knowledge path (backward compatible):
        adapter = KnowledgeCharacterAdapter()  # or None

    Usage:
        spec = adapter.resolve_character_reference(character_requirement)
        # spec is a CharacterReferenceSpecification

    The adapter NEVER:
        - Generates actual character values (colors, shapes)
        - Calls image providers
        - Mutates the registry
        - Makes character identity decisions
    """

    def __init__(
        self,
        registry: Optional[KnowledgeRegistry] = None,
        *,
        context: Optional[KnowledgeContext] = None,
    ) -> None:
        # Three accepted shapes (mirrors KnowledgeStoryboardAdapter):
        #   1. KnowledgeContext (canonical L-U3) — preferred
        #   2. KnowledgeRegistry (legacy)     — backward-compatible
        #   3. None                           — no-knowledge mode
        if context is not None:
            self._context = context
        elif registry is not None:
            self._context = _build_context_from_registry(registry)
        else:
            self._context = KnowledgeContext.disabled(name="character-no-knowledge")

        self._resolver: KnowledgeResolver = self._context.resolver

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """True iff the Knowledge Layer is available and non-empty."""
        return self._resolver.is_active()

    @property
    def context(self) -> KnowledgeContext:
        """The KnowledgeContext backing this adapter."""
        return self._context

    @property
    def resolver(self) -> KnowledgeResolver:
        """The resolver backing this adapter."""
        return self._resolver

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def resolve_character_reference(
        self,
        requirement: CharacterRequirement,
    ) -> CharacterReferenceSpecification:
        """Resolve character guidance from the Knowledge Layer.

        Returns a `CharacterReferenceSpecification` that provides structured
        guidance to the CharacterSystemEngine. The engine uses this guidance
        (or ignores it, with reason) to construct a `CharacterDefinition`.

        Parameters:
            requirement: The CharacterRequirement from the StoryboardPackage.

        Returns:
            A frozen `CharacterReferenceSpecification` with resolved rules,
            provenance, and conflict information.
        """
        character_id = requirement.character_id

        # Collect all relevant results from the resolver
        all_results: list[KnowledgeResult] = []

        # Resolve CHARACTER domain entries
        char_results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.CHARACTER)
        )
        all_results.extend(char_results)

        # Resolve VISUAL_STYLE entries that mention character
        style_results = self._resolver.resolve(
            KnowledgeQuery(
                domain=KnowledgeDomain.VISUAL_STYLE,
                tags=frozenset({"character"}),
            )
        )
        all_results.extend(style_results)

        # Resolve CONTINUITY entries for character
        cont_results = self._resolver.resolve(
            KnowledgeQuery(
                domain=KnowledgeDomain.CONTINUITY,
                tags=frozenset({"character"}),
            )
        )
        all_results.extend(cont_results)

        # Resolve negative constraints
        neg_results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.NEGATIVE_CONSTRAINT)
        )
        all_results.extend(neg_results)

        # Translate to character-specific rules
        resolved_rules = self._translate_to_rules(all_results)

        # Build palette guidance
        palette_guidance = self._build_palette_guidance(all_results)

        # Build wardrobe guidance
        wardrobe_guidance = self._build_wardrobe_guidance(all_results)

        # Build negative constraints
        negative_constraints = self._build_negative_constraints(neg_results)

        # Collect knowledge IDs used
        knowledge_ids = frozenset(r.knowledge_id for r in all_results)

        # Collect provenance
        provenance_list = [r.provenance for r in all_results if r.provenance]

        return CharacterReferenceSpecification(
            character_id=character_id,
            resolved_rules=resolved_rules,
            palette_guidance=palette_guidance,
            wardrobe_guidance=wardrobe_guidance,
            negative_constraints=negative_constraints,
            knowledge_ids_used=knowledge_ids,
            knowledge_version=(
                self._resolver.registry_version
                if self.is_active()
                else "no-knowledge"
            ),
            is_knowledge_active=self.is_active(),
            fallback_policy_used=self._context.fallback_policy.value,
        )

    # ------------------------------------------------------------------
    # Translation helpers
    # ------------------------------------------------------------------

    def _translate_to_rules(
        self, results: list[KnowledgeResult]
    ) -> list[ResolvedCharacterRule]:
        """Translate KnowledgeResults to ResolvedCharacterRules."""
        rules: list[ResolvedCharacterRule] = []
        for result in results:
            category = self._tag_to_category(result.tags)
            is_identity = category in _IDENTITY_BEARING_CATEGORIES

            for rule_text in result.rules:
                provenance = result.provenance
                rules.append(
                    ResolvedCharacterRule(
                        rule_id=result.knowledge_id,
                        domain=result.domain.value,
                        category=category,
                        rule=rule_text,
                        governed_properties=frozenset(self._category_to_properties(category)),
                        is_identity_bearing=is_identity,
                        provenance=provenance,
                        knowledge_version=result.version,
                        confidence=provenance.confidence,
                    )
                )
        return rules

    @staticmethod
    def _tag_to_category(tags: frozenset[str]) -> str:
        """Map a set of tags to a character property category."""
        for tag in tags:
            if tag in _TAG_TO_CATEGORY:
                return _TAG_TO_CATEGORY[tag]
        return "general"

    @staticmethod
    def _category_to_properties(category: str) -> list[str]:
        """Map a category to the properties it governs."""
        mapping = {
            "identity_lock": [
                IdentityBearingProperty.HEAD_SHAPE,
                IdentityBearingProperty.FACE_STRUCTURE,
            ],
            "consistency": [
                IdentityBearingProperty.PROPORTIONS,
                IdentityBearingProperty.SILHOUETTE,
            ],
            "signature_prop": ["signature_prop"],
            "style_profile": [
                IdentityBearingProperty.STYLE_PROFILE,
                IdentityBearingProperty.DEFAULT_OUTLINE,
            ],
            "wardrobe": ["wardrobe"],
            "family_grouping": ["family_grouping"],
            "design_rules": [
                IdentityBearingProperty.HEAD_SHAPE,
                IdentityBearingProperty.FACE_STRUCTURE,
                IdentityBearingProperty.PROPORTIONS,
            ],
        }
        return mapping.get(category, ["general"])

    def _build_palette_guidance(
        self, results: list[KnowledgeResult]
    ) -> Optional[PaletteGuidance]:
        """Build palette guidance from relevant results."""
        color_results = [
            r for r in results
            if "color" in r.tags or "palette" in r.tags
        ]
        if not color_results:
            return None

        primary_hints: list[str] = []
        secondary_hints: list[str] = []
        outline_hint: Optional[str] = None
        skin_tone_hint: Optional[str] = None
        rule_texts: list[str] = []

        for r in color_results:
            rule_texts.extend(list(r.rules))
            for rule in r.rules:
                lower = rule.lower()
                if "primary" in lower:
                    primary_hints.append(rule)
                elif "secondary" in lower:
                    secondary_hints.append(rule)
                elif "outline" in lower:
                    outline_hint = rule
                elif "skin" in lower:
                    skin_tone_hint = rule

        if not rule_texts:
            return None

        # Use the first result's provenance
        provenance = color_results[0].provenance
        return PaletteGuidance(
            primary_hints=primary_hints or ["use consistent primary color across references"],
            secondary_hints=secondary_hints,
            outline_hint=outline_hint,
            skin_tone_hint=skin_tone_hint,
            rules=frozenset(rule_texts),
            provenance=provenance,
            knowledge_version=color_results[0].version,
        )

    def _build_wardrobe_guidance(
        self, results: list[KnowledgeResult]
    ) -> Optional[WardrobeGuidance]:
        """Build wardrobe guidance from relevant results."""
        wardrobe_results = [
            r for r in results
            if any(t in r.tags for t in _WARDROBE_TAGS)
        ]
        if not wardrobe_results:
            return None

        rules: list[str] = []
        permitted: list[str] = []
        forbidden: list[str] = []
        is_locked = True

        for r in wardrobe_results:
            rules.extend(list(r.rules))
            for rule in r.rules:
                lower = rule.lower()
                if "locked" in lower or "stable" in lower or "preserve" in lower:
                    is_locked = True
                    permitted.append(rule)
                elif "may vary" in lower or "scene" in lower:
                    is_locked = False
                    permitted.append(rule)
                if "forbid" in lower or "never" in lower:
                    forbidden.append(rule)

        provenance = wardrobe_results[0].provenance
        return WardrobeGuidance(
            is_continuity_locked=is_locked,
            permitted_variations=frozenset(permitted),
            forbidden_variations=frozenset(forbidden),
            rules=frozenset(rules),
            provenance=provenance,
            knowledge_version=wardrobe_results[0].version,
        )

    def _build_negative_constraints(
        self, results: list[KnowledgeResult]
    ) -> list[NegativeConstraint]:
        """Build negative constraints from negative constraint domain results."""
        constraints: list[NegativeConstraint] = []
        for r in results:
            for rule in r.rules:
                # Extract "do not alter X" / "forbid X" patterns
                if any(
                    kw in rule.lower()
                    for kw in [
                        "do not",
                        "never",
                        "forbid",
                        "must not",
                        "not allow",
                    ]
                ):
                    # Try to extract the property being constrained
                    constrained_properties = self._extract_constrained_properties(rule)
                    for prop in constrained_properties:
                        constraints.append(
                            NegativeConstraint(
                                forbids_property=prop,
                                rule=rule,
                                is_identity_bearing=True,
                                provenance=r.provenance,
                                knowledge_version=r.version,
                            )
                        )
        return constraints

    @staticmethod
    def _extract_constrained_properties(rule_text: str) -> list[str]:
        """Extract the property names being constrained by a negative rule.

        Strategy: look for characteristic property keywords in the rule text.
        """
        text = rule_text.lower()
        properties: list[str] = []

        # Identity-bearing property keywords
        keyword_map = {
            "head shape": IdentityBearingProperty.HEAD_SHAPE,
            "head_shape": IdentityBearingProperty.HEAD_SHAPE,
            "face": IdentityBearingProperty.FACE_STRUCTURE,
            "face structure": IdentityBearingProperty.FACE_STRUCTURE,
            "silhouette": IdentityBearingProperty.SILHOUETTE,
            "proportion": IdentityBearingProperty.PROPORTIONS,
            "palette": IdentityBearingProperty.PALETTE,
            "color": IdentityBearingProperty.PALETTE,
            "skin tone": IdentityBearingProperty.SKIN_TONE,
            "skin_tone": IdentityBearingProperty.SKIN_TONE,
            "style": IdentityBearingProperty.STYLE_PROFILE,
            "outfit": "wardrobe",
            "wardrobe": "wardrobe",
            "clothing": "wardrobe",
            "prop": "signature_prop",
        }

        for keyword, prop in keyword_map.items():
            if keyword in text and prop not in properties:
                properties.append(prop)

        # If no specific property found, use a generic one
        if not properties:
            properties.append(IdentityBearingProperty.STYLE_PROFILE)

        return properties


# ============================================================================
# Internal helpers
# ============================================================================

def _build_context_from_registry(
    registry: KnowledgeRegistry,
    name: str = "character-legacy-registry",
) -> KnowledgeContext:
    """Build a KnowledgeContext from a legacy registry (mirrors storyboard_adapter)."""
    sources = [s for s in default_sources() if s.source_id in registry.sources_loaded]
    return KnowledgeContext.from_registry(
        registry=registry,
        sources=sources,
        name=name,
    )


__all__ = [
    "KnowledgeCharacterAdapter",
]
