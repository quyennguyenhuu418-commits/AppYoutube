"""
KnowledgeContext — lifecycle wrapper for Knowledge Consumption.

L-U3 — Knowledge Consumption Architecture.

The `KnowledgeContext` is a small, optional convenience that bundles:

    - the KnowledgeResolver (canonical consumption entry point)
    - a fallback policy (what to do when nothing matches)
    - an optional name (for logging)

It is NOT a service locator. It does NOT expose `get_current_context()`.
It is NOT a global mutable singleton.

Purpose
-------
A production subsystem (StoryboardEngine, CharacterEngine, ...) accepts
an OPTIONAL `knowledge_context` in its constructor. The context bundles
the resolver + fallback policy. If the subsystem receives `None`, it
behaves exactly as before L-U2 / L-U3 (backward compatibility).

This is the **only** public surface of Knowledge Consumption visible to
production subsystems. Subsystems never see `KnowledgeRegistry` directly.

Forward compatibility
---------------------
If a future prompt needs:

    - more than one resolver in a single request
    - request-scoped metadata
    - logging hooks

those concerns belong on `KnowledgeContext`, not on `KnowledgeResolver`.
This keeps the resolver itself small and stable.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .resolver import KnowledgeResolver
from .schemas import KnowledgeSource


# ============================================================================
# Fallback policy
# ============================================================================

class FallbackPolicy(str, Enum):
    """What should consumers do when the resolver returns no results?

    The policy is chosen per-subsystem. Different subsystems may have
    different policies; the choice lives in the consumer, not the
    resolver.

    Values
    ------
    ENGINE_DEFAULT : consumer falls back to its pre-L-U3 hard-coded
                     default. This is the canonical L-U2 behaviour.

    WARN            : consumer logs a warning and falls back to its
                     pre-L-U3 hard-coded default.

    REJECT          : consumer treats "no knowledge" as a hard error
                     and refuses to proceed. Use this only when the
                     subsystem genuinely requires knowledge (rare).

    SILENT          : consumer silently uses its default. Use only when
                     the consumer can recover cleanly without the
                     user noticing.
    """

    ENGINE_DEFAULT = "engine_default"
    WARN = "warn"
    REJECT = "reject"
    SILENT = "silent"


# ============================================================================
# Context
# ============================================================================

class KnowledgeContext(BaseModel):
    """Bundles a resolver + fallback policy + source provenance into one object.

    A `KnowledgeContext` is immutable. To create a new context, build
    a new one. There is no `set_resolver()` method.

    The `name` field is optional and only used for observability.
    The `sources` mapping is the in-memory source provenance table used
    to build `KnowledgeProvenance` records. It maps
    `KnowledgeSource.source_id -> KnowledgeSource`.
    """

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    resolver: KnowledgeResolver = Field(
        ...,
        description="The canonical resolver. Never None.",
    )
    fallback_policy: FallbackPolicy = Field(
        default=FallbackPolicy.ENGINE_DEFAULT,
        description="How to behave when no knowledge matches.",
    )
    name: str = Field(
        default="default",
        min_length=1,
        max_length=64,
        description="Free-form identifier for observability/logging.",
    )
    sources: dict[str, KnowledgeSource] = Field(
        default_factory=dict,
        description="Optional source provenance map (id -> KnowledgeSource).",
    )

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def disabled(cls, name: str = "no-knowledge") -> "KnowledgeContext":
        """Construct a context that points at an empty resolver.

        This is the L-U2 backward-compatible path: `resolver.is_active()`
        returns False and all consumers fall back to their engine
        defaults.
        """
        return cls(
            resolver=KnowledgeResolver(registry=None),
            fallback_policy=FallbackPolicy.ENGINE_DEFAULT,
            name=name,
        )

    @classmethod
    def from_registry(
        cls,
        registry,
        sources: Optional[list] = None,
        name: str = "default",
        fallback_policy: FallbackPolicy = FallbackPolicy.ENGINE_DEFAULT,
    ) -> "KnowledgeContext":
        """Construct a context from a registry (may be None).

        Args:
            registry: a KnowledgeRegistry (or None for no-knowledge).
            sources: optional list of KnowledgeSource records. When
                omitted, the default L-U1 sources are used if the
                registry is the default one.
            name: observability name.
            fallback_policy: policy when no knowledge matches.
        """
        sources_map: dict[str, KnowledgeSource] = {}
        if sources is not None:
            for s in sources:
                sources_map[s.source_id] = s
        elif registry is not None and registry.sources_loaded:
            # Try to use the L-U1 default sources. They match the
            # recorded `sources_loaded` IDs.
            from .seeds import default_sources
            for s in default_sources():
                if s.source_id in registry.sources_loaded:
                    sources_map[s.source_id] = s
        return cls(
            resolver=KnowledgeResolver(registry=registry),
            fallback_policy=fallback_policy,
            name=name,
            sources=sources_map,
        )


__all__ = [
    "FallbackPolicy",
    "KnowledgeContext",
]
