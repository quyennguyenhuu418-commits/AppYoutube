"""VoiceResolver tests (PROMPT 8 §15, §32, §33)."""
from __future__ import annotations

import pytest

from app.voice.resolver import VoiceResolutionError, VoiceResolver
from app.voice.registry import VoiceRegistryManager
from app.voice.schemas import (
    NarrationUnit,
    TtsEnvironment,
    TtsProviderName,
    VoiceDefinition,
    VoiceInstance,
    VoiceLifecycleStatus,
    VoiceSettings,
)


def _voice(voice_id: str = "narrator_en", **kw) -> VoiceDefinition:
    defaults = dict(
        voice_id=voice_id,
        name=voice_id,
        language="en",
        provider=TtsProviderName.MOCK,
        status=VoiceLifecycleStatus.APPROVED,
    )
    defaults.update(kw)
    return VoiceDefinition(**defaults)


def _build_resolver(
    voices: list[VoiceDefinition] | None = None,
    instances: list[VoiceInstance] | None = None,
    environment: TtsEnvironment = TtsEnvironment.DEVELOPMENT,
    project_default: str | None = "narrator_en",
    fallback: str | None = "narrator_en",
) -> tuple[VoiceResolver, dict[str, VoiceDefinition]]:
    # None → default narrator; [] → explicitly empty
    if voices is None:
        voices = [_voice("narrator_en")]
    reg = VoiceRegistryManager()
    for v in voices:
        reg.register(v)
    defs = {v.voice_id: v for v in voices}
    r = VoiceResolver(
        registry=reg,
        voice_definitions=defs,
        voice_instances=instances or [],
        environment=environment,
        project_default_voice_id=project_default,
        fallback_voice_id=fallback,
    )
    return r, defs


def _unit(narration_id: str = "n_0001", **kw) -> NarrationUnit:
    defaults = dict(
        narration_id=narration_id,
        text="Rome fell in 476 AD",
        speaker_id="narrator",
        language="en",
    )
    defaults.update(kw)
    return NarrationUnit(**defaults)


# ---------------------------------------------------------------------------
# Explicit unit voice_id
# ---------------------------------------------------------------------------

def test_resolve_explicit_voice_id():
    r, _ = _build_resolver(voices=[_voice("narrator_en"), _voice("alt_en")])
    unit = _unit(voice_id="alt_en")
    res = r.resolve(unit)
    assert res.resolved_voice_id == "alt_en"
    assert res.strategy == "explicit"
    assert res.fallback_used is False


def test_resolve_explicit_unknown_voice_id_raises():
    r, _ = _build_resolver()
    with pytest.raises(VoiceResolutionError):
        r.resolve(_unit(voice_id="missing"))


# ---------------------------------------------------------------------------
# Project default
# ---------------------------------------------------------------------------

def test_resolve_project_default():
    r, _ = _build_resolver(project_default="narrator_en")
    res = r.resolve(_unit())
    assert res.resolved_voice_id == "narrator_en"
    assert res.strategy == "project_default"


def test_resolve_project_default_not_approved_raises():
    r, _ = _build_resolver(
        voices=[_voice("draft", status=VoiceLifecycleStatus.DRAFT)],
        project_default="draft",
    )
    # Production rejects DRAFT.
    r.environment = TtsEnvironment.PRODUCTION
    with pytest.raises(VoiceResolutionError):
        r.resolve(_unit())


# ---------------------------------------------------------------------------
# VoiceInstance match
# ---------------------------------------------------------------------------

def test_resolve_via_voice_instance_speaker_role():
    instances = [
        VoiceInstance(
            instance_id="inst_narr",
            voice_id="narrator_en",
            speaker_role="narrator",
            speaker_id="narrator",
        ),
    ]
    r, _ = _build_resolver(
        voices=[_voice("narrator_en"), _voice("alt_en")],
        instances=instances,
    )
    res = r.resolve(_unit())
    assert res.resolved_voice_id == "narrator_en"
    assert res.strategy == "instance_match"


