"""Stage 5: storyboard — thin adapter that runs the Storyboard Intelligence Engine.

Responsibilities:
1. Read story_package.json (canonical StoryPackage from s2_thesis).
2. Run the StoryboardEngine to produce a StoryboardPackage (canonical).
3. Write both storyboard_package.json (canonical) and storyboard.json
   (legacy compat for s6_assets / s8_scene_json).
4. Cache invalidation: if the story package changes, storyboard re-runs.

The legacy Storyboard schema is preserved via StoryPackage.to_legacy_storyboard()
for downstream stages that still read storyboard.json.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.core.paths import job_dir, read_json, stage_path, write_json
from app.pipeline.cache import should_skip
from app.pipeline.stages.base import Stage, StageContext
from app.schemas.research_package import ResearchPackage
from app.schemas.story import StoryPackage
from app.schemas.storyboard import StoryboardPackage
from app.storyboard.engine import StoryboardEngine

log = get_logger(__name__)


class StoryboardStage(Stage):
    """Storyboard stage — runs Storyboard Intelligence Engine."""

    name = "storyboard"
    label = "Storyboard"

    def run(self, ctx: StageContext) -> dict:
        out = stage_path(ctx.job_id, "storyboard")
        if should_skip(out):
            log.info("[storyboard] cached storyboard.json found, skipping")
            return read_json(out)

        story_pkg = StoryPackage.model_validate(
            read_json(stage_path(ctx.job_id, "story_package"))
        )

        # Optionally load the canonical ResearchPackage for evidence linking.
        research_pkg: ResearchPackage | None = None
        research_path = stage_path(ctx.job_id, "research_package")
        if research_path.exists():
            try:
                research_pkg = ResearchPackage.model_validate(read_json(research_path))
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "[storyboard] could not load research_package.json for evidence linking: %s",
                    exc,
                )

        # Run the Storyboard Intelligence Engine.
        engine = StoryboardEngine(job_id=ctx.job_id)
        storyboard_pkg = engine.run(
            story_package=story_pkg,
            research_package=research_pkg,
        )

        # Persist the canonical StoryboardPackage.
        sb_path = stage_path(ctx.job_id, "storyboard_package")
        write_json(sb_path, storyboard_pkg.to_dict())

        # Bridge to legacy storyboard.json (for s6_assets, s8_scene_json).
        legacy = story_pkg.to_legacy_storyboard()
        # Augment legacy with the new beat durations if available.
        try:
            for i, beat in enumerate(storyboard_pkg.visual_beats):
                if i < len(legacy.get("beats", [])):
                    legacy["beats"][i]["duration_sec"] = beat.duration
                    legacy["beats"][i]["visual_mode"] = beat.visual_mode.value
                    legacy["beats"][i]["scene_id"] = (
                        beat.scene_definition_candidate.scene_id
                        if beat.scene_definition_candidate
                        else f"scene_{i + 1:03d}"
                    )
        except Exception as exc:  # noqa: BLE001
            log.warning("[storyboard] could not augment legacy beats: %s", exc)
        write_json(out, legacy)

        beat_count = len(storyboard_pkg.visual_beats)
        scene_count = len(storyboard_pkg.scene_definition_candidates)
        quality = storyboard_pkg.storyboard_quality_score
        quality_score = quality.overall_score if quality else 0.0
        log.info(
            "[storyboard] wrote %d beats, %d scene candidates, quality=%.2f",
            beat_count, scene_count, quality_score,
        )
        return legacy
