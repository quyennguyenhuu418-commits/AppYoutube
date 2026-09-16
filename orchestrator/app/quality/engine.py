"""
Quality Engine — orchestrates all dimension validators.

L-U7 — Hybrid Quality Validation.

Architecture
------------
    QualityValidationContext
            ↓
    QualityEngine.validate(context)
            ↓
    ┌─────────────────────────────────────────┐
    │ 1. validate_contract_compatibility      │
    │ 2. validate_semantic_completeness       │
    │ 3. validate_character_identity          │
    │ 4. validate_camera                      │
    │ 5. validate_motion                      │
    │ 6. validate_camera_motion_compatibility │
    │ 7. validate_continuity                  │
    │ 8. validate_prompt_loss                 │
    │ 9. validate_knowledge_provenance        │
    │ 10. validate_sound_semantic             │
    │ 11. validate_format                     │
    │ 12. validate_fallback_visibility       │
    │ 13. validate_conflict_visibility        │
    │ 14. validate_provider_readiness         │
    │ 15. validate_generation_readiness       │
    └─────────────────────────────────────────┘
            ↓
    Aggregate issues by dimension, severity
            ↓
    Policy-driven decision → PASS / WARN / REJECT / UNAVAILABLE
            ↓
    QualityValidationResult (frozen, deterministic)

Critical invariants:
1. The engine REPORTS. It NEVER mutates upstream contracts.
2. No fake quality scores.
3. No provider SDK / Remotion / FFmpeg imports.
4. Deterministic: same input → same output.
5. Validation fingerprint is derived from canonical inputs ONLY.
"""

from __future__ import annotations

from typing import Optional

from app.quality import validators as V
from app.quality.schemas import (
    DimensionResult,
    DimensionState,
    GenerationReadiness,
    PromptLossReport,
    QualityValidationContext,
    QualityValidationResult,
    ValidationDimension,
    ValidationIssue,
    ValidationPolicy,
    ValidationPolicyName,
    ValidationSeverity,
    ValidationStatus,
    derive_content_fingerprint,
    derive_deterministic_id,
)


