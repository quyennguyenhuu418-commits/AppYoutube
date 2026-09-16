"""TTS provider factory tests (PROMPT 8 §13)."""
from __future__ import annotations

import pytest

from app.voice.mock_tts import MockTTSProvider
from app.voice.provider_base import TTSProviderError
from app.voice.provider_factory import LegacyProviderAdapter, select_provider
from app.voice.schemas import TtsEnvironment, TtsProviderName


# ---------------------------------------------------------------------------
# select_provider
# ---------------------------------------------------------------------------

def test_select_provider_returns_mock_when_environment_is_mock():
    p = select_provider(TtsProviderName.ELEVENLABS, TtsEnvironment.MOCK)
    assert isinstance(p, MockTTSProvider)


def test_select_provider_returns_mock_when_provider_is_mock():
    p = select_provider(TtsProviderName.MOCK, TtsEnvironment.DEVELOPMENT)
    assert isinstance(p, MockTTSProvider)


def test_select_provider_gtts_development():
    p = select_provider(TtsProviderName.GTTS, TtsEnvironment.DEVELOPMENT)
    assert isinstance(p, LegacyProviderAdapter)
    assert p.name == TtsProviderName.GTTS


def test_select_provider_unknown_provider_raises():
    with pytest.raises(TTSProviderError):
        select_provider(TtsProviderName.COSYVOICE, TtsEnvironment.DEVELOPMENT)


# ---------------------------------------------------------------------------
# LegacyProviderAdapter
# ---------------------------------------------------------------------------

def test_legacy_provider_adapter_wraps_gtts():
    from app.providers.gtts_tts import GttsTTSProvider
    legacy = GttsTTSProvider()
    adapter = LegacyProviderAdapter(
        legacy, TtsProviderName.GTTS,
        capability_overrides={"supported_languages": ["en", "vi"]},
    )
    assert adapter.capability.supported_languages == ["en", "vi"]
    assert adapter.name == TtsProviderName.GTTS
    assert adapter.capability.deterministic is False


# ---------------------------------------------------------------------------
# ElevenLabs without key
# ---------------------------------------------------------------------------

def test_elevenlabs_without_key_development_falls_back(monkeypatch):
    """When ELEVENLABS_API_KEY is missing and environment is DEVELOPMENT,
    factory falls back to gTTS (audited, not silent)."""
    # Patch the settings object directly via property override.
    from app.core import config as cfg_mod
    # Inject a fake property on the singleton.
    original_has = cfg_mod.settings.has_elevenlabs
    cfg_mod.settings.__class__.has_elevenlabs = property(lambda self: False)
    try:
        # Select ElevenLabs in DEVELOPMENT → should fall back to gTTS.
        p = select_provider(TtsProviderName.ELEVENLABS, TtsEnvironment.DEVELOPMENT)
        assert isinstance(p, LegacyProviderAdapter)
        assert p.name == TtsProviderName.GTTS
    finally:
        cfg_mod.settings.__class__.has_elevenlabs = original_has


def test_elevenlabs_without_key_production_raises(monkeypatch):
    from app.core import config as cfg_mod
    original_has = cfg_mod.settings.has_elevenlabs
    cfg_mod.settings.__class__.has_elevenlabs = property(lambda self: False)
    try:
        with pytest.raises(TTSProviderError):
            select_provider(TtsProviderName.ELEVENLABS, TtsEnvironment.PRODUCTION)
    finally:
        cfg_mod.settings.__class__.has_elevenlabs = original_has
