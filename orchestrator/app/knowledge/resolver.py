"""
KnowledgeResolver — canonical, composable resolver for the Knowledge Layer.

L-U3 — Knowledge Consumption Architecture.

The `KnowledgeResolver` is the **single canonical read-only entry point**
for any production subsystem that wants to consult the
`KnowledgeRegistry`.

Architecture
------------
    KnowledgeRegistry    <- in-memory store (L-U1)
             |
             v
    KnowledgeResolver    <- canonical, composable, domain-agnostic
             |
             v
    Domain-specific      <- thin wrappers (e.g. KnowledgeStoryboardAdapter)
             |
             v
    Production engine    <- StoryboardEngine, CharacterEngine, PromptCompiler, ...

Critical invariants
-------------------
    1. The resolver does NOT import any production engine.
       The Knowledge Layer must remain self-contained (L-U3 §19).
    2. The resolver is READ-ONLY. It never mutates the registry.
    3. The resolver is DETERMINISTIC. Same registry + same query -> same
       results, in the same order.
    4. The resolver is INJECTED. No global singleton, no service locator.
    5. The resolver is OPTIONAL. A resolver can be constructed with
       `registry=None` and will always return empty results — this is the
       "no knowledge layer" path that preserves backward compatibility.

Why a resolver (not a god-object `KnowledgeManager`)
----------------------------------------------------
A god object would expose `get_camera()`, `get_character()`, `get_asset()`,
etc. — one method per future consumer. That collapses two responsibilities:

    a)   "Where is knowledge stored?"  (resolver's job)
    b)   "What does my subsystem need?" (consumer adapter's job)

The resolver deliberately exposes only `resolve(query)` and `resolve_one(query)`.
Domain-specific adapters (like `KnowledgeStoryboardAdapter`) sit on top of it
and translate `KnowledgeResult` into subsystem-specific values.
"""

from __future__ import annotations

from typing import List, Optional

from .query import KnowledgeQuery
from .registry import KnowledgeRegistry
from .result import (
    KnowledgeProvenance,
    KnowledgeResult,
    sort_results,
)
from .schemas import KnowledgeEntry, KnowledgeSource


# ============================================================================
# Resolver
# ============================================================================

