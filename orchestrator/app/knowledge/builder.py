"""
Knowledge builder — convenience constructors for downstream consumers.

L-U1 — Production Knowledge & Visual Grammar Foundation.

The builder module exposes a tiny, stable API for downstream pipeline
stages:

    build_default_registry() -> KnowledgeRegistry
        Build an in-memory registry preloaded with the L-U1 seeds.

    build_grammar_registry() -> tuple[KnowledgeRegistry, list[VisualGrammar], list[CharacterGrammar]]
        Build the registry plus seeded grammars (placeholder; grammars
        are not seeded in L-U1 — only the knowledge registry is).

The builder is **additive**. It does not modify any existing pipeline
stage, schema, or contract.
"""

from __future__ import annotations

from typing import Optional

from .registry import KnowledgeRegistry
from .schemas import KnowledgeSource
from .seeds import default_seeds, default_sources


def build_default_registry(
    *,
    extra_entries: Optional[list] = None,
    extra_sources: Optional[list[KnowledgeSource]] = None,
    record_sources: bool = True,
) -> KnowledgeRegistry:
    """Build a KnowledgeRegistry preloaded with the L-U1 default seeds.

    Args:
        extra_entries: Additional KnowledgeEntry objects to register
            after the defaults.
        extra_sources: Additional KnowledgeSource records to record.
        record_sources: If True, record the default sources in the
            registry's `sources_loaded` field.

    Returns:
        A fully populated KnowledgeRegistry.
    """
    registry = KnowledgeRegistry()
    # Register all default seeds exactly once.
    for entry in default_seeds():
        registry.register(entry)
    if record_sources:
        for source in default_sources():
            registry.record_source(source.source_id)

    if extra_entries:
        for e in extra_entries:
            registry.register(e)

    if extra_sources:
        for s in extra_sources:
            registry.record_source(s.source_id)

    return registry


def reset_and_build(entries: list, sources: Optional[list[KnowledgeSource]] = None) -> KnowledgeRegistry:
    """Build an empty registry and register only the given entries.

    Useful for tests that want full control over registry contents.
    """
    registry = KnowledgeRegistry()
    registry.register_many(entries)
    if sources:
        for s in sources:
            registry.record_source(s.source_id)
    return registry
