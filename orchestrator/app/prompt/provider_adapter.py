"""
Provider Prompt Adapter — abstract boundary for provider-specific serialization.

L-U5 — Prompt Compiler V2.

Purpose
-------
`ProviderPromptAdapter` is the abstract boundary between the canonical
`CanonicalPromptIR` and provider-specific prompt syntax (Google Flow,
DINO AI, Axen, etc.).

The core `PromptCompiler` produces a structured IR that is
PROVIDER-NEUTRAL. Each concrete provider adapter is RESPONSIBLE for
translating the IR into provider-specific syntax.

Architecture
-----------
    CanonicalPromptIR
            ↓
    ProviderPromptAdapter (abstract)
            ↓
    ┌──────┴──────┐
    ↓              ↓
GoogleFlow     DinoPromptAdapter
Adapter       (example)
    ↓
ProviderPrompt (string)

Design principles
----------------
1. The abstract `ProviderPromptAdapter` does NOT contain provider syntax.
2. Each concrete adapter is RESPONSIBLE for its own serialization.
3. The adapters do NOT call image/video generation APIs.
4. The adapters do NOT call LLM to write prompts.
5. The adapters are DETERMINISTIC.

What this module does NOT do:
- It does NOT call any image generation API
- It does NOT generate prompts from scratch (the compiler does that)
- It does NOT contain provider SDK imports in the abstract base
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.prompt.schemas import CanonicalPromptIR, PromptCompilationResult


# ============================================================================
# Provider Prompt — the output of a provider adapter
# ============================================================================


@dataclass(frozen=True)
class ProviderPrompt:
    """A serialized provider-specific prompt.

    This is the OUTPUT of a ProviderPromptAdapter. It is NOT the canonical IR.
    """

    provider_name: str
    """Name of the provider, e.g. 'google_flow', 'dino_ai'."""

    prompt_text: str
    """The serialized provider-specific prompt string."""

    prompt_version: str
    """Version of the provider adapter that produced this prompt."""

    ir_summary: str
    """A short human-readable summary of the IR for debugging."""

    def is_empty(self) -> bool:
        return len(self.prompt_text.strip()) == 0


# ============================================================================
# Abstract base for provider adapters
# ============================================================================


class ProviderPromptAdapter(ABC):
    """Abstract adapter for serializing CanonicalPromptIR to provider syntax.

    Concrete adapters MUST implement:
        serialize(ir) -> ProviderPrompt

    Concrete adapters SHOULD:
        Be deterministic (same IR → same output)
        Preserve all semantic content from the IR
        Not invent content not present in the IR
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """The name of this provider."""
        ...

    @property
    @abstractmethod
    def adapter_version(self) -> str:
        """The version of this adapter."""
        ...

    @abstractmethod
    def serialize(self, ir: CanonicalPromptIR) -> ProviderPrompt:
        """Serialize a canonical Prompt IR to provider-specific prompt text.

        Parameters:
            ir: A valid CanonicalPromptIR.

        Returns:
            A ProviderPrompt with the serialized text.
        """
        ...

    def supports_kind(self, prompt_kind: str) -> bool:
        """Whether this adapter supports a specific prompt kind (image/video)."""
        return True  # Default: supports both

    def can_serialize(self, ir: CanonicalPromptIR) -> bool:
        """Check whether this adapter can serialize the given IR.

        Override to add provider-specific capability checks.
        """
        return True  # Default: can serialize anything


# ============================================================================
# Concrete adapter example: GoogleFlowPromptAdapter (reference implementation)
# ============================================================================
#
# This is a REFERENCE implementation showing the structure of a concrete
# provider adapter. It does NOT call the actual Google Flow API.
# It demonstrates how to serialize the canonical IR to Google Flow syntax.
#
# In production, this would be replaced with the actual Google Flow
# SDK integration.


