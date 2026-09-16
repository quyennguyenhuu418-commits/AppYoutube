"""NarrationScript adapter — build canonical narration from Story + Script.

PROMPT 8 §10: the LLM may produce narration text + speaker assignment
+ pronunciation/emphasis hints. This module converts the existing
`Script` + `StoryboardPackage` outputs into a canonical `NarrationScript`.

The adapter does NOT duplicate StoryPackage — it consumes the existing
contracts and produces a focused narration view.
"""
from __future__ import annotations

from typing import Any

from app.voice.schemas import (
    EmphasisHint,
    NarrationScript,
    NarrationUnit,
    PronunciationHint,
    SpeakerRole,
    VoiceLifecycleStatus,
)


def build_narration_script(
    *,
    script_id: str,
    job_id: str,
    project_id: str,
    script: Any,
    storyboard_package: Any | None = None,
    language: str = "en",
    locale: str = "",
    default_voice_id: str | None = None,
) -> NarrationScript:
    """Build a canonical NarrationScript from a `Script` + optional StoryboardPackage.

    `script` is an `app.schemas.script.Script` instance (or a dict
    matching its shape). One narration unit per beat.
    """
    # Normalize input — accept dict or Pydantic.
    if hasattr(script, "model_dump"):
        script_dict = script.model_dump()
    else:
        script_dict = script

    units: list[NarrationUnit] = []
    narration_id_seq = 0
    sections = script_dict.get("sections", []) if isinstance(script_dict, dict) else []
    for section in sections:
        beats = section.get("beats", []) if isinstance(section, dict) else []
        for beat in beats:
            narration_id_seq += 1
            beat_text = beat.get("text", "") if isinstance(beat, dict) else str(beat)
            narration_id = f"n_{narration_id_seq:04d}"
            unit = NarrationUnit(
                narration_id=narration_id,
                scene_id="",
                beat_id=f"beat_{narration_id_seq:04d}",
                speaker_id="narrator",
                speaker_role=SpeakerRole.NARRATOR,
                voice_id=None,
                text=beat_text,
                language=language,
                locale=locale or f"{language}-XX",
                pronunciation_hints=[],
                emphasis_hints=[],
                pacing_intent=1.0,
                expected_duration_sec=None,
                version="v1",
                source_lineage={
                    "section_name": section.get("name", "") if isinstance(section, dict) else "",
                    "beat_index": narration_id_seq - 1,
                },
            )
            units.append(unit)

    # Optionally, attach scene_ids from the storyboard beats.
    if storyboard_package is not None:
        sb = storyboard_package
        sb_beats = getattr(sb, "visual_beats", None) or []
        for i, sb_beat in enumerate(sb_beats[:len(units)]):
            beat_id = getattr(sb_beat, "beat_id", f"sb_beat_{i:04d}")
            units[i].scene_id = getattr(sb_beat, "scene_id", "") or ""
            units[i].beat_id = beat_id

    return NarrationScript(
        version="1.0.0",
        script_id=script_id,
        project_id=project_id,
        job_id=job_id,
        language=language,
        locale=locale or f"{language}-XX",
        units=units,
        default_voice_id=default_voice_id,
        version_label="v1",
    )


__all__ = ["build_narration_script"]
