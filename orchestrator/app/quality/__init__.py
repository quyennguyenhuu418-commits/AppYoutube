"""
Hybrid Quality Validation (L-U7).

L-U7 — Quality gate before provider/generation layer.

Modules:
    schemas    — canonical contracts (QualityValidationResult, Context, Policy, Issue)
    validators — pure dimension validators (deterministic, no LLM)
    engine     — orchestrator (aggregates validators, computes decision)
"""

from app.quality.engine import QualityEngine
from app.quality.schemas import (
    DimensionResult,
    DimensionState,
    GenerationReadiness,
    IssueSource,
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

__all__ = [
    "QualityEngine",
    # Enums
    "ValidationStatus",
    "GenerationReadiness",
    "ValidationSeverity",
    "ValidationDimension",
    "DimensionState",
    "ValidationPolicyName",
    "IssueSource",
    # Models
    "ValidationPolicy",
    "ValidationIssue",
    "DimensionResult",
    "PromptLossReport",
    "QualityValidationResult",
    "QualityValidationContext",
    # Helpers
    "derive_deterministic_id",
    "derive_content_fingerprint",
]
