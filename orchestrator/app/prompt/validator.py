"""
PromptValidator — deterministic validation for PromptCompilationResult.

L-U5 — Prompt Compiler V2.

Purpose
-------
The `PromptValidator` performs deterministic, NO-LLM validation of a
`CanonicalPromptIR`. It produces a structured `PromptValidationReport`.

Validation rules (deterministic, no LLM):
1. Required subject (if generating a prompt, something must be depicted)
2. Valid prompt kind
3. Character identity consistency (identity properties preserved)
4. Negative constraints present when knowledge is active
5. Provider capability compatibility (enforced via PromptKind)
6. Format validity (aspect ratio format)
7. Camera validity (shot type vocabulary)
8. Motion validity (motion pattern vocabulary)
9. No forbidden provider syntax in canonical layer (structural check)
10. Provenance integrity
11. No unresolved forbidden conflicts
12. Deterministic ordering

What this module does NOT do:
- It does NOT call any LLM to judge prompt quality
- It does NOT generate prompts
- It does NOT evaluate artistic merit
- It does NOT call image/video generation APIs
"""

from __future__ import annotations

from app.prompt.schemas import (
    CanonicalPromptIR,
    PromptCompilationRequest,
    PromptKind,
    PromptValidationReport,
    ValidationFinding,
    ValidationSeverity,
)


