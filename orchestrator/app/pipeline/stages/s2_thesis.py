"""Stage 2: thesis — runs the full StoryEngine, writes story_package.json + legacy thesis.json."""
from __future__ import annotations

from app.core.logging import get_logger
from app.core.paths import read_json, stage_path, write_json
from app.pipeline.cache import should_skip
from app.pipeline.stages.base import Stage, StageContext
from app.schemas.research_package import ResearchPackage
from app.schemas.story import StoryPackage
from app.story.engine import StoryEngine

log = get_logger(__name__)


class ThesisStage(Stage):
    """
    Thesis stage — runs the full 15-step Story Intelligence Engine.

    Reads the canonical ResearchPackage from research_package.json, generates
    the full StoryPackage (thesis candidates, angles, titles, hooks, script,
    critique, storyboard intent), then writes BOTH:
      - story_package.json  (canonical, new pipeline)
      - thesis.json         (legacy compat for downstream stages s3/s4/s5)
    """

    name = "thesis"
    label = "Luận điểm"

    def run(self, ctx: StageContext) -> dict:
        story_out = stage_path(ctx.job_id, "story_package")
        if should_skip(story_out):
            log.info("[thesis] skipping (cached): %s", story_out)
            return read_json(story_out)

        # 1. Load canonical ResearchPackage
        research_pkg = ResearchPackage.model_validate(
            read_json(stage_path(ctx.job_id, "research_package"))
        )

        # 2. Run the full Story Engine (all 15 steps internally)
        engine = StoryEngine(job_id=ctx.job_id, use_cache=True)
        story_pkg: StoryPackage = engine.run(
            job_id=ctx.job_id,
            topic=ctx.topic,
            research_package=research_pkg,
        )

        # 3. Write canonical story_package.json
        write_json(story_out, story_pkg.model_dump())
        log.info("[thesis] wrote story_package.json  thesis=%s  titles=%d",
                 story_pkg.thesis.selected_id,
                 len(story_pkg.title.candidates))

        # 4. Write legacy thesis.json for downstream compatibility
        thesis_legacy = story_pkg.to_legacy_thesis()
        write_json(stage_path(ctx.job_id, "thesis"), thesis_legacy)

        return story_pkg.model_dump()