class KnowledgeResolver:
    """Canonical read-only resolver over a `KnowledgeRegistry`.

    Construction
    ------------
        registry = build_default_registry()
        resolver = KnowledgeResolver(registry)

        # Or — "no knowledge" mode (preserves backward compatibility):
        resolver = KnowledgeResolver(None)

        # Or — with sources provenance (for full provenance records):
        resolver = KnowledgeResolver(registry, sources=source_map)

    Resolution
    ----------
        results = resolver.resolve(KnowledgeQuery.by_domain(KnowledgeDomain.CAMERA))
        first = resolver.resolve_one(KnowledgeQuery.by_id("dino.camera.push_in"))

    Threading / lifecycle
    ---------------------
    The resolver holds an immutable reference to the registry. Multiple
    consumers may share one resolver. The resolver itself is stateless
    after construction.
    """

    def __init__(
        self,
        registry: Optional[KnowledgeRegistry] = None,
        *,
        sources: Optional[dict[str, "KnowledgeSource"]] = None,
    ) -> None:
        # We store the reference, never copy. The registry is read-only
        # from the resolver's perspective.
        self._registry = registry
        # Provenance source map. If not provided, falls back to a
        # synthesized "system" provenance for every entry.
        self._sources: dict[str, "KnowledgeSource"] = dict(sources or {})

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """True iff a non-empty registry is attached."""
        return self._registry is not None and len(self._registry.entries) > 0

    @property
    def registry_version(self) -> str:
        """The attached registry's version, or "no-registry"."""
        if self._registry is None:
            return "no-registry"
        return self._registry.version

    @property
    def loaded_source_ids(self) -> list[str]:
        """Source IDs in the registry, sorted for determinism."""
        if self._registry is None:
            return []
        return sorted(self._registry.sources_loaded)

    # ------------------------------------------------------------------
    # Core resolution
    # ------------------------------------------------------------------

    def resolve(self, query: KnowledgeQuery) -> List[KnowledgeResult]:
        """Resolve a query and return a deterministically-ordered list of results.

        Returns an empty list when:
            - the registry is None
            - the registry is empty
            - no entry matches the query

        Never raises on "not found". Callers should explicitly check
        `if not results:`.
        """
        if not self.is_active():
            return []

        if query.domain is not None:
            entries = self._registry.find_by_domain(query.domain)
        else:
            # iterate over the values (the actual entries), not the keys
            entries = sorted(self._registry.entries.values(), key=lambda e: e.id)

        results: list[KnowledgeResult] = []
        for entry in entries:
            if not self._matches(entry, query):
                continue
            results.append(self._to_result(entry))

        return sort_results(results)

    def resolve_one(self, query: KnowledgeQuery) -> Optional[KnowledgeResult]:
        """Resolve a query and return the first match, or None.

        "First match" follows the deterministic ordering produced by
        `sort_results`. For queries by `knowledge_id`, this is the
        canonical entry.
        """
        results = self.resolve(query)
        if not results:
            return None
        return results[0]

    # ------------------------------------------------------------------
    # Matching logic
    # ------------------------------------------------------------------

    @staticmethod
    def _matches(entry: KnowledgeEntry, query: KnowledgeQuery) -> bool:
        """Apply all query filters to an entry."""
        if query.knowledge_id is not None and entry.id != query.knowledge_id:
            return False
        if query.domain is not None and entry.domain != query.domain:
            return False
        if query.status is not None and entry.status != query.status:
            return False
        if query.version_pin is not None and entry.version != query.version_pin:
            return False
        if query.tags and not query.tags.issubset(set(entry.tags)):
            return False
        if query.applicability and not query.applicability.issubset(set(entry.applicability)):
            return False
        return True

    # ------------------------------------------------------------------
    # Result construction
    # ------------------------------------------------------------------

    def _to_result(self, entry: KnowledgeEntry) -> KnowledgeResult:
        """Convert a KnowledgeEntry into an immutable KnowledgeResult."""
        source = self._source_for(entry)
        return KnowledgeResult(
            knowledge_id=entry.id,
            domain=entry.domain,
            name=entry.name,
            status=entry.status,
            rules=frozenset(entry.rules),
            examples=frozenset(entry.examples),
            tags=frozenset(entry.tags),
            applicability=frozenset(entry.applicability),
            version=entry.version,
            provenance=self._provenance_for(entry, source),
            found=True,
        )

    @staticmethod
    def _provenance_for(entry: KnowledgeEntry, source: Optional[KnowledgeSource]) -> KnowledgeProvenance:
        """Build a KnowledgeProvenance from an entry + its source.

        If the entry's source is missing (defensive), we synthesize a
        "system" provenance so the result is never broken.
        """
        if source is None:
            return KnowledgeProvenance(
                source_id="system",
                source_type="system",
                source_reference="internal://registry",
                source_version="1.0.0",
                confidence=0.5,
            )
        return KnowledgeProvenance(
                source_id=source.source_id,
                source_type=source.source_type.value,
                source_reference=source.source_reference or "",
                source_version=source.version,
                confidence=source.confidence,
            )

    def _source_for(self, entry: KnowledgeEntry) -> Optional[KnowledgeSource]:
        """Return the KnowledgeSource that owns an entry, or None.

        Sources live in the resolver's own provenance map (passed at
        construction). The registry only tracks IDs.

        L-U1 maps entries to sources via the entry's tags: a tag like
        'google_flow', 'dino_ai', or 'axen' identifies the source.
        """
        if not self._sources:
            return None
        # Try tag-based mapping (canonical L-U1 way).
        tag_to_source = {
            "google_flow": "src_google_flow_v1",
            "dino_ai": "src_dino_ai_v1",
            "axen": "src_axen_ref_learner_v1",
        }
        for tag in entry.tags:
            sid = tag_to_source.get(tag)
            if sid and sid in self._sources:
                return self._sources[sid]
        # Try any source whose ID is mentioned in the entry tags.
        for tag in entry.tags:
            for source_id, source in self._sources.items():
                if tag in source_id or source_id.endswith(tag):
                    return source
        # Fall back to the first known source.
        for source in self._sources.values():
            return source
        return None


__all__ = ["KnowledgeResolver"]
