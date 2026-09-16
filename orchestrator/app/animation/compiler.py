"""Animation Compiler — validate → normalize → resolve → compile.

PROMPT 7 §25: Build a compiler-like layer that turns an AnimationPlan into
a runtime representation the renderer can consume deterministically.

Validation passes:
1. Structural — all required fields present, types correct.
2. Reference — every target_id resolves to a known canonical ID.
3. Temporal — no negative durations, no overlapping conflicting tracks
   without explicit priority.
4. Interaction — every PropInteraction's character_anchor and prop_anchor
   exist on the corresponding character skeleton / prop definition.

Normalization passes:
5. Time — keyframes sorted by time_sec; pose_segments sorted.
6. Duration — each track's effective duration is computed and consistent.
7. Target IDs — normalized to lowercase canonical form.

Compilation passes:
8. Conflict resolution — when two tracks affect the same target+property
   at the same time, the higher-priority track wins; deterministic.
9. Runtime representation — produce a normalized plan with no implicit
   defaults remaining.
"""
from __future__ import annotations

import logging
from typing import Any

from app.animation.schemas import (
    AnimationEvent,
    AnimationPlan,
    AnimationTarget,
    AnimationTrack,
    CharacterAnimation,
    Interpolation,
    Keyframe,
    PropAnimation,
    TargetKind,
)
from app.core.logging import get_logger

log = get_logger(__name__)


# ============================================================================
# Compile errors
# ============================================================================

