"""
Knowledge Camera/Motion/Sound Adapter — thin adapter for L-U6.

L-U6 — Camera + Motion + Sound Compiler.

Purpose
-------
This adapter consumes `KnowledgeContext` (L-U3) and produces structured
camera, motion, and sound knowledge for the `CameraMotionSoundCompiler`.

Architecture
-----------
    KnowledgeContext (L-U3)
            ↓
    KnowledgeResolver (L-U3)
            ↓
    KnowledgeCameraMotionSoundAdapter (L-U6 — thin)
            ↓
    ResolvedCameraMotionSoundKnowledge
            ↓
    CameraMotionSoundCompiler (L-U6)
            ↓
    CameraMotionSoundCompilationResult

Design principles
---------------
1. THIN adapter — all resolution goes through `KnowledgeResolver`.
   No direct registry access.
2. PROVIDER-NEUTRAL — produces structured guidance, NOT provider syntax.
3. OPTIONAL — if no `KnowledgeContext`, returns empty/defaults.

What this adapter does NOT do:
    - Generate actual camera/motion/sound
    - Call image/video generation providers
    - Mutate the KnowledgeRegistry
    - Make decisions about semantic semantics (that's the compiler's job)
"""

from __future__ import annotations

from typing import Any, FrozenSet, Optional

from app.knowledge import (
    FallbackPolicy,
    KnowledgeContext,
    KnowledgeDomain,
    KnowledgeQuery,
    KnowledgeRegistry,
    KnowledgeResolver,
    KnowledgeResult,
)
from app.knowledge.result import KnowledgeProvenance


# ============================================================================
# Resolved knowledge — structured output
# ============================================================================


class ResolvedCameraKnowledge:
    """Camera knowledge resolved from CAMERA domain."""

    __slots__ = (
        "shot_type", "movement", "framing", "subject_relationship",
        "movement_direction", "intensity", "duration_sec", "rules",
        "knowledge_ids", "provenance_list", "is_active",
    )

    def __init__(
        self,
        shot_type: Optional[str] = None,
        movement: Optional[str] = None,
        framing: Optional[str] = None,
        subject_relationship: Optional[str] = None,
        movement_direction: Optional[str] = None,
        intensity: Optional[str] = None,
        duration_sec: Optional[float] = None,
        rules: Optional[list[str]] = None,
        knowledge_ids: Optional[FrozenSet[str]] = None,
        provenance_list: Optional[list[KnowledgeProvenance]] = None,
        is_active: bool = False,
    ) -> None:
        self.shot_type = shot_type
        self.movement = movement
        self.framing = framing
        self.subject_relationship = subject_relationship
        self.movement_direction = movement_direction
        self.intensity = intensity
        self.duration_sec = duration_sec
        self.rules = rules or []
        self.knowledge_ids = knowledge_ids or frozenset()
        self.provenance_list = provenance_list or []
        self.is_active = is_active

    @property
    def primary_provenance(self) -> Optional[KnowledgeProvenance]:
        return self.provenance_list[0] if self.provenance_list else None


class ResolvedMotionKnowledge:
    """Motion knowledge resolved from MOTION / CAMERA_MOVEMENT domain."""

    __slots__ = (
        "pattern", "subject_action", "direction", "intensity",
        "duration_sec", "loop", "rules", "knowledge_ids",
        "provenance_list", "is_active",
    )

    def __init__(
        self,
        pattern: Optional[str] = None,
        subject_action: Optional[str] = None,
        direction: Optional[str] = None,
        intensity: Optional[str] = None,
        duration_sec: Optional[float] = None,
        loop: bool = False,
        rules: Optional[list[str]] = None,
        knowledge_ids: Optional[FrozenSet[str]] = None,
        provenance_list: Optional[list[KnowledgeProvenance]] = None,
        is_active: bool = False,
    ) -> None:
        self.pattern = pattern
        self.subject_action = subject_action
        self.direction = direction
        self.intensity = intensity
        self.duration_sec = duration_sec
        self.loop = loop
        self.rules = rules or []
        self.knowledge_ids = knowledge_ids or frozenset()
        self.provenance_list = provenance_list or []
        self.is_active = is_active

    @property
    def primary_provenance(self) -> Optional[KnowledgeProvenance]:
        return self.provenance_list[0] if self.provenance_list else None


