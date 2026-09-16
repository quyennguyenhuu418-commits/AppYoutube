"""
Provider Generation Layer — L-U8 Provider Adapter Layer.

Canonical boundary between the semantic production pipeline (L-U1–L-U8)
and the generation runtime.

Submodules
----------
schemas  — Canonical Pydantic contracts (ProviderDefinition, ProviderCapability,
           ProviderPromptAdapter, ProviderGenerationRequest, SemanticLossReport,
           ProviderError).
registry — Deterministic ProviderRegistry (single source of truth).
matcher  — Deterministic CapabilityMatcher.
mock_adapter — Deterministic MockProviderAdapter (no real generation).

Usage
-----
from app.providers.generation.schemas import *
from app.providers.generation.registry import get_registry
from app.providers.generation.matcher import match_capability, find_compatible_providers
from app.providers.generation.mock_adapter import MockGenerationProviderAdapter
"""

from app.providers.generation.schemas import (
    AspectRatioSpec,
    CapabilityCompatibility,
    CapabilityMatchResult,
    CapabilityVerificationStatus,
    ExecutionMode,
    GenerationCapabilityRequirement,
    ProviderCapability,
    ProviderDefinition,
    ProviderError,
    ProviderErrorKind,
    ProviderPromptAdapter,
    ProviderPromptRepresentation,
    ProviderGenerationRequest,
    ProviderStatus,
    ProviderType,
    ProviderVerificationStatus,
    RetryClassification,
    SemanticLossField,
    SemanticLossReport,
    SemanticLossStatus,
)

from app.providers.generation.registry import get_registry

__all__ = [
    # Enums
    "AspectRatioSpec",
    "CapabilityCompatibility",
    "CapabilityMatchResult",
    "CapabilityVerificationStatus",
    "ExecutionMode",
    "GenerationCapabilityRequirement",
    "ProviderCapability",
    "ProviderDefinition",
    "ProviderError",
    "ProviderErrorKind",
    "ProviderPromptAdapter",
    "ProviderPromptRepresentation",
    "ProviderGenerationRequest",
    "ProviderStatus",
    "ProviderType",
    "ProviderVerificationStatus",
    "RetryClassification",
    "SemanticLossField",
    "SemanticLossReport",
    "SemanticLossStatus",
    # Registry
    "get_registry",
]
