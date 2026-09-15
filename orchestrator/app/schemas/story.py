"""
Story Intelligence Engine canonical schemas.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ---- Enums ----
class AngleType(str, Enum):
    MYSTERY = "mystery"; SURVIVAL = "survival"; CONTRADICTION = "contradiction"
    MODERN_COMPARISON = "modern_comparison"; EVOLUTION = "evolution"; TECHNOLOGY = "technology"
    HUMAN_BEHAVIOR = "human_behavior"; ENVIRONMENT = "environment"; SOCIAL_SYSTEM = "social_system"
    UNEXPECTED_CONSEQUENCE = "unexpected_consequence"; PARADOX = "paradox"; TRANSFORMATION = "transformation"

class NarrativePurpose(str, Enum):
    HOOK = "hook"; SETUP = "setup"; CENTRAL_QUESTION = "central_question"; CONTEXT = "context"
    FIRST_DISCOVERY = "first_discovery"; ESCALATION = "escalation"; COMPLICATION = "complication"
    EVIDENCE = "evidence"; COUNTERPOINT = "counterpoint"; REVELATION = "revelation"
    EXPLANATION = "explanation"; PAYOFF = "payoff"; MODERN_REFLECTION = "modern_reflection"; ENDING = "ending"

class EmotionalState(str, Enum):
    CALM = "calm"; TENSE = "tense"; WARM = "warm"; TRIUMPHANT = "triumphant"
    MYSTERIOUS = "mysterious"; NEUTRAL = "neutral"

class ScriptVersion(str, Enum):
    DRAFT = "draft"; CRITIQUE = "critique"; REVISION = "revision"; FINAL = "final"

class CertaintyLevel(str, Enum):
    SUPPORTED = "supported"; INFERENTIAL = "inferential"; CONDITIONAL = "conditional"
    SPECULATIVE = "speculative"; UNSUPPORTED = "unsupported"

class TitleRiskFlag(str, Enum):
    TOO_BROAD = "title_too_broad"; OVERPROMISE = "title_overpromise"
    NOT_SUPPORTED = "title_not_supported"; TOO_GENERIC = "title_too_generic"; SCRIPT_MISMATCH = "title_script_mismatch"

class CritiqueSeverity(str, Enum):
    CRITICAL = "critical"; WARNING = "warning"; INFO = "info"

class CritiqueCategory(str, Enum):
    FACTUALITY = "factuality"; EVIDENCE_ALIGNMENT = "evidence_alignment"; HOOK = "hook"
    NARRATIVE = "narrative"; PACING = "pacing"; CURIOSITY = "curiosity"; CLARITY = "clarity"
    INFORMATION_DENSITY = "information_density"; REDUNDANCY = "redundancy"
    EMOTIONAL_PROGRESS = "emotional_progress"; VISUAL_POTENTIAL = "visual_potential"
    NATURAL_LANGUAGE = "natural_language"; ENDING = "ending"; AI_WRITING_RISK = "ai_writing_risk"

class ReviewStatus(str, Enum):
    DRAFT = "draft"; NEEDS_REVIEW = "needs_review"; APPROVED = "approved"; REJECTED = "rejected"

class StoryStatus(str, Enum):
    BLOCKED = "blocked"; IN_PROGRESS = "in_progress"; NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"; REJECTED = "rejected"

class VisualMode(str, Enum):
    CHARACTER = "character"; ENVIRONMENT = "environment"; DIAGRAM = "diagram"
    MAP = "map"; TIMELINE = "timeline"; COMPARISON = "comparison"
    ARTIFACT = "artifact"; TEXT = "text"; HYBRID = "hybrid"


# ---- Metadata ----
class ArtifactVersion(BaseModel):
    version: str = Field(default="v0.0.0", min_length=1, max_length=32)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    provider: str = "openai"
    model: str = ""
    configuration: dict[str, Any] = Field(default_factory=dict)
    input_hash: str = ""


class StoryMetadata(BaseModel):
    version: str = "1"
    story_package_id: str = Field(min_length=1, max_length=64)
    research_package_id: str = Field(min_length=1, max_length=64)
    research_package_hash: str = Field(default="", max_length=64)
    topic: str = ""
    job_id: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: StoryStatus = StoryStatus.IN_PROGRESS
    review_status: ReviewStatus = ReviewStatus.DRAFT
    research_quality_passed: bool = False
    research_quality_overall: float = 0.0
    research_failures: list[str] = Field(default_factory=list)
    research_warnings: list[str] = Field(default_factory=list)


# ---- Thesis ----
class ThesisCandidate(BaseModel):
    thesis_id: str = Field(min_length=1, max_length=32)
    statement: str = Field(min_length=20, max_length=500)
    supporting_claim_ids: list[str] = Field(default_factory=list)
    contradicting_claim_ids: list[str] = Field(default_factory=list)
    uncertainty: str = Field(default="", max_length=300)
    explanatory_power: float = Field(ge=0.0, le=1.0, default=0.5)
    novelty: float = Field(ge=0.0, le=1.0, default=0.5)
    story_value: float = Field(ge=0.0, le=1.0, default=0.5)
    visual_value: float = Field(ge=0.0, le=1.0, default=0.5)
    audience_relevance: float = Field(ge=0.0, le=1.0, default=0.5)
    evidence_strength: float = Field(ge=0.0, le=1.0, default=0.5)
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    reason: str = Field(default="", max_length=500)


class ThesisSelection(BaseModel):
    artifact_version: ArtifactVersion = Field(default_factory=ArtifactVersion)
    candidates: list[ThesisCandidate] = Field(default_factory=list)
    selected_id: str = ""
    review_status: ReviewStatus = ReviewStatus.DRAFT
    review_notes: str = Field(default="", max_length=1000)


# ---- Angle ----
class AngleCandidate(BaseModel):
    angle_id: str = Field(min_length=1, max_length=32)
    type: AngleType
    title: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=20, max_length=600)
    central_tension: str = Field(min_length=10, max_length=300)
    supporting_claim_ids: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    visual_potential: float = Field(ge=0.0, le=1.0, default=0.5)
    curiosity: float = Field(ge=0.0, le=1.0, default=0.5)
    emotional_potential: float = Field(ge=0.0, le=1.0, default=0.5)
    story_strength: float = Field(ge=0.0, le=1.0, default=0.5)
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)


class AngleSelection(BaseModel):
    artifact_version: ArtifactVersion = Field(default_factory=ArtifactVersion)
    candidates: list[AngleCandidate] = Field(default_factory=list)
    selected_id: str = ""
    review_status: ReviewStatus = ReviewStatus.DRAFT
    review_notes: str = Field(default="", max_length=1000)


# ---- Title ----
class TitleCandidate(BaseModel):
    title_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=5, max_length=120)
    curiosity_score: float = Field(ge=0.0, le=1.0, default=0.5)
    clarity_score: float = Field(ge=0.0, le=1.0, default=0.5)
    specificity_score: float = Field(ge=0.0, le=1.0, default=0.5)
    novelty_score: float = Field(ge=0.0, le=1.0, default=0.5)
    truthfulness_score: float = Field(ge=0.0, le=1.0, default=0.5)
    thesis_alignment: float = Field(ge=0.0, le=1.0, default=0.5)
    payoff_alignment: float = Field(ge=0.0, le=1.0, default=0.5)
    mobile_readability: float = Field(ge=0.0, le=1.0, default=0.5)
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    risk_flags: list[TitleRiskFlag] = Field(default_factory=list)
    promised_question: str = Field(default="", max_length=200)
    promised_payoff: str = Field(default="", max_length=300)


class TitleSelection(BaseModel):
    artifact_version: ArtifactVersion = Field(default_factory=ArtifactVersion)
    candidates: list[TitleCandidate] = Field(default_factory=list)
    selected_id: str = ""
    validated_against_script: bool = False
    validation_note: str = Field(default="", max_length=200)
    review_status: ReviewStatus = ReviewStatus.DRAFT
    review_notes: str = Field(default="", max_length=1000)


# ---- Hook ----
class HookCandidate(BaseModel):
    hook_id: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=10, max_length=300)
    curiosity: float = Field(ge=0.0, le=1.0, default=0.5)
    tension: float = Field(ge=0.0, le=1.0, default=0.5)
    clarity: float = Field(ge=0.0, le=1.0, default=0.5)
    specificity: float = Field(ge=0.0, le=1.0, default=0.5)
    payoff_potential: float = Field(ge=0.0, le=1.0, default=0.5)
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    risk_flags: list[str] = Field(default_factory=list)


class HookSelection(BaseModel):
    artifact_version: ArtifactVersion = Field(default_factory=ArtifactVersion)
    candidates: list[HookCandidate] = Field(default_factory=list)
    selected_id: str = ""
    review_status: ReviewStatus = ReviewStatus.DRAFT
    review_notes: str = Field(default="", max_length=1000)


# ---- Narrative Blueprint ----
class NarrativeBeat(BaseModel):
    beat_id: str = Field(min_length=1, max_length=32)
    purpose: NarrativePurpose
    claim_ids: list[str] = Field(default_factory=list)
    emotional_state: EmotionalState = EmotionalState.NEUTRAL
    curiosity_level: float = Field(ge=0.0, le=1.0, default=0.5)
    information_density: float = Field(ge=0.0, le=1.0, default=0.5)
    visual_potential: float = Field(ge=0.0, le=1.0, default=0.5)
    estimated_duration_sec: float = Field(ge=2.0, le=60.0, default=10.0)


class NarrativeBlueprint(BaseModel):
    artifact_version: ArtifactVersion = Field(default_factory=ArtifactVersion)
    beats: list[NarrativeBeat] = Field(default_factory=list)
    total_estimated_duration_sec: float = 0.0
    progression_flags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---- Script ----
class ScriptSegment(BaseModel):
    segment_id: str = Field(min_length=1, max_length=32)
    order: int = Field(ge=0)
    narration: str = Field(min_length=1, max_length=800)
    purpose: NarrativePurpose
    beat_id: str = Field(default="", max_length=32)
    claim_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    certainty_level: CertaintyLevel = CertaintyLevel.SUPPORTED
    emotional_state: EmotionalState = EmotionalState.NEUTRAL
    curiosity_level: float = Field(ge=0.0, le=1.0, default=0.5)
    information_density: float = Field(ge=0.0, le=1.0, default=0.5)
    estimated_duration_sec: float = Field(ge=1.0, le=60.0, default=10.0)
    visual_intent: str = Field(default="", max_length=200)
    transition_intent: str = Field(default="", max_length=100)


class ScriptVersionRecord(BaseModel):
    version_type: ScriptVersion
    artifact_version: ArtifactVersion
    segments: list[ScriptSegment] = Field(default_factory=list)
    total_word_count: int = 0
    total_duration_sec: float = 0.0
    is_final: bool = False

    def full_text(self) -> str:
        return " ".join(s.narration for s in sorted(self.segments, key=lambda x: x.order))


class ScriptDraft(BaseModel):
    versions: list[ScriptVersionRecord] = Field(default_factory=list)
    draft_version: str = ""
    critique_version: str = Field(default="", max_length=32)
    revision_version: str = Field(default="", max_length=32)
    final_version: str = Field(default="", max_length=32)
    active_version: ScriptVersion = ScriptVersion.DRAFT
    review_status: ReviewStatus = ReviewStatus.DRAFT
    review_notes: str = Field(default="", max_length=1000)

    def get_version(self, version_type: ScriptVersion) -> ScriptVersionRecord | None:
        return next((v for v in self.versions if v.version_type == version_type), None)

    def get_active(self) -> ScriptVersionRecord | None:
        return self.get_version(self.active_version)


# ---- Claim Traceability ----
class ClaimTraceEntry(BaseModel):
    segment_id: str = Field(min_length=1, max_length=32)
    claim_text_excerpt: str = Field(default="", max_length=200)
    certainty_level: CertaintyLevel
    claim_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    is_supported: bool = True
    distortion_flags: list[str] = Field(default_factory=list)
    distortion_detail: str = Field(default="", max_length=200)


class ClaimTraceabilityReport(BaseModel):
    entries: list[ClaimTraceEntry] = Field(default_factory=list)
    unsupported_entries: list[str] = Field(default_factory=list)
    critical_unsupported: list[str] = Field(default_factory=list)
    research_to_script_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    script_to_research_traceability: float = Field(ge=0.0, le=1.0, default=0.0)
    distortion_warnings: list[str] = Field(default_factory=list)
    unused_high_importance_claim_ids: list[str] = Field(default_factory=list)


# ---- Script Critique ----
class CritiqueFinding(BaseModel):
    finding_id: str = Field(min_length=1, max_length=32)
    severity: CritiqueSeverity
    segment_id: str = Field(default="", max_length=32)
    category: CritiqueCategory
    problem: str = Field(min_length=10, max_length=500)
    evidence: str = Field(default="", max_length=300)
    recommendation: str = Field(min_length=10, max_length=500)


class ScriptCritique(BaseModel):
    artifact_version: ArtifactVersion = Field(default_factory=ArtifactVersion)
    findings: list[CritiqueFinding] = Field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    hardest_section: str = Field(default="", max_length=200)
    weakest_point: str = Field(default="", max_length=300)
    best_point: str = Field(default="", max_length=300)
    would_viewer_leave_at: str = Field(default="", max_length=200)
    pacing_flags: list[str] = Field(default_factory=list)
    repetition_flags: list[str] = Field(default_factory=list)
    ai_pattern_flags: list[str] = Field(default_factory=list)


# ---- Retention Heuristic ----
class SegmentRetention(BaseModel):
    segment_id: str = Field(min_length=1, max_length=32)
    curiosity: float = Field(ge=0.0, le=1.0, default=0.5)
    new_information: float = Field(ge=0.0, le=1.0, default=0.5)
    tension: float = Field(ge=0.0, le=1.0, default=0.5)
    visual_change: float = Field(ge=0.0, le=1.0, default=0.5)
    payoff_distance: float = Field(ge=0.0, le=1.0, default=0.5)
    emotional_change: float = Field(ge=0.0, le=1.0, default=0.5)
    dropoff_risk: float = Field(ge=0.0, le=1.0, default=0.0)
    retention_score: float = Field(ge=0.0, le=1.0, default=0.0)


class RetentionAnalysis(BaseModel):
    segment_retentions: list[SegmentRetention] = Field(default_factory=list)
    opening_risk: str = Field(default="", max_length=200)
    middle_risk: str = Field(default="", max_length=200)
    ending_risk: str = Field(default="", max_length=200)
    repetition_risks: list[str] = Field(default_factory=list)
    slow_sections: list[str] = Field(default_factory=list)
    premature_reveals: list[str] = Field(default_factory=list)
    weak_payoff_flag: bool = False
    overall_retention_score: float = Field(ge=0.0, le=1.0, default=0.0)


# ---- Storyboard Intent ----
class StoryboardIntentItem(BaseModel):
    segment_id: str = Field(min_length=1, max_length=32)
    purpose: str = Field(min_length=1, max_length=200)
    visual_goal: str = Field(min_length=1, max_length=300)
    visual_mode: VisualMode
    characters: list[str] = Field(default_factory=list)
    environment: str = Field(default="", max_length=100)
    props: list[str] = Field(default_factory=list)
    camera_intent: str = Field(default="", max_length=200)
    motion_intent: str = Field(default="", max_length=200)
    text_intent: str = Field(default="", max_length=200)
    source_ids: list[str] = Field(default_factory=list)
    continuity_notes: str = Field(default="", max_length=300)


class StoryboardIntent(BaseModel):
    artifact_version: ArtifactVersion = Field(default_factory=ArtifactVersion)
    items: list[StoryboardIntentItem] = Field(default_factory=list)
    visual_mode_counts: dict[str, int] = Field(default_factory=dict)


# ---- Story Quality Score ----
class StoryQualityDimension(BaseModel):
    score: float = Field(ge=0.0, le=1.0, default=0.0)
    notes: str = Field(default="", max_length=200)


class StoryQualityScore(BaseModel):
    thesis_strength: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    evidence_alignment: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    angle_strength: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    title_strength: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    hook_strength: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    narrative_structure: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    curiosity: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    pacing: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    clarity: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    information_density: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    visual_potential: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    fact_traceability: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    natural_language: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    payoff: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    ai_writing_risk: StoryQualityDimension = Field(default_factory=StoryQualityDimension)
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


# ---- Revision History ----
class RevisionEntry(BaseModel):
    revision_number: int = Field(ge=1)
    based_on_version: str = Field(min_length=1, max_length=32)
    critique_version_id: str = Field(min_length=1, max_length=32)
    instructions_summary: str = Field(min_length=10, max_length=500)
    changes_made: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RevisionHistory(BaseModel):
    entries: list[RevisionEntry] = Field(default_factory=list)
    current_revision_number: int = 0


# ---- Story Package ----
class StoryPackage(BaseModel):
    metadata: StoryMetadata = Field(default_factory=StoryMetadata)
    research_status: str = ""
    research_failures: list[str] = Field(default_factory=list)
    research_warnings: list[str] = Field(default_factory=list)
    thesis: ThesisSelection = Field(default_factory=ThesisSelection)
    angle: AngleSelection = Field(default_factory=AngleSelection)
    title: TitleSelection = Field(default_factory=TitleSelection)
    hook: HookSelection = Field(default_factory=HookSelection)
    blueprint: NarrativeBlueprint | None = None
    script: ScriptDraft = Field(default_factory=ScriptDraft)
    traceability: ClaimTraceabilityReport | None = None
    critique: ScriptCritique | None = None
    retention: RetentionAnalysis | None = None
    revision_history: RevisionHistory = Field(default_factory=RevisionHistory)
    storyboard_intent: StoryboardIntent | None = None
    quality_score: StoryQualityScore | None = None

    @model_validator(mode="after")
    def _validate_research_gate(self) -> "StoryPackage":
        if self.metadata.status == StoryStatus.BLOCKED:
            return self
        critical = [f for f in self.research_failures if "CRITICAL" in f.upper()]
        if critical:
            self.metadata.status = StoryStatus.BLOCKED
            self.research_failures = critical
        return self

    @model_validator(mode="after")
    def _validate_thesis_selection(self) -> "StoryPackage":
        if self.thesis.selected_id and self.thesis.selected_id not in {c.thesis_id for c in self.thesis.candidates}:
            raise ValueError(f"selected thesis {self.thesis.selected_id!r} not in candidates")
        return self

    @model_validator(mode="after")
    def _validate_title_candidates_count(self) -> "StoryPackage":
        if len(self.title.candidates) < 20:
            raise ValueError(f"title candidates ({len(self.title.candidates)}) below minimum of 20")
        return self

    @model_validator(mode="after")
    def _validate_title_revalidation(self) -> "StoryPackage":
        if self.title.selected_id and not self.title.validated_against_script:
            raise ValueError("title must be validated against final script before approval")
        return self

    @model_validator(mode="after")
    def _validate_final_script_no_unsupported(self) -> "StoryPackage":
        if self.traceability and self.traceability.critical_unsupported:
            raise ValueError(f"critical unsupported claims in final script: {self.traceability.critical_unsupported}")
        return self

    @model_validator(mode="after")
    def _validate_final_segment_order(self) -> "StoryPackage":
        final_ver = self.script.get_version(ScriptVersion.FINAL)
        if final_ver:
            orders = [s.order for s in final_ver.segments]
            if orders != sorted(orders):
                raise ValueError("script segment orders must be sequential")
        return self

    def get_final_script(self) -> ScriptVersionRecord | None:
        return self.script.get_version(ScriptVersion.FINAL)

    def is_approved(self) -> bool:
        return self.metadata.review_status == ReviewStatus.APPROVED

    def is_blocked(self) -> bool:
        return self.metadata.status == StoryStatus.BLOCKED

    def to_legacy_thesis(self) -> dict:
        chosen = next(
            (c for c in self.thesis.candidates if c.thesis_id == self.thesis.selected_id),
            None,
        )
        if not chosen:
            return {}
        hook_candidate = self.hook.candidates[0] if self.hook.candidates else None
        return {
            "topic": self.metadata.topic,
            "claim": chosen.statement,
            "counter_arguments": [],
            "supporting_facts": [],
            "hook": hook_candidate.text if hook_candidate else "",
        }

    def to_legacy_title_package(self) -> dict:
        return {
            "candidates": [{"title": c.title, "rationale": ""} for c in self.title.candidates],
            "chosen_index": next(
                (i for i, c in enumerate(self.title.candidates) if c.title_id == self.title.selected_id),
                0,
            ),
        }

    def to_legacy_script(self) -> dict:
        final = self.get_final_script()
        if not final:
            return {}
        sections_map: dict[str, list[dict]] = {}
        for seg in sorted(final.segments, key=lambda s: s.order):
            purpose = seg.purpose.value
            if purpose not in sections_map:
                sections_map[purpose] = []
            sections_map[purpose].append({
                "text": seg.narration,
                "emotional_intent": seg.emotional_state.value,
            })
        sections = [{"name": name, "beats": beats} for name, beats in sections_map.items()]
        return {"topic": self.metadata.topic, "sections": sections}

    def to_legacy_storyboard(self) -> dict:
        if not self.storyboard_intent:
            return {}
        beats = [
            {
                "summary": item.visual_goal,
                "environment_id": item.environment or "diagram_white",
                "characters": item.characters,
                "visual_intent": item.visual_goal,
                "duration_sec": 10.0,
            }
            for item in self.storyboard_intent.items
        ]
        return {"beats": beats}
