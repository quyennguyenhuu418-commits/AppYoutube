"""Animation Engine — public surface.

PROMPT 7 — Animation Engine & Motion Runtime.

Exports:
    Schemas: AnimationPlan and all sub-models (see `schemas`).
    Compiler: AnimationCompiler (validate → normalize → resolve → compile).
    Builder: AnimationPlanBuilder (storyboard → AnimationPlan).
    Action Mapper: map_action, apply_action_to_character.
    Interpolation: interpolate_value, interpolate_keyframes, lerp, easings.
"""
from __future__ import annotations

from app.animation.action_mapper import apply_action_to_character, map_action
from app.animation.builder import AnimationPlanBuilder
from app.animation.compiler import (
    AnimationCompileError,
    AnimationCompiler,
    compiler_from_packages,
)
from app.animation.interpolation import (
    ease_in_cubic,
    ease_in_out_cubic,
    ease_out_cubic,
    interpolate_keyframes,
    interpolate_value,
    lerp,
)
from app.animation.schemas import (
    ActionLabel,
    AnimationEvent,
    AnimationPlan,
    AnimationPlanMetadata,
    AnimationTarget,
    AnimationTrack,
    CameraAnimation,
    CameraProperty,
    CharacterAnimation,
    Interpolation,
    Keyframe,
    PoseSegment,
    PoseTransition,
    PropAnimation,
    PropInteraction,
    TargetKind,
    TransformProperty,
    WalkCycleParams,
)

__all__ = [
    # Schemas
    "ActionLabel",
    "AnimationEvent",
    "AnimationPlan",
    "AnimationPlanMetadata",
    "AnimationTarget",
    "AnimationTrack",
    "CameraAnimation",
    "CameraProperty",
    "CharacterAnimation",
    "Interpolation",
    "Keyframe",
    "PoseSegment",
    "PoseTransition",
    "PropAnimation",
    "PropInteraction",
    "TargetKind",
    "TransformProperty",
    "WalkCycleParams",
    # Compiler
    "AnimationCompileError",
    "AnimationCompiler",
    "compiler_from_packages",
    # Builder
    "AnimationPlanBuilder",
    # Action mapper
    "apply_action_to_character",
    "map_action",
    # Interpolation
    "ease_in_cubic",
    "ease_in_out_cubic",
    "ease_out_cubic",
    "interpolate_keyframes",
    "interpolate_value",
    "lerp",
]
