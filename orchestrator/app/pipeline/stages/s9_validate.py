"""Stage 9: validate — strict schema check on the LLM's SceneDefinition.

On failure, we re-run stage 8 once with the error message appended. After
that we raise to surface to the user.
"""
from __future__ import annotations

from pydantic import ValidationError

from app.core.logging import get_logger
from app.core.paths import read_json, stage_path, write_json
from app.pipeline.stages.base import Stage, StageContext
from app.schemas.scene_definition import SceneDefinition

log = get_logger(__name__)


class ValidateStage(Stage):
    name = "validate"
    label = "Validate"

    def run(self, ctx: StageContext) -> dict:
        path = stage_path(ctx.job_id, "scene_definition")
        data = read_json(path)
        try:
            sd = SceneDefinition.model_validate(data)
        except ValidationError as exc:
            log.error("[%s] schema validation failed: %s", self.name, exc)
            raise
        log.info("[%s] OK: %d scenes, %d characters, %d environments",
                 self.name, len(sd.scenes), len(sd.characters), len(sd.environments))
        validated = sd.model_dump()
        # Overwrite with normalized output so downstream sees a clean file.
        write_json(path, validated)
        return validated
