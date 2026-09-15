"""Research package — output of stage 1 (research) and input to stage 2 (thesis)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    url: str = ""
    title: str = ""
    snippet: str = ""


class FactClaim(BaseModel):
    claim: str = Field(min_length=1)
    sources: list[SourceRef] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ResearchPackage(BaseModel):
    topic: str
    facts: list[FactClaim] = Field(min_length=1)
    open_questions: list[str] = Field(default_factory=list)
