"""
CameraMotionSoundCompiler — semantic production grammar compiler.

L-U6 — Camera + Motion + Sound Compiler.

Purpose
-------
The `CameraMotionSoundCompiler` is the L-U6 semantic compiler that
enriches the camera/motion/sound semantics in `CanonicalPromptIR`.

Architecture
-----------
    PromptCompilationRequest (L-U5)
            ↓
    PromptCompiler (L-U5) → CanonicalPromptIR (basic camera/motion/sound)
            ↓
    CameraMotionSoundCompiler (L-U6) — adds rich semantics
        ├── KnowledgeCameraMotionSoundAdapter (L-U6 — thin L-U3 consumer)
        ├── Deterministic keyword parsing (no LLM)
        └── Strict precedence: EXPLICIT > KNOWLEDGE > DEFAULT
            ↓
    CameraMotionSoundCompilationResult (extended semantics)
            ↓
    Animation / Editorial / Prompt downstream consumers

What this module does NOT do:
- It does NOT call image/video generation APIs
- It does NOT generate audio files
- It does NOT use LLM to determine semantics
- It does NOT contain Remotion / FFmpeg / provider syntax
- It does NOT compute actual audio gain (Editorial/Mastering does that)

Critical invariants:
1. CAMERA MOVEMENT ≠ SUBJECT MOTION ≠ ANIMATION PATTERN
   - camera.movement is camera action (PUSH_IN, PAN)
   - subject_motion is character/object action (WALK, GESTURE)
   - motion.pattern is rendering pattern (RIG_POSE_INTERPOLATION)

2. SOUND INTENT ≠ AUDIO MIXING
   - L-U6 describes intended sound design
   - L-U6 does NOT compute dB or mix audio
   - Editorial/Mastering does actual mixing

3. TIMING AUTHORITY IS NOT DUPLICATED
   - L-U6 expresses duration_sec as a semantic intent
   - NarrationTimeline / SpeechTiming remain the authority for narration timing
   - AnimationPlan remains the authority for animation timing

4. Bounded vocabulary — every value comes from a canonical enum
   or a KnowledgeEntry promotion.

5. Deterministic — same inputs → same result.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from app.knowledge import KnowledgeContext
from app.prompt.knowledge_adapter import (
    KnowledgeCameraMotionSoundAdapter,
    ResolvedCameraMotionSoundKnowledge,
    ResolvedCameraKnowledge,
    ResolvedMotionKnowledge,
    ResolvedSoundKnowledge,
)
from app.prompt.schemas import (
    CameraBlockExt,
    CameraDirection,
    CameraMovementVocabulary,
    CameraShotVocabulary,
    CameraMotionSoundCompilationResult,
    FramingIntent,
    MotionBlockExt,
    MotionPatternVocabulary,
    PromptCompilationRequest,
    PromptKind,
    SoundBlockExt,
    SoundLayerCategory,
    SoundLayerPriority,
    SoundLayerSpec,
    SoundLayersSpec,
    SubjectMotionDirection,
    SubjectMotionIntensity,
    SubjectMotionSpec,
    SubjectMotionVocabulary,
    SubjectRelationship,
)


# ============================================================================
# Compiler version
# ============================================================================

COMPILER_VERSION = "1.0.0"


# ============================================================================
# Compiler
# ============================================================================


class CameraMotionSoundCompiler:
    """L-U6 semantic compiler for camera, motion, and sound.

    Construction:
        # With Knowledge Layer:
        ctx = KnowledgeContext.from_registry(registry)
        compiler = CameraMotionSoundCompiler(knowledge_context=ctx)

        # Without Knowledge Layer (backward compatible):
        compiler = CameraMotionSoundCompiler()
    """

    def __init__(
        self,
        knowledge_context: Optional[KnowledgeContext] = None,
    ) -> None:
        self._knowledge_context = knowledge_context
        self._adapter: Optional[KnowledgeCameraMotionSoundAdapter] = None
        if knowledge_context is not None:
            self._adapter = KnowledgeCameraMotionSoundAdapter(
                context=knowledge_context
            )

    def is_knowledge_active(self) -> bool:
        return self._adapter is not None and self._adapter.is_active()

    @property
    def knowledge_context(self) -> Optional[KnowledgeContext]:
        return self._knowledge_context

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def compile(
        self,
        request: PromptCompilationRequest,
    ) -> CameraMotionSoundCompilationResult:
        """Compile a request into extended camera/motion/sound semantics.

        Parameters:
            request: A PromptCompilationRequest (L-U5).

        Returns:
            A CameraMotionSoundCompilationResult with extended semantics.
        """
        # 1. Resolve knowledge
        resolved_knowledge = self._resolve_knowledge(request.prompt_kind)

        # 2. Build camera semantics (with strict precedence)
        camera = self._build_camera_semantics(request, resolved_knowledge)

        # 3. Build motion semantics
        motion = self._build_motion_semantics(request, resolved_knowledge)

        # 4. Build subject motion
        subject_motion = self._build_subject_motion_semantics(request, resolved_knowledge)

        # 5. Build sound semantics
        sound = self._build_sound_semantics(request, resolved_knowledge)

        # 6. Validate
        from app.prompt.cms_validator import CameraMotionSoundValidator
        validator = CameraMotionSoundValidator()
        is_valid, validation_messages = validator.validate(
            camera=camera, motion=motion, sound=sound, prompt_kind=request.prompt_kind
        )

        # 7. Build result
        return CameraMotionSoundCompilationResult(
            request_id=request.request_id or self._derive_request_id(request),
            prompt_kind=request.prompt_kind,
            camera=camera,
            motion=motion,
            subject_motion=subject_motion,
            sound=sound,
            is_valid=is_valid,
            validation_messages=validation_messages,
            is_knowledge_active=resolved_knowledge.is_active,
            knowledge_version=resolved_knowledge.registry_version,
            knowledge_ids_used=resolved_knowledge.knowledge_ids,
            fallback_policy_used=(
                self._knowledge_context.fallback_policy.value
                if self._knowledge_context
                else "engine_default"
            ),
            compiler_version=COMPILER_VERSION,
            provenance=(
                resolved_knowledge.camera.primary_provenance
                or resolved_knowledge.motion.primary_provenance
                or resolved_knowledge.sound.primary_provenance
            ),
        )

    # ------------------------------------------------------------------
    # Internal: resolve knowledge
    # ------------------------------------------------------------------

    def _resolve_knowledge(
        self, prompt_kind: PromptKind
    ) -> ResolvedCameraMotionSoundKnowledge:
        if self._adapter is None:
            return ResolvedCameraMotionSoundKnowledge(is_active=False)
        return self._adapter.resolve_for_compilation(prompt_kind.value)

    # ------------------------------------------------------------------
    # Internal: build camera semantics
    # ------------------------------------------------------------------

    def _build_camera_semantics(
        self,
        request: PromptCompilationRequest,
        knowledge: ResolvedCameraMotionSoundKnowledge,
    ) -> CameraBlockExt:
        """Build extended camera semantics with deterministic precedence.

        Precedence:
            EXPLICIT (request) > KNOWLEDGE > DEFAULT
        """
        camera_knowledge = knowledge.camera

        # Shot type
        shot_type: Optional[CameraShotVocabulary] = None
        if request.scene_camera:
            shot_type = self._parse_shot_type(request.scene_camera)
        if shot_type is None and camera_knowledge.is_active and camera_knowledge.shot_type:
            shot_type = self._parse_shot_type(camera_knowledge.shot_type)

        # Movement
        movement: Optional[CameraMovementVocabulary] = None
        if request.scene_camera:
            movement = self._parse_movement(request.scene_camera)
        if movement is None and camera_knowledge.is_active and camera_knowledge.movement:
            movement = self._parse_movement(camera_knowledge.movement)

        # Framing (from knowledge only — explicit scene intent doesn't typically express this)
        framing: Optional[FramingIntent] = None
        if camera_knowledge.is_active and camera_knowledge.framing:
            framing = self._parse_framing(camera_knowledge.framing)

        # Subject relationship
        subject_relationship: Optional[SubjectRelationship] = None
        if request.scene_camera:
            subject_relationship = self._parse_subject_relationship(request.scene_camera)
        if subject_relationship is None and camera_knowledge.is_active and camera_knowledge.subject_relationship:
            subject_relationship = self._parse_subject_relationship(camera_knowledge.subject_relationship)

        # Movement direction
        direction = CameraDirection.NONE
        if request.scene_camera:
            direction = self._parse_direction(request.scene_camera)
        if direction == CameraDirection.NONE and camera_knowledge.is_active and camera_knowledge.movement_direction:
            direction = self._parse_direction(camera_knowledge.movement_direction)

        # Intensity
        intensity = SubjectMotionIntensity.MEDIUM
        if camera_knowledge.is_active and camera_knowledge.intensity:
            intensity = self._parse_intensity(camera_knowledge.intensity)

        # Duration
        duration_sec: Optional[float] = None
        if camera_knowledge.is_active and camera_knowledge.duration_sec:
            duration_sec = camera_knowledge.duration_sec

        return CameraBlockExt(
            shot_type=shot_type,
            movement=movement,
            framing=framing,
            subject_relationship=subject_relationship,
            movement_direction=direction,
            intensity=intensity,
            duration_sec=duration_sec,
            provenance=camera_knowledge.primary_provenance,
        )

    # ------------------------------------------------------------------
    # Internal: build motion semantics
    # ------------------------------------------------------------------

    def _build_motion_semantics(
        self,
        request: PromptCompilationRequest,
        knowledge: ResolvedCameraMotionSoundKnowledge,
    ) -> MotionBlockExt:
        """Build extended motion semantics."""
        motion_knowledge = knowledge.motion

        # Pattern
        pattern: Optional[MotionPatternVocabulary] = None
        if motion_knowledge.is_active and motion_knowledge.pattern:
            pattern = self._parse_motion_pattern(motion_knowledge.pattern)

        # Subject action (from request scene_action)
        subject_action: Optional[SubjectMotionVocabulary] = None
        if request.scene_action:
            subject_action = self._parse_subject_action(request.scene_action)
        if subject_action is None and motion_knowledge.is_active and motion_knowledge.subject_action:
            subject_action = self._parse_subject_action(motion_knowledge.subject_action)

        # Direction
        direction = SubjectMotionDirection.NONE
        if motion_knowledge.is_active and motion_knowledge.direction:
            direction = self._parse_motion_direction(motion_knowledge.direction)

        # Easing
        easing = None
        if motion_knowledge.is_active and motion_knowledge.rules:
            for rule in motion_knowledge.rules:
                if "ease_in_out" in rule.lower():
                    easing = "ease_in_out"
                    break
                elif "ease_in" in rule.lower():
                    easing = "ease_in"
                    break
                elif "ease_out" in rule.lower():
                    easing = "ease_out"
                    break
                elif "linear" in rule.lower():
                    easing = "linear"
                    break

        # Duration
        duration_sec: Optional[float] = None
        if motion_knowledge.is_active and motion_knowledge.duration_sec:
            duration_sec = motion_knowledge.duration_sec

        # Loop
        loop = motion_knowledge.loop if motion_knowledge.is_active else False

        return MotionBlockExt(
            pattern=pattern,
            duration_sec=duration_sec,
            loop=loop,
            subject_action=subject_action,
            direction=direction,
            easing=easing,
            provenance=motion_knowledge.primary_provenance,
        )

    # ------------------------------------------------------------------
    # Internal: build subject motion
    # ------------------------------------------------------------------

    def _build_subject_motion_semantics(
        self,
        request: PromptCompilationRequest,
        knowledge: ResolvedCameraMotionSoundKnowledge,
    ) -> SubjectMotionSpec:
        """Build subject motion (what the subject is doing).

        Subject motion = SEMANTIC, not animation implementation.
        """
        motion_knowledge = knowledge.motion

        # Action: explicit scene_action takes precedence
        action = SubjectMotionVocabulary.NONE
        if request.scene_action:
            parsed = self._parse_subject_action(request.scene_action)
            if parsed is not None:
                action = parsed
        elif motion_knowledge.is_active and motion_knowledge.subject_action:
            parsed = self._parse_subject_action(motion_knowledge.subject_action)
            if parsed is not None:
                action = parsed

        # Direction
        direction = SubjectMotionDirection.NONE
        if motion_knowledge.is_active and motion_knowledge.direction:
            direction = self._parse_motion_direction(motion_knowledge.direction)

        # Intensity
        intensity = SubjectMotionIntensity.MEDIUM
        if motion_knowledge.is_active and motion_knowledge.intensity:
            intensity = self._parse_intensity(motion_knowledge.intensity)

        # Duration
        duration_sec: Optional[float] = None
        if motion_knowledge.is_active and motion_knowledge.duration_sec:
            duration_sec = motion_knowledge.duration_sec

        # Target ID
        target_id: Optional[str] = None
        if request.character_reference_id:
            target_id = f"character:{request.character_reference_id}"

        return SubjectMotionSpec(
            action=action,
            direction=direction,
            intensity=intensity,
            duration_sec=duration_sec,
            target_id=target_id,
            provenance=motion_knowledge.primary_provenance,
        )

    # ------------------------------------------------------------------
    # Internal: build sound semantics
    # ------------------------------------------------------------------

    def _build_sound_semantics(
        self,
        request: PromptCompilationRequest,
        knowledge: ResolvedCameraMotionSoundKnowledge,
    ) -> SoundBlockExt:
        """Build extended sound semantics.

        L-U6 describes INTENTED SOUND DESIGN.
        It does NOT mix audio. Editorial/Mastering does that.
        """
        sound_knowledge = knowledge.sound

        # Category
        category = None
        if sound_knowledge.is_active and sound_knowledge.category:
            category = self._parse_sound_category(sound_knowledge.category)

        # Description
        description = None
        if sound_knowledge.is_active and sound_knowledge.description:
            description = sound_knowledge.description

        # Layers
        layers = self._build_sound_layers(sound_knowledge, request)

        # Master duck
        master_duck = sound_knowledge.duck_under_narration if sound_knowledge.is_active else False

        return SoundBlockExt(
            category=category,
            description=description,
            layers=layers,
            master_duck_under_narration=master_duck,
            provenance=sound_knowledge.primary_provenance,
        )

    def _build_sound_layers(
        self,
        sound_knowledge: ResolvedSoundKnowledge,
        request: PromptCompilationRequest,
    ) -> SoundLayersSpec:
        """Build semantic sound layers.

        L-U6 default for VIDEO: narration + ambient + music
        L-U6 default for IMAGE: ambient only

        These are SEMANTIC defaults. They do NOT generate audio files.
        """
        layers: list[SoundLayerSpec] = []

        # If knowledge explicitly provided sound layers, use them
        if sound_knowledge.is_active and sound_knowledge.layers:
            for layer_dict in sound_knowledge.layers:
                layer = SoundLayerSpec(
                    category=self._parse_sound_category(
                        layer_dict.get("category", "ambient")
                    ),
                    description=layer_dict.get("description"),
                    priority=SoundLayerPriority(
                        layer_dict.get("priority", "tertiary")
                    ),
                    duck_under_narration=layer_dict.get("duck_under_narration", False),
                    loop=layer_dict.get("loop", True),
                    volume_hint=layer_dict.get("volume_hint", "medium"),
                )
                layers.append(layer)
        else:
            # Engine default: minimal semantic layers based on prompt kind
            if request.prompt_kind == PromptKind.VIDEO:
                # For VIDEO, narration is a layer (referenced, not generated)
                layers.append(SoundLayerSpec(
                    category=SoundLayerCategory.NARRATION,
                    priority=SoundLayerPriority.PRIMARY,
                    duck_under_narration=False,
                    loop=False,
                    volume_hint="loud",
                ))
                # Ambient
                layers.append(SoundLayerSpec(
                    category=SoundLayerCategory.AMBIENT,
                    priority=SoundLayerPriority.TERTIARY,
                    duck_under_narration=True,
                    loop=True,
                    volume_hint="quiet",
                ))
                # Music (optional)
                layers.append(SoundLayerSpec(
                    category=SoundLayerCategory.MUSIC,
                    priority=SoundLayerPriority.SECONDARY,
                    duck_under_narration=True,
                    loop=True,
                    volume_hint="medium",
                ))

        return SoundLayersSpec(
            layers=layers,
            master_duck_under_narration=sound_knowledge.duck_under_narration,
            provenance=sound_knowledge.primary_provenance,
        )

    # ------------------------------------------------------------------
    # Internal: vocabulary parsers (deterministic)
    # ------------------------------------------------------------------

    def _parse_shot_type(self, value: str) -> Optional[CameraShotVocabulary]:
        text = value.lower().replace("_", " ").replace("-", " ")
        if "extreme wide" in text or "ews" in text:
            return CameraShotVocabulary.EXTREME_WIDE
        if "wide" in text:
            return CameraShotVocabulary.WIDE
        if "medium wide" in text:
            return CameraShotVocabulary.MEDIUM_WIDE
        if "medium close" in text:
            return CameraShotVocabulary.MEDIUM_CLOSE
        if "medium" in text:
            return CameraShotVocabulary.MEDIUM
        if "close" in text and "extreme" not in text:
            return CameraShotVocabulary.CLOSE
        if "extreme close" in text or "ecu" in text:
            return CameraShotVocabulary.EXTREME_CLOSE
        if "over shoulder" in text or "ots" in text:
            return CameraShotVocabulary.OVER_SHOULDER
        if "pov" in text or "point of view" in text:
            return CameraShotVocabulary.POV
        if "dutch" in text:
            return CameraShotVocabulary.DUTCH
        if "bird" in text:
            return CameraShotVocabulary.BIRDS_EYE
        if "worm" in text:
            return CameraShotVocabulary.WORMS_EYE
        if "two shot" in text:
            return CameraShotVocabulary.TWO_SHOT
        return None

    def _parse_movement(self, value: str) -> Optional[CameraMovementVocabulary]:
        text = value.lower().replace("_", " ").replace("-", " ")
        if "push" in text or "dolly forward" in text:
            return CameraMovementVocabulary.PUSH_IN
        if "pull" in text or "dolly back" in text:
            return CameraMovementVocabulary.PULL_OUT
        if "pan" in text:
            return CameraMovementVocabulary.PAN
        if "tilt" in text:
            return CameraMovementVocabulary.TILT
        if "zoom" in text:
            return CameraMovementVocabulary.ZOOM
        if "tracking" in text or "follow" in text:
            return CameraMovementVocabulary.TRACKING
        if "shake" in text:
            return CameraMovementVocabulary.SHAKE
        if "orbit" in text:
            return CameraMovementVocabulary.ORBIT
        if "hold" in text or "static" in text:
            return CameraMovementVocabulary.HOLD
        return None

    def _parse_framing(self, value: str) -> Optional[FramingIntent]:
        text = value.lower()
        if "rule" in text and "third" in text:
            return FramingIntent.RULE_OF_THIRDS
        if "golden" in text:
            return FramingIntent.GOLDEN_RATIO
        if "leading" in text:
            return FramingIntent.LEADING_ROOM
        if "asymmetric" in text:
            return FramingIntent.ASYMMETRIC
        if "balanced" in text:
            return FramingIntent.BALANCED
        if "center" in text:
            return FramingIntent.CENTER
        return None

    def _parse_subject_relationship(self, value: str) -> Optional[SubjectRelationship]:
        text = value.lower().replace("_", " ").replace("-", " ")
        if "pov" in text or "point of view" in text:
            return SubjectRelationship.POV
        if "over shoulder" in text or "ots" in text:
            return SubjectRelationship.OVER
        if "under" in text:
            return SubjectRelationship.UNDER
        if "three quarter" in text:
            return SubjectRelationship.THREE_QUARTER
        if "back" in text:
            return SubjectRelationship.BACK
        if "side" in text:
            return SubjectRelationship.SIDE
        if "front" in text:
            return SubjectRelationship.FRONT
        return None

    def _parse_direction(self, value: str) -> CameraDirection:
        text = value.lower().replace("_", " ").replace("-", " ")
        if "forward" in text or "push" in text:
            return CameraDirection.FORWARD
        if "backward" in text or "pull" in text:
            return CameraDirection.BACKWARD
        if "left" in text:
            return CameraDirection.LEFT
        if "right" in text:
            return CameraDirection.RIGHT
        if "up" in text:
            return CameraDirection.UP
        if "down" in text:
            return CameraDirection.DOWN
        return CameraDirection.NONE

    def _parse_intensity(self, value: str) -> SubjectMotionIntensity:
        text = value.lower()
        if "high" in text or "fast" in text or "quick" in text:
            return SubjectMotionIntensity.HIGH
        if "low" in text or "slow" in text or "subtle" in text:
            return SubjectMotionIntensity.LOW
        return SubjectMotionIntensity.MEDIUM

    def _parse_motion_pattern(self, value: str) -> Optional[MotionPatternVocabulary]:
        text = value.lower().replace("_", " ").replace("-", " ")
        if "frame" in text and "by" in text:
            return MotionPatternVocabulary.FRAME_BY_FRAME
        if "loop" in text:
            return MotionPatternVocabulary.LOOP
        if "rig" in text or "interpolation" in text:
            return MotionPatternVocabulary.RIG_POSE_INTERPOLATION
        if "kinetic" in text:
            return MotionPatternVocabulary.KINETIC_TEXT
        if "shake" in text or "nervous" in text:
            return MotionPatternVocabulary.SHAKE_NERVOUS
        return None

    def _parse_subject_action(self, value: str) -> Optional[SubjectMotionVocabulary]:
        text = value.lower().replace("_", " ").replace("-", " ")
        # Order matters: check more specific first
        if "celebrate" in text:
            return SubjectMotionVocabulary.CELEBRATE
        if "thinking" in text or "think" in text:
            return SubjectMotionVocabulary.THINK
        if "running" in text or "run" in text:
            return SubjectMotionVocabulary.RUN
        if "walking" in text or "walk" in text:
            return SubjectMotionVocabulary.WALK
        if "pointing" in text or "point" in text:
            return SubjectMotionVocabulary.POINT
        if "gesture" in text:
            return SubjectMotionVocabulary.GESTURE
        if "hide" in text or "hiding" in text:
            return SubjectMotionVocabulary.HIDE
        if "sitting" in text or "sit" in text:
            return SubjectMotionVocabulary.SIT
        if "entering" in text or "enter" in text:
            return SubjectMotionVocabulary.ENTER
        if "exiting" in text or "exit" in text:
            return SubjectMotionVocabulary.EXIT
        if "turning" in text or "turn" in text:
            return SubjectMotionVocabulary.TURN
        if "looking" in text or "look" in text:
            return SubjectMotionVocabulary.LOOK
        if "breathing" in text or "breathe" in text:
            return SubjectMotionVocabulary.BREATHING
        if "idle" in text or "standing" in text or "stand" in text:
            return SubjectMotionVocabulary.IDLE
        return None

    def _parse_motion_direction(self, value: str) -> SubjectMotionDirection:
        text = value.lower().replace("_", " ").replace("-", " ")
        if "forward" in text:
            return SubjectMotionDirection.FORWARD
        if "backward" in text:
            return SubjectMotionDirection.BACKWARD
        if "left" in text:
            return SubjectMotionDirection.LEFT
        if "right" in text:
            return SubjectMotionDirection.RIGHT
        if "up" in text:
            return SubjectMotionDirection.UP
        if "down" in text:
            return SubjectMotionDirection.DOWN
        return SubjectMotionDirection.NONE

    def _parse_sound_category(self, value: str) -> Optional[SoundLayerCategory]:
        text = value.lower().replace("_", " ").replace("-", " ")
        if "ambient" in text or "atmosphere" in text:
            return SoundLayerCategory.AMBIENT
        if "music" in text or "score" in text:
            return SoundLayerCategory.MUSIC
        if "sfx" in text or "sound effect" in text:
            return SoundLayerCategory.SFX
        if "environment" in text:
            return SoundLayerCategory.ENVIRONMENT
        if "impact" in text:
            return SoundLayerCategory.IMPACT
        if "narration" in text:
            return SoundLayerCategory.NARRATION
        if "dialogue" in text or "dialog" in text:
            return SoundLayerCategory.DIALOGUE
        if "silence" in text or "silent" in text:
            return SoundLayerCategory.SILENCE
        return None

    # ------------------------------------------------------------------
    # Internal: deterministic request ID
    # ------------------------------------------------------------------

    def _derive_request_id(self, request: PromptCompilationRequest) -> str:
        content = f"cms:{request.prompt_kind.value}:{request.character_reference_id or ''}:{request.scene_camera or ''}:{request.scene_action or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


__all__ = [
    "CameraMotionSoundCompiler",
    "COMPILER_VERSION",
]