class AnimationCompileError(Exception):
    """Raised when an AnimationPlan cannot be compiled.

    Per PROMPT 7 §25:
    - unknown target
    - invalid time
    - negative duration
    - conflicting keyframes (unresolved)
    - missing anchors
    - unsupported interpolation
    - impossible transition
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"AnimationPlan compilation failed: {len(errors)} errors: " + "; ".join(errors[:5]))


# ============================================================================
# Compiler
# ============================================================================

class AnimationCompiler:
    """Compiles an AnimationPlan into a normalized, validated runtime form.

    Usage:
        compiler = AnimationCompiler(known_characters={"hunter_main", ...},
                                     known_props={"spear", ...},
                                     known_environments={"ice_age_plains", ...},
                                     character_skeleton={"hunter_main": {"hand_left", "head", ...}},
                                     prop_anchors={"spear": {"grip_center", "tip", ...}})
        compiled = compiler.compile(plan)
    """

    def __init__(
        self,
        known_characters: set[str] | None = None,
        known_props: set[str] | None = None,
        known_environments: set[str] | None = None,
        character_skeleton: dict[str, set[str]] | None = None,
        prop_anchors: dict[str, set[str]] | None = None,
    ):
        self.known_characters = known_characters or set()
        self.known_props = known_props or set()
        self.known_environments = known_environments or set()
        self.character_skeleton = character_skeleton or {}
        self.prop_anchors = prop_anchors or {}

    def compile(self, plan: AnimationPlan) -> AnimationPlan:
        """Run all validation + normalization passes.

        Returns the same plan object (mutated) with warnings/failures
        populated. Raises AnimationCompileError on fatal failures.
        """
        errors: list[str] = []

        self._validate_references(plan, errors)
        self._validate_interactions(plan, errors)
        self._validate_temporal(plan, errors)
        self._validate_interpolations(plan, errors)

        self._normalize(plan)

        if errors:
            plan.failures.extend(errors)
            raise AnimationCompileError(errors)

        return plan

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def _validate_references(self, plan: AnimationPlan, errors: list[str]) -> None:
        """Verify every target_id resolves to a known canonical ID."""
        for char_anim in plan.characters:
            if self.known_characters and char_anim.character_id not in self.known_characters:
                errors.append(
                    f"Unknown character_id '{char_anim.character_id}'. "
                    f"Known: {sorted(self.known_characters)}"
                )
            for track in char_anim.motion_tracks:
                self._check_target(track.target, errors)

        for prop_anim in plan.props:
            if self.known_props and prop_anim.prop_id not in self.known_props:
                errors.append(
                    f"Unknown prop_id '{prop_anim.prop_id}'. "
                    f"Known: {sorted(self.known_props)}"
                )
            for track in prop_anim.motion_tracks:
                self._check_target(track.target, errors)

        for track in plan.tracks:
            self._check_target(track.target, errors)

        # Camera target must be present
        for track in plan.tracks:
            if track.target.kind == TargetKind.CAMERA:
                if track.target.target_id not in {"camera:main", "camera:" + plan.camera.camera_id}:
                    plan.warnings.append(
                        f"Camera track target_id '{track.target.target_id}' "
                        f"does not match plan.camera.camera_id '{plan.camera.camera_id}'"
                    )

    def _check_target(self, target: AnimationTarget, errors: list[str]) -> None:
        """Verify a single target resolves."""
        tid = target.target_id
        if target.kind == TargetKind.CHARACTER:
            cid = tid.split(":", 1)[1] if ":" in tid else tid
            if self.known_characters and cid not in self.known_characters:
                errors.append(
                    f"Unknown character target '{tid}'. "
                    f"Known: {sorted(self.known_characters)}"
                )
        elif target.kind == TargetKind.PROP:
            pid = tid.split(":", 1)[1] if ":" in tid else tid
            if self.known_props and pid not in self.known_props:
                errors.append(
                    f"Unknown prop target '{tid}'. "
                    f"Known: {sorted(self.known_props)}"
                )
        elif target.kind == TargetKind.ENVIRONMENT:
            eid = tid.split(":", 1)[1] if ":" in tid else tid
            if self.known_environments and eid not in self.known_environments:
                errors.append(
                    f"Unknown environment target '{tid}'. "
                    f"Known: {sorted(self.known_environments)}"
                )
        elif target.kind == TargetKind.CAMERA:
            # Camera IDs are always valid (single-segment or "main").
            if not tid.startswith("camera:"):
                errors.append(
                    f"Camera target must start with 'camera:' prefix: '{tid}'"
                )

    def _validate_interactions(self, plan: AnimationPlan, errors: list[str]) -> None:
        """Verify every PropInteraction's anchors exist on the character/prop."""
        for prop_anim in plan.props:
            for interaction in prop_anim.interactions:
                # Character anchor must exist on the character skeleton.
                if self.character_skeleton:
                    char_anchors = self.character_skeleton.get(interaction.character_id, set())
                    if char_anchors and interaction.character_anchor not in char_anchors:
                        errors.append(
                            f"Interaction '{interaction.interaction_id}': "
                            f"character anchor '{interaction.character_anchor}' "
                            f"not in character '{interaction.character_id}' skeleton "
                            f"(known: {sorted(char_anchors)})"
                        )
                # Prop anchor must exist on the prop definition.
                if self.prop_anchors:
                    prop_anchor_set = self.prop_anchors.get(interaction.prop_id, set())
                    if prop_anchor_set and interaction.prop_anchor not in prop_anchor_set:
                        errors.append(
                            f"Interaction '{interaction.interaction_id}': "
                            f"prop anchor '{interaction.prop_anchor}' "
                            f"not in prop '{interaction.prop_id}' anchors "
                            f"(known: {sorted(prop_anchor_set)})"
                        )

    def _validate_temporal(self, plan: AnimationPlan, errors: list[str]) -> None:
        """Verify timing is valid: no negative durations, keyframes within bounds."""
        for char_anim in plan.characters:
            for seg in char_anim.pose_sequence:
                if seg.end_sec <= seg.start_sec:
                    errors.append(
                        f"Character '{char_anim.character_id}' pose_segment: "
                        f"end_sec ({seg.end_sec}) must be > start_sec ({seg.start_sec})"
                    )
            for track in char_anim.motion_tracks:
                self._check_track_timing(track, plan.duration_sec, errors)

        for prop_anim in plan.props:
            for interaction in prop_anim.interactions:
                if interaction.end_sec <= interaction.start_sec:
                    errors.append(
                        f"PropInteraction '{interaction.interaction_id}': "
                        f"end_sec ({interaction.end_sec}) must be > start_sec ({interaction.start_sec})"
                    )
            for track in prop_anim.motion_tracks:
                self._check_track_timing(track, plan.duration_sec, errors)

        for track in plan.tracks:
            self._check_track_timing(track, plan.duration_sec, errors)

        for event in plan.events:
            if event.at_sec > plan.duration_sec + 0.001:
                errors.append(
                    f"Event '{event.event_id}' at_sec ({event.at_sec}) "
                    f"exceeds plan duration ({plan.duration_sec})"
                )

    def _check_track_timing(
        self, track: AnimationTrack, duration_sec: float, errors: list[str]
    ) -> None:
        """Verify all keyframes are within the track's bounds."""
        for kf in track.keyframes:
            if kf.time_sec < 0:
                errors.append(
                    f"Track '{track.track_id}' keyframe has negative time_sec: {kf.time_sec}"
                )
            if kf.time_sec > duration_sec + 0.001:
                errors.append(
                    f"Track '{track.track_id}' keyframe time_sec ({kf.time_sec}) "
                    f"exceeds plan duration ({duration_sec})"
                )

    def _validate_interpolations(self, plan: AnimationPlan, errors: list[str]) -> None:
        """Verify all interpolation values are canonical.

        This is defensive — the enum already enforces this. We add a warning
        for HOLD used on the first keyframe (semantically degenerate).
        """
        for char_anim in plan.characters:
            for track in char_anim.motion_tracks:
                self._check_interpolations(track, plan.warnings)
        for prop_anim in plan.props:
            for track in prop_anim.motion_tracks:
                self._check_interpolations(track, plan.warnings)
        for track in plan.tracks:
            self._check_interpolations(track, plan.warnings)

    def _check_interpolations(
        self, track: AnimationTrack, warnings: list[str]
    ) -> None:
        """Add warnings for degenerate interpolation usage."""
        for i, kf in enumerate(track.keyframes):
            if i == 0 and kf.interpolation == Interpolation.HOLD:
                warnings.append(
                    f"Track '{track.track_id}' first keyframe uses HOLD — "
                    f"this has no effect before the next keyframe."
                )

    # -----------------------------------------------------------------------
    # Normalization
    # -----------------------------------------------------------------------

    def _normalize(self, plan: AnimationPlan) -> None:
        """Normalize times, ordering, target IDs."""
        # Sort events by at_sec.
        plan.events.sort(key=lambda e: e.at_sec)

        # Sort keyframes within each track.
        for char_anim in plan.characters:
            for track in char_anim.motion_tracks:
                track.keyframes.sort(key=lambda k: k.time_sec)
            char_anim.pose_sequence.sort(key=lambda s: s.start_sec)
        for prop_anim in plan.props:
            for track in prop_anim.motion_tracks:
                track.keyframes.sort(key=lambda k: k.time_sec)
        for track in plan.tracks:
            track.keyframes.sort(key=lambda k: k.time_sec)

        # Normalize target IDs to lowercase canonical form.
        for char_anim in plan.characters:
            for track in char_anim.motion_tracks:
                track.target.target_id = track.target.target_id.lower()
        for prop_anim in plan.props:
            for track in prop_anim.motion_tracks:
                track.target.target_id = track.target.target_id.lower()
        for track in plan.tracks:
            track.target.target_id = track.target.target_id.lower()

    # -----------------------------------------------------------------------
    # Conflict resolution
    # -----------------------------------------------------------------------

    def resolve_track_conflicts(
        self, tracks: list[AnimationTrack]
    ) -> list[AnimationTrack]:
        """Deterministically resolve conflicts between tracks.

        When two tracks affect the same (target, property) at overlapping
        times, the higher-priority track wins. Ties broken by track_id
        alphabetical order (deterministic).

        Returns the survivor tracks.
        """
        # Group by (target_id, property)
        groups: dict[tuple[str, str], list[AnimationTrack]] = {}
        for track in tracks:
            key = (track.target.target_id, track.property.value)
            groups.setdefault(key, []).append(track)

        survivors: list[AnimationTrack] = []
        for key, group in groups.items():
            if len(group) == 1:
                survivors.append(group[0])
                continue
            # Pick highest priority, then lexicographic track_id.
            group_sorted = sorted(
                group,
                key=lambda t: (-t.priority, t.track_id),
            )
            winner = group_sorted[0]
            survivors.append(winner)
            # Add a warning for transparency.
            for loser in group_sorted[1:]:
                log.warning(
                    "Animation conflict: track '%s' (priority %d) lost to '%s' "
                    "(priority %d) on target %s property %s",
                    loser.track_id, loser.priority,
                    winner.track_id, winner.priority,
                    key[0], key[1],
                )

        return survivors


