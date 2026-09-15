"""Character Intelligence Engine — produces canonical character identities,
asset packages, pose/expression libraries, and continuity metadata
from StoryboardPackage CharacterRequirements."""
from __future__ import annotations

from app.character.cache import CharacterCache
from app.character.engine import (
    CharacterSystemEngine,
    build_all_expressions,
    build_all_poses,
    build_character_definition,
    build_character_instance,
    build_default_skeleton,
    build_default_wardrobe,
    build_registry_entry,
    character_identity_key,
    map_action_to_pose,
    map_expression_to_label,
    score_character,
)
from app.character.svg_generator import (
    compute_svg_hash,
    generate_character_preview_svg,
    generate_expression_svg,
    generate_pose_svg,
    validate_svg,
)

__all__ = [
    "CharacterCache",
    "CharacterSystemEngine",
    "build_all_expressions",
    "build_all_poses",
    "build_character_definition",
    "build_character_instance",
    "build_default_skeleton",
    "build_default_wardrobe",
    "build_registry_entry",
    "character_identity_key",
    "compute_svg_hash",
    "generate_character_preview_svg",
    "generate_expression_svg",
    "generate_pose_svg",
    "map_action_to_pose",
    "map_expression_to_label",
    "score_character",
    "validate_svg",
]
