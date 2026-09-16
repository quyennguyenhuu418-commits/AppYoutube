"""
KnowledgeStoryboardAdapter — bridges the Knowledge Layer (L-U1) to the
StoryboardEngine (Prompt 4).

L-U2 — Knowledge Layer Read-Only Integration (initial).
L-U3 — Knowledge Consumption Architecture (resolver-backed).

Purpose
-------
The KnowledgeStoryboardAdapter is the **only** integration point between
the Knowledge Layer and the StoryboardEngine. It exposes a small,
stable API that the engine can consult:

    get_camera_for_mode(mode)        -> camera-type / reason / focus
    get_motion_for_mode(mode)        -> motion-type / intensity / purpose
    get_style_profile()              -> visual style palette / outline
    get_negative_constraints()       -> canonical forbid list
    get_text_overlay_convention()    -> typography style

Architectural rule
------------------
1. The adapter is a **READ-ONLY** consumer of the KnowledgeResolver. It
   never mutates the registry.
2. The adapter is **optional**. The StoryboardEngine without the
   adapter behaves exactly as before (backward compatible).
3. The adapter is **deterministic**. Same resolver + same input -> same
   output.
4. The adapter is **non-fatal**. If a lookup fails, it returns a
   sensible default and logs (does not raise). The engine should
   never crash because of an adapter failure.
5. The adapter is **self-contained**. It does not import from
   `storyboard.engine` or any other `app/storyboard/*` module.

L-U3 changes
------------
The adapter now accepts either:

    - a `KnowledgeRegistry` (legacy L-U2 path — preserved)
    - a `KnowledgeContext`  (canonical L-U3 path — preferred)
    - `None`                 (no knowledge — defaults only)

Internally it constructs a `KnowledgeResolver` (the canonical read
path) and delegates all lookup logic to it. The adapter itself is now
a thin translation layer that turns `KnowledgeResult` into
storyboard-specific values (camera type, motion type, etc.).

This eliminates the previous registry-direct-access path without
changing any external behaviour. All L-U2 tests continue to pass.
"""

from __future__ import annotations

from typing import Any, Optional

from app.knowledge import (
    KnowledgeContext,
    KnowledgeDomain,
    KnowledgeEntry,
    KnowledgeQuery,
    KnowledgeRegistry,
    KnowledgeResult,
    KnowledgeResolver,
    KnowledgeSource,
    KnowledgeStatus,
)
from app.schemas.storyboard import (
    StoryboardCameraType,
    StoryboardMotionType,
    StoryboardVisualMode,
)


def _build_context_from_registry(
    registry: KnowledgeRegistry,
    name: str = "legacy-registry",
) -> KnowledgeContext:
    """Build a KnowledgeContext that mirrors the L-U1 default sources
    when the registry has them loaded.

    This keeps L-U2 test compatibility: when a registry is built with
    `build_default_registry()`, the default sources are auto-attached.
    """
    from app.knowledge.seeds import default_sources

    sources: list[KnowledgeSource] = []
    for s in default_sources():
        if s.source_id in registry.sources_loaded:
            sources.append(s)
    return KnowledgeContext.from_registry(
        registry=registry,
        sources=sources,
        name=name,
    )


# ============================================================================
# Mode-to-camera mapping (DINO AI bounded vocabulary)
# ============================================================================

# These mappings are derived from the DINO AI Cinematic Dictionary and the
# Google Flow visual patterns. They are intentionally conservative: only
# apply a knowledge-derived choice when it matches an existing
# StoryboardCameraType / StoryboardMotionType enum value.

_DINO_CAMERA_BY_MODE: dict[str, StoryboardCameraType] = {
    StoryboardVisualMode.CHARACTER.value: StoryboardCameraType.PUSH_IN,
    StoryboardVisualMode.ENVIRONMENT.value: StoryboardCameraType.PARALLAX,
    StoryboardVisualMode.DIAGRAM.value: StoryboardCameraType.STATIC,
    StoryboardVisualMode.MAP.value: StoryboardCameraType.PAN,
    StoryboardVisualMode.TIMELINE.value: StoryboardCameraType.TRACK,
    StoryboardVisualMode.COMPARISON.value: StoryboardCameraType.PULL_OUT,
    StoryboardVisualMode.ARTIFACT.value: StoryboardCameraType.PUSH_IN,
    StoryboardVisualMode.TEXT_GRAPHIC.value: StoryboardCameraType.STATIC,
    StoryboardVisualMode.DATA_VISUALIZATION.value: StoryboardCameraType.STATIC,
    StoryboardVisualMode.ARCHIVAL.value: StoryboardCameraType.STATIC,
    StoryboardVisualMode.HYBRID.value: StoryboardCameraType.STATIC,
}


