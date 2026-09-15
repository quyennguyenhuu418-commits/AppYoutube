"""Stage 7: narration — converts the full script text to audio with word timestamps."""
from __future__ import annotations

from app.core.logging import get_logger
from app.core.paths import job_dir, read_json, stage_path, write_json
from app.pipeline.cache import should_skip
from app.pipeline.stages.base import Stage, StageContext
from app.providers.base import TTSRequest
from app.providers.tts import get_tts_provider
from app.schemas.script import Script

log = get_logger(__name__)


class NarrationStage(Stage):
    name = "narration"
    label = "Narration"

    def run(self, ctx: StageContext) -> dict:
        audio_path = job_dir(ctx.job_id) / "narration.mp3"
        words_path = stage_path(ctx.job_id, "narration.words")

        if should_skip(audio_path) and should_skip(words_path):
            log.info("[%s] cached, skipping", self.name)
            return {
                "audio_path": str(audio_path),
                "words": read_json(words_path),
                "duration_sec": _approx_duration(read_json(words_path)),
            }

        script_dict = ctx.state.get("script") or read_json(stage_path(ctx.job_id, "script"))
        script = Script.model_validate(script_dict)
        text = script.full_text()
        log.info("[%s] synthesizing %d chars", self.name, len(text))

        provider = get_tts_provider()
        req = TTSRequest(text=text, output_path=str(audio_path), language="en")
        resp = provider.synthesize(req)
        write_json(words_path, resp.word_timestamps)
        log.info("[%s] audio=%s words=%d duration=%.2fs",
                 self.name, resp.audio_path, len(resp.word_timestamps), resp.duration_sec)
        return {
            "audio_path": resp.audio_path,
            "words": resp.word_timestamps,
            "duration_sec": resp.duration_sec,
        }


def _approx_duration(words: list[dict]) -> float:
    if not words:
        return 0.0
    return float(words[-1].get("end_sec", 0.0))
