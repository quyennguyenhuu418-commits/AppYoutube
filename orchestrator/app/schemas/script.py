"""Script and thesis schemas — outputs of the early planning stages."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Thesis(BaseModel):
    """A fact-checked central thesis the documentary will defend."""
    topic: str
    claim: str = Field(min_length=10, max_length=500)
    counter_arguments: list[str] = Field(default_factory=list)
    supporting_facts: list[str] = Field(min_length=1)
    hook: str = Field(default="", max_length=200)


class TitleCandidate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    rationale: str = Field(default="", max_length=300)


class TitlePackage(BaseModel):
    candidates: list[TitleCandidate] = Field(min_length=1)
    chosen_index: int = Field(default=0, ge=0)


class ScriptBeat(BaseModel):
    """One beat in the narration script. Roughly one sentence."""
    text: str = Field(min_length=1, max_length=400)
    emotional_intent: str = Field(default="neutral", max_length=32)


class ScriptSection(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    beats: list[ScriptBeat] = Field(min_length=1)


class Script(BaseModel):
    """Full narration script. Beats are concatenated to form `narration_text`."""
    topic: str
    sections: list[ScriptSection] = Field(min_length=1)

    def full_text(self) -> str:
        """Flatten all beats into one narration string for TTS."""
        chunks: list[str] = []
        for section in self.sections:
            for beat in section.beats:
                chunks.append(beat.text)
        return " ".join(chunks)


class StoryboardBeat(BaseModel):
    """One beat in the visual storyboard — roughly one scene."""
    summary: str = Field(min_length=1, max_length=300)
    environment_id: str = Field(min_length=1, max_length=64)
    characters: list[str] = Field(default_factory=list)
    visual_intent: str = Field(default="", max_length=200)
    duration_sec: float = Field(default=8.0, ge=2.0, le=60.0)


class Storyboard(BaseModel):
    beats: list[StoryboardBeat] = Field(min_length=1)