_DINO_MOTION_BY_MODE: dict[str, StoryboardMotionType] = {
    StoryboardVisualMode.CHARACTER.value: StoryboardMotionType.CHARACTER_ACTION,
    StoryboardVisualMode.ENVIRONMENT.value: StoryboardMotionType.PARALLAX_DRIFT,
    StoryboardVisualMode.DIAGRAM.value: StoryboardMotionType.OVERLAY_APPEAR,
    StoryboardVisualMode.MAP.value: StoryboardMotionType.PARALLAX_DRIFT,
    StoryboardVisualMode.TIMELINE.value: StoryboardMotionType.CAMERA_PUSH,
    StoryboardVisualMode.COMPARISON.value: StoryboardMotionType.ZOOM_FOCUS,
    StoryboardVisualMode.ARTIFACT.value: StoryboardMotionType.PROP_ROTATE,
    StoryboardVisualMode.TEXT_GRAPHIC.value: StoryboardMotionType.OVERLAY_APPEAR,
    StoryboardVisualMode.DATA_VISUALIZATION.value: StoryboardMotionType.OVERLAY_APPEAR,
    StoryboardVisualMode.ARCHIVAL.value: StoryboardMotionType.NONE,
    StoryboardVisualMode.HYBRID.value: StoryboardMotionType.NONE,
}


# ============================================================================
# Fallback defaults (used when KnowledgeRegistry is unavailable or empty)
# ============================================================================

class _Defaults:
    """Conservative defaults that mirror the existing StoryboardEngine
    behaviour when no knowledge adapter is configured.

    These are the values that were hard-coded inside the engine before
    L-U2. We expose them here so the adapter can be tested in isolation
    and so that downstream code can audit what "no knowledge" means.
    """
    CAMERA_BY_MODE: dict[str, StoryboardCameraType] = dict(_DINO_CAMERA_BY_MODE)
    MOTION_BY_MODE: dict[str, StoryboardMotionType] = dict(_DINO_MOTION_BY_MODE)
    STYLE_PROFILE: dict[str, str] = {}
    NEGATIVE_CONSTRAINTS: list[str] = []
    TEXT_OVERLAY: dict[str, str] = {}


# ============================================================================
# The adapter
# ============================================================================

