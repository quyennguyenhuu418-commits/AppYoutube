"""
KnowledgePromptAdapter — thin adapter bridging Knowledge Layer to PromptCompiler.

L-U5 — Prompt Compiler V2.

Purpose
-------
The `KnowledgePromptAdapter` is the ONLY integration point between the
Knowledge Layer and the PromptCompiler. It translates `KnowledgeResult`
from the canonical `KnowledgeResolver` into prompt-specific guidance.

Architecture
------------
    KnowledgeContext (L-U3)
            ↓
    KnowledgeResolver (L-U3)
            ↓
    KnowledgePromptAdapter (L-U5 — thin)
            ↓
    PromptCompiler (L-U5)

Design principles
----------------
1. THIN adapter — all resolution goes through `KnowledgeResolver`.
   No direct registry access.
2. PROVIDER-NEUTRAL — the adapter produces structured guidance,
   NOT provider-specific prompt syntax.
3. OPTIONAL — if no `KnowledgeContext` is provided, returns empty/None
   and the compiler falls back to engine defaults.

What this adapter does NOT do:
    - Generate actual prompts
    - Call image/video generation providers
    - Mutate the KnowledgeRegistry
    - Make decisions about prompt structure (that is the compiler's job)

What this adapter DOES:
    - Consult the Knowledge Layer for prompt-related rules
    - Translate results into prompt-specific guidance blocks
    - Preserve provenance
    - Handle missing knowledge gracefully
"""

from __future__ import annotations

from typing import Any, FrozenSet, Optional

from app.knowledge import (
    FallbackPolicy,
    KnowledgeContext,
    KnowledgeDomain,
    KnowledgeQuery,
    KnowledgeRegistry,
    KnowledgeResolver,
    KnowledgeResult,
)
from app.knowledge.result import KnowledgeProvenance


# ============================================================================
# Resolved prompt knowledge — structured output from the adapter
# ============================================================================


class ResolvedStyleKnowledge:
    """Style knowledge resolved from VISUAL_STYLE domain."""

    __slots__ = (
        "profile",
        "palette_hint",
        "outline_hint",
        "line_quality",
        "rendering_notes",
        "rules",
        "knowledge_ids",
        "provenance_list",
        "is_active",
    )

    def __init__(
        self,
        profile: Optional[str] = None,
        palette_hint: Optional[str] = None,
        outline_hint: Optional[str] = None,
        line_quality: Optional[str] = None,
        rendering_notes: Optional[list[str]] = None,
        rules: Optional[list[str]] = None,
        knowledge_ids: Optional[FrozenSet[str]] = None,
        provenance_list: Optional[list[KnowledgeProvenance]] = None,
        is_active: bool = False,
    ) -> None:
        self.profile = profile
        self.palette_hint = palette_hint
        self.outline_hint = outline_hint
        self.line_quality = line_quality
        self.rendering_notes = rendering_notes or []
        self.rules = rules or []
        self.knowledge_ids = knowledge_ids or frozenset()
        self.provenance_list = provenance_list or []
        self.is_active = is_active

    @property
    def primary_provenance(self) -> Optional[KnowledgeProvenance]:
        return self.provenance_list[0] if self.provenance_list else None


class ResolvedCameraKnowledge:
    """Camera knowledge resolved from CAMERA domain."""

    __slots__ = (
        "shot_type",
        "movement",
        "rules",
        "knowledge_ids",
        "provenance_list",
        "is_active",
    )

    def __init__(
        self,
        shot_type: Optional[str] = None,
        movement: Optional[str] = None,
        rules: Optional[list[str]] = None,
        knowledge_ids: Optional[FrozenSet[str]] = None,
        provenance_list: Optional[list[KnowledgeProvenance]] = None,
        is_active: bool = False,
    ) -> None:
        self.shot_type = shot_type
        self.movement = movement
        self.rules = rules or []
        self.knowledge_ids = knowledge_ids or frozenset()
        self.provenance_list = provenance_list or []
        self.is_active = is_active

    @property
    def primary_provenance(self) -> Optional[KnowledgeProvenance]:
        return self.provenance_list[0] if self.provenance_list else None


