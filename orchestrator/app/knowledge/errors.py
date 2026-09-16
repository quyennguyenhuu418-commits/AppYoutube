"""
Knowledge errors — canonical error semantics for Knowledge Consumption.

L-U3 — Knowledge Consumption Architecture.

We intentionally keep the error model small. Most "not found" cases
return `None` or empty lists, not exceptions. Exceptions are reserved
for genuinely exceptional conditions:

    - KnowledgeInvalidQuery        : the caller constructed an invalid query
    - KnowledgeVersionMismatch     : version_pin resolved but no entry matches
                                     (caller asked for a specific version)
    - KnowledgeConflict            : two entries matched with the same ID+version
                                     (caller has a registry corruption)
    - KnowledgeUnavailable         : the resolver cannot operate at all
                                     (no registry attached AND fallback is
                                     REJECT)

This minimal set is enough to be actionable without exploding into 30
exception classes (L-U3 §25).
"""

from __future__ import annotations


class KnowledgeError(Exception):
    """Base class for all Knowledge Consumption errors."""


class KnowledgeInvalidQuery(KnowledgeError):
    """A query was constructed with invalid state (defensive only)."""


class KnowledgeVersionMismatch(KnowledgeError):
    """A version_pinned query returned no matching entry."""

    def __init__(self, knowledge_id: str, version: str) -> None:
        super().__init__(
            f"Knowledge version pin {version!r} for {knowledge_id!r} not found."
        )
        self.knowledge_id = knowledge_id
        self.version = version


class KnowledgeConflict(KnowledgeError):
    """Two entries with the same (id, version) coexist in the registry."""


class KnowledgeUnavailable(KnowledgeError):
    """Knowledge cannot be resolved at all and the policy forbids fallback."""


__all__ = [
    "KnowledgeError",
    "KnowledgeInvalidQuery",
    "KnowledgeVersionMismatch",
    "KnowledgeConflict",
    "KnowledgeUnavailable",
]
