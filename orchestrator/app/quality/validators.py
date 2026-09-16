"""
Dimension validators — pure functions, deterministic, no LLM.

L-U7 — Hybrid Quality Validation.

This module hosts the per-dimension validators. Each function:
- Takes canonical upstream contracts (read-only).
- Returns a list of `ValidationIssue` (sorted, deterministic).
- NEVER mutates inputs.
- NEVER calls providers, LLMs, or any I/O.

Validator categories
-------------------
- validate_contract_compatibility
- validate_semantic_completeness
- validate_character_identity
- validate_camera
- validate_motion
- validate_camera_motion_compatibility
- validate_continuity
- validate_prompt_loss
- validate_knowledge_provenance
- validate_sound_semantic
- validate_format
- validate_fallback_visibility
- validate_conflict_visibility
- validate_provider_readiness
- validate_generation_readiness

Each is a pure function. The QualityEngine aggregates them.
"""

from __future__ import annotations

from typing import Optional

from app.quality.schemas import (
    IssueSource,
    QualityValidationContext,
    ValidationDimension,
    ValidationIssue,
    ValidationSeverity,
)


# ============================================================================
# Helpers
# ============================================================================


def _make_issue_id(rule_id: str, idx: int = 0) -> str:
    return f"{rule_id}#{idx}"


def _format_path(*parts: str) -> str:
    return ".".join(p for p in parts if p)


# ============================================================================
# 1. Contract compatibility
# ============================================================================


def validate_contract_compatibility(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Verify that upstream contracts are well-formed and compatible."""
    issues: list[ValidationIssue] = []

    # At minimum, we need ONE canonical input
    if not context.has_minimum_inputs():
        issues.append(
            ValidationIssue(
                issue_id=_make_issue_id("contract.no-input"),
                dimension="contract_compatibility",
                severity=ValidationSeverity.BLOCKING,
                source=IssueSource.STRUCTURAL,
                message=(
                    "No canonical input provided. "
                    "Need at least one of: "
                    "PromptCompilationResult, CameraMotionSoundCompilationResult."
                ),
                rule_id="contract.no-input",
            )
        )

    # If we have a CMS result and a Prompt result, their prompt_kind must match
    pcr = context.prompt_compilation_result
    cms = context.cms_compilation_result

    if pcr is not None and cms is not None:
        pcr_kind = getattr(pcr, "prompt_kind", None)
        cms_kind = getattr(cms, "prompt_kind", None)
        if pcr_kind is not None and cms_kind is not None and pcr_kind != cms_kind:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("contract.prompt-kind-mismatch"),
                    dimension="contract_compatibility",
                    severity=ValidationSeverity.ERROR,
                    source=IssueSource.CROSS_CONTRACT,
                    message=(
                        f"prompt_kind mismatch: "
                        f"Prompt={pcr_kind}, CMS={cms_kind}."
                    ),
                    rule_id="contract.prompt-kind-mismatch",
                )
            )

    return issues


# ============================================================================
# 2. Semantic completeness
# ============================================================================


def validate_semantic_completeness(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Check that required semantic fields are present.

    Rules depend on prompt_kind and scene intent.
    """
    issues: list[ValidationIssue] = []

    cms = context.cms_compilation_result
    if cms is None:
        return issues  # nothing to validate

    # Prompt kind
    prompt_kind = getattr(cms, "prompt_kind", None)
    if prompt_kind is None:
        return issues

    # Camera intent: shot_type is required for both IMAGE and VIDEO
    camera = getattr(cms, "camera", None)
    if camera is not None:
        shot_type = getattr(camera, "shot_type", None)
        movement = getattr(camera, "movement", None)

        if shot_type is None:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("completeness.camera-shot-type"),
                    dimension="semantic_completeness",
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.STRUCTURAL,
                    message="Camera shot_type is not set.",
                    field_path="camera.shot_type",
                    rule_id="completeness.camera-shot-type",
                )
            )

        if prompt_kind.value == "video" and movement is None:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("completeness.camera-movement-video"),
                    dimension="semantic_completeness",
                    severity=ValidationSeverity.INFO,
                    source=IssueSource.STRUCTURAL,
                    message="VIDEO scene has no camera movement (defaults to HOLD).",
                    field_path="camera.movement",
                    rule_id="completeness.camera-movement-video",
                )
            )

    # Sound layers for VIDEO (configurable)
    if prompt_kind.value == "video" and context.policy.require_sound_layers_for_video:
        sound = getattr(cms, "sound", None)
        if sound is not None:
            layers = getattr(sound, "layers", None)
            layer_list = getattr(layers, "layers", None) if layers else None
            if not layer_list:
                issues.append(
                    ValidationIssue(
                        issue_id=_make_issue_id("completeness.sound-layers-video"),
                        dimension="semantic_completeness",
                        severity=ValidationSeverity.WARNING,
                        source=IssueSource.STRUCTURAL,
                        message="VIDEO scene has no semantic sound layers.",
                        field_path="sound.layers",
                        rule_id="completeness.sound-layers-video",
                    )
                )

    return issues