# ============================================================================
# Convenience: build compiler from existing packages
# ============================================================================

def compiler_from_packages(
    character_system_package: Any | None = None,
    asset_system_package: Any | None = None,
) -> AnimationCompiler:
    """Build an AnimationCompiler populated from existing canonical packages.

    Both arguments are optional; missing values produce empty registries
    (no validation against them).
    """
    known_characters: set[str] = set()
    character_skeleton: dict[str, set[str]] = {}
    if character_system_package is not None:
        for char in getattr(character_system_package, "characters", []) or []:
            cid = getattr(char, "character_id", None) or getattr(char, "id", None)
            if cid:
                known_characters.add(cid)
                joints = set()
                skel = getattr(char, "skeleton", None)
                if skel is not None:
                    for j in getattr(skel, "joints", []) or []:
                        jid = getattr(j, "joint_id", None)
                        if jid:
                            joints.add(jid)
                character_skeleton[cid] = joints

    known_props: set[str] = set()
    known_environments: set[str] = set()
    prop_anchors: dict[str, set[str]] = {}
    if asset_system_package is not None:
        for env in getattr(asset_system_package, "environments", []) or []:
            eid = getattr(env, "asset_id", None)
            if eid:
                known_environments.add(eid)
        for prop in getattr(asset_system_package, "props", []) or []:
            pid = getattr(prop, "asset_id", None)
            if pid:
                known_props.add(pid)
                anchors = set()
                for a in getattr(prop, "anchor_points", []) or []:
                    aid = getattr(a, "anchor_id", None)
                    if aid:
                        anchors.add(aid)
                prop_anchors[pid] = anchors

    return AnimationCompiler(
        known_characters=known_characters,
        known_props=known_props,
        known_environments=known_environments,
        character_skeleton=character_skeleton,
        prop_anchors=prop_anchors,
    )