class ResolvedSoundKnowledge:
    """Sound knowledge resolved from SOUND domain."""

    __slots__ = (
        "category", "description", "layers", "duck_under_narration",
        "rules", "knowledge_ids", "provenance_list", "is_active",
    )

    def __init__(
        self,
        category: Optional[str] = None,
        description: Optional[str] = None,
        layers: Optional[list[dict[str, Any]]] = None,
        duck_under_narration: bool = False,
        rules: Optional[list[str]] = None,
        knowledge_ids: Optional[FrozenSet[str]] = None,
        provenance_list: Optional[list[KnowledgeProvenance]] = None,
        is_active: bool = False,
    ) -> None:
        self.category = category
        self.description = description
        self.layers = layers or []
        self.duck_under_narration = duck_under_narration
        self.rules = rules or []
        self.knowledge_ids = knowledge_ids or frozenset()
        self.provenance_list = provenance_list or []
        self.is_active = is_active

    @property
    def primary_provenance(self) -> Optional[KnowledgeProvenance]:
        return self.provenance_list[0] if self.provenance_list else None


class ResolvedCameraMotionSoundKnowledge:
    """Complete camera/motion/sound knowledge resolved from the Knowledge Layer."""

    __slots__ = (
        "camera", "motion", "sound", "is_active",
        "knowledge_ids", "registry_version",
    )

    def __init__(
        self,
        camera: Optional[ResolvedCameraKnowledge] = None,
        motion: Optional[ResolvedMotionKnowledge] = None,
        sound: Optional[ResolvedSoundKnowledge] = None,
        is_active: bool = False,
        knowledge_ids: Optional[FrozenSet[str]] = None,
        registry_version: str = "no-knowledge",
    ) -> None:
        self.camera = camera or ResolvedCameraKnowledge()
        self.motion = motion or ResolvedMotionKnowledge()
        self.sound = sound or ResolvedSoundKnowledge()
        self.is_active = is_active
        self.knowledge_ids = knowledge_ids or frozenset()
        self.registry_version = registry_version

    def all_knowledge_ids(self) -> list[str]:
        all_ids: list[str] = []
        all_ids.extend(self.camera.knowledge_ids)
        all_ids.extend(self.motion.knowledge_ids)
        all_ids.extend(self.sound.knowledge_ids)
        return all_ids


# ============================================================================
# The adapter
# ============================================================================


