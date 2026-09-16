"""Pronunciation / Emphasis hint tests (PROMPT 8 §30, §31)."""
from __future__ import annotations

import pytest

from app.voice.pronunciation import (
    apply_emphasis_to_settings,
    hints_to_provider_params,
)
from app.voice.schemas import (
    EmphasisHint,
    PronunciationHint,
    VoiceSettings,
)


def test_hints_to_provider_params_basic():
    ph = PronunciationHint(hint_id="h1", word="Rome", phonetic="roʊm")
    eh = EmphasisHint(hint_id="e1", text="important", intensity=0.8)
    out = hints_to_provider_params([ph], [eh], voice_id="v1")
    assert out["voice_id"] == "v1"
    assert len(out["pronunciations"]) == 1
    assert len(out["emphases"]) == 1


def test_hints_to_provider_params_empty():
    out = hints_to_provider_params([], [], voice_id="v1")
    assert out["pronunciations"] == []
    assert out["emphases"] == []


def test_apply_emphasis_pacing_change_slows_rate():
    base = VoiceSettings(speaking_rate=1.0)
    eh = EmphasisHint(hint_id="e1", text="x", intensity=0.5, pacing_change=-0.3)
    out = apply_emphasis_to_settings(base, [eh])
    assert out.speaking_rate == pytest.approx(0.7, abs=0.05)


def test_apply_emphasis_intensity_raises_stability():
    base = VoiceSettings(stability=0.5)
    eh = EmphasisHint(hint_id="e1", text="x", intensity=1.0, pacing_change=0.0)
    out = apply_emphasis_to_settings(base, [eh])
    assert out.stability == pytest.approx(0.6, abs=0.05)  # 0.5 + 0.1*(1.0-0.5)


def test_apply_emphasis_no_hints_returns_base():
    base = VoiceSettings(speaking_rate=1.2, stability=0.7)
    out = apply_emphasis_to_settings(base, [])
    assert out.speaking_rate == base.speaking_rate
    assert out.stability == base.stability


def test_apply_emphasis_rate_bounds_respected():
    base = VoiceSettings(speaking_rate=2.0)
    eh = EmphasisHint(hint_id="e1", text="x", intensity=0.5, pacing_change=0.5)
    out = apply_emphasis_to_settings(base, [eh])
    assert out.speaking_rate <= 2.0  # clamped to upper bound
