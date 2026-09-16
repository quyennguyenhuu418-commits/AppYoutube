"""
Prompt Compilation — canonical subsystem for L-U5 + L-U6.

Modules:
    schemas              — canonical contracts (PromptIR, Request, Result) + L-U6 extensions
    compiler             — L-U5 core compilation logic
    validator            — L-U5 validation
    adapters             — L-U5 knowledge adapter
    knowledge_adapter    — L-U6 thin knowledge adapter
    cms_compiler         — L-U6 Camera + Motion + Sound semantic compiler
    cms_validator        — L-U6 deterministic validator
    provider_adapter     — provider-specific serialization boundary
"""

from app.prompt.schemas import (
    CanonicalPromptIR,
    PromptCompilationRequest,
    PromptCompilationResult,
    PromptKind,
    PromptValidationReport,
)

__all__ = [
    "CanonicalPromptIR",
    "PromptCompilationRequest",
    "PromptCompilationResult",
    "PromptKind",
    "PromptValidationReport",
]
