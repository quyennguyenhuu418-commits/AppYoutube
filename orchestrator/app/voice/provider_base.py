"""TTS provider abstraction (PROMPT 8 §13–§14).

The canonical `TTSProvider` ABC is implemented by:
- `ElevenLabsTTSProvider` / `GttsTTSProvider` in `app.providers.*` (legacy)
- `MockTTSProvider` in `app.voice.mock_tts`

The legacy `TTSProvider` ABC (`app.providers.base`) is intentionally
unchanged to preserve backward compatibility with s7_narration. The
newer `VoiceTTSProvider` ABC in this module is the canonical one used by
the Voice / TTS / Audio Intelligence Layer. Legacy providers are wrapped
by `LegacyProviderAdapter`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.voice.schemas import (
    ProviderCapability,
    TtsProviderName,
    VoiceDefinition,
    VoiceSettings,
)


class VoiceTTSRequest:
    """Provider-neutral TTS synthesis request."""

    __slots__ = (
        "text",
        "voice",
        "settings_override",
        "output_path",
        "language",
        "locale",
        "pronunciation_hints",
        "metadata",
        "fingerprint",
    )

    def __init__(
        self,
        text: str,
        voice: VoiceDefinition,
        settings_override: VoiceSettings | None,
        output_path: str,
        language: str,
        locale: str,
        pronunciation_hints: list,
        metadata: dict[str, Any] | None = None,
        fingerprint: str = "",
    ) -> None:
        self.text = text
        self.voice = voice
        self.settings_override = settings_override
        self.output_path = output_path
        self.language = language
        self.locale = locale
        self.pronunciation_hints = pronunciation_hints
        self.metadata = metadata or {}
        self.fingerprint = fingerprint


class VoiceTTSResponse:
    """Provider-neutral TTS synthesis response."""

    __slots__ = (
        "audio_path",
        "duration_sec",
        "sample_rate",
        "channels",
        "bits_per_sample",
        "format",
        "word_timestamps",
        "provider_artifact_meta",
    )

    def __init__(
        self,
        audio_path: str,
        duration_sec: float,
        sample_rate: int,
        channels: int,
        bits_per_sample: int,
        format: str,
        word_timestamps: list[dict[str, Any]] | None = None,
        provider_artifact_meta: dict[str, Any] | None = None,
    ) -> None:
        self.audio_path = audio_path
        self.duration_sec = duration_sec
        self.sample_rate = sample_rate
        self.channels = channels
        self.bits_per_sample = bits_per_sample
        self.format = format
        self.word_timestamps = word_timestamps or []
        self.provider_artifact_meta = provider_artifact_meta or {}


class TTSProviderError(Exception):
    """Base error for TTS provider failures."""

    def __init__(self, message: str, *, provider: TtsProviderName, category: str = "provider"):
        super().__init__(message)
        self.provider = provider
        self.category = category


class TTSUnsupportedLanguageError(TTSProviderError):
    """Raised when the provider does not support the requested language."""
    def __init__(self, provider: TtsProviderName, language: str):
        super().__init__(
            f"Provider {provider.value} does not support language {language!r}",
            provider=provider,
            category="unsupported_language",
        )
        self.language = language


class TTSEmptyTextError(TTSProviderError):
    """Raised when the synthesis request has empty text."""
    def __init__(self, provider: TtsProviderName):
        super().__init__(
            "Cannot synthesize empty text",
            provider=provider,
            category="empty_text",
        )


class TTSCorruptAudioError(TTSProviderError):
    """Raised when the provider returned corrupt / unparseable audio."""
    def __init__(self, provider: TtsProviderName, message: str = "corrupt audio"):
        super().__init__(message, provider=provider, category="corrupt_audio")


class VoiceTTSProvider(ABC):
    """Canonical TTS provider interface for the Voice Intelligence Layer.

    Concrete implementations:
    - `MockTTSProvider` (deterministic, tests + smoke)
    - `LegacyProviderAdapter` (wraps `app.providers.*`)
    - Future: CosyVoice, F5-TTS, Vi-F5-TTS, local GPU
    """
    name: TtsProviderName = TtsProviderName.MOCK
    capability: ProviderCapability

    @abstractmethod
    def synthesize(self, request: VoiceTTSRequest) -> VoiceTTSResponse: ...

    def validate_voice(self, voice: VoiceDefinition) -> bool:
        """Validate that this provider can synthesize the given voice.

        Default implementation: check capability matrix.
        """
        if voice.language not in self.capability.supported_languages:
            return False
        return True

    def get_voice_metadata(self, voice: VoiceDefinition) -> dict[str, Any]:
        """Provider-specific metadata (e.g. provider voice id mapping).

        Default: return provider + provider_voice_id.
        """
        return {
            "provider": self.name.value,
            "provider_voice_id": voice.provider_voice_id,
            "capability": self.capability.model_dump(mode="json"),
        }

    def estimate_duration(self, text: str, settings: VoiceSettings) -> float:
        """Estimate audio duration for given text + settings (seconds).

        Default heuristic: ~3 words/sec at rate=1.0; scaled by speaking_rate.
        This is a coarse estimate; authoritative duration comes from
        `synthesize()`.
        """
        words = max(len(text.split()), 1)
        base = words / 3.0
        return round(base / max(settings.speaking_rate, 0.1), 3)

    def supports_language(self, language: str) -> bool:
        """Check capability for a language code."""
        return language in self.capability.supported_languages


__all__ = [
    "VoiceTTSRequest",
    "VoiceTTSResponse",
    "VoiceTTSProvider",
    "TTSProviderError",
    "TTSUnsupportedLanguageError",
    "TTSEmptyTextError",
    "TTSCorruptAudioError",
]
