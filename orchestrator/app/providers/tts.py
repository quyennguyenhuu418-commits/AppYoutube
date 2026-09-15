"""
TTS provider factory.

Selection rules:
  - If `ELEVENLABS_API_KEY` is set -> ElevenLabs provider.
  - Otherwise -> gTTS provider (free, no word timestamps but functional).
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import TTSProvider
from app.providers.elevenlabs_tts import ElevenLabsTTSProvider
from app.providers.gtts_tts import GttsTTSProvider

log = get_logger(__name__)


def get_tts_provider() -> TTSProvider:
    if settings.has_elevenlabs:
        log.info("Using ElevenLabs TTS provider.")
        return ElevenLabsTTSProvider()
    log.warning(
        "ELEVENLABS_API_KEY not set; using gTTS provider (no precise word timestamps)."
    )
    return GttsTTSProvider()
