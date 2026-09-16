"""Voice lifecycle management tests (PROMPT 8 §9)."""
from __future__ import annotations

import pytest

from app.voice import lifecycle
from app.voice.schemas import VoiceLifecycleStatus


# ---------------------------------------------------------------------------
# can_transition
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("current,target,allowed", [
    (VoiceLifecycleStatus.DRAFT, VoiceLifecycleStatus.VALIDATED, True),
    (VoiceLifecycleStatus.DRAFT, VoiceLifecycleStatus.APPROVED, False),
    (VoiceLifecycleStatus.VALIDATED, VoiceLifecycleStatus.APPROVED, True),
    (VoiceLifecycleStatus.VALIDATED, VoiceLifecycleStatus.DRAFT, True),
    (VoiceLifecycleStatus.APPROVED, VoiceLifecycleStatus.ACTIVE, True),
    (VoiceLifecycleStatus.ACTIVE, VoiceLifecycleStatus.DEPRECATED, True),
    (VoiceLifecycleStatus.DEPRECATED, VoiceLifecycleStatus.ARCHIVED, True),
    (VoiceLifecycleStatus.ARCHIVED, VoiceLifecycleStatus.DRAFT, False),
    (VoiceLifecycleStatus.ARCHIVED, VoiceLifecycleStatus.ACTIVE, False),
    (VoiceLifecycleStatus.DRAFT, VoiceLifecycleStatus.ACTIVE, False),
])
def test_can_transition(current, target, allowed):
    assert lifecycle.can_transition(current, target) is allowed


def test_assert_transition_raises_on_invalid():
    with pytest.raises(ValueError):
        lifecycle.assert_transition(
            VoiceLifecycleStatus.DRAFT, VoiceLifecycleStatus.ACTIVE,
        )


# ---------------------------------------------------------------------------
# Resolvability sets
# ---------------------------------------------------------------------------

def test_resolvable_in_production_includes_approved_active():
    assert VoiceLifecycleStatus.APPROVED in lifecycle.RESOLVABLE_IN_PRODUCTION
    assert VoiceLifecycleStatus.ACTIVE in lifecycle.RESOLVABLE_IN_PRODUCTION


def test_resolvable_in_production_excludes_draft_validated():
    assert VoiceLifecycleStatus.DRAFT not in lifecycle.RESOLVABLE_IN_PRODUCTION
    assert VoiceLifecycleStatus.VALIDATED not in lifecycle.RESOLVABLE_IN_PRODUCTION


def test_resolvable_in_development_includes_draft_validated():
    assert VoiceLifecycleStatus.DRAFT in lifecycle.RESOLVABLE_IN_DEVELOPMENT
    assert VoiceLifecycleStatus.VALIDATED in lifecycle.RESOLVABLE_IN_DEVELOPMENT


def test_resolvable_in_development_excludes_archived():
    assert VoiceLifecycleStatus.ARCHIVED not in lifecycle.RESOLVABLE_IN_DEVELOPMENT
