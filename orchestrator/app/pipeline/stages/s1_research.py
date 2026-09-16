"""
Stage 1: research — the Research Intelligence Engine.

This stage runs the full research pipeline:
  1. Question decomposition
  2. Source search (DuckDuckGo or mock)
  3. Content fetch and scoring
  4. Source deduplication
  5. Claim extraction
  6. Claim-source graph
  7. Contradiction detection
  8. Uncertainty modeling
  9. Timeline building
 10. Visual opportunity extraction
 11. Story opportunity extraction
 12. Synthesis
 13. Quality scoring

Outputs:
- workspace/{job_id}/research.json      — backward-compatible, consumed by downstream stages
- workspace/{job_id}/research_package.json — full rich ResearchPackage
- workspace/{job_id}/research.log      — structured event log
- workspace/{job_id}/research_cache/    — hash-keyed cache
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import stage_path, write_json
from app.pipeline.cache import should_skip
from app.pipeline.stages.base import Stage, StageContext
from app.research.engine import ResearchEngine

log = get_logger(__name__)


class ResearchStage(Stage):
    name = "research"
    label = "Nghiên cứu"

    def run(self, ctx: StageContext) -> dict:
        """
        Run the Research Intelligence Engine for the given topic.

        Returns a backward-compatible dict matching the old ResearchPackage schema
        so downstream stages continue to work without modification.
        """
        out = stage_path(ctx.job_id, "research")
        if should_skip(out):
            log.info("[%s] cached, skipping", self.name)
            # Load and return the cached full package
            from app.core.paths import read_json
            return read_json(out)

        log.info("[%s] running Research Intelligence Engine for topic: %s", self.name, ctx.topic)

        # Determine whether to use mock providers
        use_mock = not settings.has_openai

        engine = ResearchEngine(job_id=ctx.job_id, use_mock=use_mock)
        pkg = engine.run(ctx.topic)

        log.info(
            "[%s] complete: %d sources, %d claims, %d contradictions, quality=%.3f",
            self.name,
            len(pkg.sources),
            len(pkg.claims),
            len(pkg.contradictions),
            pkg.quality_score.overall_score,
        )

        # Write the backward-compatible dict for downstream stages
        legacy = pkg.to_legacy_dict()
        write_json(out, legacy)

        return legacy