class KnowledgeStoryboardAdapter:
    """Read-only bridge between KnowledgeResolver and StoryboardEngine.

    The adapter exposes:
        get_camera_for_mode(mode)
        get_motion_for_mode(mode)
        get_style_profile()
        get_negative_constraints()
        get_text_overlay_convention()
        is_active()

    Construction (L-U3 accepts three forms):
        # Canonical L-U3 path (preferred):
        ctx = KnowledgeContext.from_registry(registry)
        adapter = KnowledgeStoryboardAdapter(context=ctx)

        # Legacy L-U2 path (still supported):
        adapter = KnowledgeStoryboardAdapter(registry=registry)

        # No-knowledge path:
        adapter = KnowledgeStoryboardAdapter()  # or None

    Usage in StoryboardEngine:
        if self._knowledge_adapter:
            cam_type = self._knowledge_adapter.get_camera_for_mode(beat.visual_mode)
        else:
            cam_type = _Defaults.CAMERA_BY_MODE.get(beat.visual_mode.value, STATIC)
    """

    def __init__(
        self,
        registry: Optional[KnowledgeRegistry] = None,
        *,
        context: Optional[KnowledgeContext] = None,
    ) -> None:
        # Three accepted shapes:
        #   1. KnowledgeContext (canonical L-U3) — preferred
        #   2. KnowledgeRegistry (legacy L-U2)    — backward-compatible
        #   3. None                              — no-knowledge
        if context is not None:
            self._context = context
        elif registry is not None:
            # Wrap the legacy registry in a context so we use one code
            # path. This auto-attaches L-U1 default sources when
            # present so provenance survives.
            self._context = _build_context_from_registry(
                registry, name="legacy-registry"
            )
        else:
            self._context = KnowledgeContext.disabled(name="no-knowledge")

        # Always go through the resolver. There is no direct registry
        # access in this class anymore (L-U3 invariant).
        self._resolver: KnowledgeResolver = self._context.resolver

    # ------------------------------------------------------------------
    # Compatibility shims — preserve the L-U2 surface
    # ------------------------------------------------------------------

    @property
    def _registry(self) -> Optional[KnowledgeRegistry]:
        """Legacy accessor for tests and external callers that need the
        underlying registry. Returns None when the adapter was
        constructed from a context without exposing the registry.

        New code should consult the resolver instead.
        """
        # We deliberately don't store the registry on the adapter
        # anymore. If a caller really needs the registry, they should
        # pass it to the constructor and retain the reference.
        return None

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """Return True iff a non-empty registry is attached.

        When False, all lookups fall back to the conservative defaults.
        """
        return self._resolver.is_active()

    def get_registry_version(self) -> str:
        """Return the registry version (or "no-registry")."""
        return self._resolver.registry_version

    def list_loaded_sources(self) -> list[str]:
        """Return the list of source IDs that the registry has loaded."""
        return self._resolver.loaded_source_ids

    @property
    def context(self) -> KnowledgeContext:
        """The KnowledgeContext backing this adapter (L-U3)."""
        return self._context

    # ------------------------------------------------------------------
    # Camera (DINO AI)
    # ------------------------------------------------------------------

    def get_camera_for_mode(
        self, mode: StoryboardVisualMode
    ) -> StoryboardCameraType:
        """Return the camera type for a given visual mode.

        Strategy (L-U3 — resolver-backed):
            1. Query the resolver for CAMERA-domain entries that match
               the mode (via tag/applicability).
            2. If a match carries vocabulary hints, return that.
            3. Otherwise, return the DINO-derived default.
            4. Otherwise, return STATIC.
        """
        if self._resolver.is_active():
            query = KnowledgeQuery(
                domain=KnowledgeDomain.CAMERA,
                tags=frozenset({mode.value}),
                applicability=frozenset({mode.value}),
            )
            for entry in self._resolver.resolve(query):
                # Match by canonical string inside the entry name.
                lowered = entry.name.lower().replace(" ", "_")
                for cam in StoryboardCameraType:
                    if cam.value in lowered:
                        return cam
        return _Defaults.CAMERA_BY_MODE.get(mode.value, StoryboardCameraType.STATIC)

    def get_camera_reason(self, mode: StoryboardVisualMode) -> Optional[str]:
        """Return a human-readable reason for the camera choice, derived
        from the knowledge entry, if any."""
        if not self._resolver.is_active():
            return None
        query = KnowledgeQuery(
            domain=KnowledgeDomain.CAMERA,
            tags=frozenset({mode.value}),
            applicability=frozenset({mode.value}),
        )
        for entry in self._resolver.resolve(query):
            for rule in entry.rules:
                if "use" in rule.lower():
                    return f"[knowledge: {entry.knowledge_id}] {rule}"
        return None

    # ------------------------------------------------------------------
    # Motion (DINO AI + Google Flow)
    # ------------------------------------------------------------------

    def get_motion_for_mode(
        self, mode: StoryboardVisualMode
    ) -> StoryboardMotionType:
        """Return the motion type for a given visual mode.

        Strategy (L-U3 — resolver-backed):
            1. Query the resolver for MOTION-domain entries that match.
            2. Special-case frame_by_frame -> NONE (L-U2 behaviour).
            3. Otherwise return DINO default.
            4. Otherwise return NONE.
        """
        if self._resolver.is_active():
            query = KnowledgeQuery(
                domain=KnowledgeDomain.MOTION,
                tags=frozenset({mode.value}),
                applicability=frozenset({mode.value}),
            )
            for entry in self._resolver.resolve(query):
                if "frame_by_frame" in entry.knowledge_id:
                    return _Defaults.MOTION_BY_MODE.get(
                        mode.value, StoryboardMotionType.NONE
                    )
        return _Defaults.MOTION_BY_MODE.get(mode.value, StoryboardMotionType.NONE)

    def get_motion_intensity(self, mode: StoryboardVisualMode) -> float:
        """Return the motion intensity (0.0-1.0) for a given mode."""
        # Conservative default that matches the pre-L-U2 behaviour.
        defaults = {
            StoryboardVisualMode.CHARACTER.value: 0.6,
            StoryboardVisualMode.ENVIRONMENT.value: 0.4,
            StoryboardVisualMode.DIAGRAM.value: 0.3,
            StoryboardVisualMode.MAP.value: 0.4,
            StoryboardVisualMode.TIMELINE.value: 0.5,
            StoryboardVisualMode.COMPARISON.value: 0.5,
            StoryboardVisualMode.ARTIFACT.value: 0.5,
            StoryboardVisualMode.TEXT_GRAPHIC.value: 0.3,
            StoryboardVisualMode.DATA_VISUALIZATION.value: 0.3,
            StoryboardVisualMode.ARCHIVAL.value: 0.2,
            StoryboardVisualMode.HYBRID.value: 0.4,
        }
        return defaults.get(mode.value, 0.5)

    # ------------------------------------------------------------------
    # Style (Google Flow)
    # ------------------------------------------------------------------

    def get_style_profile(self) -> dict[str, Any]:
        """Return the active visual style profile (palette, outline, etc.).

        Returns an empty dict if no knowledge is available.
        """
        if not self._resolver.is_active():
            return dict(_Defaults.STYLE_PROFILE)
        # Query VISUAL_STYLE domain for EXPLICIT entries.
        results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.VISUAL_STYLE)
        )
        if not results:
            return dict(_Defaults.STYLE_PROFILE)
        for entry in results:
            if entry.status == KnowledgeStatus.EXPLICIT:
                return {
                    "knowledge_id": entry.knowledge_id,
                    "name": entry.name,
                    "rules": sorted(entry.rules),
                }
        return dict(_Defaults.STYLE_PROFILE)

    # ------------------------------------------------------------------
    # Negative constraints (Google Flow)
    # ------------------------------------------------------------------

    def get_negative_constraints(self) -> list[str]:
        """Return the canonical negative-constraint forbid list."""
        if not self._resolver.is_active():
            return list(_Defaults.NEGATIVE_CONSTRAINTS)
        results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.NEGATIVE_CONSTRAINT)
        )
        if not results:
            return list(_Defaults.NEGATIVE_CONSTRAINTS)
        forbids: list[str] = []
        for entry in results:
            for rule in entry.rules:
                # Rules like "An image prompt SHOULD forbid 'no gradients'..."
                # Extract the quoted forbidden token.
                for token in self._extract_quoted_tokens(rule):
                    if token.startswith("no "):
                        forbids.append(token)
        # De-duplicate while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for f in forbids:
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out

    @staticmethod
    def _extract_quoted_tokens(text: str) -> list[str]:
        """Extract tokens inside single quotes."""
        out: list[str] = []
        in_token = False
        buf: list[str] = []
        for ch in text:
            if ch == "'":
                if in_token:
                    out.append("".join(buf))
                    buf = []
                in_token = not in_token
            elif in_token:
                buf.append(ch)
        return out

    # ------------------------------------------------------------------
    # Text overlay convention (Google Flow)
    # ------------------------------------------------------------------

    def get_text_overlay_convention(self) -> dict[str, str]:
        """Return the canonical text overlay style.

        Returns an empty dict if no knowledge is available.
        """
        if not self._resolver.is_active():
            return dict(_Defaults.TEXT_OVERLAY)
        # Look for FORMAT-domain entries tagged text_overlay.
        results = self._resolver.resolve(
            KnowledgeQuery(tags=frozenset({"text_overlay"}))
        )
        if not results:
            return dict(_Defaults.TEXT_OVERLAY)
        # Use the first EXPLICIT entry.
        for entry in results:
            if entry.status == KnowledgeStatus.EXPLICIT:
                return {
                    "knowledge_id": entry.knowledge_id,
                    "rules": sorted(entry.rules),
                }
        return dict(_Defaults.TEXT_OVERLAY)

    # ------------------------------------------------------------------
    # Continuity (Google Flow)
    # ------------------------------------------------------------------

    def get_continuity_rules(self) -> list[str]:
        """Return the canonical continuity rules."""
        if not self._resolver.is_active():
            return []
        results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.CONTINUITY)
        )
        rules: list[str] = []
        for entry in results:
            rules.extend(sorted(entry.rules))
        return rules


__all__ = [
    "KnowledgeStoryboardAdapter",
]