class KnowledgeCameraMotionSoundAdapter:
    """Thin adapter: Knowledge Layer → CameraMotionSoundCompiler.

    Construction:
        ctx = KnowledgeContext.from_registry(registry)
        adapter = KnowledgeCameraMotionSoundAdapter(context=ctx)

        # No-knowledge path (backward compatible):
        adapter = KnowledgeCameraMotionSoundAdapter()  # or None

    Usage:
        knowledge = adapter.resolve_for_compilation(prompt_kind=PromptKind.VIDEO)
    """

    def __init__(
        self,
        registry: Optional[KnowledgeRegistry] = None,
        *,
        context: Optional[KnowledgeContext] = None,
    ) -> None:
        if context is not None:
            self._context = context
        elif registry is not None:
            self._context = _build_context_from_registry(registry)
        else:
            self._context = KnowledgeContext.disabled(name="cms-no-knowledge")

        self._resolver: KnowledgeResolver = self._context.resolver

    def is_active(self) -> bool:
        return self._resolver.is_active()

    @property
    def context(self) -> KnowledgeContext:
        return self._context

    def resolve_for_compilation(
        self,
        prompt_kind: str,
    ) -> ResolvedCameraMotionSoundKnowledge:
        """Resolve camera/motion/sound knowledge from the Knowledge Layer.

        Parameters:
            prompt_kind: 'image' or 'video'

        Returns:
            A ResolvedCameraMotionSoundKnowledge bundle.
        """
        all_ids: list[str] = []

        # 1. Resolve CAMERA
        camera_results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.CAMERA)
        )
        all_ids.extend(r.knowledge_id for r in camera_results)
        camera = self._build_camera_knowledge(camera_results)

        # 2. Resolve MOTION
        motion_results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.MOTION)
        )
        all_ids.extend(r.knowledge_id for r in motion_results)
        motion = self._build_motion_knowledge(motion_results)

        # 3. Resolve CAMERA_MOVEMENT
        cam_movement_results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.CAMERA_MOVEMENT)
        )
        all_ids.extend(r.knowledge_id for r in cam_movement_results)
        # Merge camera movement into camera knowledge
        camera = self._merge_camera_movement(camera, cam_movement_results)

        # 4. Resolve SOUND
        sound_results = self._resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.SOUND)
        )
        all_ids.extend(r.knowledge_id for r in sound_results)
        sound = self._build_sound_knowledge(sound_results)

        return ResolvedCameraMotionSoundKnowledge(
            camera=camera,
            motion=motion,
            sound=sound,
            is_active=self.is_active(),
            knowledge_ids=frozenset(all_ids),
            registry_version=(
                self._resolver.registry_version
                if self.is_active()
                else "no-knowledge"
            ),
        )

    # ------------------------------------------------------------------
    # Camera knowledge builder
    # ------------------------------------------------------------------

    def _build_camera_knowledge(
        self, results: list[KnowledgeResult]
    ) -> ResolvedCameraKnowledge:
        if not results:
            return ResolvedCameraKnowledge()

        shot_type: Optional[str] = None
        framing: Optional[str] = None
        subject_relationship: Optional[str] = None
        rules: list[str] = []
        provenance_list: list[KnowledgeProvenance] = []

        for r in results:
            if r.provenance:
                provenance_list.append(r.provenance)
            for rule in r.rules:
                rules.append(rule)
                lower = rule.lower()
                # Shot types
                if "extreme wide" in lower or "ews" in lower:
                    shot_type = "extreme_wide"
                elif "wide" in lower and "medium" not in lower:
                    shot_type = "wide"
                elif "medium" in lower and "close" not in lower:
                    shot_type = "medium"
                elif "close" in lower and "extreme" not in lower:
                    shot_type = "close"
                elif "extreme close" in lower or "ecu" in lower:
                    shot_type = "extreme_close"
                elif "pov" in lower or "point of view" in lower:
                    shot_type = "pov"
                elif "bird" in lower:
                    shot_type = "birds_eye"
                elif "worm" in lower:
                    shot_type = "worms_eye"
                elif "dutch" in lower or "tilt" in lower:
                    shot_type = "dutch"
                elif "over shoulder" in lower or "ots" in lower:
                    shot_type = "over_shoulder"
                # Framing
                if "rule of third" in lower:
                    framing = "rule_of_thirds"
                elif "golden" in lower:
                    framing = "golden_ratio"
                elif "center" in lower:
                    framing = "center"
                # Subject relationship
                if "pov" in lower or "point of view" in lower:
                    subject_relationship = "pov"

        return ResolvedCameraKnowledge(
            shot_type=shot_type,
            framing=framing,
            subject_relationship=subject_relationship,
            rules=rules,
            knowledge_ids=frozenset(r.knowledge_id for r in results),
            provenance_list=provenance_list,
            is_active=True,
        )

    def _merge_camera_movement(
        self,
        camera: ResolvedCameraKnowledge,
        results: list[KnowledgeResult],
    ) -> ResolvedCameraKnowledge:
        if not results:
            return camera

        movement: Optional[str] = None
        direction: Optional[str] = None
        intensity: Optional[str] = None
        duration: Optional[float] = None
        provenance_list: list[KnowledgeProvenance] = list(camera.provenance_list)
        rules = list(camera.rules)

        for r in results:
            if r.provenance:
                provenance_list.append(r.provenance)
            for rule in r.rules:
                rules.append(rule)
                lower = rule.lower()
                # Movements
                if "push" in lower or "dolly forward" in lower:
                    movement = "push_in"
                    direction = "forward"
                elif "pull" in lower or "dolly back" in lower:
                    movement = "pull_out"
                    direction = "backward"
                elif "pan" in lower:
                    movement = "pan"
                    if "left" in lower:
                        direction = "left"
                    elif "right" in lower:
                        direction = "right"
                elif "tilt" in lower:
                    movement = "tilt"
                    if "up" in lower:
                        direction = "up"
                    elif "down" in lower:
                        direction = "down"
                elif "zoom" in lower:
                    movement = "zoom"
                elif "tracking" in lower or "follow" in lower:
                    movement = "tracking"
                elif "hold" in lower or "static" in lower:
                    movement = "hold"
                elif "shake" in lower:
                    movement = "shake"
                elif "orbit" in lower:
                    movement = "orbit"
                # Intensity
                if "slow" in lower:
                    intensity = "low"
                elif "fast" in lower or "quick" in lower:
                    intensity = "high"
                elif "medium" in lower or "cinematic" in lower:
                    intensity = "medium"
                # Duration
                for tok in rule.split():
                    try:
                        val = float(tok)
                        if 0 < val <= 300:
                            duration = val
                    except ValueError:
                        pass

        return ResolvedCameraKnowledge(
            shot_type=camera.shot_type,
            movement=camera.movement or movement,
            framing=camera.framing,
            subject_relationship=camera.subject_relationship,
            movement_direction=direction or camera.movement_direction,
            intensity=intensity or camera.intensity,
            duration_sec=duration or camera.duration_sec,
            rules=rules,
            knowledge_ids=camera.knowledge_ids | frozenset(r.knowledge_id for r in results),
            provenance_list=provenance_list,
            is_active=True,
        )

    # ------------------------------------------------------------------
    # Motion knowledge builder
    # ------------------------------------------------------------------

    def _build_motion_knowledge(
        self, results: list[KnowledgeResult]
    ) -> ResolvedMotionKnowledge:
        if not results:
            return ResolvedMotionKnowledge()

        pattern: Optional[str] = None
        subject_action: Optional[str] = None
        direction: Optional[str] = None
        intensity: Optional[str] = None
        duration: Optional[float] = None
        loop: bool = False
        rules: list[str] = []
        provenance_list: list[KnowledgeProvenance] = []

        for r in results:
            if r.provenance:
                provenance_list.append(r.provenance)
            for rule in r.rules:
                rules.append(rule)
                lower = rule.lower()
                # Motion patterns
                if "frame" in lower and "by" in lower:
                    pattern = "frame_by_frame"
                elif "loop" in lower:
                    pattern = "loop"
                    loop = True
                elif "rig" in lower or "pose" in lower:
                    pattern = "rig_pose_interpolation"
                elif "kinetic" in lower or "text" in lower:
                    pattern = "kinetic_text"
                elif "shake" in lower or "nervous" in lower:
                    pattern = "shake_nervous"
                # Subject actions
                if "walk" in lower:
                    subject_action = "walk"
                elif "run" in lower:
                    subject_action = "run"
                elif "gesture" in lower:
                    subject_action = "gesture"
                elif "point" in lower:
                    subject_action = "point"
                elif "think" in lower:
                    subject_action = "think"
                elif "celebrate" in lower:
                    subject_action = "celebrate"
                elif "idle" in lower or "stand" in lower:
                    subject_action = "idle"
                # Direction
                if "left" in lower:
                    direction = "left"
                elif "right" in lower:
                    direction = "right"
                elif "forward" in lower:
                    direction = "forward"
                elif "backward" in lower:
                    direction = "backward"
                # Intensity
                if "slow" in lower:
                    intensity = "low"
                elif "fast" in lower or "quick" in lower:
                    intensity = "high"
                elif "medium" in lower:
                    intensity = "medium"
                # Duration
                for tok in rule.split():
                    try:
                        val = float(tok)
                        if 0 < val <= 300:
                            duration = val
                    except ValueError:
                        pass

        return ResolvedMotionKnowledge(
            pattern=pattern,
            subject_action=subject_action,
            direction=direction,
            intensity=intensity,
            duration_sec=duration,
            loop=loop,
            rules=rules,
            knowledge_ids=frozenset(r.knowledge_id for r in results),
            provenance_list=provenance_list,
            is_active=True,
        )

    # ------------------------------------------------------------------
    # Sound knowledge builder
    # ------------------------------------------------------------------

    def _build_sound_knowledge(
        self, results: list[KnowledgeResult]
    ) -> ResolvedSoundKnowledge:
        if not results:
            return ResolvedSoundKnowledge()

        category: Optional[str] = None
        description: Optional[str] = None
        duck_under: bool = False
        layers: list[dict[str, Any]] = []
        rules: list[str] = []
        provenance_list: list[KnowledgeProvenance] = []

        for r in results:
            if r.provenance:
                provenance_list.append(r.provenance)
            for rule in r.rules:
                rules.append(rule)
                lower = rule.lower()
                # Sound categories
                if "ambient" in lower or "atmosphere" in lower:
                    category = "ambient"
                elif "music" in lower or "score" in lower:
                    category = "music"
                elif "sfx" in lower or "sound effect" in lower:
                    category = "sfx"
                elif "environment" in lower:
                    category = "environment"
                elif "impact" in lower:
                    category = "impact"
                elif "silence" in lower or "silent" in lower:
                    category = "silence"
                # Ducking
                if "duck" in lower or "reduce" in lower or "under narration" in lower:
                    duck_under = True
                # Extract semantic description
                if len(rule) > 10:
                    description = rule

        return ResolvedSoundKnowledge(
            category=category,
            description=description,
            layers=layers,
            duck_under_narration=duck_under,
            rules=rules,
            knowledge_ids=frozenset(r.knowledge_id for r in results),
            provenance_list=provenance_list,
            is_active=True,
        )


# ============================================================================
# Internal helpers
# ============================================================================


def _build_context_from_registry(
    registry: KnowledgeRegistry,
    name: str = "cms-legacy-registry",
) -> KnowledgeContext:
    from app.knowledge.seeds import default_sources

    sources = [
        s for s in default_sources() if s.source_id in registry.sources_loaded
    ]
    return KnowledgeContext.from_registry(
        registry=registry,
        sources=sources,
        name=name,
    )


__all__ = [
    "KnowledgeCameraMotionSoundAdapter",
    "ResolvedCameraMotionSoundKnowledge",
    "ResolvedCameraKnowledge",
    "ResolvedMotionKnowledge",
    "ResolvedSoundKnowledge",
]