class ResolvedMotionKnowledge:
    """Motion knowledge resolved from MOTION / CAMERA_MOVEMENT domain."""

    __slots__ = (
        "pattern",
        "rules",
        "knowledge_ids",
        "provenance_list",
        "is_active",
    )

    def __init__(
        self,
        pattern: Optional[str] = None,
        rules: Optional[list[str]] = None,
        knowledge_ids: Optional[FrozenSet[str]] = None,
        provenance_list: Optional[list[KnowledgeProvenance]] = None,
        is_active: bool = False,
    ) -> None:
        self.pattern = pattern
        self.rules = rules or []
        self.knowledge_ids = knowledge_ids or frozenset()
        self.provenance_list = provenance_list or []
        self.is_active = is_active

    @property
    def primary_provenance(self) -> Optional[KnowledgeProvenance]:
        return self.provenance_list[0] if self.provenance_list else None


class ResolvedNegativeConstraints:
    """Negative constraints resolved from NEGATIVE_CONSTRAINT domain."""

    __slots__ = (
        "constraints",
        "knowledge_ids",
        "provenance_list",
        "is_active",
    )

    def __init__(
        self,
        constraints: Optional[list[dict[str, Any]]] = None,
        knowledge_ids: Optional[FrozenSet[str]] = None,
        provenance_list: Optional[list[KnowledgeProvenance]] = None,
        is_active: bool = False,
    ) -> None:
        self.constraints = constraints or []
        self.knowledge_ids = knowledge_ids or frozenset()
        self.provenance_list = provenance_list or []
        self.is_active = is_active

    @property
    def primary_provenance(self) -> Optional[KnowledgeProvenance]:
        return self.provenance_list[0] if self.provenance_list else None


class ResolvedPromptKnowledge:
    """Complete prompt knowledge resolved from the Knowledge Layer.

    Bundles all domain-specific resolved knowledge into one object.
    """

    __slots__ = (
        "style",
        "camera",
        "motion",
        "negative_constraints",
        "is_active",
        "knowledge_ids",
        "registry_version",
    )

    def __init__(
        self,
        style: Optional[ResolvedStyleKnowledge] = None,
        camera: Optional[ResolvedCameraKnowledge] = None,
        motion: Optional[ResolvedMotionKnowledge] = None,
        negative_constraints: Optional[ResolvedNegativeConstraints] = None,
        is_active: bool = False,
        knowledge_ids: Optional[FrozenSet[str]] = None,
        registry_version: str = "no-knowledge",
    ) -> None:
        self.style = style or ResolvedStyleKnowledge()
        self.camera = camera or ResolvedCameraKnowledge()
        self.motion = motion or ResolvedMotionKnowledge()
        self.negative_constraints = (
            negative_constraints or ResolvedNegativeConstraints()
        )
        self.is_active = is_active
        self.knowledge_ids = knowledge_ids or frozenset()
        self.registry_version = registry_version

    def all_provenance(self) -> list[KnowledgeProvenance]:
        """All provenance records from all resolved knowledge."""
        results: list[KnowledgeProvenance] = []
        for slot_name in self.__slots__:
            if slot_name in (
                "is_active",
                "knowledge_ids",
                "registry_version",
            ):
                continue
            val = getattr(self, slot_name, None)
            if val is not None and hasattr(val, "provenance_list"):
                results.extend(val.provenance_list)  # type: ignore[attr-defined]
        return results


# ============================================================================
# The adapter
# ============================================================================


