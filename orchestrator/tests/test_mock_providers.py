"""Tests for the mock LLM provider and the path/job-store helpers."""
from __future__ import annotations

import json

from app.core.paths import read_json, write_json
from app.providers.base import LLMMessage, LLMRequest
from app.providers.mock_llm import (
    MOCK_RESEARCH, MOCK_SCRIPT, MOCK_THESIS, MOCK_TITLES,
    _mock_scene_json, MockLLMProvider,
)
from app.schemas.research import ResearchPackage
from app.schemas.scene_definition import SceneDefinition
from app.schemas.script import Script, Thesis, TitlePackage


def test_mock_research_is_a_valid_package() -> None:
    pkg = ResearchPackage.model_validate(MOCK_RESEARCH)
    assert len(pkg.facts) >= 1


def test_mock_thesis_is_valid() -> None:
    Thesis.model_validate(MOCK_THESIS)


def test_mock_titles_is_valid() -> None:
    pkg = TitlePackage.model_validate(MOCK_TITLES)
    assert 0 <= pkg.chosen_index < len(pkg.candidates)


def test_mock_script_full_text_matches_concatenation() -> None:
    script = Script.model_validate(MOCK_SCRIPT)
    full = script.full_text()
    # Spot-check that all section names appear in the full text.
    for section in script.sections:
        for beat in section.beats:
            assert beat.text in full


def test_mock_scene_json_is_valid() -> None:
    sd = SceneDefinition.model_validate(_mock_scene_json())
    assert len(sd.scenes) > 5


def test_mock_llm_provider_routes_by_intent() -> None:
    """The provider returns the right fixture based on the user prompt."""
    provider = MockLLMProvider()

    # Research intent.
    resp = provider.complete(LLMRequest(
        messages=[LLMMessage(role="user", content="please gather research and sources")],
        json_mode=True,
    ))
    parsed = json.loads(resp.content)
    assert "facts" in parsed and len(parsed["facts"]) >= 1

    # Scene JSON intent.
    resp = provider.complete(LLMRequest(
        messages=[LLMMessage(role="user", content="emit a scene definition")],
        json_mode=True,
    ))
    parsed = json.loads(resp.content)
    assert "scenes" in parsed


def test_roundtrip_json(tmp_path) -> None:
    """The JSON helpers handle unicode and round-trip cleanly."""
    p = tmp_path / "x.json"
    data = {"中文": "测试", "emoji": "🎬"}
    write_json(p, data)
    assert read_json(p) == data
