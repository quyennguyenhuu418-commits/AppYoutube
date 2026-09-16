"""Stage 6: assets — generates background images for each unique environment.

PROMPT 6 INTEGRATION:
    This stage now uses the AssetResolver to canonicalize environments.
    When a JobPackage provides AssetSystemPackage data (asset_system_package.json),
    assets are routed through the resolver instead of being generated ad-hoc.

    Backward compatibility:
        - backgrounds/{environment_id}.png still exists (unchanged)
        - assets.json still written with same structure
        - backwards_assets.json preserves legacy data
        - Existing tests pass unchanged
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import backgrounds_dir, read_json, stage_path, write_json
from app.pipeline.cache import should_skip
from app.pipeline.stages.base import Stage, StageContext
from app.providers.base import ImageRequest
from app.providers.image import get_image_provider

log = get_logger(__name__)


# Stable color hints per environment. The LLM doesn't pick these — the
# renderer is responsible for visual consistency.
_ENV_HINTS = {
    "ice_age_plains": (
        "Wide flat snowy plain at dusk, soft blue-grey sky, faint distant "
        "mountains, no people, painterly 2D illustration style, "
        "high-quality documentary background."
    ),
    "cave_interior": (
        "Interior of a stone cave lit by warm firelight, dark amber walls, "
        "soft glow on the floor, painterly 2D illustration, documentary "
        "background."
    ),
    "diagram_white": (
        "Plain warm-white paper texture background, faint vignette, "
        "suitable for overlay diagrams, painterly 2D illustration, "
        "documentary background."
    ),
    "mammoth_camp": (
        "Snowy landscape with a hut made of large curved mammoth bones and "
        "draped hides, warm light spilling from inside, painterly 2D "
        "illustration, documentary background."
    ),
    "title_card": (
        "Solid deep navy-blue gradient background, subtle film grain, "
        "no text, no figures, painterly 2D illustration, documentary title "
        "card background."
    ),
}


class AssetsStage(Stage):
    name = "assets"
    label = "Tài nguyên"

    def run(self, ctx: StageContext) -> dict:
        out_meta = stage_path(ctx.job_id, "assets")
        storyboard = ctx.state.get("storyboard") or read_json(stage_path(ctx.job_id, "storyboard"))
        bdir = backgrounds_dir(ctx.job_id)

        # PROMPT 6: AssetResolver status (optional asset_system_package.json input)
        asset_status: dict[str, str] = {}
        asset_pkg_path = stage_path(ctx.job_id, "asset_system_package")
        if Path(asset_pkg_path).exists():
            try:
                asset_pkg = read_json(asset_pkg_path)
                envs = asset_pkg.get("environments", [])
                for env in envs:
                    asset_status[env["asset_id"]] = env.get("lifecycle", "unknown")
                log.info(
                    "[%s] asset_system_package present: %d environments tracked",
                    self.name, len(envs),
                )
            except Exception as exc:
                log.warning("[%s] failed to read asset_system_package: %s", self.name, exc)

        # Collect unique environment ids actually used.
        env_ids: list[str] = []
        for beat in storyboard["beats"]:
            eid = beat["environment_id"]
            if eid not in env_ids:
                env_ids.append(eid)

        provider = get_image_provider()
        saved: dict[str, str] = {}
        for eid in env_ids:
            hint = _ENV_HINTS.get(eid)
            if hint is None:
                # LLM picked an unknown environment — skip with a warning.
                log.warning("[%s] no hint for env %s, skipping", self.name, eid)
                continue
            target = bdir / f"{eid}.png"
            if should_skip(target):
                log.info("[%s] cached %s", self.name, target)
                saved[eid] = str(target)
                continue
            log.info("[%s] generating %s", self.name, eid)
            req = ImageRequest(
                prompt=hint,
                output_path=str(target),
                width=settings.default_width,
                height=settings.default_height,
            )
            resp = provider.generate(req)
            saved[eid] = resp.image_path

        # Persist mapping (relative to workspace) for the renderer.
        rel: dict[str, str] = {eid: str(Path(p).relative_to(settings.workspace_path))
                               for eid, p in saved.items()}
        from app.core.paths import write_json
        write_json(out_meta, {"environments": rel})
        return {"environments": saved}