class QualityEngine:
    """L-U7 — Hybrid Quality Validation Engine.

    Pure, deterministic. NO LLM. NO provider. NO renderer.
    """

    ENGINE_VERSION = "1.0.0"
    POLICY_VERSION = "1.0.0"

    def __init__(self, policy: Optional[ValidationPolicy] = None) -> None:
        self._policy = policy or ValidationPolicy.standard()

    @property
    def policy(self) -> ValidationPolicy:
        return self._policy

    def set_policy(self, policy: ValidationPolicy) -> None:
        """Set the validation policy. Idempotent."""
        self._policy = policy

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def validate(
        self,
        context: QualityValidationContext,
    ) -> QualityValidationResult:
        """Run all dimension validators and aggregate results.

        Parameters:
            context: QualityValidationContext (immutable bundle of upstream contracts)

        Returns:
            QualityValidationResult (frozen, deterministic)
        """
        # Special case: no minimum inputs → UNAVAILABLE
        if not context.has_minimum_inputs():
            return self._build_unavailable(context)

        # Run all 15 dimension validators
        all_issues: list[ValidationIssue] = []
        dim_to_issues: dict[ValidationDimension, list[ValidationIssue]] = {}

        dimension_funcs = [
            (ValidationDimension.CONTRACT_COMPATIBILITY, V.validate_contract_compatibility),
            (ValidationDimension.SEMANTIC_COMPLETENESS, V.validate_semantic_completeness),
            (ValidationDimension.CHARACTER_IDENTITY_CONSISTENCY, V.validate_character_identity),
            (ValidationDimension.CAMERA, V.validate_camera),
            (ValidationDimension.MOTION, V.validate_motion),
            (ValidationDimension.CAMERA_MOTION_COMPATIBILITY, V.validate_camera_motion_compatibility),
            (ValidationDimension.CONTINUITY, V.validate_continuity),
            (ValidationDimension.PROMPT_LOSS, V.validate_prompt_loss),
            (ValidationDimension.KNOWLEDGE_PROVENANCE, V.validate_knowledge_provenance),
            (ValidationDimension.SOUND_SEMANTIC, V.validate_sound_semantic),
            (ValidationDimension.FORMAT, V.validate_format),
            (ValidationDimension.FALLBACK_VISIBILITY, V.validate_fallback_visibility),
            (ValidationDimension.CONFLICT_VISIBILITY, V.validate_conflict_visibility),
            (ValidationDimension.PROVIDER_READINESS, V.validate_provider_readiness),
            (ValidationDimension.GENERATION_READINESS, V.validate_generation_readiness),
        ]

        for dim, func in dimension_funcs:
            try:
                issues = func(context)
            except Exception as exc:  # pragma: no cover - safety net
                issues = [
                    ValidationIssue(
                        issue_id=f"validator.{dim.value}.exception",
                        dimension=dim,
                        severity=ValidationSeverity.ERROR,
                        message=f"Validator '{dim.value}' raised: {exc!s}",
                        rule_id=f"validator.{dim.value}.exception",
                    )
                ]
            dim_to_issues[dim] = issues
            all_issues.extend(issues)

        # Build per-dimension results
        dimension_results: list[DimensionResult] = []
        for dim, _ in dimension_funcs:
            issues = dim_to_issues.get(dim, [])
            dr = DimensionResult.from_issues(dim, issues)
            dimension_results.append(dr)

        # Sort all issues by (severity, dimension, issue_id)
        severity_order = {
            ValidationSeverity.BLOCKING: 0,
            ValidationSeverity.ERROR: 1,
            ValidationSeverity.WARNING: 2,
            ValidationSeverity.INFO: 3,
        }
        all_issues.sort(
            key=lambda i: (
                severity_order.get(i.severity, 99),
                i.dimension.value,
                i.issue_id,
            )
        )

        blocking = tuple(
            i for i in all_issues if i.severity == ValidationSeverity.BLOCKING
        )
        errors = tuple(
            i for i in all_issues if i.severity == ValidationSeverity.ERROR
        )
        warnings = tuple(
            i for i in all_issues if i.severity == ValidationSeverity.WARNING
        )
        infos = tuple(
            i for i in all_issues if i.severity == ValidationSeverity.INFO
        )

        # Apply policy
        status = self._compute_status(blocking, errors, warnings, context)
        generation_readiness = self._compute_readiness(status, blocking, errors)

        # Compute fingerprints (deterministic from canonical inputs)
        prompt_fingerprint = self._compute_prompt_fingerprint(
            context.prompt_compilation_result
        )
        cms_fingerprint = self._compute_cms_fingerprint(
            context.cms_compilation_result
        )
        char_id = self._compute_character_id(context.character_reference_spec)
        sb_fingerprint = self._compute_storyboard_fingerprint(context.storyboard_package)

        validation_id = derive_deterministic_id(
            prompt_compilation_fingerprint=prompt_fingerprint,
            cms_compilation_fingerprint=cms_fingerprint,
            character_reference_id=char_id,
            storyboard_fingerprint=sb_fingerprint,
            policy_name=self._policy.name.value,
            engine_version=self.ENGINE_VERSION,
        )

        # Build prompt loss report (structural)
        prompt_loss = self._build_prompt_loss_report(all_issues)

        return QualityValidationResult(
            validation_id=validation_id,
            status=status,
            generation_readiness=generation_readiness,
            is_valid=(status == ValidationStatus.PASS or status == ValidationStatus.WARN),
            policy_name=self._policy.name,
            dimensions=tuple(dimension_results),
            blocking_issues=blocking,
            errors=errors,
            warnings=warnings,
            infos=infos,
            prompt_loss=prompt_loss,
            knowledge_version=context.knowledge_version,
            is_knowledge_active=context.is_knowledge_active,
            knowledge_ids_used=context.knowledge_ids_used,
            prompt_compilation_fingerprint=prompt_fingerprint,
            cms_compilation_fingerprint=cms_fingerprint,
            character_reference_id=char_id,
            storyboard_fingerprint=sb_fingerprint,
            engine_version=self.ENGINE_VERSION,
            policy_version=self.POLICY_VERSION,
        )

    # ------------------------------------------------------------------
    # Status / readiness computation
    # ------------------------------------------------------------------

    def _compute_status(
        self,
        blocking: tuple[ValidationIssue, ...],
        errors: tuple[ValidationIssue, ...],
        warnings: tuple[ValidationIssue, ...],
        context: QualityValidationContext,
    ) -> ValidationStatus:
        if blocking and self._policy.block_on_blocking:
            return ValidationStatus.REJECT
        if errors and self._policy.block_on_error:
            return ValidationStatus.REJECT
        if warnings and self._policy.block_on_warning:
            if len(warnings) > self._policy.max_warnings:
                return ValidationStatus.REJECT
            return ValidationStatus.WARN
        if warnings:
            return ValidationStatus.WARN
        return ValidationStatus.PASS

    def _compute_readiness(
        self,
        status: ValidationStatus,
        blocking: tuple[ValidationIssue, ...],
        errors: tuple[ValidationIssue, ...],
    ) -> GenerationReadiness:
        if status == ValidationStatus.REJECT:
            return GenerationReadiness.NOT_READY
        if status == ValidationStatus.WARN:
            return GenerationReadiness.READY_WITH_WARNINGS
        if status == ValidationStatus.PASS:
            return GenerationReadiness.READY
        return GenerationReadiness.UNAVAILABLE

    # ------------------------------------------------------------------
    # Fingerprint helpers
    # ------------------------------------------------------------------

    def _compute_prompt_fingerprint(
        self, pcr: object
    ) -> Optional[str]:
        if pcr is None:
            return None
        try:
            content = self._stable_json(pcr)
        except Exception:
            content = str(pcr)
        return derive_content_fingerprint(content)

    def _compute_cms_fingerprint(
        self, cms: object
    ) -> Optional[str]:
        if cms is None:
            return None
        try:
            content = self._stable_json(cms)
        except Exception:
            content = str(cms)
        return derive_content_fingerprint(content)

    def _compute_character_id(self, spec: object) -> Optional[str]:
        if spec is None:
            return None
        return getattr(spec, "character_id", None)

    def _compute_storyboard_fingerprint(
        self, storyboard: object
    ) -> Optional[str]:
        if storyboard is None:
            return None
        try:
            content = (
                storyboard.model_dump_json()
                if hasattr(storyboard, "model_dump_json")
                else str(storyboard)
            )
        except Exception:
            content = str(storyboard)
        return derive_content_fingerprint(content)

    def _stable_json(self, obj: object) -> str:
        """Stable JSON serialization that excludes timestamp/now fields.

        Excludes `compiled_at` and `validated_at` fields which use
        `default_factory=datetime.utcnow()` and would otherwise break
        determinism of the validation fingerprint.
        """
        try:
            data = obj.model_dump(mode="json")
        except Exception:
            return obj.model_dump_json() if hasattr(obj, "model_dump_json") else str(obj)

        # Strip non-deterministic fields
        for key in ("compiled_at", "validated_at", "created_at", "updated_at"):
            if isinstance(data, dict):
                data.pop(key, None)
        return str(data)

    # ------------------------------------------------------------------
    # Prompt loss
    # ------------------------------------------------------------------

    def _build_prompt_loss_report(
        self, issues: list[ValidationIssue]
    ) -> Optional[PromptLossReport]:
        loss_issues = [
            i for i in issues if i.dimension == ValidationDimension.PROMPT_LOSS
        ]
        if not loss_issues:
            return PromptLossReport(
                expected_elements=(),
                resolved_elements=(),
                lost_elements=(),
                partially_resolved=(),
                severity=ValidationSeverity.INFO,
            )

        # Collect any reported lost elements
        lost: list[str] = []
        for i in loss_issues:
            if i.field_path:
                lost.append(i.field_path)

        if not lost:
            return None

        return PromptLossReport(
            expected_elements=tuple(lost),
            resolved_elements=(),
            lost_elements=tuple(lost),
            partially_resolved=(),
            severity=ValidationSeverity.WARNING,
        )

    # ------------------------------------------------------------------
    # Unavailable
    # ------------------------------------------------------------------

    def _build_unavailable(
        self, context: QualityValidationContext
    ) -> QualityValidationResult:
        issue = ValidationIssue(
            issue_id="unavailable.no-inputs",
            dimension=ValidationDimension.CONTRACT_COMPATIBILITY,
            severity=ValidationSeverity.BLOCKING,
            message="No canonical input provided.",
        )
        return QualityValidationResult(
            validation_id="unavailable",
            status=ValidationStatus.UNAVAILABLE,
            generation_readiness=GenerationReadiness.UNAVAILABLE,
            is_valid=False,
            policy_name=self._policy.name,
            dimensions=(),
            blocking_issues=(issue,),
            errors=(),
            warnings=(),
            infos=(),
            prompt_loss=None,
            knowledge_version=context.knowledge_version,
            is_knowledge_active=context.is_knowledge_active,
            knowledge_ids_used=context.knowledge_ids_used,
            engine_version=self.ENGINE_VERSION,
            policy_version=self.POLICY_VERSION,
        )


# ============================================================================
# Public exports
# ============================================================================


__all__ = ["QualityEngine"]
