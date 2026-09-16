"""NarrationScript adapter tests (PROMPT 8 §10, §11)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.script import Script, ScriptBeat, ScriptSection
from app.voice.narration import build_narration_script


def _script() -> Script:
    return Script(
        topic="Ice Age",
        sections=[
            ScriptSection(name="intro", beats=[
                ScriptBeat(text="Rome fell in 476 AD.", emotional_intent="neutral"),
                ScriptBeat(text="Constantinople rose in 330 AD.", emotional_intent="neutral"),
            ]),
            ScriptSection(name="body", beats=[
                ScriptBeat(text="The transition was gradual.", emotional_intent="neutral"),
            ]),
        ],
    )


def test_build_narration_script_basic():
    s = _script()
    ns = build_narration_script(
        script_id="ns1", job_id="job1", project_id="proj1", script=s,
    )
    assert len(ns.units) == 3
    assert ns.units[0].text == "Rome fell in 476 AD."
    assert ns.units[0].narration_id == "n_0001"
    assert ns.units[0].speaker_id == "narrator"


def test_build_narration_script_unique_ids():
    s = _script()
    ns = build_narration_script(
        script_id="ns1", job_id="job1", project_id="proj1", script=s,
    )
    ids = [u.narration_id for u in ns.units]
    assert len(set(ids)) == len(ids)


def test_build_narration_script_locale_default():
    s = _script()
    ns = build_narration_script(
        script_id="ns1", job_id="job1", project_id="proj1",
        script=s, language="vi",
    )
    assert ns.locale == "vi-XX"
    for u in ns.units:
        assert u.locale == "vi-XX"


def test_build_narration_script_locale_explicit():
    s = _script()
    ns = build_narration_script(
        script_id="ns1", job_id="job1", project_id="proj1",
        script=s, language="vi", locale="vi-VN",
    )
    assert ns.locale == "vi-VN"


def test_build_narration_script_accepts_dict():
    s = _script()
    d = s.model_dump()
    ns = build_narration_script(
        script_id="ns1", job_id="job1", project_id="proj1", script=d,
    )
    assert len(ns.units) == 3


def test_build_narration_script_default_voice_id():
    s = _script()
    ns = build_narration_script(
        script_id="ns1", job_id="job1", project_id="proj1",
        script=s, default_voice_id="narrator_vi",
    )
    assert ns.default_voice_id == "narrator_vi"


def test_build_narration_script_invalid_default_voice_id():
    s = _script()
    with pytest.raises(ValidationError):
        build_narration_script(
            script_id="ns1", job_id="job1", project_id="proj1",
            script=s, default_voice_id="Bad ID!",
        )