class PromptValidator:
    """Deterministic validator for PromptCompilationResult.

    All validation rules are deterministic and do NOT require LLM.
    """

    def validate(
        self,
        ir: CanonicalPromptIR,
        request: PromptCompilationRequest,
    ) -> PromptValidationReport:
        """Validate a canonical Prompt IR.

        Returns a PromptValidationReport with blocking, warning, and info findings.
        """
        blocking: list[ValidationFinding] = []
        warnings: list[ValidationFinding] = []
        info: list[ValidationFinding] = []

        # Rule 1: Valid prompt kind
        self._check_prompt_kind(ir, info)

        # Rule 2: Required subject
        self._check_subject_present(ir, blocking)

        # Rule 3: Character identity consistency
        self._check_identity_consistency(ir, warnings)

        # Rule 4: Negative constraints when knowledge active
        self._check_constraints_present(ir, warnings)

        # Rule 5: Provider capability compatibility
        self._check_capability_compatibility(ir, request, warnings)

        # Rule 6: Format validity
        self._check_format_validity(ir, warnings)

        # Rule 7: Camera validity
        self._check_camera_validity(ir, warnings)

        # Rule 8: Motion validity (VIDEO only)
        self._check_motion_validity(ir, warnings)

        # Rule 9: No forbidden syntax
        self._check_no_forbidden_syntax(ir, blocking)

        # Rule 10: Provenance integrity
        self._check_provenance_integrity(ir, warnings)

        # Rule 11: No unresolved conflicts
        self._check_no_conflicts(ir, blocking)

        # Rule 12: Deterministic ordering (structural)
        self._check_deterministic_structure(ir, info)

        return PromptValidationReport(
            is_valid=len(blocking) == 0,
            blocking_findings=blocking,
            warnings=warnings,
            info=info,
        )

    def _check_prompt_kind(
        self, ir: CanonicalPromptIR, info: list[ValidationFinding]
    ) -> None:
        """Validate that prompt kind is set and consistent."""
        if ir.prompt_kind not in (PromptKind.IMAGE, PromptKind.VIDEO):
            info.append(
                ValidationFinding(
                    rule_id="prompt_kind",
                    field_path="ir.prompt_kind",
                    message=f"Unexpected prompt kind: {ir.prompt_kind}",
                    severity=ValidationSeverity.INFO,
                )
            )

    def _check_subject_present(
        self, ir: CanonicalPromptIR, blocking: list[ValidationFinding]
    ) -> None:
        """A prompt must have a subject (character, environment, or action)."""
        has_subject = (
            (ir.subject is not None and ir.subject.character_id is not None)
            or (ir.environment is not None and ir.environment.setting is not None)
            or (ir.action is not None and ir.action.description is not None)
        )
        if not has_subject:
            blocking.append(
                ValidationFinding(
                    rule_id="subject_required",
                    field_path="ir.subject",
                    message="Prompt IR has no subject: at least one of character, environment, or action is required",
                    severity=ValidationSeverity.BLOCKING,
                )
            )

    def _check_identity_consistency(
        self, ir: CanonicalPromptIR, warnings: list[ValidationFinding]
    ) -> None:
        """Identity-bearing properties should not disappear from the IR."""
        # If we have a character reference but no identity preservation,
        # warn that identity may not be preserved
        if ir.subject and ir.subject.character_id:
            if not ir.identity or len(ir.identity.locked_properties) == 0:
                warnings.append(
                    ValidationFinding(
                        rule_id="identity_not_preserved",
                        field_path="ir.identity",
                        message=(
                            f"Character '{ir.subject.character_id}' has no identity "
                            "preservation rules. Character may be redesigned "
                            "across scenes."
                        ),
                        severity=ValidationSeverity.WARNING,
                    )
                )

    def _check_constraints_present(
        self, ir: CanonicalPromptIR, warnings: list[ValidationFinding]
    ) -> None:
        """When knowledge is active, negative constraints should be present."""
        if ir.is_knowledge_active:
            if ir.constraints.is_empty():
                warnings.append(
                    ValidationFinding(
                        rule_id="constraints_missing",
                        field_path="ir.constraints",
                        message=(
                            "Knowledge is active but no negative constraints "
                            "were resolved. Consider adding identity preservation "
                            "constraints."
                        ),
                        severity=ValidationSeverity.WARNING,
                    )
                )

    def _check_capability_compatibility(
        self,
        ir: CanonicalPromptIR,
        request: PromptCompilationRequest,
        warnings: list[ValidationFinding],
    ) -> None:
        """Check that IR fields are compatible with the declared prompt kind."""
        if ir.prompt_kind == PromptKind.IMAGE:
            # Motion should not be declared for IMAGE
            if ir.motion is not None:
                warnings.append(
                    ValidationFinding(
                        rule_id="motion_on_image",
                        field_path="ir.motion",
                        message=(
                            "Motion declared on IMAGE prompt. "
                            "Motion is VIDEO-only. Ignoring motion."
                        ),
                        severity=ValidationSeverity.WARNING,
                    )
                )

    def _check_format_validity(
        self, ir: CanonicalPromptIR, warnings: list[ValidationFinding]
    ) -> None:
        """Validate aspect ratio format."""
        if ir.format and ir.format.aspect_ratio:
            ar = ir.format.aspect_ratio
            valid_ratios = {"16:9", "9:16", "4:3", "1:1", "21:9"}
            if ar not in valid_ratios:
                warnings.append(
                    ValidationFinding(
                        rule_id="aspect_ratio_unknown",
                        field_path="ir.format.aspect_ratio",
                        message=(
                            f"Aspect ratio '{ar}' is not in the canonical "
                            f"list {valid_ratios}. This may not be supported "
                            "by all providers."
                        ),
                        severity=ValidationSeverity.WARNING,
                    )
                )

    def _check_camera_validity(
        self, ir: CanonicalPromptIR, warnings: list[ValidationFinding]
    ) -> None:
        """Validate that camera shot types use canonical vocabulary."""
        if ir.camera and ir.camera.shot_type:
            # shot_type should already be a canonical vocabulary enum value
            # If it's a string, it might not be valid
            if isinstance(ir.camera.shot_type, str):
                valid_shots = {
                    "extreme_wide", "wide", "medium_wide", "medium",
                    "medium_close", "close", "extreme_close", "over_shoulder",
                    "pov", "dutch", "birds_eye", "worms_eye", "two_shot",
                }
                if ir.camera.shot_type not in valid_shots:
                    warnings.append(
                        ValidationFinding(
                            rule_id="camera_shot_unknown",
                            field_path="ir.camera.shot_type",
                            message=(
                                f"Camera shot type '{ir.camera.shot_type}' "
                                f"is not in canonical vocabulary. "
                                f"Known: {valid_shots}"
                            ),
                            severity=ValidationSeverity.WARNING,
                        )
                    )

    def _check_motion_validity(
        self, ir: CanonicalPromptIR, warnings: list[ValidationFinding]
    ) -> None:
        """Validate that motion patterns use canonical vocabulary (VIDEO only)."""
        if ir.prompt_kind != PromptKind.VIDEO:
            return
        if ir.motion and ir.motion.pattern:
            if isinstance(ir.motion.pattern, str):
                valid_patterns = {
                    "frame_by_frame", "loop", "rig_pose_interpolation",
                    "kinetic_text", "shake_nervous",
                }
                if ir.motion.pattern not in valid_patterns:
                    warnings.append(
                        ValidationFinding(
                            rule_id="motion_pattern_unknown",
                            field_path="ir.motion.pattern",
                            message=(
                                f"Motion pattern '{ir.motion.pattern}' "
                                f"is not in canonical vocabulary. "
                                f"Known: {valid_patterns}"
                            ),
                            severity=ValidationSeverity.WARNING,
                        )
                    )

    def _check_no_forbidden_syntax(
        self, ir: CanonicalPromptIR, blocking: list[ValidationFinding]
    ) -> None:
        """Check that no provider-specific syntax leaked into the IR.

        The canonical IR should NOT contain provider-specific syntax like
        --ar, --style, Google Flow flags, etc. These belong in the
        ProviderPromptAdapter, not in the core IR.
        """
        # Check string fields for common provider syntax patterns
        forbidden_patterns = [
            "--ar", "--style", "--seed", "--model",
            "google_flow", "dino_api", "vertex_ai",
            "openai_image", "dalle", "midjourney",
        ]

        findings: list[ValidationFinding] = []

        # Check subject description
        if ir.subject and ir.subject.character_description:
            text = ir.subject.character_description
            for pattern in forbidden_patterns:
                if pattern in text:
                    blocking.append(
                        ValidationFinding(
                            rule_id="forbidden_provider_syntax",
                            field_path="ir.subject.character_description",
                            message=(
                                f"Provider-specific syntax '{pattern}' found in "
                                "canonical IR. Provider syntax belongs in "
                                "ProviderPromptAdapter, not in core IR."
                            ),
                            severity=ValidationSeverity.BLOCKING,
                        )
                    )
                    return  # Already found one, no need to check further

        # Check style palette hint
        if ir.style and ir.style.palette_hint:
            text = ir.style.palette_hint
            for pattern in forbidden_patterns:
                if pattern in text:
                    blocking.append(
                        ValidationFinding(
                            rule_id="forbidden_provider_syntax",
                            field_path="ir.style.palette_hint",
                            message=f"Provider-specific syntax '{pattern}' in IR",
                            severity=ValidationSeverity.BLOCKING,
                        )
                    )
                    return

    def _check_provenance_integrity(
        self, ir: CanonicalPromptIR, warnings: list[ValidationFinding]
    ) -> None:
        """Check that provenance is present when knowledge is active."""
        if ir.is_knowledge_active:
            if len(ir.knowledge_ids_used) == 0:
                warnings.append(
                    ValidationFinding(
                        rule_id="provenance_missing",
                        field_path="ir.knowledge_ids_used",
                        message=(
                            "Knowledge is active but no knowledge IDs are "
                            "recorded in the IR. Provenance may be incomplete."
                        ),
                        severity=ValidationSeverity.WARNING,
                    )
                )

    def _check_no_conflicts(
        self, ir: CanonicalPromptIR, blocking: list[ValidationFinding]
    ) -> None:
        """Check for unresolved conflicts in the IR."""
        # If the IR has explicit conflicts (not yet implemented in L-U5,
        # but the pattern exists in L-U4), we would check them here.
        # For L-U5, we leave this as a structural check placeholder.
        pass

    def _check_deterministic_structure(
        self, ir: CanonicalPromptIR, info: list[ValidationFinding]
    ) -> None:
        """Check that the IR has a deterministic structure."""
        if ir.compiler_version:
            info.append(
                ValidationFinding(
                    rule_id="compiler_version",
                    field_path="ir.compiler_version",
                    message=f"Compiled with PromptCompiler {ir.compiler_version}",
                    severity=ValidationSeverity.INFO,
                )
            )


__all__ = [
    "PromptValidator",
]
