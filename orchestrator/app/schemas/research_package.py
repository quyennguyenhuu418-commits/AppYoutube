"""
Research Intelligence Engine — output schema.

This file defines the complete ResearchPackage schema. Every field is
enumerated, typed, and bounded. The engine produces JSON matching this
schema; downstream stages (thesis, script, storyboard) consume it.

Schema version: 1.0
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SourceTier(str, Enum):
    TIER1 = "TIER1"   # Peer-reviewed, primary archaeological, Nature/Science/PNAS
    TIER2 = "TIER2"   # Smithsonian, major museums, universities, established science pubs
    TIER3 = "TIER3"   # Reference works, encyclopedias, Wikipedia, educational resources
    TIER4 = "TIER4"   # Blogs, commercial sites, forums, Reddit — discovery only


class ClaimType(str, Enum):
    HISTORICAL = "historical"
    ARCHAEOLOGICAL = "archaeological"
    BIOLOGICAL = "biological"
    ANTHROPOLOGICAL = "anthropological"
    CLIMATOLOGICAL = "climatological"
    GEOGRAPHICAL = "geographical"
    QUANTITATIVE = "quantitative"
    TECHNOLOGICAL = "technological"
    BEHAVIORAL = "behavioral"
    INTERPRETIVE = "interpretive"


class CertaintyLevel(str, Enum):
    STRONG_EVIDENCE = "STRONG_EVIDENCE"
    PLAUSIBLE_INTERPRETATION = "PLAUSIBLE_INTERPRETATION"
    SPECULATION = "SPECULATION"
    UNKNOWN = "UNKNOWN"


class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    QUALIFIED = "qualified"
    UNRESOLVED = "unresolved"


class SourceRelationship(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    CONTEXTUALIZES = "contextualizes"


class ContradictionResolution(str, Enum):
    UNRESOLVED = "unresolved"
    PARTIAL = "partial"
    RESOLVED = "resolved"


class ResearchQuestionStatus(str, Enum):
    ACTIVE = "active"
    COVERED = "covered"
    UNANSWERABLE = "unanswerable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class VisualOpportunityType(str, Enum):
    CHARACTER_ACTION = "character_action"
    ENVIRONMENT = "environment"
    ARTIFACT = "artifact"
    MAP = "map"
    TIMELINE = "timeline"
    DIAGRAM = "diagram"
    RECONSTRUCTION = "reconstruction"
    ANIMATION = "animation"
    NUMBER_VISUALIZATION = "number_visualization"


class ResearchGapStatus(str, Enum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNRESOLVED_DEBATE = "unresolved_debate"
    UNSTUDIED = "unstudied"
    OUT_OF_SCOPE = "out_of_scope"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class ResearchMetadata(BaseModel):
    version: str = Field(default="1.0")
    topic: str = Field(min_length=1, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    duration_sec: float = Field(default=0.0, ge=0.0)
    job_id: str = Field(default="")
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_warnings: list[str] = Field(default_factory=list)
    source_count: int = Field(default=0, ge=0)
    claim_count: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Research Questions
# ---------------------------------------------------------------------------

class ResearchQuestion(BaseModel):
    id: str = Field(min_length=1, max_length=16, pattern=r"^RQ-\d{3}$")
    text: str = Field(min_length=5, max_length=500)
    question_type: str = Field(default="sub", max_length=32)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    status: ResearchQuestionStatus = Field(default=ResearchQuestionStatus.ACTIVE)
    parent_id: str | None = Field(default=None, max_length=16)
    sources_touched: list[str] = Field(default_factory=list)
    claims_touched: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

class SourceLineage(BaseModel):
    original_url: str = Field(default="")
    intermediate_urls: list[str] = Field(default_factory=list)
    is_independent: bool = Field(default=True)


class Source(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^SRC-[A-Z0-9]+$")
    url: str = Field(min_length=1, max_length=2000)
    title: str = Field(min_length=1, max_length=500)
    tier: SourceTier = Field(default=SourceTier.TIER3)
    authority: float = Field(default=0.5, ge=0.0, le=1.0)
    recency: float = Field(default=0.5, ge=0.0, le=1.0)
    methodology: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    citation_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    independence: float = Field(default=1.0, ge=0.0, le=1.0)
    overall_score: float = Field(default=0.5, ge=0.0, le=1.0)
    score_reason: str = Field(default="", max_length=500)
    content_hash: str = Field(default="", max_length=64)
    snippet: str = Field(default="", max_length=2000)
    published_date: str = Field(default="", max_length=64)
    author: str = Field(default="", max_length=200)
    domain: str = Field(default="", max_length=200)
    lineage: SourceLineage = Field(default_factory=SourceLineage)
    reviewed: bool = Field(default=False)
    approved: bool = Field(default=True)
    claims_from_this_source: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _compute_overall_score(self) -> Self:
        """Auto-compute overall_score from sub-dimensions."""
        weights = {
            "authority": 0.30,
            "recency": 0.10,
            "methodology": 0.20,
            "relevance": 0.15,
            "citation_quality": 0.15,
            "independence": 0.10,
        }
        total = sum(getattr(self, k) * v for k, v in weights.items())
        object.__setattr__(self, "overall_score", round(total, 3))
        return self


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

class Claim(BaseModel):
    claim_id: str = Field(min_length=1, max_length=16, pattern=r"^CLM-\d{3}$")
    text: str = Field(min_length=5, max_length=1000)
    claim_type: ClaimType = Field(default=ClaimType.HISTORICAL)
    importance: str = Field(default="medium", max_length=16)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    certainty_level: CertaintyLevel = Field(default=CertaintyLevel.PLAUSIBLE_INTERPRETATION)
    certainty_reason: str = Field(default="", max_length=500)
    status: ClaimStatus = Field(default=ClaimStatus.SUPPORTED)
    uncertainty: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=500)
    source_ids: list[str] = Field(default_factory=list)
    contradictory_claim_ids: list[str] = Field(default_factory=list)
    visual_opportunity_id: str | None = Field(default=None, max_length=32)
    story_opportunity_id: str | None = Field(default=None, max_length=32)


# ---------------------------------------------------------------------------
# Claim <-> Source links
# ---------------------------------------------------------------------------

class ClaimSourceLink(BaseModel):
    claim_id: str
    source_id: str
    relationship: SourceRelationship = Field(default=SourceRelationship.SUPPORTS)
    notes: str = Field(default="", max_length=200)


# ---------------------------------------------------------------------------
# Contradictions
# ---------------------------------------------------------------------------

class Contradiction(BaseModel):
    id: str = Field(min_length=1, max_length=16, pattern=r"^CTR-[A-Z0-9]+$")
    claim_id_a: str
    claim_id_b: str
    position_a: str = Field(max_length=500)
    position_b: str = Field(max_length=500)
    possible_reason: str = Field(default="", max_length=500)
    resolution: ContradictionResolution = Field(default=ContradictionResolution.UNRESOLVED)
    resolution_notes: str = Field(default="", max_length=500)


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

class TimelineEvent(BaseModel):
    period: str = Field(min_length=1, max_length=100)
    start_date: str = Field(default="", max_length=64)
    end_date: str = Field(default="", max_length=64)
    events: list[str] = Field(min_length=1)
    uncertainty: str = Field(default="", max_length=200)
    is_approximate: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------

class GeographicSite(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    region: str = Field(default="", max_length=100)
    country: str = Field(default="", max_length=100)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    period: str = Field(default="", max_length=100)
    evidence: str = Field(default="", max_length=500)


# ---------------------------------------------------------------------------
# Quantitative Facts
# ---------------------------------------------------------------------------

class QuantitativeFact(BaseModel):
    id: str = Field(min_length=1, max_length=16, pattern=r"^QF-\d{3}$")
    value: float | None = Field(default=None)
    unit: str = Field(min_length=1, max_length=64)
    context: str = Field(default="", max_length=300)
    minimum: float | None = Field(default=None)
    maximum: float | None = Field(default=None)
    approximate: bool = Field(default=False)
    uncertainty: str = Field(default="", max_length=200)
    source_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Visual Opportunities
# ---------------------------------------------------------------------------

class VisualOpportunity(BaseModel):
    id: str = Field(min_length=1, max_length=32, pattern=r"^VO-\d{3}$")
    claim_id: str
    opportunity_type: VisualOpportunityType
    description: str = Field(min_length=5, max_length=500)
    visual_spec: str = Field(default="", max_length=1000)
    environment_hint: str = Field(default="", max_length=100)
    mood_hint: str = Field(default="", max_length=50)


# ---------------------------------------------------------------------------
# Story Opportunities
# ---------------------------------------------------------------------------

class StoryOpportunity(BaseModel):
    id: str = Field(min_length=1, max_length=32, pattern=r"^SO-\d{3}$")
    hook_candidates: list[str] = Field(min_length=1)
    surprising_facts: list[str] = Field(min_length=1)
    contradictions: list[str] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    emotional_beats: list[str] = Field(min_length=1)
    questions: list[str] = Field(default_factory=list)
    final_takeaways: list[str] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Research Synthesis
# ---------------------------------------------------------------------------

class ResearchSynthesis(BaseModel):
    central_question: str = Field(min_length=5, max_length=500)
    short_answer: str = Field(min_length=10, max_length=500)
    detailed_answer: str = Field(min_length=20, max_length=5000)
    strongest_evidence: list[str] = Field(min_length=1)
    weakest_evidence: list[str] = Field(default_factory=list)
    major_uncertainties: list[str] = Field(min_length=1)
    major_disagreements: list[str] = Field(default_factory=list)
    timeline_summary: list[str] = Field(default_factory=list)
    important_examples: list[str] = Field(min_length=1)
    counterintuitive_findings: list[str] = Field(default_factory=list)
    visual_opportunity_ids: list[str] = Field(default_factory=list)
    story_opportunity_ids: list[str] = Field(default_factory=list)
    research_gap_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Research Quality Score
# ---------------------------------------------------------------------------

class ResearchQualityScore(BaseModel):
    source_quality: float = Field(ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    claim_traceability: float = Field(ge=0.0, le=1.0)
    independence: float = Field(ge=0.0, le=1.0)
    contradiction_detection: float = Field(ge=0.0, le=1.0)
    uncertainty_handling: float = Field(ge=0.0, le=1.0)
    research_depth: float = Field(ge=0.0, le=1.0)
    visual_value: float = Field(ge=0.0, le=1.0)
    story_value: float = Field(ge=0.0, le=1.0)
    overall_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _compute_overall(self) -> Self:
        """Overall score is the weighted average of category scores."""
        weights = {
            "source_quality": 0.15,
            "coverage": 0.10,
            "claim_traceability": 0.15,
            "independence": 0.10,
            "contradiction_detection": 0.10,
            "uncertainty_handling": 0.10,
            "research_depth": 0.10,
            "visual_value": 0.10,
            "story_value": 0.10,
        }
        total = sum(getattr(self, k) * v for k, v in weights.items())
        object.__setattr__(self, "overall_score", round(total, 3))
        return self


# ---------------------------------------------------------------------------
# Research Gaps
# ---------------------------------------------------------------------------

class ResearchGap(BaseModel):
    id: str = Field(min_length=1, max_length=16, pattern=r"^GAP-\d{3}$")
    question: str = Field(min_length=5, max_length=500)
    status: ResearchGapStatus = Field(default=ResearchGapStatus.INSUFFICIENT_EVIDENCE)
    reason: str = Field(default="", max_length=500)
    related_question_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Research Package — top level
# ---------------------------------------------------------------------------

class ResearchPackage(BaseModel):
    """The complete research package — the sole output of the Research Engine."""

    # Metadata
    metadata: ResearchMetadata

    # Content sections
    research_questions: list[ResearchQuestion] = Field(min_length=1)
    sources: list[Source] = Field(min_length=1)
    claims: list[Claim] = Field(min_length=1)
    claim_source_links: list[ClaimSourceLink] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    research_gaps: list[ResearchGap] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    geography: list[GeographicSite] = Field(default_factory=list)
    quantitative_facts: list[QuantitativeFact] = Field(default_factory=list)
    visual_opportunities: list[VisualOpportunity] = Field(default_factory=list)
    story_opportunities: list[StoryOpportunity] = Field(default_factory=list)
    synthesis: ResearchSynthesis

    # Quality
    quality_score: ResearchQualityScore

    @model_validator(mode="after")
    def _validate_references(self) -> Self:
        """Cross-field validation: all claim/source IDs referenced actually exist."""
        source_ids = {s.id for s in self.sources}
        claim_ids = {c.claim_id for c in self.claims}

        # ClaimSourceLink references
        for link in self.claim_source_links:
            if link.claim_id not in claim_ids:
                raise ValueError(f"ClaimSourceLink references unknown claim '{link.claim_id}'")
            if link.source_id not in source_ids:
                raise ValueError(f"ClaimSourceLink references unknown source '{link.source_id}'")

        # Contradiction references
        for ct in self.contradictions:
            if ct.claim_id_a not in claim_ids:
                raise ValueError(f"Contradiction CTR references unknown claim '{ct.claim_id_a}'")
            if ct.claim_id_b not in claim_ids:
                raise ValueError(f"Contradiction CTR references unknown claim '{ct.claim_id_b}'")

        # Claim.source_ids references
        for claim in self.claims:
            for sid in claim.source_ids:
                if sid not in source_ids:
                    raise ValueError(f"Claim {claim.claim_id} references unknown source '{sid}'")

        # QuantitativeFact source references
        for qf in self.quantitative_facts:
            for sid in qf.source_ids:
                if sid not in source_ids:
                    raise ValueError(f"QuantitativeFact {qf.id} references unknown source '{sid}'")

        # ResearchGap related question references
        gap_q_ids = {g.id for g in self.research_gaps}
        rq_ids = {rq.id for rq in self.research_questions}
        for gap in self.research_gaps:
            for qid in gap.related_question_ids:
                if qid not in rq_ids:
                    raise ValueError(f"ResearchGap {gap.id} references unknown question '{qid}'")

        # Synthesis references
        all_vo_ids = {vo.id for vo in self.visual_opportunities}
        all_so_ids = {so.id for so in self.story_opportunities}
        for vid in self.synthesis.visual_opportunity_ids:
            if vid not in all_vo_ids:
                raise ValueError(f"Synthesis references unknown VisualOpportunity '{vid}'")
        for sid in self.synthesis.story_opportunity_ids:
            if sid not in all_so_ids:
                raise ValueError(f"Synthesis references unknown StoryOpportunity '{sid}'")
        for gid in self.synthesis.research_gap_ids:
            if gid not in gap_q_ids:
                raise ValueError(f"Synthesis references unknown ResearchGap '{gid}'")

        return self

    def to_legacy_dict(self) -> dict[str, Any]:
        """
        Produce a backward-compatible dict matching the old ResearchPackage schema
        so downstream stages (thesis, script, storyboard) that still read
        workspace/{job_id}/research.json continue to work.
        """
        return {
            "topic": self.metadata.topic,
            "facts": [
                {
                    "claim": c.text,
                    "sources": [
                        {
                            "url": s.url,
                            "title": s.title,
                            "snippet": s.snippet,
                        }
                        for s in self.sources
                        if s.id in c.source_ids
                    ],
                    "confidence": c.confidence,
                }
                for c in self.claims
            ],
            "open_questions": [g.question for g in self.research_gaps],
        }
