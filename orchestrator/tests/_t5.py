"""
Comprehensive tests for L-U7 — Hybrid Quality Validation.

Covers all required categories:
A. Schema
B. Determinism
C. Completeness
D. Identity
E. Camera
F. Motion
G. Camera/Motion distinction
H. Camera/Motion compatibility
I. Continuity
J. Prompt loss
K. Provenance
L. Fallback
M. Conflict
N. Sound
O. Format
P. Storyboard
Q. Character
R. Knowledge architecture
S. Provider neutrality
T. Renderer neutrality
U. Cross-scene
V. Policy
W. Fingerprint
X. Golden fixtures
Y. Backward compatibility
"""

from __future__ import annotations

import pytest

from app.character.reference_schema import (
    CharacterReferenceSpecification,
    IdentityBearingProperty,
    SceneVariableProperty,
)
from app.prompt.cms_compiler import CameraMotionSoundCompiler
from app.prompt.compiler import PromptCompiler
from app.prompt.schemas import (
    CameraBlockExt,
    CameraDirection,
    CameraMotionVocabulary,
    CameraShotVocabulary,
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
)
from app.quality.engine import QualityEngine
from app.quality.schemas import (
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


# ============================================================================
# Helpers
# ============================================================================


def _build_pcr(prompt_kind=PromptKind.IMAGE, **kwargs):
    """Build a PromptCompilationRequest."""
    defaults = {
        "prompt_kind": prompt_kind,
        "character_reference_id": "farmer_01",
        "scene_camera": "medium",
        "aspect_ratio": "16:9",
    }
    defaults.update(kwargs)
    return PromptCompilationRequest(**defaults)


def _build_cms_result(prompt_kind=PromptKind.IMAGE, **kwargs):
    """Build a CMS compilation result."""
    compiler = CameraMotionSoundCompiler()
    req = _build_pcr(prompt_kind=prompt_kind, **kwargs)
    return compiler.compile(req)


def _build_prompt_result(prompt_kind=PromptKind.IMAGE, **kwargs):
    """Build a PromptCompilationResult."""
    compiler = PromptCompiler()
    req = _build_pcr(prompt_kind=prompt_kind, **kwargs)
    return compiler.compile(req)


def _build_char_spec(char_id="farmer_01"):
    return CharacterReferenceSpecification(
        character_id=char_id,
        identity_properties=frozenset({
            IdentityBearingProperty.HEAD_SHAPE,
            IdentityBearingProperty.PALETTE,
        }),
        scene_variables=frozenset({
            SceneVariableProperty.POSE,
            SceneVariableProperty.EXPRESSION,
        }),
    )


def _build_context(
    prompt_kind=PromptKind.IMAGE,
    with_pcr=True,
    with_cms=True,
    with_char=True,
    with_sb=False,
    policy=None,
    **kwargs,
):
    pcr = _build_prompt_result(prompt_kind=prompt_kind, **kwargs) if with_pcr else None
    cms = _build_cms_result(prompt_kind=prompt_kind, **kwargs) if with_cms else None
    char = _build_char_spec() if with_char else None

    return QualityValidationContext(
        prompt_compilation_result=pcr,
        cms_compilation_result=cms,
        character_reference_spec=char,
        policy=policy or ValidationPolicy.standard(),
    )


# ============================================================================
# A. Schema validation
# ============================================================================


class TestSchema:
    """Schema validation for all L-U7 contracts."""

    def test_validation_status_enum(self):
        assert ValidationStatus.PASS.value == "pass"
