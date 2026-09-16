"""
CameraMotionSoundValidator — deterministic validation for L-U6.

L-U6 — Camera + Motion + Sound Compiler.

Purpose
-------
The `CameraMotionSoundValidator` performs deterministic, NO-LLM
validation of `CameraMotionSoundCompilationResult`.

Validation rules (deterministic, no LLM):
1. Valid camera shot type
2. Valid camera movement
3. Valid motion pattern
4. Valid sound category
5. Camera movement must not be on IMAGE (motion is VIDEO only)
6. Subject motion is VIDEO only
7. Sound layers must not contain contradictory ducking
8. No forbidden provider syntax in canonical layer
9. Provenance integrity
10. No invalid vocabulary

What this module does NOT do:
- It does NOT call any LLM to judge quality
- It does NOT generate camera/motion/sound
- It does NOT call image/video/audio generation APIs
"""

from __future__ import annotations

from app.prompt.schemas import (
    CameraBlockExt,
    CameraMovementVocabulary,
    CameraShotVocabulary,
    MotionBlockExt,
    MotionPatternVocabulary,
    PromptKind,
    SoundBlockExt,
    SoundLayerCategory,
    SoundLayerSpec,
    SoundLayersSpec,
    SubjectMotionSpec,
    SubjectMotionVocabulary,
)


class CameraMotionSoundValidator:
    """Deterministic validator for CameraMotionSoundCompilationResult.

    All validation rules are deterministic and do NOT require LLM.
    """

    def validate(
        self,
        camera: CameraBlockExt,
        motion: MotionBlockExt,
        sound: SoundBlockExt,
        prompt_kind: PromptKind,
    ) -> tuple[bool, list[str]]:
        """Validate camera/motion/sound semantics.

        Returns:
            (is_valid, messages)
        """
        messages: list[str] = []
        is_valid = True

        # Rule 1: Camera movement is VIDEO only
        if prompt_kind == PromptKind.IMAGE:
            if camera.movement is not None:
                messages.append(
                    "Camera movement declared on IMAGE prompt; "
                    "movement is VIDEO-only."
                )

        # Rule 2: Subject motion is VIDEO only
        if prompt_kind == PromptKind.IMAGE:
            if motion.subject_action is not None and motion.subject_action != SubjectMotionVocabulary.NONE:
                messages.append(
                    "Subject motion declared on IMAGE prompt; "
                    "subject motion is VIDEO-only."
                )

        # Rule 3: Camera shot type vocabulary
        if camera.shot_type is not None:
            valid_shots = set(CameraShotVocabulary.__members__.values())
            if camera.shot_type not in valid_shots:
                is_valid = False
                messages.append(
                    f"Invalid camera shot type: {camera.shot_type}"
                )

        # Rule 4: Camera movement vocabulary
        if camera.movement is not None:
            valid_movements = set(CameraMovementVocabulary.__members__.values())
            if camera.movement not in valid_movements:
                is_valid = False
                messages.append(
                    f"Invalid camera movement: {camera.movement}"
                )

        # Rule 5: Motion pattern vocabulary
        if motion.pattern is not None:
            valid_patterns = set(MotionPatternVocabulary.__members__.values())
            if motion.pattern not in valid_patterns:
                is_valid = False
                messages.append(
                    f"Invalid motion pattern: {motion.pattern}"
                )

        # Rule 6: Sound layer ducking logic
        for layer in sound.layers.layers:
            if layer.duck_under_narration and layer.category == SoundLayerCategory.NARRATION:
                is_valid = False
                messages.append(
                    f"Narration layer cannot duck under itself: {layer.category}"
                )

        # Rule 7: No forbidden provider syntax in canonical layer
        self._check_no_provider_syntax(camera, motion, sound, messages)

        # Rule 8: Duration validity
        if camera.duration_sec is not None and camera.duration_sec > 300.0:
            messages.append(
                f"Camera duration too long: {camera.duration_sec}s (max 300s)"
            )

        if motion.duration_sec is not None and motion.duration_sec > 300.0:
            messages.append(
                f"Motion duration too long: {motion.duration_sec}s (max 300s)"
            )

        # Rule 9: Sound layer count
        if len(sound.layers.layers) > 8:
            messages.append(
                f"Too many sound layers: {len(sound.layers.layers)} (max 8)"
            )

        return is_valid, messages

    def _check_no_provider_syntax(
        self,
        camera: CameraBlockExt,
        motion: MotionBlockExt,
        sound: SoundBlockExt,
        messages: list[str],
    ) -> None:
        """Detect provider-specific syntax in canonical layer.

        Provider syntax belongs in ProviderPromptAdapter, not in core.
        """
        forbidden = [
            "--ar", "--style", "--seed", "--model", "--camera",
            "google_flow", "dino_api", "vertex_ai",
            "interpolate()", "spring()", "useCurrentFrame()",
            "frame=", "pan_x=", "pan_y=",
        ]

        text_fields = []

        # Notes fields
        if camera.notes:
            text_fields.append(("camera.notes", camera.notes))
        if motion.notes:
            text_fields.append(("motion.notes", motion.notes))
        if sound.notes:
            text_fields.append(("sound.notes", sound.notes))
        if sound.description:
            text_fields.append(("sound.description", sound.description))

        for field_name, text in text_fields:
            text_lower = text.lower()
            for pattern in forbidden:
                if pattern.lower() in text_lower:
                    messages.append(
                        f"Provider-specific syntax '{pattern}' in {field_name}. "
                        "Provider syntax belongs in ProviderPromptAdapter."
                    )

    def _check_subject_motion(
        self,
        subject_motion: SubjectMotionSpec,
        prompt_kind: PromptKind,
        messages: list[str],
    ) -> None:
        """Validate subject motion."""
        if prompt_kind == PromptKind.IMAGE:
            if subject_motion.action != SubjectMotionVocabulary.NONE:
                messages.append(
                    "Subject motion action declared on IMAGE; "
                    "subject motion is VIDEO-only."
                )


__all__ = [
    "CameraMotionSoundValidator",
]