def test_resolve_via_voice_instance_speaker_id():
    instances = [
        VoiceInstance(
            instance_id="inst_char_a",
            voice_id="alt_en",
            speaker_role="character_a",
            speaker_id="char_a",
        ),
    ]
    r, _ = _build_resolver(
        voices=[_voice("narrator_en"), _voice("alt_en")],
        instances=instances,
    )
    res = r.resolve(_unit(speaker_id="char_a", speaker_role="character_a"))
    assert res.resolved_voice_id == "alt_en"
    assert res.strategy == "instance_match"


# ---------------------------------------------------------------------------
# Compatible fallback (matching language)
# ---------------------------------------------------------------------------

def test_resolve_compatible_fallback():
    r, _ = _build_resolver(
        voices=[
            _voice("vi_narrator", language="vi", status=VoiceLifecycleStatus.ACTIVE),
            _voice("en_narrator", language="en"),
        ],
        project_default=None,
        fallback=None,
    )
    res = r.resolve(_unit(language="vi"))
    assert res.resolved_voice_id == "vi_narrator"
    assert res.strategy == "compatible_fallback"
    assert res.fallback_used is True


# ---------------------------------------------------------------------------
# Mock fallback (development only)
# ---------------------------------------------------------------------------

def test_resolve_mock_fallback_in_development():
    r, _ = _build_resolver(voices=[], project_default=None, fallback=None)
    res = r.resolve(_unit(language="en"))
    assert res.resolved_voice_id.startswith("ephemeral_mock_")
    assert res.strategy == "mock_fallback"
    assert res.mock_used is True


def test_resolve_no_match_in_production_raises():
    r, _ = _build_resolver(
        voices=[], environment=TtsEnvironment.PRODUCTION,
        project_default=None, fallback=None,
    )
    with pytest.raises(VoiceResolutionError):
        r.resolve(_unit())


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def test_resolve_records_audit_event():
    r, _ = _build_resolver(project_default="narrator_en")
    r.resolve(_unit())
    r.resolve(_unit(narration_id="n_0002"))
    assert len(r.audit_log) == 2
    assert r.audit_log[0].narration_id == "n_0001"
    assert r.audit_log[1].narration_id == "n_0002"


def test_resolve_records_usage():
    r, _ = _build_resolver(project_default="narrator_en")
    r.resolve(_unit())
    r.resolve(_unit(narration_id="n_0002"))
    entry = r.registry.lookup("narrator_en")
    assert entry.usage_count == 2


# ---------------------------------------------------------------------------
# Settings override
# ---------------------------------------------------------------------------

def test_resolve_uses_instance_settings_override():
    custom_settings = VoiceSettings(speaking_rate=1.5)
    instances = [
        VoiceInstance(
            instance_id="inst_x",
            voice_id="narrator_en",
            speaker_id="narrator",
            speaker_role="narrator",
            settings_override=custom_settings,
        ),
    ]
    r, _ = _build_resolver(
        voices=[_voice("narrator_en")],
        instances=instances,
    )
    res = r.resolve(_unit())
    assert res.settings_used.speaking_rate == 1.5
    assert "instance_settings_override" in res.events


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def test_select_provider_returns_mock_by_default():
    from app.voice.mock_tts import MockTTSProvider
    r, defs = _build_resolver(voices=[_voice("narrator_en")])
    prov = r.select_provider_for(defs["narrator_en"], _unit())
    assert isinstance(prov, MockTTSProvider)


def test_select_provider_handles_not_implemented():
    r, defs = _build_resolver(
        voices=[_voice("v1", provider=TtsProviderName.COSYVOICE)],
    )
    # In DEVELOPMENT: falls back to mock with warning.
    prov = r.select_provider_for(defs["v1"], _unit())
    from app.voice.mock_tts import MockTTSProvider
    assert isinstance(prov, MockTTSProvider)


def test_select_provider_strict_in_production():
    from app.voice.provider_base import TTSProviderError
    r, defs = _build_resolver(
        voices=[_voice("v1", provider=TtsProviderName.COSYVOICE)],
    )
    r.environment = TtsEnvironment.PRODUCTION
    with pytest.raises(TTSProviderError):
        r.select_provider_for(defs["v1"], _unit())