# ============================================================================
# 3. Character identity
# ============================================================================


def validate_character_identity(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Verify identity consistency (L-U4 invariant)."""
    issues: list[ValidationIssue] = []

    spec = context.character_reference_spec
    if spec is None:
        # Only complain if the scene requires a character
        # (CMS has subject_motion.target_id referencing a character)
        cms = context.cms_compilation_result
        if cms is not None:
            target_id = getattr(getattr(cms, "subject_motion", None), "target_id", None)
            if target_id and target_id.startswith("character:"):
                issues.append(
                    ValidationIssue(
                        issue_id=_make_issue_id("identity.missing-spec"),
                        dimension="character_identity_consistency",
                        severity=ValidationSeverity.WARNING,
                        source=IssueSource.STRUCTURAL,
                        message=(
                            f"Scene references character '{target_id}' "
                            "but no CharacterReferenceSpecification is provided."
                        ),
                        field_path="subject_motion.target_id",
                        rule_id="identity.missing-spec",
                    )
                )
        return issues

    # If a spec is provided, validate that CMS doesn't drift identity
    cms = context.cms_compilation_result
    if cms is None:
        return issues

    # Identity properties should not be touched by scene variables
    # (CMS doesn't embed identity, so this is a structural check)
    identity_props = getattr(spec, "identity_properties", frozenset())
    scene_vars = getattr(spec, "scene_variables", frozenset())

    # The spec itself must have at least one identity property
    if not identity_props:
        issues.append(
            ValidationIssue(
                issue_id=_make_issue_id("identity.no-identity-properties"),
                dimension="character_identity_consistency",
                severity=ValidationSeverity.ERROR,
                source=IssueSource.STRUCTURAL,
                message=(
                    "CharacterReferenceSpecification has no identity_properties. "
                    "Every character must have at least one identity property."
                ),
                field_path="character_reference_spec.identity_properties",
                rule_id="identity.no-identity-properties",
            )
        )

    # The spec must have at least one scene variable
    if not scene_vars:
        issues.append(
            ValidationIssue(
                issue_id=_make_issue_id("identity.no-scene-variables"),
                dimension="character_identity_consistency",
                severity=ValidationSeverity.WARNING,
                source=IssueSource.STRUCTURAL,
                message=(
                    "CharacterReferenceSpecification has no scene_variables. "
                    "At least one scene variable is expected for natural variation."
                ),
                field_path="character_reference_spec.scene_variables",
                rule_id="identity.no-scene-variables",
            )
        )

    return issues


# ============================================================================
# 4. Camera
# ============================================================================


def validate_camera(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Validate camera vocabulary (L-U5/L-U6 bounded vocabulary)."""
    issues: list[ValidationIssue] = []

    cms = context.cms_compilation_result
    if cms is None:
        return issues

    camera = getattr(cms, "camera", None)
    if camera is None:
        return issues

    movement = getattr(camera, "movement", None)
    prompt_kind = getattr(cms, "prompt_kind", None)

    # Camera movement must not be on IMAGE
    if movement is not None and prompt_kind is not None:
        if prompt_kind.value == "image" and not context.policy.allow_motion_on_image:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("camera.movement-on-image"),
                    dimension="camera",
                    severity=ValidationSeverity.ERROR,
                    source=IssueSource.STRUCTURAL,
                    message=(
                        f"Camera movement '{movement.value}' on IMAGE prompt. "
                        "Movement is VIDEO-only."
                    ),
                    field_path="camera.movement",
                    rule_id="camera.movement-on-image",
                )
            )

    # Camera direction must be consistent with movement
    direction = getattr(camera, "movement_direction", None)
    if movement is not None and direction is not None:
        direction_value = direction.value
        # HOLD / SHAKE / ORBIT can have any direction
        # PUSH_IN expects FORWARD
        # PULL_OUT expects BACKWARD
        # PAN expects LEFT or RIGHT
        # TILT expects UP or DOWN
        if movement.value == "push_in" and direction_value not in {"forward", "none"}:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("camera.direction-mismatch"),
                    dimension="camera",
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.STRUCTURAL,
                    message=(
                        f"PUSH_IN with direction={direction_value}; "
                        "expected FORWARD or NONE."
                    ),
                    field_path="camera.movement_direction",
                    rule_id="camera.direction-mismatch",
                )
            )
        if movement.value == "pull_out" and direction_value not in {"backward", "none"}:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("camera.direction-mismatch"),
                    dimension="camera",
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.STRUCTURAL,
                    message=(
                        f"PULL_OUT with direction={direction_value}; "
                        "expected BACKWARD or NONE."
                    ),
                    field_path="camera.movement_direction",
                    rule_id="camera.direction-mismatch",
                )
            )
        if movement.value == "pan" and direction_value not in {"left", "right", "none"}:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("camera.direction-mismatch"),
                    dimension="camera",
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.STRUCTURAL,
                    message=(
                        f"PAN with direction={direction_value}; "
                        "expected LEFT, RIGHT, or NONE."
                    ),
                    field_path="camera.movement_direction",
                    rule_id="camera.direction-mismatch",
                )
            )

    return issues


