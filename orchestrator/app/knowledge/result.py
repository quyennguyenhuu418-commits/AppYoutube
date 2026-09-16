"""
KnowledgeResult — canonical immutable result returned by the resolver.

L-U3 — Knowledge Consumption Architecture.

A `KnowledgeResult` is what a consumer actually receives from a
`KnowledgeResolver.resolve(query)` call. It is an immutable view of a
`KnowledgeEntry` plus provenance/version metadata.

Design rationale
----------------
We deliberately do NOT duplicate the full `KnowledgeEntry` shape into a
new model. The result is a thin wrapper that:

    1. References the source `KnowledgeEntry` by stable ID.
    2. Carries the resolved version explicitly.
    3. Carries provenance (source + version + confidence) explicitly.
    4. Is read-only / frozen.

Provenance preservation
-----------------------
Every consumer that takes a `KnowledgeResult` MUST be able to reconstruct
"which knowledge produced this decision?" from the result alone. The
`provenance` field is non-optional for that reason.

Deterministic ordering
----------------------
Multiple results returned by a single query are ordered deterministically
by `(domain, id, version)` — see `KnowledgeResolver._sort_results`.
Consumers must not rely on insertion order.
"""

from __future__ import annotations

from typing import FrozenSet, Optional

from pydantic import BaseModel, Field

from .schemas import KnowledgeDomain, KnowledgeSource, KnowledgeStatus


# ============================================================================
# Result contract
# ============================================================================

class KnowledgeProvenance(BaseModel):
    """Compact provenance record attached to a `KnowledgeResult`.

    Carries enough information to trace back to the underlying
    `KnowledgeSource` without forcing the consumer to import it.
    """

    model_config = {"frozen": True}

    source_id: str = Field(min_length=1, max_length=128)
    source_type: str = Field(min_length=1, max_length=64)
    source_reference: str = Field(min_length=1, max_length=512)
    source_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    confidence: float = Field(ge=0.0, le=1.0)


class KnowledgeResult(BaseModel):
    """Immutable, read-only view of a knowledge entry resolved from the registry.

    Consumers MUST treat this as read-only. Mutating the model after
    construction raises `ValidationError`.
    """

    model_config = {"frozen": True}

    knowledge_id: str = Field(min_length=3, max_length=96)
    domain: KnowledgeDomain
    name: str = Field(min_length=1, max_length=200)
    status: KnowledgeStatus

    # Rules are immutable at the result layer.
    rules: FrozenSet[str] = Field(min_length=1, max_length=64)
    examples: FrozenSet[str] = Field(default_factory=frozenset, max_length=32)
    tags: FrozenSet[str] = Field(default_factory=frozenset, max_length=32)
    applicability: FrozenSet[str] = Field(
        default_factory=frozenset, max_length=16
    )

    # Version + provenance.
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    provenance: KnowledgeProvenance

    # Whether this entry was found (True) or whether the resolver returned
    # a structural empty result to indicate "no match" (False).
    found: bool = True

    # ------------------------------------------------------------------
    # Provenance helpers
    # ------------------------------------------------------------------

    @property
    def provenance_label(self) -> str:
        """Convenience string for logs and audit trails."""
        return (
            f"[{self.knowledge_id}@{self.version} "
            f"via {self.provenance.source_type}:{self.provenance.source_id}]"
        )


# ============================================================================
# Empty / not-found result
# ============================================================================

class KnowledgeNotFound(BaseModel):
    """Sentinel for "no entry matched this query".

    Distinct from `KnowledgeResult(found=False)` so that consumers can
    easily branch on a 404-like outcome.
    """

    model_config = {"frozen": True}

    domain: Optional[KnowledgeDomain] = None
    knowledge_id: Optional[str] = None
    reason: str = "no_entry_matched"


# ============================================================================
# Result ordering
# ============================================================================

def sort_results(results: list[KnowledgeResult]) -> list[KnowledgeResult]:
    """Deterministic ordering for resolver output.

    Sort key: (domain.value, knowledge_id, version).
    Consumers MUST call this before returning results to ensure stable
    ordering across runs.
    """
    return sorted(
        results,
        key=lambda r: (r.domain.value, r.knowledge_id, r.version),
    )


__all__ = [
    "KnowledgeProvenance",
    "KnowledgeResult",
    "KnowledgeNotFound",
    "sort_results",
]
