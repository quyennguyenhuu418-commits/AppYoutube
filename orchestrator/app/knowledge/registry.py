"""
Knowledge Registry — deterministic retrieval over the knowledge layer.

L-U1 — Production Knowledge & Visual Grammar Foundation.

Purpose
-------
The KnowledgeRegistry is the **only** entry point for downstream
pipeline stages to retrieve production knowledge. It is deterministic:
the same query always returns the same result.

Operations
----------
    register(entry)              — add a KnowledgeEntry to the registry
    get(entry_id)                — retrieve by stable ID
    find_by_domain(domain)       — list all entries in a domain
    find_by_tag(tag)             — list all entries carrying a tag
    find_by_status(status)       — list entries by epistemic status
    search(query)                — substring search across name + tags
    apply_filters(filters)       — multi-filter retrieval
    as_dataframe_summary()       — diagnostic dump

Critical invariants
-------------------
    1. Entries are immutable once registered (use bump_version to update).
    2. ID collisions raise an explicit error (do not silently overwrite).
    3. find_by_* methods return sorted lists (deterministic ordering).
    4. The registry never executes LLM calls.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field

from .schemas import (
    KnowledgeDomain,
    KnowledgeEntry,
    KnowledgeStatus,
)


class KnowledgeRegistry(BaseModel):
    """In-memory deterministic Knowledge Registry.

    Thread-safety: this is a Pydantic model with frozen=False; the
    registry is intended for read-heavy workloads and is NOT safe
    under concurrent mutation. Production code should build the
    registry once at startup.
    """

    entries: dict[str, KnowledgeEntry] = Field(default_factory=dict)

    # Provenance
    sources_loaded: list[str] = Field(
        default_factory=list,
        max_length=64,
        description="KnowledgeSource IDs that have been loaded",
    )
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")

    version_history: dict[str, list[KnowledgeEntry]] = Field(
        default_factory=dict,
        description="Past versions of entries (oldest first)",
    )

    # ----- Mutation -----

    def register(self, entry: KnowledgeEntry) -> None:
        """Add a KnowledgeEntry to the registry.

        Raises:
            ValueError: if entry.id is already registered.
        """
        if entry.id in self.entries:
            raise ValueError(
                f"KnowledgeEntry id={entry.id!r} already registered; "
                "use bump_version() to update, or rename the new entry."
            )
        self.entries[entry.id] = entry

    def register_many(self, entries: Iterable[KnowledgeEntry]) -> int:
        """Add many entries; returns the number registered."""
        n = 0
        for e in entries:
            self.register(e)
            n += 1
        return n

    def bump_version(self, entry_id: str, new_entry: KnowledgeEntry) -> None:
        """Update an existing entry to a new version.

        The old entry is preserved in `version_history` and the new
        entry takes its place at the same id.

        Raises:
            KeyError: if entry_id is not registered.
            ValueError: if new_entry.id != entry_id.
        """
        if entry_id not in self.entries:
            raise KeyError(f"No entry registered with id={entry_id!r}")
        if new_entry.id != entry_id:
            raise ValueError(
                f"bump_version requires new_entry.id ({new_entry.id!r}) "
                f"to match entry_id ({entry_id!r})"
            )
        # Append old to history
        old = self.entries[entry_id]
        self.version_history.setdefault(entry_id, []).append(old)
        # Install new
        self.entries[entry_id] = new_entry

    def record_source(self, source_id: str) -> None:
        """Record that a KnowledgeSource has been loaded."""
        if source_id not in self.sources_loaded:
            self.sources_loaded.append(source_id)

    # ----- Retrieval -----

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Retrieve a single entry by id, or None if not found."""
        return self.entries.get(entry_id)

    def must_get(self, entry_id: str) -> KnowledgeEntry:
        """Retrieve a single entry by id; raise KeyError if missing."""
        if entry_id not in self.entries:
            raise KeyError(f"No KnowledgeEntry with id={entry_id!r}")
        return self.entries[entry_id]

    def find_by_domain(self, domain: KnowledgeDomain) -> list[KnowledgeEntry]:
        """All entries in a domain, sorted by id (deterministic)."""
        return sorted(
            (e for e in self.entries.values() if e.domain == domain),
            key=lambda e: e.id,
        )

    def find_by_tag(self, tag: str) -> list[KnowledgeEntry]:
        """All entries carrying the given tag, sorted by id."""
        return sorted(
            (e for e in self.entries.values() if tag in e.tags),
            key=lambda e: e.id,
        )

    def find_by_status(self, status: KnowledgeStatus) -> list[KnowledgeEntry]:
        """All entries with the given status, sorted by id."""
        return sorted(
            (e for e in self.entries.values() if e.status == status),
            key=lambda e: e.id,
        )

    def find_by_applicability(self, tag: str) -> list[KnowledgeEntry]:
        """All entries whose `applicability` list contains the tag."""
        return sorted(
            (e for e in self.entries.values() if tag in e.applicability),
            key=lambda e: e.id,
        )

    def search(self, query: str) -> list[KnowledgeEntry]:
        """Substring search on name + description + tags, sorted by id.

        Case-insensitive. Empty query returns all entries.
        """
        q = query.strip().lower()
        if not q:
            return sorted(self.entries.values(), key=lambda e: e.id)
        hits: list[KnowledgeEntry] = []
        for e in self.entries.values():
            haystacks = [
                e.name.lower(),
                e.description.lower(),
                " ".join(e.tags).lower(),
            ]
            if any(q in s for s in haystacks):
                hits.append(e)
        return sorted(hits, key=lambda e: e.id)

    def apply_filters(
        self,
        domain: Optional[KnowledgeDomain] = None,
        status: Optional[KnowledgeStatus] = None,
        tag: Optional[str] = None,
        applicability: Optional[str] = None,
    ) -> list[KnowledgeEntry]:
        """Multi-filter retrieval; all filters are AND-ed together.

        Any None filter is ignored. Results are sorted by id.
        """
        out: list[KnowledgeEntry] = []
        for e in self.entries.values():
            if domain is not None and e.domain != domain:
                continue
            if status is not None and e.status != status:
                continue
            if tag is not None and tag not in e.tags:
                continue
            if applicability is not None and applicability not in e.applicability:
                continue
            out.append(e)
        return sorted(out, key=lambda e: e.id)

    # ----- Diagnostics -----

    def summary(self) -> dict[str, Any]:
        """Diagnostic summary, sorted and JSON-safe."""
        by_domain: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for e in self.entries.values():
            by_domain[e.domain.value] = by_domain.get(e.domain.value, 0) + 1
            by_status[e.status.value] = by_status.get(e.status.value, 0) + 1
        return {
            "version": self.version,
            "total_entries": len(self.entries),
            "sources_loaded": sorted(self.sources_loaded),
            "by_domain": dict(sorted(by_domain.items())),
            "by_status": dict(sorted(by_status.items())),
            "history_depth": {
                k: len(v) for k, v in sorted(self.version_history.items())
            },
        }
