"""Voice lifecycle management.

PROMPT 8 §9. Voice lifecycle is a state machine. Only voices in
`VALIDATED` or higher states may be resolved by the resolver in
non-development environments.
"""
from __future__ import annotations

from app.voice.schemas import VoiceLifecycleStatus


# Allowed transitions (from -> set of allowed targets).
_TRANSITIONS: dict[VoiceLifecycleStatus, set[VoiceLifecycleStatus]] = {
    VoiceLifecycleStatus.DRAFT: {
        VoiceLifecycleStatus.VALIDATED,
        VoiceLifecycleStatus.DEPRECATED,
        VoiceLifecycleStatus.ARCHIVED,
    },
    VoiceLifecycleStatus.VALIDATED: {
        VoiceLifecycleStatus.APPROVED,
        VoiceLifecycleStatus.DRAFT,
        VoiceLifecycleStatus.DEPRECATED,
        VoiceLifecycleStatus.ARCHIVED,
    },
    VoiceLifecycleStatus.APPROVED: {
        VoiceLifecycleStatus.ACTIVE,
        VoiceLifecycleStatus.DEPRECATED,
        VoiceLifecycleStatus.ARCHIVED,
    },
    VoiceLifecycleStatus.ACTIVE: {
        VoiceLifecycleStatus.DEPRECATED,
        VoiceLifecycleStatus.ARCHIVED,
    },
    VoiceLifecycleStatus.DEPRECATED: {
        VoiceLifecycleStatus.ARCHIVED,
    },
    VoiceLifecycleStatus.ARCHIVED: set(),
}


# States that the resolver may use in PRODUCTION.
RESOLVABLE_IN_PRODUCTION: frozenset[VoiceLifecycleStatus] = frozenset({
    VoiceLifecycleStatus.APPROVED,
    VoiceLifecycleStatus.ACTIVE,
})

# States allowed in DEVELOPMENT mode (anything except ARCHIVED).
RESOLVABLE_IN_DEVELOPMENT: frozenset[VoiceLifecycleStatus] = frozenset({
    VoiceLifecycleStatus.DRAFT,
    VoiceLifecycleStatus.VALIDATED,
    VoiceLifecycleStatus.APPROVED,
    VoiceLifecycleStatus.ACTIVE,
    VoiceLifecycleStatus.DEPRECATED,
})


def can_transition(
    current: VoiceLifecycleStatus,
    target: VoiceLifecycleStatus,
) -> bool:
    """Return True if `current -> target` is a valid transition."""
    return target in _TRANSITIONS[current]


def assert_transition(
    current: VoiceLifecycleStatus,
    target: VoiceLifecycleStatus,
) -> None:
    """Raise ValueError if transition is not allowed."""
    if not can_transition(current, target):
        raise ValueError(
            f"Invalid voice lifecycle transition: {current.value} -> {target.value}"
        )


__all__ = [
    "can_transition",
    "assert_transition",
    "RESOLVABLE_IN_PRODUCTION",
    "RESOLVABLE_IN_DEVELOPMENT",
]
