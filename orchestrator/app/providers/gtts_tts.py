"""
Google Text-to-Speech fallback provider.

Used when ElevenLabs is unavailable (no key, free tier limits, network
issues). Generates an MP3 via gTTS, then computes word-level timestamps by
aligning the audio duration evenly across words.

The word alignment is rough but functional: each word gets a slot of
`(end_sec - start_sec) / num_words` seconds. For a smoother result we'd
plug in `faster-whisper` for forced alignment, but that adds a heavy
dependency — out of scope for the MVP.
"""
from __future__ import annotations

from pathlib import Path

from gtts import gTTS

from app.core.logging import get_logger
from app.providers.base import TTSProvider, TTSRequest, TTSResponse

log = get_logger(__name__)


class GttsTTSProvider(TTSProvider):
    name = "gtts"

    def synthesize(self, request: TTSRequest) -> TTSResponse:
        out_path = Path(request.output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # gTTS splits on sentence boundaries but doesn't return word timing.
        # We compute uniform alignment: total duration / word count.
        tts = gTTS(text=request.text, lang=request.language, slow=False)
        tts.save(str(out_path))

        # Probe audio duration with a tiny helper. If pydub/ffmpeg fails we
        # fall back to a 3 wps estimate.
        duration = _probe_audio_duration(out_path)
        words_text = request.text.split()
        n = max(len(words_text), 1)
        per_word = duration / n
        words = []
        for i, w in enumerate(words_text):
            words.append({
                "word": w,
                "start_sec": round(i * per_word, 3),
                "end_sec": round((i + 1) * per_word, 3),
            })
        log.info("gTTS synthesized %d words, duration=%.2fs", n, duration)
        return TTSResponse(
            audio_path=str(out_path),
            word_timestamps=words,
            duration_sec=duration,
        )


def _probe_audio_duration(path: Path) -> float:
    """Best-effort audio duration probe. Returns 0.0 on failure.

    Tries pydub first (uses ffmpeg under the hood), then falls back to a
    rough 3-words-per-second estimate based on file size.
    """
    try:
        from pydub import AudioSegment  # type: ignore
        seg = AudioSegment.from_file(path)
        return seg.duration_seconds
    except Exception:
        # Last-ditch estimate: assume ~1 second per 50 bytes of MP3.
        try:
            return max(path.stat().st_size / 16000.0, 1.0)
        except Exception:
            return 10.0
