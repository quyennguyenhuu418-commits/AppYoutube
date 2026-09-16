"""
Stage 9: validate — strict schema check + asset identity integrity.

On failure, we re-run stage 8 once with the error message appended. After
that we raise to surface to the user.

PROMPT 6.5 INTEGRATION:
    This stage now performs deterministic post-generation validation of all
    referenced asset IDs against the canonical registry. Unknown character_ids,
    environment_ids, and prop kinds will fail validation.
"""
from __future__ import annotations

from pydantic import ValidationError

from app.core.logging import get_logger
from app.core.paths import read_json, stage_path, write_json
from app.pipeline.stages.base import Stage, StageContext
from app.schemas.scene_definition import SceneDefinition

log = get_logger(__name__)

# Canonical prop kinds that the renderer supports (from SceneDefinition PropKind)
VALID_PROP_KINDS = {
    "human_silhouette", "cave", "fire", "tree_pine", "snowflake",
    "arrow", "timeline", "chart_axes", "animal_mammoth", "sun",
    "mountain", "question_mark",
}

# Canonical environment IDs that are predefined or registered
# These are populated from asset_system_package.json if present
_CANONICAL_ENVIRONMENTS: set[str] = {
    "ice_age_plains", "cave_interior", "diagram_white",
    "mammoth_camp", "title_card",
}

# Canonical character IDs pattern (snake_case, alphanumeric + underscore)
_CHARACTER_ID_PATTERN = None  # Loaded from character_system_package.json


def _load_asset_registry(job_id: str) -> set[str]:
    """Load known environment IDs from asset_system_package.json."""
    env_ids: set[str] = set()
    asset_pkg_path = stage_path(job_id, "asset_system_package")
    try:
        if asset_pkg_path.exists():
            pkg = read_json(asset_pkg_path)
            for env in pkg.get("environments", []):
                if "asset_id" in env:
                    env_ids.add(env["asset_id"])
    except Exception as exc:
        log.warning("[validate] failed to load asset_system_package: %s", exc)
    return env_ids


def _load_character_ids(job_id: str) -> set[str]:
    """Load known character IDs from character_system_package.json."""
    char_ids: set[str] = set()
    char_pkg_path = stage_path(job_id, "character_system_package")
    try:
        if char_pkg_path.exists():
            pkg = read_json(char_pkg_path)
            for char in pkg.get("characters", []):
                if "character_id" in char:
                    char_ids.add(char["character_id"])
                elif "id" in char:
                    char_ids.add(char["id"])
    except Exception as exc:
        log.warning("[validate] failed to load character_system_package: %s", exc)
    return char_ids


def _validate_asset_integrity(
    sd: SceneDefinition,
    job_id: str,
) -> list[str]:
    """Validate that all referenced assets are canonical and known.

    Returns a list of error messages. Empty list means validation passed.
    """
    errors: list[str] = []

    # Load known assets from registry
    known_envs = _CANONICAL_ENVIRONMENTS | _load_asset_registry(job_id)
    known_chars = _load_character_ids(job_id)

    # Validate character references
    known_char_ids = {c.id for c in sd.characters}
    for scene in sd.scenes:
        for actor in scene.actors:
            if actor.character_id not in known_char_ids:
                # Unknown character in scene - check if it's in the canonical list
                if known_chars and actor.character_id not in known_chars:
                    errors.append(
                        f"Scene '{scene.id}' actor references unknown character "
                        f"'{actor.character_id}'. Known: {sorted(known_chars)}"
                    )

    # Validate environment references
    known_env_ids = {e.id for e in sd.environments}
    for scene in sd.scenes:
        if scene.environment_id not in known_env_ids:
            if known_envs and scene.environment_id not in known_envs:
                errors.append(
                    f"Scene '{scene.id}' references unknown environment "
                    f"'{scene.environment_id}'. Known: {sorted(known_envs)}"
                )

    # Validate prop kinds
    for scene in sd.scenes:
        for prop in scene.props:
            if prop.kind.value not in VALID_PROP_KINDS:
                errors.append(
                    f"Scene '{scene.id}' prop uses unknown kind "
                    f"'{prop.kind.value}'. Valid kinds: {sorted(VALID_PROP_KINDS)}"
                )

    return errors


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

        # PROMPT 6.5: Asset identity integrity check
        asset_errors = _validate_asset_integrity(sd, ctx.job_id)
        if asset_errors:
            error_msg = (
                f"[{self.name}] asset integrity check failed:\n" +
                "\n".join(f"  - {e}" for e in asset_errors)
            )
            log.error(error_msg)
            raise ValueError(error_msg)

        log.info("[%s] OK: %d scenes, %d characters, %d environments, asset IDs verified",
                 self.name, len(sd.scenes), len(sd.characters), len(sd.environments))
        validated = sd.model_dump()
        # Overwrite with normalized output so downstream sees a clean file.
        write_json(path, validated)
        return validated
