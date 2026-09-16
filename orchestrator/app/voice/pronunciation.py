"""Pronunciation / Emphasis hint canonical model + provider translator.

PROMPT 8 §30–§31. Canonical hints are provider-neutral; concrete
providers translate them into their own syntax (SSML, IPA, custom
phoneme fields, etc.).

The mock provider does not consume hints (its capability says so).
ElevenLabs can consume emphasis_intensity via stability/similarity
overrides.
"""
from __future__ import annotations

from typing import Any

from app.voice.schemas import (
    EmphasisHint,
    PronunciationHint,
    VoiceSettings,
)


def hints_to_provider_params(
    pronunciation: list[PronunciationHint],
    emphasis: list[EmphasisHint],
    voice_id: str,
) -> dict[str, Any]:
    """Translate canonical hints into a provider-agnostic parameter dict.

    Returns a dict; concrete providers consume what they support and
    ignore the rest. No provider-specific syntax leaks here.
    """
    return {
        "pronunciations": [h.model_dump(mode="json") for h in pronunciation],
        "emphases": [h.model_dump(mode="json") for h in emphasis],
        "voice_id": voice_id,
    }


def apply_emphasis_to_settings(
    base: VoiceSettings,
    emphasis_hints: list[EmphasisHint],
) -> VoiceSettings:
    """Adjust VoiceSettings.speaking_rate / stability based on emphasis hints.

    Aggregate effect: average pacing_change shifts speaking_rate;
    average intensity shifts stability slightly upward.
    """
    if not emphasis_hints:
        return base
    avg_pacing = sum(h.pacing_change for h in emphasis_hints) / len(emphasis_hints)
    avg_intensity = sum(h.intensity for h in emphasis_hints) / len(emphasis_hints)
    new_rate = max(0.5, min(2.0, base.speaking_rate * (1.0 + avg_pacing)))
    new_stability = max(0.0, min(1.0, base.stability + 0.1 * (avg_intensity - 0.5)))
    return base.model_copy(update={
        "speaking_rate": round(new_rate, 3),
        "stability": round(new_stability, 3),
    })


__all__ = [
    "hints_to_provider_params",
    "apply_emphasis_to_settings",
]