class KnowledgePromptAdapter:
    """Thin adapter: Knowledge Layer → PromptCompiler.

    Construction:
        # Canonical L-U3 path (preferred):
        ctx = KnowledgeContext.from_registry(registry)
        adapter = KnowledgePromptAdapter(context=ctx)

        # No-knowledge path (backward compatible):
        adapter = KnowledgePromptAdapter()  # or None

    Usage:
        knowledge = adapter.resolve_for_prompt(prompt_kind=PromptKind.IMAGE)
        # knowledge is a ResolvedPromptKnowledge
    """

    def __init__(
        self,
        registry: Optional[KnowledgeRegistry] = None,
        *,
        context: Optional[KnowledgeContext] = None,
    ) -> None:
        # Accept KnowledgeContext (canonical), KnowledgeRegistry (legacy),
        # or None (no-knowledge mode)
        if context is not None:
            self._context = context
        elif registry is not None:
            self._context = _build_context_from_registry(registry)
        else:
            self._context = KnowledgeContext.disabled(name="prompt-no-knowledge")

        self._resolver: KnowledgeResolver = self._context.resolver

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """True iff the Knowledge Layer is available and non-empty."""
        return self._resolver.is_active()

    @property
    def context(self) -> KnowledgeContext:
        return self._context

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def resolve_for_prompt(
        self,
        prompt_kind: str,
    ) -> ResolvedPromptKnowledge:
        """Resolve prompt-related knowledge from the Knowledge Layer.

        Parameters:
            prompt_kind: 'image' or 'video'

        Returns:
            A ResolvedPromptKnowledge bundle with style, camera, motion,
            and negative constraints.
        """
        # Collect knowledge IDs from all resolutions
        all_knowledge_ids: list[str] = []
        all_provenance: list[KnowledgeProvenance] = []

        # 1. Resolve VISUAL_STYLE
        style_results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.VISUAL_STYLE)
        )
        all_knowledge_ids.extend(r.knowledge_id for r in style_results)
        all_provenance.extend(r.provenance for r in style_results if r.provenance)

        # 2. Resolve IMAGE_PROMPT or VIDEO_PROMPT domain
        prompt_domain = (
            KnowledgeDomain.IMAGE_PROMPT
            if prompt_kind == "image"
            else KnowledgeDomain.VIDEO_PROMPT
        )
        prompt_results = self._resolver.resolve(
            KnowledgeQuery(domain=prompt_domain)
        )
        all_knowledge_ids.extend(r.knowledge_id for r in prompt_results)
        all_provenance.extend(
            r.provenance for r in prompt_results if r.provenance
        )

        # 3. Resolve CAMERA
        camera_results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.CAMERA)
        )
        all_knowledge_ids.extend(r.knowledge_id for r in camera_results)
        all_provenance.extend(r.provenance for r in camera_results if r.provenance)

        # 4. Resolve MOTION (VIDEO only)
        motion_results: list[KnowledgeResult] = []
        if prompt_kind == "video":
            motion_results = self._resolver.resolve(
                KnowledgeQuery(domain=KnowledgeDomain.MOTION)
            )
            all_knowledge_ids.extend(r.knowledge_id for r in motion_results)
            all_provenance.extend(
                r.provenance for r in motion_results if r.provenance
            )

        # 5. Resolve NEGATIVE_CONSTRAINT
        neg_results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.NEGATIVE_CONSTRAINT)
        )
        all_knowledge_ids.extend(r.knowledge_id for r in neg_results)
        all_provenance.extend(r.provenance for r in neg_results if r.provenance)

        # Build resolved knowledge
        return ResolvedPromptKnowledge(
            style=self._build_style_knowledge(style_results),
            camera=self._build_camera_knowledge(camera_results),
            motion=self._build_motion_knowledge(motion_results),
            negative_constraints=self._build_negative_constraints(neg_results),
            is_active=self.is_active(),
            knowledge_ids=frozenset(all_knowledge_ids),
            registry_version=(
                self._resolver.registry_version
                if self.is_active()
                else "no-knowledge"
            ),
        )

    # ------------------------------------------------------------------
    # Translation helpers
    # ------------------------------------------------------------------

    def _build_style_knowledge(
        self, results: list[KnowledgeResult]
    ) -> ResolvedStyleKnowledge:
        """Translate VISUAL_STYLE results to structured style knowledge."""
        if not results:
            return ResolvedStyleKnowledge()

        profile: Optional[str] = None
        palette_hint: Optional[str] = None
        outline_hint: Optional[str] = None
        line_quality: Optional[str] = None
        rendering_notes: list[str] = []
        rules: list[str] = []
        provenance_list: list[KnowledgeProvenance] = []

        for r in results:
            if r.provenance:
                provenance_list.append(r.provenance)

            for rule in r.rules:
                rules.append(rule)
                lower = rule.lower()
                if "hand_drawn" in lower or "doodle" in lower:
                    profile = "hand_drawn_doodle"
                    rendering_notes.append(rule)
                elif "semi_realistic" in lower or "2d" in lower:
                    profile = "semi_realistic_2d"
                    rendering_notes.append(rule)
                elif "flat_vector" in lower or "flat" in lower:
                    profile = "flat_vector"
                    rendering_notes.append(rule)
                elif "earth tone" in lower or "muted" in lower:
                    palette_hint = rule
                elif "outline" in lower or "marker" in lower:
                    outline_hint = rule
                elif "line" in lower or "sketch" in lower:
                    line_quality = rule

        return ResolvedStyleKnowledge(
            profile=profile,
            palette_hint=palette_hint,
            outline_hint=outline_hint,
            line_quality=line_quality,
            rendering_notes=rendering_notes,
            rules=rules,
            knowledge_ids=frozenset(r.knowledge_id for r in results),
            provenance_list=provenance_list,
            is_active=True,
        )

    def _build_camera_knowledge(
        self, results: list[KnowledgeResult]
    ) -> ResolvedCameraKnowledge:
        """Translate CAMERA domain results to structured camera knowledge."""
        if not results:
            return ResolvedCameraKnowledge()

        shot_type: Optional[str] = None
        movement: Optional[str] = None
        rules: list[str] = []
        provenance_list: list[KnowledgeProvenance] = []

        for r in results:
            if r.provenance:
                provenance_list.append(r.provenance)
            for rule in r.rules:
                rules.append(rule)
                lower = rule.lower()
                # Shot types
                if "extreme wide" in lower or "ews" in lower:
                    shot_type = "extreme_wide"
                elif "wide" in lower and "medium" not in lower:
                    shot_type = "wide"
                elif "medium" in lower and "close" not in lower:
                    shot_type = "medium"
                elif "close" in lower:
                    shot_type = "close"
                elif "extreme close" in lower or "ecu" in lower:
                    shot_type = "extreme_close"
                elif "pov" in lower or "point of view" in lower:
                    shot_type = "pov"
                elif "bird" in lower or "top" in lower:
                    shot_type = "birds_eye"
                elif "worm" in lower or "below" in lower:
                    shot_type = "worms_eye"
                elif "dutch" in lower or "tilt" in lower:
                    shot_type = "dutch"
                # Movements
                if "push" in lower or "dolly forward" in lower:
                    movement = "push_in"
                elif "pull" in lower or "dolly back" in lower:
                    movement = "pull_out"
                elif "pan" in lower:
                    movement = "pan"
                elif "tilt" in lower:
                    movement = "tilt"
                elif "zoom" in lower:
                    movement = "zoom"
                elif "tracking" in lower or "follow" in lower:
                    movement = "tracking"
                elif "hold" in lower or "static" in lower:
                    movement = "hold"

        return ResolvedCameraKnowledge(
            shot_type=shot_type,
            movement=movement,
            rules=rules,
            knowledge_ids=frozenset(r.knowledge_id for r in results),
            provenance_list=provenance_list,
            is_active=True,
        )

    def _build_motion_knowledge(
        self, results: list[KnowledgeResult]
    ) -> ResolvedMotionKnowledge:
        """Translate MOTION domain results to structured motion knowledge."""
        if not results:
            return ResolvedMotionKnowledge()

        pattern: Optional[str] = None
        rules: list[str] = []
        provenance_list: list[KnowledgeProvenance] = []

        for r in results:
            if r.provenance:
                provenance_list.append(r.provenance)
            for rule in r.rules:
                rules.append(rule)
                lower = rule.lower()
                if "frame" in lower and "by" in lower:
                    pattern = "frame_by_frame"
                elif "loop" in lower:
                    pattern = "loop"
                elif "rig" in lower or "interpolation" in lower:
                    pattern = "rig_pose_interpolation"
                elif "kinetic" in lower or "text" in lower:
                    pattern = "kinetic_text"
                elif "shake" in lower or "nervous" in lower:
                    pattern = "shake_nervous"

        return ResolvedMotionKnowledge(
            pattern=pattern,
            rules=rules,
            knowledge_ids=frozenset(r.knowledge_id for r in results),
            provenance_list=provenance_list,
            is_active=True,
        )

    def _build_negative_constraints(
        self, results: list[KnowledgeResult]
    ) -> ResolvedNegativeConstraints:
        """Translate NEGATIVE_CONSTRAINT domain to structured constraints."""
        if not results:
            return ResolvedNegativeConstraints()

        constraints: list[dict[str, Any]] = []
        provenance_list: list[KnowledgeProvenance] = []

        for r in results:
            if r.provenance:
                provenance_list.append(r.provenance)
            for rule in r.rules:
                # Only include rules that look like negative constraints
                lower = rule.lower()
                if any(
                    kw in lower
                    for kw in [
                        "do not",
                        "never",
                        "forbid",
                        "must not",
                        "not allow",
                        "avoid",
                        "no ",
                        "do NOT",
                    ]
                ):
                    # Extract the property being constrained
                    constrained = self._extract_constrained_property(rule)
                    constraints.append(
                        {
                            "constraint_id": r.knowledge_id,
                            "property_name": constrained,
                            "constraint_text": rule,
                            "is_identity_bearing": constrained
                            in {
                                "head_shape",
                                "face_structure",
                                "proportions",
                                "palette",
                                "style",
                                "wardrobe",
                                "signature_prop",
                            },
                        }
                    )

        return ResolvedNegativeConstraints(
            constraints=constraints,
            knowledge_ids=frozenset(r.knowledge_id for r in results),
            provenance_list=provenance_list,
            is_active=True,
        )

    @staticmethod
    def _extract_constrained_property(rule_text: str) -> str:
        """Extract the property being constrained by a negative rule."""
        text = rule_text.lower()

        # Priority order for identity-bearing properties
        property_keywords = [
            ("head shape", "head_shape"),
            ("face", "face_structure"),
            ("proportion", "proportions"),
            ("palette", "palette"),
            ("color", "palette"),
            ("outline", "outline"),
            ("style", "style"),
            ("wardrobe", "wardrobe"),
            ("clothing", "wardrobe"),
            ("outfit", "wardrobe"),
            ("prop", "signature_prop"),
            ("silhouette", "silhouette"),
        ]

        for keyword, prop in property_keywords:
            if keyword in text:
                return prop

        return "general"  # default


# ============================================================================
# Internal helpers
# ============================================================================


def _build_context_from_registry(
    registry: KnowledgeRegistry,
    name: str = "prompt-legacy-registry",
) -> KnowledgeContext:
    """Build a KnowledgeContext from a legacy registry."""
    from app.knowledge.seeds import default_sources

    sources = [
        s for s in default_sources() if s.source_id in registry.sources_loaded
    ]
    return KnowledgeContext.from_registry(
        registry=registry,
        sources=sources,
        name=name,
    )


__all__ = [
    "KnowledgePromptAdapter",
    "ResolvedPromptKnowledge",
    "ResolvedStyleKnowledge",
    "ResolvedCameraKnowledge",
    "ResolvedMotionKnowledge",
    "ResolvedNegativeConstraints",
]
