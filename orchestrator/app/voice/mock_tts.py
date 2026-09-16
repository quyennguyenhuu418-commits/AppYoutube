"""Deterministic Mock TTS provider (PROMPT 8 §21, §37, §50).

This provider is the canonical TTS for:
- Unit tests
- The animation smoke test
- End-to-end voice/audio smoke test
- Any test that needs a real audio file with known properties

Design
------
- Pure stdlib (`wave`, `struct`, `math`, `hashlib`).
- Produces a 16-bit PCM mono WAV file.
- For the same input (text + voice fingerprint), the byte content is
  byte-identical.
- Output duration is computed deterministically from text length and
  `speaking_rate`.
- Word timestamps are generated uniformly across the audio duration
  with deterministic per-word offsets based on the word index.
- No external services. No API keys. No network. No filesystem
  dependency beyond standard library.

Deterministic contract
----------------------
Given:
  text="Rome fell in 476 AD"  (normalized)
  voice_id="narrator_en"
  speaking_rate=1.0
  sample_rate=22050

Output:
  Same byte sequence every time.
  Same duration every time (within 1e-6 sec rounding).
  Same word timestamps every time.

This is the foundation for the audio smoke test (PROMPT 8 §37–§40) and
the cross-runtime contract tests.
"""
from __future__ import annotations

import hashlib
import math
import struct
import wave
from pathlib import Path

from app.voice.provider_base import (
    TTSEmptyTextError,
    VoiceTTSProvider,
    VoiceTTSRequest,
    VoiceTTSResponse,
)
from app.voice.schemas import (
    ProviderCapability,
    TtsProviderName,
    TimestampSource,
    VoiceDefinition,
    VoiceSettings,
)


# Default audio parameters — match the smoke test expectations.
DEFAULT_SAMPLE_RATE = 22050
DEFAULT_CHANNELS = 1
DEFAULT_BITS_PER_SAMPLE = 16

# Default words per second at speaking_rate=1.0.
_BASE_WORDS_PER_SECOND = 3.0


class MockTTSProvider(VoiceTTSProvider):
    """Deterministic mock TTS provider.

    Generates a sine-wave modulated tone whose fundamental frequency is
    derived from the voice fingerprint, so different voices produce
    audibly-distinct (but still deterministic) test fixtures.
    """

    name = TtsProviderName.MOCK
    capability = ProviderCapability(
        provider=TtsProviderName.MOCK,
        supported_languages=["en", "vi", "ko", "zh", "es", "fr", "de", "ja"],
        supports_word_timestamps=True,    # generates uniform timestamps
        supports_pronunciation_hints=False,
        supports_emphasis_hints=False,
        supports_ssml=False,
        supports_voice_cloning=False,
        supports_streaming=False,
        output_formats=["wav"],
        max_text_length=20000,
        requires_api_key=False,
        deterministic=True,
    )

    # -------------------------------------------------------------------
    # Synthesis
    # -------------------------------------------------------------------

    def synthesize(self, request: VoiceTTSRequest) -> VoiceTTSResponse:
        text = request.text.strip()
        if not text:
            raise TTSEmptyTextError(self.name)

        # Settings: prefer override, fall back to voice default.
        settings = request.settings_override or request.voice.settings

        # Compute duration deterministically.
        words = text.split()
        n_words = max(len(words), 1)
        duration_sec = round(n_words / _BASE_WORDS_PER_SECOND / settings.speaking_rate, 3)
        if duration_sec <= 0.0:
            duration_sec = 0.05  # minimum audible artifact

        # Fundamental frequency derived from the full voice fingerprint.
        # We hash the full fingerprint string so that different voice
        # configs (same text) produce distinguishable test tones.
        full_seed_hex = 0
        if request.fingerprint:
            full_seed_hex = int(hashlib.sha256(request.fingerprint.encode()).hexdigest()[:8], 16)
        fundamental_hz = 110.0 + (full_seed_hex % 3300) / 10.0  # 110..440 Hz

        # Generate WAV.
        out_path = Path(request.output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sample_rate = DEFAULT_SAMPLE_RATE
        channels = DEFAULT_CHANNELS
        bits = DEFAULT_BITS_PER_SAMPLE
        n_samples = int(round(duration_sec * sample_rate))
        with wave.open(str(out_path), "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(bits // 8)
            wav.setframerate(sample_rate)
            amp = 0.20 * 32767  # ~ -14 dBFS, gentle test tone
            frames = bytearray()
            omega = 2.0 * math.pi * fundamental_hz / sample_rate
            for i in range(n_samples):
                # Two harmonics with slow envelope → distinguishable tone per voice.
                v = (
                    math.sin(i * omega) * 0.7
                    + math.sin(i * omega * 2.0) * 0.3
                )
                # Envelope: fade-in 5%, fade-out 5% to avoid clicks.
                fade_n = max(int(0.05 * sample_rate), 1)
                if i < fade_n:
                    v *= i / fade_n
                elif i > n_samples - fade_n:
                    v *= (n_samples - i) / fade_n
                sample = int(v * amp)
                frames += struct.pack("<h", sample)
            wav.writeframes(bytes(frames))

        # Word timestamps: uniform alignment across audio duration.
        # Each word slot = (duration_sec / n_words). Start at 0.
        per_word = duration_sec / n_words
        word_timestamps: list[dict] = []
        for i, w in enumerate(words):
            word_timestamps.append({
                "word": w,
                "start_sec": round(i * per_word, 3),
                "end_sec": round((i + 1) * per_word, 3),
                "confidence": 0.9,
            })

        return VoiceTTSResponse(
            audio_path=str(out_path),
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            channels=channels,
            bits_per_sample=bits,
            format="wav",
            word_timestamps=word_timestamps,
            provider_artifact_meta={
                "fundamental_hz": fundamental_hz,
                "seed_hex": full_seed_hex,
                "timestamp_source": TimestampSource.UNIFORM_ALIGNMENT.value,
            },
        )

    # -------------------------------------------------------------------
    # Capability helpers
    # -------------------------------------------------------------------

    def validate_voice(self, voice: VoiceDefinition) -> bool:
        # Mock supports everything we declare.
        return super().validate_voice(voice)

    def estimate_duration(self, text: str, settings: VoiceSettings) -> float:
        words = max(len(text.split()), 1)
        return round(words / _BASE_WORDS_PER_SECOND / settings.speaking_rate, 3)


__all__ = ["MockTTSProvider", "DEFAULT_SAMPLE_RATE", "DEFAULT_CHANNELS", "DEFAULT_BITS_PER_SAMPLE"]
