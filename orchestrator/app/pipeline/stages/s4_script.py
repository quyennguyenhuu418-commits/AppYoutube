"""Stage 4: script — reads story_package.json and writes legacy script.json."""
from __future__ import annotations

from app.core.logging import get_logger
from app.core.paths import read_json, stage_path, write_json
from app.pipeline.cache import should_skip
from app.pipeline.stages.base import Stage, StageContext
from app.schemas.story import ScriptVersion, StoryPackage

log = get_logger(__name__)


class ScriptStage(Stage):
    """
    Script stage — read-only adapter that reads the canonical StoryPackage
    from story_package.json and writes legacy script.json for downstream
    stages that still expect it.
    """

    name = "script"
    label = "Kịch bản"

    def run(self, ctx: StageContext) -> dict:
        out = stage_path(ctx.job_id, "script")
        if should_skip(out):
            return read_json(out)

        story_pkg = StoryPackage.model_validate(
            read_json(stage_path(ctx.job_id, "story_package"))
        )

        legacy = story_pkg.to_legacy_script()
        write_json(out, legacy)

        seg_count = 0
        final_ver = story_pkg.get_final_script()
        if final_ver:
            seg_count = len(final_ver.segments)

        log.info("[script] wrote script with %d segments", seg_count)
        return legacy