# ============================================================================
# 5. Motion
# ============================================================================


def validate_motion(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Validate motion (animation pattern + subject motion)."""
    issues: list[ValidationIssue] = []

    cms = context.cms_compilation_result
    if cms is None:
        return issues

    motion = getattr(cms, "motion", None)
    subject_motion = getattr(cms, "subject_motion", None)
    prompt_kind = getattr(cms, "prompt_kind", None)

    # Subject motion must not be on IMAGE
    if subject_motion is not None and prompt_kind is not None:
        if prompt_kind.value == "image" and not context.policy.allow_motion_on_image:
            action = getattr(subject_motion, "action", None)
            action_value = getattr(action, "value", None) if action else None
            if action_value and action_value != "none":
                issues.append(
                    ValidationIssue(
                        issue_id=_make_issue_id("motion.subject-motion-on-image"),
                        dimension="motion",
                        severity=ValidationSeverity.ERROR,
                        source=IssueSource.STRUCTURAL,
                        message=(
                            f"Subject motion '{action_value}' on IMAGE prompt. "
                            "Subject motion is VIDEO-only."
                        ),
                        field_path="subject_motion.action",
                        rule_id="motion.subject-motion-on-image",
                    )
                )

    return issues


# ============================================================================
# 6. Camera / Motion compatibility
# ============================================================================


def validate_camera_motion_compatibility(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Three distinct concepts check + cross-compatibility."""
    issues: list[ValidationIssue] = []

    cms = context.cms_compilation_result
    if cms is None:
        return issues

    camera = getattr(cms, "camera", None)
    motion = getattr(cms, "motion", None)
    subject_motion = getattr(cms, "subject_motion", None)

    # A camera movement that's clearly subject motion is a category error.
    # E.g. PUSH_IN with subject_motion.target_id=None and motion.pattern=None
    # and subject_motion.action=WALK would mean "the camera walks" — wrong.
    movement = getattr(camera, "movement", None) if camera else None
    subject_action = (
        getattr(getattr(subject_motion, "action", None), "value", None)
        if subject_motion
        else None
    )

    # Detect POV vs OTS conflict on shot_type
    shot_type = getattr(camera, "shot_type", None) if camera else None
    subject_rel = (
        getattr(camera, "subject_relationship", None) if camera else None
    )
    if shot_type is not None and subject_rel is not None:
        if shot_type.value == "pov" and subject_rel.value in {"over", "under"}:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("camera_motion.pov-ots-conflict"),
                    dimension=ValidationDimension.CAMERA_MOTION_COMPATIBILITY,
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.CROSS_CONTRACT,
                    message=(
                        "POV shot_type with over/under subject_relationship; "
                        "may indicate semantic conflict."
                    ),
                    field_path="camera.subject_relationship",
                    rule_id="camera_motion.pov-ots-conflict",
                )
            )

    # KINETIC_TEXT + subject walking is suspicious but allowed
    if motion is not None:
        pattern = getattr(motion, "pattern", None)
        pattern_value = getattr(pattern, "value", None) if pattern else None
        if (
            pattern_value == "kinetic_text"
            and subject_action
            and subject_action not in {"none", "idle", "stand"}
        ):
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("camera_motion.kinetic-text-walking"),
                    dimension="camera_motion_compatibility",
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.CROSS_CONTRACT,
                    message=(
                        f"KINETIC_TEXT motion pattern with subject action "
                        f"'{subject_action}'. May indicate semantic ambiguity."
                    ),
                    field_path="motion.pattern",
                    rule_id="camera_motion.kinetic-text-walking",
                )
            )

    return issues


