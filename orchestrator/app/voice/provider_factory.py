"""TTS provider factory + legacy provider adapter (PROMPT 8 §13).

Selects a concrete `VoiceTTSProvider` based on:
- Voice's declared `provider`
- Environment (MOCK / DEVELOPMENT / PRODUCTION)
- Available API keys

In PRODUCTION mode, an unsupported provider (or missing API key) raises
an error — no silent fallback. In DEVELOPMENT mode, fallback to gTTS or
mock is allowed and audited. In MOCK mode, the mock is always used.
"""
from __future__ import annotations

import logging
from typing import Any

from app.voice.mock_tts import MockTTSProvider
from app.voice.provider_base import (
    TTSProviderError,
    VoiceTTSProvider,
)
from app.voice.schemas import (
    TtsEnvironment,
    TtsProviderName,
)

log = logging.getLogger(__name__)


class LegacyProviderAdapter(VoiceTTSProvider):
    """Adapts the legacy `app.providers.*` TTS providers to the canonical
    `VoiceTTSProvider` interface.

    Kept for backward compatibility with `s7_narration` and any other
    caller that already depends on the legacy ABC. The voice/audio
    intelligence layer treats these providers as opaque — capability
    flags are set conservatively.
    """

    name: TtsProviderName = TtsProviderName.GTTS

    def __init__(self, legacy_provider: Any, name: TtsProviderName,
                 capability_overrides: dict[str, Any] | None = None):
        self._legacy = legacy_provider
        self.name = name
        # Build a conservative capability declaration.
        overrides = capability_overrides or {}
        from app.voice.schemas import ProviderCapability
        supported_languages = overrides.get(
            "supported_languages",
            ["en"],   # safe default; can be widened per provider
        )
        self.capability = ProviderCapability(
            provider=name,
            supported_languages=supported_languages,
            supports_word_timestamps=overrides.get("supports_word_timestamps", False),
            supports_pronunciation_hints=False,
            supports_emphasis_hints=False,
            supports_ssml=False,
            supports_voice_cloning=False,
            supports_streaming=False,
            output_formats=["mp3", "wav"],
            max_text_length=overrides.get("max_text_length", 5000),
            requires_api_key=overrides.get("requires_api_key", True),
            deterministic=False,
        )

    def synthesize(self, request):
        # Lazy import — only the legacy provider is touched when actually called.
        from app.providers.base import TTSRequest
        legacy_req = TTSRequest(
            text=request.text,
            output_path=request.output_path,
            voice_id=request.voice.provider_voice_id or None,
            language=request.language,
        )
        resp = self._legacy.synthesize(legacy_req)
        # Translate.
        from app.voice.provider_base import VoiceTTSResponse
        return VoiceTTSResponse(
            audio_path=resp.audio_path,
            duration_sec=resp.duration_sec,
            sample_rate=22050,   # legacy does not return SR; default
            channels=1,
            bits_per_sample=16,
            format="mp3",
            word_timestamps=resp.word_timestamps,
            provider_artifact_meta={"legacy": True},
        )


def select_provider(
    provider_name: TtsProviderName,
    environment: TtsEnvironment = TtsEnvironment.DEVELOPMENT,
) -> VoiceTTSProvider:
    """Select a concrete TTS provider.

    Resolution:
    - MOCK environment → always MockTTSProvider.
    - MOCK provider name → MockTTSProvider.
    - GTTS / ELEVENLABS → LegacyProviderAdapter wrapping app.providers.*.
    - Future providers (CosyVoice / F5-TTS / Vi-F5-TTS / LOCAL_GPU) → raise
      NotImplementedError unless their concrete class is registered.
    """
    if environment == TtsEnvironment.MOCK or provider_name == TtsProviderName.MOCK:
        log.debug("[voice] selecting MOCK TTS provider")
        return MockTTSProvider()

    if provider_name == TtsProviderName.GTTS:
        from app.providers.gtts_tts import GttsTTSProvider
        legacy = GttsTTSProvider()
        adapter = LegacyProviderAdapter(
            legacy,
            TtsProviderName.GTTS,
            capability_overrides={
                "supported_languages": ["en", "vi", "zh", "ko", "es", "fr", "de", "ja"],
                "supports_word_timestamps": True,   # uniform alignment
                "requires_api_key": False,
                "max_text_length": 50000,
            },
        )
        log.debug("[voice] selecting gTTS provider via LegacyProviderAdapter")
        return adapter

    if provider_name == TtsProviderName.ELEVENLABS:
        from app.providers.elevenlabs_tts import ElevenLabsTTSProvider
        from app.core.config import settings
        if not settings.has_elevenlabs:
            if environment == TtsEnvironment.PRODUCTION:
                raise TTSProviderError(
                    "ELEVENLABS_API_KEY not set; cannot use ElevenLabs in PRODUCTION",
                    provider=TtsProviderName.ELEVENLABS,
                    category="missing_credentials",
                )
            log.warning(
                "[voice] ELEVENLABS_API_KEY missing; falling back to gTTS "
                "(environment=%s)", environment.value,
            )
            return select_provider(TtsProviderName.GTTS, environment)
        legacy = ElevenLabsTTSProvider()
        adapter = LegacyProviderAdapter(
            legacy,
            TtsProviderName.ELEVENLABS,
            capability_overrides={
                # ElevenLabs multilingual model supports a wide set; conservative defaults.
                "supported_languages": ["en", "vi", "zh", "ko", "es", "fr", "de", "ja", "pt", "ru", "it", "pl", "hi", "ar", "tr"],
                "supports_word_timestamps": True,
                "requires_api_key": True,
                "max_text_length": 5000,
            },
        )
        log.debug("[voice] selecting ElevenLabs provider via LegacyProviderAdapter")
        return adapter

    # Future providers — explicit registration required.
    raise TTSProviderError(
        f"TTS provider {provider_name.value} is not yet implemented",
        provider=provider_name,
        category="not_implemented",
    )


__all__ = ["select_provider", "LegacyProviderAdapter"]
