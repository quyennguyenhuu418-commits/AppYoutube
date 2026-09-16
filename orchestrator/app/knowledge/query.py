"""
KnowledgeQuery — canonical query contract for Knowledge Consumption.

L-U3 — Knowledge Consumption Architecture.

A query is a deterministic, immutable specification of "which knowledge
entries am I asking for?". It carries:

    domain         Optional KnowledgeDomain filter
    knowledge_id   Optional exact-ID filter
    tags           Optional tag-intersection filter
    applicability  Optional applicability-intersection filter
    status         Optional status filter (default: any)
    version_pin    Optional version pin (default: latest)
    context        Optional opaque consumer context (free-form)

Critical invariants
-------------------
    1. A query is IMMUTABLE. Once constructed, its fields are frozen.
    2. A query is DETERMINISTIC. Same query -> same results.
    3. A query has NO side effects. It does not touch the registry.
    4. The resolver never invents fields. Unknown filters return
       empty results, not errors.

The resolver (KnowledgeResolver, in `resolver.py`) accepts a query and
returns a list of `KnowledgeResult` (in `result.py`).
"""

from __future__ import annotations

from typing import FrozenSet, Optional

from pydantic import BaseModel, Field

from .schemas import KnowledgeDomain, KnowledgeStatus


# ============================================================================
# Query contract
# ============================================================================

class KnowledgeQuery(BaseModel):
    """A canonical, deterministic query against the KnowledgeRegistry.

    All fields are optional. An empty query (all fields None / empty)
    returns the full registry.

    Versioning semantics
    --------------------
        version_pin = None (default)
            Return entries at their CURRENT registered version.
        version_pin = "X.Y.Z" (exact semver)
            Return only entries whose version matches exactly.
            If no entry matches, the resolver returns an empty list
            (NOT a fallback to current version).

    The resolver documents whether a query version-pins or not. This
    field makes that explicit.
    """

    model_config = {"frozen": True}

    domain: Optional[KnowledgeDomain] = Field(
        default=None,
        description="Filter by KnowledgeDomain. None means any domain.",
    )
    knowledge_id: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=96,
        description="Filter by exact entry ID. None means any ID.",
    )
    tags: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=32,
        description="Filter: only entries that contain ALL of these tags.",
    )
    applicability: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=16,
        description="Filter: only entries that contain ALL of these applicability tags.",
    )
    status: Optional[KnowledgeStatus] = Field(
        default=None,
        description="Filter by epistemic status. None means any status.",
    )
    version_pin: Optional[str] = Field(
        default=None,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Pin to exact semver. None means current version.",
    )

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def by_id(cls, knowledge_id: str) -> "KnowledgeQuery":
        """Query for one specific entry by its stable ID."""
        return cls(knowledge_id=knowledge_id)

    @classmethod
    def by_domain(cls, domain: KnowledgeDomain) -> "KnowledgeQuery":
        """Query all entries in a domain."""
        return cls(domain=domain)

    @classmethod
    def by_tag(cls, tag: str) -> "KnowledgeQuery":
        """Query entries that carry a specific tag."""
        return cls(tags=frozenset({tag}))

    @classmethod
    def by_applicability(cls, applicability: str) -> "KnowledgeQuery":
        """Query entries that declare a specific applicability."""
        return cls(applicability=frozenset({applicability}))

    @classmethod
    def project_rules_in(cls, domain: KnowledgeDomain) -> "KnowledgeQuery":
        """Query PROJECT_RULE entries in a domain (project-decided rules)."""
        return cls(domain=domain, status=KnowledgeStatus.PROJECT_RULE)


__all__ = ["KnowledgeQuery"]