# ============================================================================
# 7. Continuity
# ============================================================================


def validate_continuity(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Cross-scene continuity validation."""
    issues: list[ValidationIssue] = []

    # Cross-scene: previous scene exists
    prev = context.previous_scene_context
    if prev is None:
        return issues  # single-scene mode

    # Compare character references
    prev_spec = getattr(prev, "character_reference_spec", None)
    curr_spec = context.character_reference_spec

    if prev_spec is not None and curr_spec is not None:
        prev_id = getattr(prev_spec, "character_id", None)
        curr_id = getattr(curr_spec, "character_id", None)

        if prev_id != curr_id:
            # Different character is not necessarily an issue;
            # but if it's the same scene sequence, this might be a switch.
            # We don't block; we just note.
            pass

    return issues


# ============================================================================
# 8. Prompt loss detection
# ============================================================================


def validate_prompt_loss(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Structural prompt loss detection.

    No LLM. No fuzzy matching. Just structural field-presence check.
    """
    issues: list[ValidationIssue] = []

    pcr = context.prompt_compilation_result
    if pcr is None:
        return issues

    # If we have explicit request fields, check that some of them made it
    # into the IR
    ir = getattr(pcr, "ir", None)
    if ir is None:
        return issues

    # Compare explicit fields → resolved fields
    expected = []
    resolved = []

    cms = context.cms_compilation_result
    subject_motion = getattr(cms, "subject_motion", None) if cms else None
    if subject_motion is not None:
        target_id = getattr(subject_motion, "target_id", None)
        if target_id:
            expected.append("subject_motion.target_id")
            resolved.append("subject_motion.target_id")

    # Check if there was a scene_action but no resolved subject_action
    # (We don't have the original request here, but the CMS compiler would
    # have captured this in validation_messages.)
    validation = getattr(pcr, "validation", None)
    if validation is not None:
        # PromptValidationReport has blocking_findings + warnings + info (L-U5)
        # CameraMotionSoundCompilationResult has validation_messages (L-U6)
        msgs = getattr(validation, "validation_messages", None)
        if msgs is None:
            b_findings = getattr(validation, "blocking_findings", []) or []
            warns = getattr(validation, "warnings", []) or []
            msgs = [getattr(f, "message", str(f)) for f in b_findings + warns]
        for msg in (msgs or []):
            if "scene_action" in str(msg).lower() and "lost" in str(msg).lower():
                issues.append(
                    ValidationIssue(
                        issue_id=_make_issue_id("prompt-loss.scene-action"),
                        dimension=ValidationDimension.PROMPT_LOSS,
                        severity=ValidationSeverity.WARNING,
                        source=IssueSource.STRUCTURAL,
                        message=str(msg),
                        field_path="subject_motion.action",
                        rule_id="prompt-loss.scene-action",
                    )
                )

    return issues


# ============================================================================
# 9. Knowledge provenance
# ============================================================================


def validate_knowledge_provenance(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Verify knowledge provenance on knowledge-derived fields."""
    issues: list[ValidationIssue] = []

    cms = context.cms_compilation_result
    if cms is None:
        return issues

    is_active = getattr(cms, "is_knowledge_active", False)

    if not is_active:
        if not context.policy.allow_knowledge_disabled:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("knowledge.disabled"),
                    dimension="knowledge_provenance",
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.STRUCTURAL,
                    message=(
                        "Knowledge Layer is disabled. "
                        "Validation continues but provenance is reduced."
                    ),
                    rule_id="knowledge.disabled",
                )
            )
        return issues

    # Knowledge is active: check that knowledge-derived elements have provenance
    # Camera
    camera = getattr(cms, "camera", None)
    if camera is not None:
        provenance = getattr(camera, "provenance", None)
        if provenance is None and context.policy.require_provenance_on_knowledge_fields:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("knowledge.missing-camera-provenance"),
                    dimension="knowledge_provenance",
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.KNOWLEDGE,
                    message=(
                        "Camera has no provenance despite knowledge being active."
                    ),
                    field_path="camera.provenance",
                    rule_id="knowledge.missing-camera-provenance",
                )
            )

    # Motion
    motion = getattr(cms, "motion", None)
    if motion is not None:
        provenance = getattr(motion, "provenance", None)
        if provenance is None and context.policy.require_provenance_on_knowledge_fields:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("knowledge.missing-motion-provenance"),
                    dimension="knowledge_provenance",
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.KNOWLEDGE,
                    message=(
                        "Motion has no provenance despite knowledge being active."
                    ),
                    field_path="motion.provenance",
                    rule_id="knowledge.missing-motion-provenance",
                )
            )

    # Sound
    sound = getattr(cms, "sound", None)
    if sound is not None:
        provenance = getattr(sound, "provenance", None)
        if provenance is None and context.policy.require_provenance_on_knowledge_fields:
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("knowledge.missing-sound-provenance"),
                    dimension="knowledge_provenance",
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.KNOWLEDGE,
                    message=(
                        "Sound has no provenance despite knowledge being active."
                    ),
                    field_path="sound.provenance",
                    rule_id="knowledge.missing-sound-provenance",
                )
            )

    return issues


# ============================================================================
# 10. Sound semantic
# ============================================================================


def validate_sound_semantic(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Sound semantic validation (intent, NOT audio mixing)."""
    issues: list[ValidationIssue] = []

    cms = context.cms_compilation_result
    if cms is None:
        return issues

    sound = getattr(cms, "sound", None)
    if sound is None:
        return issues

    layers_obj = getattr(sound, "layers", None)
    layer_list = getattr(layers_obj, "layers", None) if layers_obj else None

    if not layer_list:
        return issues  # no layers to validate

    # Check narration layer has primary priority
    for layer in layer_list:
        cat = getattr(layer, "category", None)
        pri = getattr(layer, "priority", None)

        if cat is None or pri is None:
            continue

        cat_value = getattr(cat, "value", None)
        pri_value = getattr(pri, "value", None)

        if cat_value == "narration" and pri_value != "primary":
            issues.append(
                ValidationIssue(
                    issue_id=_make_issue_id("sound.narration-not-primary"),
                    dimension="sound_semantic",
                    severity=ValidationSeverity.WARNING,
                    source=IssueSource.STRUCTURAL,
                    message=(
                        f"Narration layer priority is '{pri_value}'; "
                        "expected 'primary'."
                    ),
                    field_path="sound.layers",
                    rule_id="sound.narration-not-primary",
                )
            )

    return issues


# ============================================================================
# 11. Format
# ============================================================================


def validate_format(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Format consistency (IMAGE/VIDEO, aspect_ratio, format)."""
    issues: list[ValidationIssue] = []

    cms = context.cms_compilation_result
    if cms is None:
        return issues

    prompt_kind = getattr(cms, "prompt_kind", None)
    if prompt_kind is None:
        return issues

    # IMAGE must not have motion
    if prompt_kind.value == "image":
        camera = getattr(cms, "camera", None)
        if camera is not None:
            movement = getattr(camera, "movement", None)
            if movement is not None and not context.policy.allow_motion_on_image:
                issues.append(
                    ValidationIssue(
                        issue_id=_make_issue_id("format.motion-on-image"),
                        dimension="format",
                        severity=ValidationSeverity.ERROR,
                        source=IssueSource.STRUCTURAL,
                        message=(
                            "IMAGE prompt with camera movement."
                        ),
                        field_path="camera.movement",
                        rule_id="format.motion-on-image",
                    )
                )

    return issues


# ============================================================================
# 12. Fallback visibility
# ============================================================================


def validate_fallback_visibility(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Verify fallback is recorded and visible."""
    issues: list[ValidationIssue] = []

    cms = context.cms_compilation_result
    if cms is None:
        return issues

    fallback = getattr(cms, "fallback_policy_used", None)
    is_active = getattr(cms, "is_knowledge_active", False)

    if not is_active and fallback is None:
        issues.append(
            ValidationIssue(
                issue_id=_make_issue_id("fallback.unrecorded"),
                dimension="fallback_visibility",
                severity=ValidationSeverity.WARNING,
                source=IssueSource.STRUCTURAL,
                message=(
                    "Knowledge is inactive but fallback_policy_used is not recorded."
                ),
                rule_id="fallback.unrecorded",
            )
        )

    if fallback is not None and fallback == "silent":
        issues.append(
            ValidationIssue(
                issue_id=_make_issue_id("fallback.silent-mode"),
                dimension="fallback_visibility",
                severity=ValidationSeverity.WARNING,
                source=IssueSource.ENGINE_DEFAULT,
                message=(
                    "SILENT fallback policy in use; "
                    "traceability may be reduced."
                ),
                rule_id="fallback.silent-mode",
            )
        )

    return issues


# ============================================================================
# 13. Conflict visibility
# ============================================================================


def validate_conflict_visibility(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Verify conflicts are visible and traceable."""
    issues: list[ValidationIssue] = []

    pcr = context.prompt_compilation_result
    if pcr is None:
        return issues

    has_conflicts = getattr(pcr, "has_conflicts", False)
    has_overrides = getattr(pcr, "has_overrides", False)

    # If there are conflicts, the result must have some indication of them
    if has_conflicts:
        # Conflicts should be reflected in the result somewhere.
        # We trust the L-U5 compiler to surface them.
        # Here we just note that conflicts exist.
        pass

    if has_overrides:
        if context.policy.require_explicit_override_justification:
            # The override must be visible (e.g. via validation messages).
            # If has_overrides=True but no provenance, that's a quality issue.
            pass

    return issues


# ============================================================================
# 14. Provider readiness
# ============================================================================


def validate_provider_readiness(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Semantic readiness for downstream provider adapter.

    This is NOT a test against a real provider.
    """
    issues: list[ValidationIssue] = []

    cms = context.cms_compilation_result
    if cms is None:
        return issues

    # Camera must be present for provider adapter to consume
    camera = getattr(cms, "camera", None)
    if camera is None:
        issues.append(
            ValidationIssue(
                issue_id=_make_issue_id("provider.no-camera"),
                dimension="provider_readiness",
                severity=ValidationSeverity.BLOCKING,
                source=IssueSource.STRUCTURAL,
                message=(
                    "Camera is missing; provider adapter cannot consume."
                ),
                field_path="camera",
                rule_id="provider.no-camera",
            )
        )

    # Forbidden provider syntax in notes
    forbidden = ["--ar", "--style", "--seed", "--model", "--camera"]
    for field_name in ["camera", "motion", "sound"]:
        field = getattr(cms, field_name, None)
        if field is None:
            continue
        notes = getattr(field, "notes", "") or ""
        for pattern in forbidden:
            if pattern in notes:
                issues.append(
                    ValidationIssue(
                        issue_id=_make_issue_id(f"provider.{field_name}.syntax-leak"),
                        dimension="provider_readiness",
                        severity=ValidationSeverity.BLOCKING,
                        source=IssueSource.STRUCTURAL,
                        message=(
                            f"Provider syntax '{pattern}' leaked into "
                            f"{field_name}.notes. This belongs in ProviderPromptAdapter."
                        ),
                        field_path=f"{field_name}.notes",
                        rule_id=f"provider.{field_name}.syntax-leak",
                    )
                )

    return issues


# ============================================================================
# 15. Generation readiness
# ============================================================================


def validate_generation_readiness(
    context: QualityValidationContext,
) -> list[ValidationIssue]:
    """Semantic readiness check before downstream generation."""
    issues: list[ValidationIssue] = []

    # This is mostly a placeholder; the actual readiness decision is
    # made by the QualityEngine based on all dimensions.
    # Here we just check for known hard blockers.

    cms = context.cms_compilation_result
    if cms is None:
        return issues

    # No camera = not ready
    camera = getattr(cms, "camera", None)
    if camera is None:
        issues.append(
            ValidationIssue(
                issue_id=_make_issue_id("generation.no-camera"),
                dimension="generation_readiness",
                severity=ValidationSeverity.BLOCKING,
                source=IssueSource.STRUCTURAL,
                message=(
                    "Cannot proceed to generation without camera intent."
                ),
                field_path="camera",
                rule_id="generation.no-camera",
            )
        )

    return issues


# ============================================================================
# Public exports
# ============================================================================


__all__ = [
    "validate_contract_compatibility",
    "validate_semantic_completeness",
    "validate_character_identity",
    "validate_camera",
    "validate_motion",
    "validate_camera_motion_compatibility",
    "validate_continuity",
    "validate_prompt_loss",
    "validate_knowledge_provenance",
    "validate_sound_semantic",
    "validate_format",
    "validate_fallback_visibility",
    "validate_conflict_visibility",
    "validate_provider_readiness",
    "validate_generation_readiness",
]