class GoogleFlowPromptAdapter(ProviderPromptAdapter):
    """Reference adapter for Google Flow-style prompt syntax.

    This adapter serializes CanonicalPromptIR to a Google Flow-style
    prompt format. It is a REFERENCE implementation showing the structure
    only. It does NOT call the Google Flow API.

    The adapter preserves the CANONICAL IR structure and maps it to
    Google Flow prompt conventions:
        - Style first
        - Subject description
        - Environment
        - Camera/motion
        - Negative constraints
        - Format flags
    """

    ADAPTER_VERSION = "1.0.0"

    @property
    def provider_name(self) -> str:
        return "google_flow"

    @property
    def adapter_version(self) -> str:
        return self.ADAPTER_VERSION

    def serialize(self, ir: CanonicalPromptIR) -> ProviderPrompt:
        """Serialize a canonical Prompt IR to Google Flow-style text."""
        parts: list[str] = []

        # 1. Style
        if ir.style:
            style_parts = [ir.style.profile.value.replace("_", " ")]
            if ir.style.palette_hint:
                style_parts.append(ir.style.palette_hint)
            if ir.style.outline_hint:
                style_parts.append(ir.style.outline_hint)
            if ir.style.line_quality:
                style_parts.append(ir.style.line_quality)
            for note in ir.style.rendering_notes[:3]:
                if note and note not in style_parts:
                    style_parts.append(note)
            if style_parts:
                parts.append(", ".join(style_parts))

        # 2. Subject / Character
        if ir.subject:
            subject_parts = []
            if ir.subject.character_description:
                subject_parts.append(ir.subject.character_description)
            if ir.subject.character_id:
                subject_parts.append(f"character: {ir.subject.character_id}")
            if ir.subject.pose:
                subject_parts.append(f"pose: {ir.subject.pose}")
            if ir.subject.expression:
                subject_parts.append(f"expression: {ir.subject.expression}")
            if ir.subject.props:
                subject_parts.append(f"props: {', '.join(ir.subject.props)}")
            if subject_parts:
                parts.append("; ".join(subject_parts))

        # 3. Environment
        if ir.environment:
            env_parts = []
            if ir.environment.setting:
                env_parts.append(ir.environment.setting)
            if ir.environment.era:
                env_parts.append(ir.environment.era)
            if ir.environment.time_of_day:
                env_parts.append(ir.environment.time_of_day)
            if ir.environment.lighting:
                env_parts.append(ir.environment.lighting)
            if env_parts:
                parts.append(", ".join(env_parts))

        # 4. Action
        if ir.action:
            action_parts = []
            if ir.action.description:
                action_parts.append(ir.action.description)
            if ir.action.verbs:
                action_parts.append(" ".join(ir.action.verbs))
            if action_parts:
                parts.append(" ".join(action_parts))

        # 5. Camera
        if ir.camera:
            cam_parts = []
            if ir.camera.shot_type:
                cam_parts.append(f"shot: {ir.camera.shot_type.value.replace('_', ' ')}")
            if ir.camera.movement:
                cam_parts.append(f"movement: {ir.camera.movement.value.replace('_', ' ')}")
            if cam_parts:
                parts.append(" | ".join(cam_parts))

        # 6. Motion (VIDEO only)
        if ir.motion and ir.prompt_kind.value == "video":
            mot_parts = []
            if ir.motion.pattern:
                mot_parts.append(f"motion: {ir.motion.pattern.value.replace('_', ' ')}")
            if ir.motion.loop:
                mot_parts.append("loop")
            if mot_parts:
                parts.append(" | ".join(mot_parts))

        # 7. Background
        if ir.background:
            bg_parts = []
            if ir.background.color:
                bg_parts.append(f"background: {ir.background.color}")
            if ir.background.treatment:
                bg_parts.append(ir.background.treatment)
            if bg_parts:
                parts.append(" | ".join(bg_parts))

        # 8. Negative constraints
        if ir.constraints and not ir.constraints.is_empty():
            neg_parts = []
            for constraint in ir.constraints.constraints[:6]:
                # Shorten constraint text for prompt
                text = constraint.constraint_text[:80]
                neg_parts.append(f"NO {constraint.property_name}: {text}")
            if neg_parts:
                parts.append(" | ".join(neg_parts))

        # 9. Format
        if ir.format:
            fmt_parts = []
            if ir.format.aspect_ratio:
                fmt_parts.append(f"aspect ratio: {ir.format.aspect_ratio}")
            if ir.format.medium:
                fmt_parts.append(f"medium: {ir.format.medium}")
            if fmt_parts:
                parts.append(" | ".join(fmt_parts))

        # Assemble
        prompt_text = " | ".join(parts)

        # Build summary
        ir_summary_parts = []
        if ir.subject and ir.subject.character_id:
            ir_summary_parts.append(f"char={ir.subject.character_id}")
        if ir.style:
            ir_summary_parts.append(f"style={ir.style.profile.value}")
        if ir.camera and ir.camera.shot_type:
            ir_summary_parts.append(f"shot={ir.camera.shot_type.value}")
        ir_summary = ", ".join(ir_summary_parts) if ir_summary_parts else "(no content)"

        return ProviderPrompt(
            provider_name=self.provider_name,
            prompt_text=prompt_text,
            prompt_version=self.ADAPTER_VERSION,
            ir_summary=ir_summary,
        )


__all__ = [
    "ProviderPrompt",
    "ProviderPromptAdapter",
    "GoogleFlowPromptAdapter",
]
