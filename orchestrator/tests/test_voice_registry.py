"""VoiceRegistry tests (PROMPT 8 §8)."""
from __future__ import annotations

import pytest

from app.voice.registry import (
    DuplicateVoiceError,
    VoiceNotFoundError,
    VoiceRegistryManager,
)
from app.voice.schemas import (
    TtsEnvironment,
    VoiceDefinition,
    VoiceLifecycleStatus,
    VoiceRegistry,
    VoiceRegistryEntry,
)


def _voice(voice_id: str = "narrator_en", **kw) -> VoiceDefinition:
    defaults = dict(
        voice_id=voice_id,
        name=voice_id.replace("_", " ").title(),
        language="en",
        provider="mock",
        status=VoiceLifecycleStatus.APPROVED,
    )
    defaults.update(kw)
    return VoiceDefinition(**defaults)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_basic():
    mgr = VoiceRegistryManager()
    entry = mgr.register(_voice("v1"))
    assert entry.voice_id == "v1"
    assert mgr.has("v1")


def test_register_duplicate_raises():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("v1"))
    with pytest.raises(DuplicateVoiceError):
        mgr.register(_voice("v1"))


def test_register_replace_overwrites():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("v1", status=VoiceLifecycleStatus.DRAFT))
    mgr.register(_voice("v1", status=VoiceLifecycleStatus.APPROVED), replace=True)
    assert mgr.lookup("v1").status == VoiceLifecycleStatus.APPROVED


# ---------------------------------------------------------------------------
# Lookup / search
# ---------------------------------------------------------------------------

def test_lookup_not_found():
    mgr = VoiceRegistryManager()
    with pytest.raises(VoiceNotFoundError):
        mgr.lookup("missing")


def test_list_and_search():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("v1"))
    mgr.register(_voice("v2"))
    assert len(mgr.list()) == 2
    found = mgr.search(lambda e: e.voice_id.startswith("v1"))
    assert len(found) == 1
    assert found[0].voice_id == "v1"


def test_find_by_status():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("v1", status=VoiceLifecycleStatus.APPROVED))
    mgr.register(_voice("v2", status=VoiceLifecycleStatus.DRAFT))
    approved = mgr.find_by_status(VoiceLifecycleStatus.APPROVED)
    assert len(approved) == 1
    assert approved[0].voice_id == "v1"


def test_find_approved_and_active():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("a1", status=VoiceLifecycleStatus.APPROVED))
    mgr.register(_voice("a2", status=VoiceLifecycleStatus.ACTIVE))
    mgr.register(_voice("d1", status=VoiceLifecycleStatus.DRAFT))
    assert len(mgr.find_approved()) == 1
    assert len(mgr.find_active()) == 1


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------

def test_transition_valid():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("v1", status=VoiceLifecycleStatus.DRAFT))
    # First transition: DRAFT -> VALIDATED (no approval bookkeeping).
    mgr.transition("v1", VoiceLifecycleStatus.VALIDATED)
    # Then: VALIDATED -> APPROVED with approved_by.
    entry = mgr.transition("v1", VoiceLifecycleStatus.APPROVED, approved_by="alice")
    assert entry.status == VoiceLifecycleStatus.APPROVED
    assert entry.approved_by == "alice"
    assert entry.approved_at is not None
    # Then: APPROVED -> ACTIVE.
    entry = mgr.transition("v1", VoiceLifecycleStatus.ACTIVE)
    assert entry.status == VoiceLifecycleStatus.ACTIVE
    assert entry.approved_by == "alice"  # preserved


def test_transition_invalid_raises():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("v1", status=VoiceLifecycleStatus.DRAFT))
    with pytest.raises(ValueError):
        mgr.transition("v1", VoiceLifecycleStatus.ACTIVE)


def test_deprecate_records_reason():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("v1", status=VoiceLifecycleStatus.APPROVED))
    entry = mgr.deprecate("v1", reason="replaced by v2")
    assert entry.status == VoiceLifecycleStatus.DEPRECATED
    assert entry.deprecated_reason == "replaced by v2"


# ---------------------------------------------------------------------------
# Usage tracking
# ---------------------------------------------------------------------------

def test_record_usage_increments_count():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("v1"))
    mgr.record_usage("v1")
    mgr.record_usage("v1")
    assert mgr.lookup("v1").usage_count == 2


# ---------------------------------------------------------------------------
# Resolvability
# ---------------------------------------------------------------------------

def test_is_resolvable_production_requires_approved_or_active():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("a", status=VoiceLifecycleStatus.APPROVED))
    mgr.register(_voice("d", status=VoiceLifecycleStatus.DRAFT))
    assert mgr.is_resolvable("a", TtsEnvironment.PRODUCTION) is True
    assert mgr.is_resolvable("d", TtsEnvironment.PRODUCTION) is False


def test_is_resolvable_development_includes_draft():
    mgr = VoiceRegistryManager()
    mgr.register(_voice("d", status=VoiceLifecycleStatus.DRAFT))
    assert mgr.is_resolvable("d", TtsEnvironment.DEVELOPMENT) is True


def test_is_resolvable_unknown_voice():
    mgr = VoiceRegistryManager()
    assert mgr.is_resolvable("ghost", TtsEnvironment.PRODUCTION) is False


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_to_dict_round_trip():
    mgr = VoiceRegistryManager(VoiceRegistry(project_id="p1"))
    mgr.register(_voice("v1"))
    d = mgr.to_dict()
    assert d["project_id"] == "p1"
    assert len(d["voices"]) == 1
