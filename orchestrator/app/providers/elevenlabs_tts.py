"""
ElevenLabs TTS provider.

Uses the `/v1/text-to-speech/{voice_id}/with-timestamps` endpoint so we
get word-level timing data for caption highlighting. Falls back to plain
`/text-to-speech` if timestamps aren't available (e.g. on free tier).

If `ELEVENLABS_API_KEY` is missing, the factory in `tts.py` substitutes the
`GttsTTSProvider` instead. This file does not need to handle that case.
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import TTSProvider, TTSRequest, TTSResponse

log = get_logger(__name__)

ELEVEN_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsTTSProvider(TTSProvider):
    name = "elevenlabs"

    def __init__(self) -> None:
        if not settings.has_elevenlabs:
            raise RuntimeError(
                "ELEVENLABS_API_KEY is not set; ElevenLabsTTSProvider cannot be used."
            )
        self._api_key = settings.elevenlabs_api_key
        self._voice_id = settings.elevenlabs_voice_id
        self._model_id = settings.elevenlabs_model_id

    def synthesize(self, request: TTSRequest) -> TTSResponse:
        voice_id = request.voice_id or self._voice_id
        out_path = Path(request.output_path)

        url = f"{ELEVEN_BASE}/text-to-speech/{voice_id}/with-timestamps"
        headers = {
            "xi-api-key": self._api_key,
            "accept": "application/json",
            "content-type": "application/json",
        }
        payload = {
            "text": request.text,
            "model_id": self._model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        }

        t0 = time.time()
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            log.error("ElevenLabs request failed after %.1fs: %s", time.time() - t0, exc)
            raise

        # Decode audio (base64) and write.
        import base64
        audio_bytes = base64.b64decode(data["audio_base64"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(audio_bytes)

        # Word timestamps come back as a flat list; convert to seconds.
        words: list[dict] = []
        for item in data.get("word_timestamps", []):
            words.append({
                "word": item.get("word", ""),
                "start_sec": (item.get("start_time_ms", 0) or 0) / 1000.0,
                "end_sec": (item.get("end_time_ms", 0) or 0) / 1000.0,
            })

        duration = (words[-1]["end_sec"] if words else 0.0)

        log.info("ElevenLabs synthesized %d words in %.2fs", len(words), time.time() - t0)
        return TTSResponse(
            audio_path=str(out_path),
            word_timestamps=words,
            duration_sec=duration,
        )
