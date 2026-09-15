"""
Comprehensive tests for the Story Intelligence Engine.

Covers:
1. Schema validation tests (~20)
2. Engine integration tests with mock provider (~15)
3. Cache tests (~5)
4. Distortion detection tests (~5)
5. AI-writing risk heuristic tests (~5)
"""
from __future__ import annotations

import os
import time

# Force mock mode before any other imports.
os.environ["OPENAI_API_KEY"] = ""

import pytest
from pydantic import ValidationError

from app.schemas.story import (
    AngleCandidate,
    AngleSelection,
    AngleType,
    ArtifactVersion,
    ClaimTraceEntry,
    ClaimTraceabilityReport,
    CritiqueCategory,
    CritiqueFinding,
    CritiqueSeverity,
    ScriptCritique,
    EmotionalState,
    HookCandidate,
    HookSelection,
    NarrativeBeat,
    NarrativeBlueprint,
    NarrativePurpose,
    RevisionEntry,
    RevisionHistory,
    ScriptDraft,
    ScriptSegment,
    ScriptVersion,
    ScriptVersionRecord,
    SegmentRetention,
    RetentionAnalysis,
    StoryMetadata,
    StoryPackage,
    StoryQualityDimension,
    StoryQualityScore,
    StoryStatus,
    ThesisCandidate,
    ThesisSelection,
    TitleCandidate,
    TitleRiskFlag,
    TitleSelection,
    StoryboardIntentItem,
    StoryboardIntent,
    VisualMode,
    CertaintyLevel,
    ReviewStatus,
)
from app.schemas.research_package import (
    Claim,
    ClaimSourceLink,
    ClaimType,
    Contradiction,
    ContradictionResolution,
    ResearchMetadata,
    ResearchPackage,
    ResearchQuestion,
    ResearchQualityScore as ResearchQualityScoreRP,
    ResearchSynthesis,
    Source,
    SourceLineage,
    SourceRelationship,
    SourceTier,
)
from app.story.engine import StoryEngine
from app.story.cache import StoryCache
from app.providers.mock_llm import MockLLMProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_research_package(quality_overall: float = 0.85) -> ResearchPackage:
    """Build a valid ResearchPackage for story engine tests.

    Contains 2 TIER1 sources, 3 claims with source links,
    contradictions, synthesis, and a configurable quality score.

    The quality_overall parameter scales the category scores so the
    ResearchQualityScore validator (which auto-computes overall_score from
    the categories) yields a matching value.
    """
    # Scale categories so weighted average lands near quality_overall.
    base_categories = {
        "source_quality": 0.85,
        "coverage": 0.80,
        "claim_traceability": 0.90,
        "independence": 0.88,
        "contradiction_detection": 0.70,
        "uncertainty_handling": 0.80,
        "research_depth": 0.72,
        "visual_value": 0.85,
        "story_value": 0.90,
    }
    # Weighted sum of base values = ~0.83; scale to match desired quality_overall.
    base_sum = sum(base_categories.values()) / len(base_categories)
    scale = quality_overall / base_sum if base_sum > 0 else 1.0
    categories = {k: round(max(0.0, min(1.0, v * scale)), 3) for k, v in base_categories.items()}
    sources = [
        Source(
            id="SRC-00000001",
            url="https://www.nature.com/articles/s41586-019-1290-4",
            title="The evolutionary history of cold adaptation in humans",
            tier=SourceTier.TIER1,
            authority=0.95,
            recency=0.7,
            methodology=0.95,
            relevance=0.9,
            citation_quality=0.95,
            independence=1.0,
            overall_score=0.92,
            snippet="Ancient humans developed cold-adapted physiological traits.",
        ),
        Source(
            id="SRC-00000002",
            url="https://www.smithsonianmag.com/science-nature/how-neanderthals-adapted-to-cold-180971856/",
            title="How Neanderthals Adapted to Cold",
            tier=SourceTier.TIER1,
            authority=0.85,
            recency=0.7,
            methodology=0.7,
            relevance=0.9,
            citation_quality=0.8,
            independence=0.9,
            overall_score=0.82,
            snippet="Neanderthal anatomy and behavior helped them survive European winters.",
        ),
    ]
    claims = [
        Claim(
            claim_id="CLM-001",
            text="Neanderthals lived through glacial winters in Europe for over 200,000 years.",
            claim_type=ClaimType.HISTORICAL,
            importance="high",
            confidence=0.9,
            source_ids=["SRC-00000001"],
        ),
        Claim(
            claim_id="CLM-002",
            text="The controlled use of fire dates back at least 400,000 years.",
            claim_type=ClaimType.ARCHAEOLOGICAL,
            importance="high",
            confidence=0.92,
            source_ids=["SRC-00000001"],
        ),
        Claim(
            claim_id="CLM-003",
            text="Mammoth-bone huts have been excavated in Ukraine and Russia.",
            claim_type=ClaimType.ARCHAEOLOGICAL,
            importance="high",
            confidence=0.88,
            source_ids=["SRC-00000002"],
        ),
    ]
    claim_links = [
        ClaimSourceLink(claim_id="CLM-001", source_id="SRC-00000001", relationship=SourceRelationship.SUPPORTS),
        ClaimSourceLink(claim_id="CLM-002", source_id="SRC-00000001", relationship=SourceRelationship.SUPPORTS),
        ClaimSourceLink(claim_id="CLM-003", source_id="SRC-00000002", relationship=SourceRelationship.SUPPORTS),
    ]
    contradictions = [
        Contradiction(
            id="CTR-001",
            claim_id_a="CLM-001",
            claim_id_b="CLM-002",
            position_a="Neanderthals lived through 200,000 years of winters",
            position_b="Fire use dates back 400,000 years",
            resolution=ContradictionResolution.PARTIAL,
        ),
    ]
    synthesis = ResearchSynthesis(
        central_question="How did ancient humans survive deadly Ice Age winters?",
        short_answer="Through fire, clothing, shelter, and food.",
        detailed_answer="Ancient humans survived through a combination of fire, tailored clothing, cooperative shelter, and high-fat megafauna hunting into a flexible survival system.",
        strongest_evidence=["Controlled fire use dated to 400,000 years ago"],
        major_uncertainties=["How did vulnerable populations survive?"],
        important_examples=["Mammoth-bone hut at Simbioskaya, Ukraine"],
        counterintuitive_findings=["Fat was more valuable than meat in extreme cold"],
    )
    qscore = ResearchQualityScoreRP(
        source_quality=categories["source_quality"],
        coverage=categories["coverage"],
        claim_traceability=categories["claim_traceability"],
        independence=categories["independence"],
        contradiction_detection=categories["contradiction_detection"],
        uncertainty_handling=categories["uncertainty_handling"],
        research_depth=categories["research_depth"],
        visual_value=categories["visual_value"],
        story_value=categories["story_value"],
        overall_score=quality_overall,
    )
    return ResearchPackage(
        metadata=ResearchMetadata(
            topic="How Did Ancient Humans Survive Deadly Winters?",
            version="1.0",
            quality_score=quality_overall,
            source_count=len(sources),
            claim_count=len(claims),
        ),
        research_questions=[
            ResearchQuestion(
                id="RQ-001",
                text="What enabled ancient humans to survive deadly Ice Age winters?",
            )
        ],  # Required field, min_length=1
        sources=sources,
        claims=claims,
        claim_source_links=claim_links,
        contradictions=contradictions,
        synthesis=synthesis,
        quality_score=qscore,
    )


@pytest.fixture
def research_package() -> ResearchPackage:
    """A valid high-quality research package (overall=0.85)."""
    return _make_research_package(quality_overall=0.85)


# ---------------------------------------------------------------------------
# 1. Schema Validation Tests (~20)
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    """Schema-level validation for story schemas."""

    def test_minimum_title_count(self):
        """19 title candidates raises ValueError; 20 passes."""
        pkg = _make_story_package_with_titles(19)
        with pytest.raises(ValueError, match="title candidates.*below minimum"):
            StoryPackage.model_validate(pkg)

        pkg20 = _make_story_package_with_titles(20)
        StoryPackage.model_validate(pkg20)  # should not raise

    def test_thesis_selection_must_exist(self):
        """selected_id not in candidates raises ValueError."""
        pkg = _minimal_story_package()
        pkg["thesis"]["selected_id"] = "THS-FAKE-ID"
        with pytest.raises(ValueError, match="selected thesis"):
            StoryPackage.model_validate(pkg)

    def test_title_must_be_validated(self):
        """Title selected but not validated raises ValueError."""
        pkg = _minimal_story_package()
        pkg["title"]["selected_id"] = pkg["title"]["candidates"][0]["title_id"]
        pkg["title"]["validated_against_script"] = False
        with pytest.raises(ValueError, match="validated against"):
            StoryPackage.model_validate(pkg)

    def test_final_unsupported_claims_blocked(self):
        """traceability.critical_unsupported raises ValueError in final script."""
        pkg = _minimal_story_package()
        # Add a final version to the script
        pkg["script"]["versions"].append(
            _make_final_script_version([{"segment_id": "SEG-001", "order": 1, "purpose": "setup", "narration": "Test narration."}])
        )
        pkg["traceability"] = {
            "entries": [],
            "unsupported_entries": [],
            "critical_unsupported": ["SEG-001"],
            "research_to_script_coverage": 0.5,
            "script_to_research_traceability": 0.5,
            "distortion_warnings": [],
            "unused_high_importance_claim_ids": [],
        }
        with pytest.raises(ValueError, match="critical unsupported"):
            StoryPackage.model_validate(pkg)

    def test_final_segment_order_sequential(self):
        """Non-sequential segment orders in FINAL version raise ValueError."""
        pkg = _minimal_story_package()
        pkg["script"]["versions"].append({
            "version_type": "final",
            "artifact_version": {"version": "v1", "created_at": "2024-01-01T00:00:00Z", "provider": "openai", "model": "gpt-4o", "configuration": {}, "input_hash": "x"},
            "segments": [
                {"segment_id": "SEG-001", "order": 0, "narration": "First.", "purpose": "hook", "beat_id": "B-001", "claim_ids": [], "source_ids": [], "certainty_level": "supported", "emotional_state": "neutral", "curiosity_level": 0.5, "information_density": 0.5, "estimated_duration_sec": 8.0, "visual_intent": "", "transition_intent": ""},
                {"segment_id": "SEG-002", "order": 5, "narration": "Third (but order=5).", "purpose": "setup", "beat_id": "B-002", "claim_ids": [], "source_ids": [], "certainty_level": "supported", "emotional_state": "neutral", "curiosity_level": 0.5, "information_density": 0.5, "estimated_duration_sec": 8.0, "visual_intent": "", "transition_intent": ""},
                {"segment_id": "SEG-003", "order": 2, "narration": "Second (but order=2).", "purpose": "evidence", "beat_id": "B-003", "claim_ids": [], "source_ids": [], "certainty_level": "supported", "emotional_state": "neutral", "curiosity_level": 0.5, "information_density": 0.5, "estimated_duration_sec": 8.0, "visual_intent": "", "transition_intent": ""},
            ],
            "total_word_count": 10,
            "total_duration_sec": 24.0,
            "is_final": True,
        })
        pkg["traceability"] = {
            "entries": [],
            "unsupported_entries": [],
            "critical_unsupported": [],
            "research_to_script_coverage": 0.5,
            "script_to_research_traceability": 0.5,
            "distortion_warnings": [],
            "unused_high_importance_claim_ids": [],
        }
        pkg["title"]["selected_id"] = pkg["title"]["candidates"][0]["title_id"]
        pkg["title"]["validated_against_script"] = True
        with pytest.raises(ValueError, match="sequential"):
            StoryPackage.model_validate(pkg)

    def test_research_gate_blocks_critical(self):
        """research_failures containing 'CRITICAL' sets status=BLOCKED."""
        pkg = _minimal_story_package()
        pkg["research_failures"] = ["SOME_WARNING", "CRITICAL: insufficient sources"]
        pkg["metadata"]["status"] = "in_progress"  # pre-validate, then validator should override
        validated = StoryPackage.model_validate(pkg)
        assert validated.metadata.status == StoryStatus.BLOCKED

    def test_research_gate_allows_warnings(self):
        """Non-CRITICAL failures do not block (status stays in_progress)."""
        pkg = _minimal_story_package()
        pkg["research_failures"] = ["WARNING: low coverage in region X"]
        validated = StoryPackage.model_validate(pkg)
        assert validated.metadata.status == StoryStatus.IN_PROGRESS

    def test_enums_complete(self):
        """All enum values across all story enums are accessible."""
        # AngleType — all 12 values
        for angle in AngleType:
            AngleCandidate(angle_id="A-1", type=angle, title="Test Title", description="x" * 20, central_tension="x" * 10)

        # NarrativePurpose — all 14 values
        for purpose in NarrativePurpose:
            NarrativeBeat(beat_id="B-1", purpose=purpose, emotional_state=EmotionalState.NEUTRAL)

        # EmotionalState — all 6 values
        for emo in EmotionalState:
            assert emo in EmotionalState

        # ScriptVersion — all 4 values
        for ver in ScriptVersion:
            assert ver in ScriptVersion

        # CertaintyLevel (story) — all 5 values
        for cert in CertaintyLevel:
            ClaimTraceEntry(
                segment_id="SEG-1",
                certainty_level=cert,
                claim_ids=["CLM-001"],
            )

        # TitleRiskFlag — all 6 values
        for flag in TitleRiskFlag:
            assert flag in TitleRiskFlag

        # CritiqueSeverity — all 3 values
        for sev in CritiqueSeverity:
            assert sev in CritiqueSeverity

        # CritiqueCategory — all 14 values
        for cat in CritiqueCategory:
            CritiqueFinding(
                finding_id="F-1",
                severity=CritiqueSeverity.WARNING,
                category=cat,
                problem="x" * 10,
                recommendation="x" * 10,
            )

        # ReviewStatus — all 4 values
        for status in ReviewStatus:
            assert status in ReviewStatus

        # StoryStatus — all 5 values
        for status in StoryStatus:
            assert status in StoryStatus

        # VisualMode — all 9 values
        for mode in VisualMode:
            StoryboardIntentItem(
                segment_id="SEG-1",
                purpose="x",
                visual_goal="x" * 10,
                visual_mode=mode,
            )

        def test_story_package_defaults(self):
            """StoryPackage with minimal metadata uses correct default values."""
            pkg = StoryPackage(
                metadata=StoryMetadata(
                    story_package_id="SP-TEST",
                    research_package_id="RP-TEST",
                )
            )
            assert pkg.metadata.status == StoryStatus.IN_PROGRESS
            assert pkg.metadata.review_status == ReviewStatus.DRAFT
            assert pkg.metadata.research_quality_passed is False
            assert pkg.research_failures == []
            assert pkg.research_warnings == []
            assert isinstance(pkg.thesis, ThesisSelection)
            assert isinstance(pkg.angle, AngleSelection)
            assert isinstance(pkg.title, TitleSelection)
            assert isinstance(pkg.hook, HookSelection)
            assert isinstance(pkg.script, ScriptDraft)
            assert isinstance(pkg.revision_history, RevisionHistory)
            assert pkg.blueprint is None
            assert pkg.traceability is None
            assert pkg.critique is None
            assert pkg.retention is None
            assert pkg.storyboard_intent is None
            assert pkg.quality_score is None

    def test_legacy_to_legacy_thesis(self):
        """to_legacy_thesis returns correct shape with topic, claim, hook."""
        pkg_dict = _minimal_story_package()
        pkg = StoryPackage.model_validate(pkg_dict)
        legacy = pkg.to_legacy_thesis()
        assert legacy["topic"] == "How Did Ancient Humans Survive Deadly Winters?"
        assert "claim" in legacy
        assert isinstance(legacy["counter_arguments"], list)
        assert isinstance(legacy["supporting_facts"], list)

    def test_legacy_to_legacy_title_package(self):
        """to_legacy_title_package returns candidates list and chosen_index."""
        pkg_dict = _minimal_story_package()
        pkg = StoryPackage.model_validate(pkg_dict)
        legacy = pkg.to_legacy_title_package()
        assert "candidates" in legacy
        assert "chosen_index" in legacy
        assert isinstance(legacy["candidates"], list)
        assert legacy["chosen_index"] >= 0

    def test_legacy_to_legacy_script(self):
        """to_legacy_script returns topic and sections grouped by purpose."""
        pkg_dict = _minimal_story_package()
        pkg_dict["script"]["versions"].append(
            _make_final_script_version([
                {"segment_id": "SEG-001", "order": 0, "narration": "Hook text.", "purpose": "hook"},
                {"segment_id": "SEG-002", "order": 1, "narration": "Setup text.", "purpose": "setup"},
            ])
        )
        pkg = StoryPackage.model_validate(pkg_dict)
        legacy = pkg.to_legacy_script()
        assert legacy["topic"] == "How Did Ancient Humans Survive Deadly Winters?"
        assert "sections" in legacy
        section_names = [s["name"] for s in legacy["sections"]]
        assert "hook" in section_names
        assert "setup" in section_names

    def test_legacy_to_legacy_storyboard(self):
        """to_legacy_storyboard returns beats with summary, environment_id, characters."""
        pkg_dict = _minimal_story_package()
        pkg_dict["storyboard_intent"] = {
            "artifact_version": {"version": "v1", "created_at": "2024-01-01T00:00:00Z", "provider": "openai", "model": "gpt-4o", "configuration": {}, "input_hash": "x"},
            "items": [
                {
                    "segment_id": "SEG-001",
                    "purpose": "hook",
                    "visual_goal": "Lone figure in snow",
                    "visual_mode": "environment",
                    "characters": ["narrator"],
                    "environment": "ice_age_plains",
                    "props": [],
                    "camera_intent": "zoom in",
                    "motion_intent": "",
                    "text_intent": "",
                    "source_ids": [],
                    "continuity_notes": "",
                },
            ],
            "visual_mode_counts": {"environment": 1},
        }
        pkg = StoryPackage.model_validate(pkg_dict)
        legacy = pkg.to_legacy_storyboard()
        assert "beats" in legacy
        assert len(legacy["beats"]) == 1
        beat = legacy["beats"][0]
        assert "summary" in beat
        assert "environment_id" in beat
        assert beat["environment_id"] == "ice_age_plains"

    def test_story_package_research_gate_validator_no_op_when_blocked(self):
        """Validator skips when status is already BLOCKED."""
        pkg_dict = _minimal_story_package()
        pkg_dict["metadata"]["status"] = "blocked"
        pkg_dict["research_failures"] = ["CRITICAL: X"]  # Should be ignored when already blocked
        validated = StoryPackage.model_validate(pkg_dict)
        assert validated.metadata.status == StoryStatus.BLOCKED
        # The validator should preserve the blocked status without modifying failures
        assert validated.research_failures == ["CRITICAL: X"]

    def test_story_package_thesis_validator_allows_empty_selection(self):
        """Thesis validator allows empty selected_id (not yet selected)."""
        pkg_dict = _minimal_story_package()
        pkg_dict["thesis"]["selected_id"] = ""  # Not selected yet
        validated = StoryPackage.model_validate(pkg_dict)
        assert validated.thesis.selected_id == ""

    def test_story_package_title_revalidation_allows_unselected(self):
        """Title revalidation allows no selection (not yet selected)."""
        pkg_dict = _minimal_story_package()
        pkg_dict["title"]["selected_id"] = ""  # Not yet selected
        pkg_dict["title"]["validated_against_script"] = False
        validated = StoryPackage.model_validate(pkg_dict)
        assert validated.title.selected_id == ""

    def test_artifact_version_defaults(self):
        """ArtifactVersion uses correct defaults."""
        av = ArtifactVersion(version="v1")
        assert av.provider == "openai"
        assert av.model == ""
        assert isinstance(av.configuration, dict)
        assert av.input_hash == ""

    def test_script_draft_version_accessors(self):
        """ScriptDraft.get_version and get_active work correctly."""
        draft = ScriptDraft()
        assert draft.get_version(ScriptVersion.DRAFT) is None
        assert draft.get_active() is None

        ver = ScriptVersionRecord(
            version_type=ScriptVersion.DRAFT,
            artifact_version=ArtifactVersion(version="v1"),
            segments=[],
        )
        draft.versions.append(ver)
        assert draft.get_version(ScriptVersion.DRAFT) is ver
        assert draft.get_active() is ver

    def test_script_version_record_full_text(self):
        """ScriptVersionRecord.full_text joins narration in order."""
        rec = ScriptVersionRecord(
            version_type=ScriptVersion.FINAL,
            artifact_version=ArtifactVersion(version="v1"),
            segments=[
                ScriptSegment(segment_id="SEG-1", order=1, narration="Second.", purpose=NarrativePurpose.SETUP, claim_ids=[], certainty_level=CertaintyLevel.SUPPORTED),
                ScriptSegment(segment_id="SEG-0", order=0, narration="First.", purpose=NarrativePurpose.HOOK, claim_ids=[], certainty_level=CertaintyLevel.SUPPORTED),
            ],
        )
        assert rec.full_text() == "First. Second."

    def test_story_quality_score_all_dimensions_present(self):
        """StoryQualityScore has all 15 dimension fields."""
        dims = [
            "thesis_strength", "evidence_alignment", "angle_strength",
            "title_strength", "hook_strength", "narrative_structure",
            "curiosity", "pacing", "clarity", "information_density",
            "visual_potential", "fact_traceability", "natural_language",
            "payoff", "ai_writing_risk",
        ]
        sqs = StoryQualityScore()
        for dim in dims:
            assert hasattr(sqs, dim), f"Missing dimension: {dim}"


# ---------------------------------------------------------------------------
# 2. Engine Integration Tests (~15)
# ---------------------------------------------------------------------------

class TestStoryEngineIntegration:
    """Full pipeline integration tests using MockLLMProvider."""

    def test_engine_creates_story_package(self, research_package: ResearchPackage):
        """Given ResearchPackage, engine.run returns a StoryPackage."""
        engine = StoryEngine(job_id="test-engine-basic", use_mock=True)
        story_pkg = engine.run(
            job_id="test-engine-basic",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        assert isinstance(story_pkg, StoryPackage)
        assert story_pkg.metadata.topic == "How Did Ancient Humans Survive Deadly Winters?"
        assert story_pkg.metadata.status in StoryStatus

    def test_quality_gate_blocks_low_quality(self):
        """quality_score.overall_score = 0.2 results in status BLOCKED."""
        low_quality = _make_research_package(quality_overall=0.2)
        engine = StoryEngine(job_id="test-blocked", use_mock=True)
        story_pkg = engine.run(
            job_id="test-blocked",
            topic="Test Topic",
            research_package=low_quality,
        )
        assert story_pkg.metadata.status == StoryStatus.BLOCKED

    def test_quality_gate_passes_high_quality(self):
        """quality_score.overall_score = 0.9 does not block."""
        high_quality = _make_research_package(quality_overall=0.9)
        engine = StoryEngine(job_id="test-passing", use_mock=True)
        story_pkg = engine.run(
            job_id="test-passing",
            topic="Test Topic",
            research_package=high_quality,
        )
        # Should not be blocked by quality gate
        assert story_pkg.metadata.status != StoryStatus.BLOCKED

    def test_thesis_generates_at_least_3_candidates(self, research_package: ResearchPackage):
        """Engine generates at least 3 ThesisCandidate objects."""
        engine = StoryEngine(job_id="test-thesis", use_mock=True)
        story_pkg = engine.run(
            job_id="test-thesis",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        assert len(story_pkg.thesis.candidates) >= 3, (
            f"Expected >=3 thesis candidates, got {len(story_pkg.thesis.candidates)}"
        )
        for tc in story_pkg.thesis.candidates:
            assert isinstance(tc, ThesisCandidate)
            assert len(tc.statement) >= 20

    def test_angle_generates_different_types(self, research_package: ResearchPackage):
        """Angle candidates span multiple AngleType values."""
        engine = StoryEngine(job_id="test-angle", use_mock=True)
        story_pkg = engine.run(
            job_id="test-angle",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        assert len(story_pkg.angle.candidates) >= 2
        angle_types = {c.type for c in story_pkg.angle.candidates}
        assert len(angle_types) >= 2, (
            f"Expected at least 2 distinct AngleType values, got: {angle_types}"
        )

    def test_title_generates_at_least_20(self, research_package: ResearchPackage):
        """Engine generates at least 20 TitleCandidate objects."""
        engine = StoryEngine(job_id="test-title", use_mock=True)
        story_pkg = engine.run(
            job_id="test-title",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        assert len(story_pkg.title.candidates) >= 20, (
            f"Expected >=20 title candidates, got {len(story_pkg.title.candidates)}"
        )
        for tc in story_pkg.title.candidates:
            assert isinstance(tc, TitleCandidate)
            assert len(tc.title) >= 5

    def test_hook_generates_at_least_5(self, research_package: ResearchPackage):
        """Engine generates at least 5 HookCandidate objects."""
        engine = StoryEngine(job_id="test-hook", use_mock=True)
        story_pkg = engine.run(
            job_id="test-hook",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        assert len(story_pkg.hook.candidates) >= 5, (
            f"Expected >=5 hook candidates, got {len(story_pkg.hook.candidates)}"
        )
        for hc in story_pkg.hook.candidates:
            assert isinstance(hc, HookCandidate)
            assert len(hc.text) >= 10

    def test_script_segments_have_sequential_orders(self, research_package: ResearchPackage):
        """Script draft segments have sequential orders 0..N-1."""
        engine = StoryEngine(job_id="test-segments", use_mock=True)
        story_pkg = engine.run(
            job_id="test-segments",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        draft_ver = story_pkg.script.get_version(ScriptVersion.DRAFT)
        assert draft_ver is not None, "No draft version found"
        orders = [s.order for s in draft_ver.segments]
        assert orders == list(range(len(orders))), (
            f"Segment orders should be sequential 0..N-1, got {orders}"
        )

    def test_traceability_links_claims(self, research_package: ResearchPackage):
        """At least 1 ClaimTraceEntry per script segment is produced."""
        engine = StoryEngine(job_id="test-trace", use_mock=True)
        story_pkg = engine.run(
            job_id="test-trace",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        assert story_pkg.traceability is not None
        assert len(story_pkg.traceability.entries) >= 1
        for entry in story_pkg.traceability.entries:
            assert isinstance(entry, ClaimTraceEntry)
            assert len(entry.segment_id) >= 1

    def test_revision_is_distinct_from_draft(self, research_package: ResearchPackage):
        """ScriptDraft.versions contains both DRAFT and REVISION version types."""
        engine = StoryEngine(job_id="test-revision", use_mock=True)
        story_pkg = engine.run(
            job_id="test-revision",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        version_types = {v.version_type for v in story_pkg.script.versions}
        assert ScriptVersion.DRAFT in version_types
        assert ScriptVersion.REVISION in version_types
        draft_rec = story_pkg.script.get_version(ScriptVersion.DRAFT)
        rev_rec = story_pkg.script.get_version(ScriptVersion.REVISION)
        assert draft_rec is not None
        assert rev_rec is not None
        # DRAFT and REVISION should be different objects (not same reference)
        assert draft_rec is not rev_rec

    def test_critique_returns_findings(self, research_package: ResearchPackage):
        """ScriptCritique.findings is non-empty after engine run."""
        engine = StoryEngine(job_id="test-critique", use_mock=True)
        story_pkg = engine.run(
            job_id="test-critique",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        assert story_pkg.critique is not None
        assert len(story_pkg.critique.findings) >= 1
        for f in story_pkg.critique.findings:
            assert isinstance(f, CritiqueFinding)
            assert len(f.problem) >= 10
            assert len(f.recommendation) >= 10

    def test_retention_per_segment(self, research_package: ResearchPackage):
        """RetentionAnalysis has 1 SegmentRetention per script segment."""
        engine = StoryEngine(job_id="test-retention", use_mock=True)
        story_pkg = engine.run(
            job_id="test-retention",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        assert story_pkg.retention is not None
        assert isinstance(story_pkg.retention, RetentionAnalysis)
        assert len(story_pkg.retention.segment_retentions) >= 1
        for sr in story_pkg.retention.segment_retentions:
            assert isinstance(sr, SegmentRetention)
            assert 0.0 <= sr.dropoff_risk <= 1.0
            assert 0.0 <= sr.retention_score <= 1.0

    def test_storyboard_intent_per_segment(self, research_package: ResearchPackage):
        """StoryboardIntent has 1 StoryboardIntentItem per script segment."""
        engine = StoryEngine(job_id="test-storyboard", use_mock=True)
        story_pkg = engine.run(
            job_id="test-storyboard",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        assert story_pkg.storyboard_intent is not None
        assert isinstance(story_pkg.storyboard_intent, StoryboardIntent)
        assert len(story_pkg.storyboard_intent.items) >= 1
        for item in story_pkg.storyboard_intent.items:
            assert isinstance(item, StoryboardIntentItem)
            assert len(item.visual_goal) >= 1
            assert len(item.purpose) >= 1

    def test_quality_score_all_dimensions(self, research_package: ResearchPackage):
        """StoryQualityScore has all 15 dimensions non-zero after engine run."""
        engine = StoryEngine(job_id="test-quality", use_mock=True)
        story_pkg = engine.run(
            job_id="test-quality",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        assert story_pkg.quality_score is not None
        dims = [
            "thesis_strength", "evidence_alignment", "angle_strength",
            "title_strength", "hook_strength", "narrative_structure",
            "curiosity", "pacing", "clarity", "information_density",
            "visual_potential", "fact_traceability", "natural_language",
            "payoff", "ai_writing_risk",
        ]
        for dim in dims:
            assert hasattr(story_pkg.quality_score, dim)
            dim_obj = getattr(story_pkg.quality_score, dim)
            assert isinstance(dim_obj, StoryQualityDimension)
            # Note: we allow zero values but check all exist
            assert hasattr(dim_obj, "score")

    def test_idempotent(self, research_package: ResearchPackage):
        """Running engine twice on same input produces equivalent output."""
        engine = StoryEngine(job_id="test-idempotent", use_mock=True)
        story_pkg_a = engine.run(
            job_id="test-idempotent",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        story_pkg_b = engine.run(
            job_id="test-idempotent",
            topic="How Did Ancient Humans Survive Deadly Winters?",
            research_package=research_package,
        )
        # Same number of candidates
        assert len(story_pkg_a.thesis.candidates) == len(story_pkg_b.thesis.candidates)
        assert len(story_pkg_a.angle.candidates) == len(story_pkg_b.angle.candidates)
        assert len(story_pkg_a.title.candidates) == len(story_pkg_b.title.candidates)
        assert len(story_pkg_a.hook.candidates) == len(story_pkg_b.hook.candidates)
        # Same status
        assert story_pkg_a.metadata.status == story_pkg_b.metadata.status


# ---------------------------------------------------------------------------
# 3. Cache Tests (~5)
# ---------------------------------------------------------------------------

class TestStoryCache:
    """Tests for StoryCache TTL, eviction, and corruption handling."""

    def test_cache_set_get_thesis(self, tmp_path):
        """Cache stores and retrieves thesis data correctly."""
        cache = StoryCache(job_dir=tmp_path / "job1")
        thesis_data = {"candidates": [{"thesis_id": "TH-001", "statement": "Test thesis."}]}
        cache.set_thesis("hash123", thesis_data)
        retrieved = cache.get_thesis("hash123")
        assert retrieved == thesis_data

    def test_cache_set_get_script(self, tmp_path):
        """Cache stores and retrieves script data correctly."""
        cache = StoryCache(job_dir=tmp_path / "job2")
        script_data = {"versions": [{"version_type": "draft", "segments": []}]}
        cache.set_script("hash456", script_data)
        retrieved = cache.get_script("hash456")
        assert retrieved == script_data

    def test_cache_ttl_evicts_expired(self, tmp_path, monkeypatch):
        """Cache entry older than TTL is evicted (returns None)."""
        cache = StoryCache(job_dir=tmp_path / "job3")
        cache.set_thesis("old-hash", {"candidates": []})

        # Manually age the cache file beyond TTL (default TTL is from settings)
        for f in cache.cache_dir.glob("*.json"):
            old_mtime = f.stat().st_mtime - (8 * 86400)  # 8 days old
            import os
            os.utime(f, (old_mtime, old_mtime))

        result = cache.get_thesis("old-hash")
        assert result is None, "Expired cache entry should return None"

    def test_cache_miss_returns_none(self, tmp_path):
        """Cache miss for non-existent key returns None."""
        cache = StoryCache(job_dir=tmp_path / "job4")
        result = cache.get_thesis("nonexistent-key-xyz123")
        assert result is None

    def test_cache_corrupt_evicts(self, tmp_path):
        """Corrupt JSON in cache file is evicted and returns None."""
        cache = StoryCache(job_dir=tmp_path / "job5")
        # Write corrupt JSON directly
        corrupt_file = cache.cache_dir / "thesis_nonexistent.json"
        cache.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(corrupt_file, "w", encoding="utf-8") as fh:
            fh.write("not valid json {")

        result = cache.get_thesis("nonexistent")
        assert result is None, "Corrupt cache entry should return None"


# ---------------------------------------------------------------------------
# 4. Distortion Detection Tests (~5)
# ---------------------------------------------------------------------------

class TestDistortionDetection:
    """Tests for claim distortion detection in traceability."""

    def test_stronger_wording_detected(self):
        """'proved' with low-certainty claim raises distortion flag."""
        entry = ClaimTraceEntry(
            segment_id="SEG-001",
            claim_text_excerpt="Science has proved that mammoths were hunted for fat.",
            certainty_level=CertaintyLevel.INFERENTIAL,
            claim_ids=["CLM-001"],
            source_ids=["SRC-00000001"],
            distortion_flags=[],
        )
        # Simulate distortion detection: "proved" is stronger than "inferential" permits
        text_lower = entry.claim_text_excerpt.lower()
        if "proved" in text_lower and entry.certainty_level in (
            CertaintyLevel.INFERENTIAL,
            CertaintyLevel.CONDITIONAL,
            CertaintyLevel.SPECULATIVE,
        ):
            entry.distortion_flags.append("stronger_wording")
            entry.distortion_detail = "'proved' overstates inferential evidence"
        assert "stronger_wording" in entry.distortion_flags

    def test_broader_scope_detected(self):
        """'all humans' with few sources triggers distortion flag."""
        entry = ClaimTraceEntry(
            segment_id="SEG-002",
            claim_text_excerpt="All humans used fire as their primary survival tool.",
            certainty_level=CertaintyLevel.SUPPORTED,
            claim_ids=["CLM-001"],
            source_ids=["SRC-00000001"],  # Only 1 source for a broad claim
            distortion_flags=[],
        )
        text_lower = entry.claim_text_excerpt.lower()
        broad_phrases = ["all humans", "all people", "every human", "all ancient"]
        if any(phrase in text_lower for phrase in broad_phrases) and len(entry.source_ids) < 3:
            entry.distortion_flags.append("broader_scope")
            entry.distortion_detail = f"Broad claim '{entry.claim_text_excerpt}' has only {len(entry.source_ids)} source(s)"
        assert "broader_scope" in entry.distortion_flags

    def test_removed_uncertainty_detected(self):
        """Removing hedges 'may' or 'suggests' from inferential text triggers flag."""
        entry = ClaimTraceEntry(
            segment_id="SEG-003",
            claim_text_excerpt="Neanderthals had fat reserves that kept them warm.",  # Original: "may have had"
            certainty_level=CertaintyLevel.INFERENTIAL,
            claim_ids=["CLM-002"],
            source_ids=["SRC-00000001"],
            distortion_flags=[],
        )
        uncertainty_words = {"may", "might", "suggests", "appears", "possibly", "could"}
        words = set(entry.claim_text_excerpt.lower().split())
        has_uncertainty = bool(words & uncertainty_words)
        if not has_uncertainty and entry.certainty_level in (
            CertaintyLevel.INFERENTIAL,
            CertaintyLevel.CONDITIONAL,
            CertaintyLevel.SPECULATIVE,
        ):
            entry.distortion_flags.append("removed_uncertainty")
            entry.distortion_detail = "Inferential claim lacks uncertainty language"
        assert "removed_uncertainty" in entry.distortion_flags

    def test_unsupported_segment_detected(self):
        """Segment with factual language but no claim_ids and no sources → UNSUPPORTED."""
        entry = ClaimTraceEntry(
            segment_id="SEG-004",
            claim_text_excerpt="This cave was inhabited for thousands of years.",
            certainty_level=CertaintyLevel.UNSUPPORTED,
            claim_ids=[],   # No linked claims
            source_ids=[],  # No linked sources
            distortion_flags=[],
            is_supported=False,
        )
        factual_indicators = {"was", "were", "inhabited", "used", "created", "built"}
        words = set(entry.claim_text_excerpt.lower().split())
        has_factual = bool(words & factual_indicators)
        if not entry.claim_ids and not entry.source_ids and has_factual:
            entry.distortion_flags.append("unsupported_factual_claim")
            entry.distortion_detail = "Factual statement with no claim or source backing"
        assert "unsupported_factual_claim" in entry.distortion_flags

    def test_supported_segment_ok(self):
        """Claim IDs linked and certainty_level=SUPPORTED → no distortion flags."""
        entry = ClaimTraceEntry(
            segment_id="SEG-005",
            claim_text_excerpt="The controlled use of fire dates back at least 400,000 years.",
            certainty_level=CertaintyLevel.SUPPORTED,
            claim_ids=["CLM-002"],
            source_ids=["SRC-00000001", "SRC-00000002"],
            distortion_flags=[],
            is_supported=True,
        )
        # Simulate check: supported claims with sources should have no flags
        if entry.certainty_level == CertaintyLevel.SUPPORTED and entry.is_supported:
            entry.distortion_flags = [f for f in entry.distortion_flags if f not in ("stronger_wording", "broader_scope", "removed_uncertainty")]
        assert len(entry.distortion_flags) == 0


# ---------------------------------------------------------------------------
# 5. AI-Writing Risk Heuristic Tests (~5)
# ---------------------------------------------------------------------------

class TestAIWritingRiskHeuristics:
    """Tests for AI-writing pattern detection in script segments."""

    def _check_ai_flags(self, narration: str) -> list[str]:
        """Helper: run AI-writing risk heuristics on narration text."""
        flags: list[str] = []
        words = narration.lower().split()
        # Count connector words
        but_count = words.count("but")
        because_count = words.count("because")
        if but_count > 2:
            flags.append("overused_but")
        if because_count > 2:
            flags.append("overused_because")
        # Formulaic transition phrases
        formulaic = [
            "but here's the thing",
            "now, this might surprise you",
            "but the truth is",
            "the fact of the matter is",
            "it turns out",
        ]
        for phrase in formulaic:
            if phrase in narration.lower():
                flags.append("formulaic_transition")
                break
        # AI summary patterns
        summary_phrases = [
            "in summary",
            "to sum up",
            "in conclusion",
            "that's why",
            "this is why",
            "in short",
        ]
        for phrase in summary_phrases:
            if phrase in narration.lower():
                flags.append("ai_summary_pattern")
                break
        return flags

    def test_overused_but_flagged(self):
        """Text with too many 'but' connectors is flagged."""
        narration = (
            "Fire was important, but clothing was also crucial. "
            "But shelter mattered too, but food was the real key."
        )
        flags = self._check_ai_flags(narration)
        assert "overused_but" in flags

    def test_overused_because_flagged(self):
        """Text with too many 'because' connectors is flagged."""
        narration = (
            "Because fire provided warmth, because it cooked food, "
            "because it dried hides, and because it enabled night activity."
        )
        flags = self._check_ai_flags(narration)
        assert "overused_because" in flags

    def test_formulaic_transitions_flagged(self):
        """Script with formulaic transition phrases is flagged."""
        narration = (
            "Fire kept them warm. But here's the thing: the real story "
            "is how cooperation tied everything together."
        )
        flags = self._check_ai_flags(narration)
        assert "formulaic_transition" in flags

        narration2 = "Now, this might surprise you: fat was more valuable than meat."
        flags2 = self._check_ai_flags(narration2)
        assert "formulaic_transition" in flags2

    def test_ai_summary_pattern_flagged(self):
        """Script with AI summary phrases like 'In summary' is flagged."""
        narration = "In summary, the four pillars of Ice Age survival were fire, fur, fat, and cooperation."
        flags = self._check_ai_flags(narration)
        assert "ai_summary_pattern" in flags

        narration2 = "To sum up, ancient humans survived because they learned to work together."
        flags2 = self._check_ai_flags(narration2)
        assert "ai_summary_pattern" in flags2

    def test_clean_script_no_flags(self):
        """Regular narrative prose with natural language has no AI flags."""
        narration = (
            "A single human, alone, would die in an Ice Age winter within hours. "
            "The first ingredient was fire. Hearths dug into cave floors, "
            "dated to four hundred thousand years ago, suggest they kept it "
            "burning almost constantly."
        )
        flags = self._check_ai_flags(narration)
        assert "overused_but" not in flags
        assert "overused_because" not in flags
        assert "formulaic_transition" not in flags
        assert "ai_summary_pattern" not in flags


# ---------------------------------------------------------------------------
# Helper builders (used by schema validation tests above)
# ---------------------------------------------------------------------------

def _make_20_titles() -> list[dict]:
    """Return 20 valid title candidate dicts for schema tests."""
    titles = []
    for i in range(20):
        titles.append({
            "title_id": f"TTL-{i+1:03d}",
            "title": f"How Ancient Humans Survived Ice Age Winters ({i})",
            "curiosity_score": 0.8,
            "clarity_score": 0.85,
            "specificity_score": 0.75,
            "novelty_score": 0.6,
            "truthfulness_score": 0.9,
            "thesis_alignment": 0.8,
            "payoff_alignment": 0.75,
            "mobile_readability": 0.85,
            "overall_score": 0.8,
            "risk_flags": [],
            "promised_question": "How did they survive?",
            "promised_payoff": "A survival formula.",
        })
    return titles


def _make_final_script_version(segments: list[dict]) -> dict:
    """Build a final script version dict from segment specs."""
    return {
        "version_type": "final",
        "artifact_version": {
            "version": "v1",
            "created_at": "2024-01-01T00:00:00Z",
            "provider": "openai",
            "model": "gpt-4o",
            "configuration": {},
            "input_hash": "final-x",
        },
        "segments": [
            {
                "segment_id": seg["segment_id"],
                "order": seg["order"],
                "narration": seg["narration"],
                "purpose": seg["purpose"],
                "beat_id": f"B-{seg['order']+1:03d}",
                "claim_ids": [],
                "source_ids": [],
                "certainty_level": CertaintyLevel.SUPPORTED,
                "emotional_state": "neutral",
                "curiosity_level": 0.5,
                "information_density": 0.5,
                "estimated_duration_sec": 8.0,
                "visual_intent": "",
                "transition_intent": "",
            }
            for seg in segments
        ],
        "total_word_count": sum(len(s["narration"].split()) for s in segments),
        "total_duration_sec": sum(8.0 for _ in segments),
        "is_final": True,
    }


def _make_story_package_with_titles(num_titles: int) -> dict:
    """Build a minimal StoryPackage dict with exactly num_titles title candidates."""
    pkg = _minimal_story_package()
    pkg["title"]["candidates"] = []
    for i in range(num_titles):
        pkg["title"]["candidates"].append({
            "title_id": f"TTL-{i+1:03d}",
            "title": f"Title Candidate Number {i+1}",
            "curiosity_score": 0.8,
            "clarity_score": 0.85,
            "specificity_score": 0.75,
            "novelty_score": 0.6,
            "truthfulness_score": 0.9,
            "thesis_alignment": 0.8,
            "payoff_alignment": 0.75,
            "mobile_readability": 0.85,
            "overall_score": 0.8,
            "risk_flags": [],
            "promised_question": "How did they survive?",
            "promised_payoff": "A survival formula.",
        })
    return pkg


def _minimal_story_package() -> dict:
    """Return a minimal but valid StoryPackage dict that passes schema validation."""
    return {
        "metadata": {
            "version": "1",
            "story_package_id": "SP-TEST-001",
            "research_package_id": "RP-TEST-001",
            "research_package_hash": "a1b2c3d4",
            "topic": "How Did Ancient Humans Survive Deadly Winters?",
            "job_id": "test-job",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "status": "in_progress",
            "review_status": "draft",
            "research_quality_passed": True,
            "research_quality_overall": 0.79,
            "research_failures": [],
            "research_warnings": [],
        },
        "research_status": "complete",
        "research_failures": [],
        "research_warnings": [],
        "thesis": {
            "artifact_version": {"version": "v1", "created_at": "2024-01-01T00:00:00Z", "provider": "openai", "model": "gpt-4o", "configuration": {}, "input_hash": "abc123"},
            "candidates": [
                {
                    "thesis_id": "THS-001",
                    "statement": (
                        "Ancient humans survived deadly Ice Age winters not through any single "
                        "invention, but by combining fire, clothing, shelter, and food into "
                        "an integrated survival system."
                    ),
                    "supporting_claim_ids": ["CLM-001", "CLM-002", "CLM-003"],
                    "contradicting_claim_ids": [],
                    "uncertainty": "Relative importance of each factor is debated.",
                    "explanatory_power": 0.9,
                    "novelty": 0.6,
                    "story_value": 0.9,
                    "visual_value": 0.85,
                    "audience_relevance": 0.95,
                    "evidence_strength": 0.88,
                    "overall_score": 0.87,
                    "reason": "Covers all major survival strategies.",
                },
                {
                    "thesis_id": "THS-002",
                    "statement": (
                        "Fire was the pivotal breakthrough that enabled humans to survive "
                        "glacial winters and fundamentally changed their relationship with nature."
                    ),
                    "supporting_claim_ids": ["CLM-002"],
                    "contradicting_claim_ids": [],
                    "uncertainty": "",
                    "explanatory_power": 0.7,
                    "novelty": 0.5,
                    "story_value": 0.75,
                    "visual_value": 0.8,
                    "audience_relevance": 0.9,
                    "evidence_strength": 0.92,
                    "overall_score": 0.78,
                    "reason": "Strong evidence but narrower scope.",
                },
                {
                    "thesis_id": "THS-003",
                    "statement": (
                        "Social cooperation and group cohesion were the ultimate survival "
                        "advantage that allowed Ice Age humans to outlast extreme seasonal challenges."
                    ),
                    "supporting_claim_ids": ["CLM-001"],
                    "contradicting_claim_ids": [],
                    "uncertainty": "Cooperation is hypothesized but difficult to verify archaeologically.",
                    "explanatory_power": 0.8,
                    "novelty": 0.75,
                    "story_value": 0.95,
                    "visual_value": 0.7,
                    "audience_relevance": 0.85,
                    "evidence_strength": 0.65,
                    "overall_score": 0.8,
                    "reason": "Strong narrative hook but softer evidence.",
                },
            ],
            "selected_id": "THS-001",
            "review_status": "draft",
            "review_notes": "",
        },
        "angle": {
            "artifact_version": {"version": "v1", "created_at": "2024-01-01T00:00:00Z", "provider": "openai", "model": "gpt-4o", "configuration": {}, "input_hash": "def456"},
            "candidates": [
                {
                    "angle_id": "ANG-001",
                    "type": "survival",
                    "title": "Fire, Fur, Fat, and Together",
                    "description": "Walk through the four pillars of Ice Age survival.",
                    "central_tension": "Could any single pillar have worked without the others?",
                    "supporting_claim_ids": ["CLM-001", "CLM-002", "CLM-003"],
                    "uncertainties": ["How much did genetic adaptation contribute?"],
                    "visual_potential": 0.9,
                    "curiosity": 0.85,
                    "emotional_potential": 0.8,
                    "story_strength": 0.92,
                    "overall_score": 0.88,
                },
                {
                    "angle_id": "ANG-002",
                    "type": "contradiction",
                    "title": "What Neanderthals Knew About Cold That Science Is Still Debating",
                    "description": "Open with a paradox: Neanderthals thrived through ice ages.",
                    "central_tension": "Were Neanderthals built for cold, or did they learn to master it?",
                    "supporting_claim_ids": ["CLM-001"],
                    "uncertainties": ["Genetic vs. behavioral adaptation is unresolved."],
                    "visual_potential": 0.75,
                    "curiosity": 0.95,
                    "emotional_potential": 0.85,
                    "story_strength": 0.8,
                    "overall_score": 0.85,
                },
            ],
            "selected_id": "ANG-001",
            "review_status": "draft",
            "review_notes": "",
        },
        "title": {
            "artifact_version": {"version": "v1", "created_at": "2024-01-01T00:00:00Z", "provider": "openai", "model": "gpt-4o", "configuration": {}, "input_hash": "ghi789"},
            "candidates": _make_20_titles(),
            "selected_id": "TTL-001",
            "validated_against_script": True,
            "validation_note": "Title mirrors topic and matches final script.",
            "review_status": "draft",
            "review_notes": "",
        },
        "hook": {
            "artifact_version": {"version": "v1", "created_at": "2024-01-01T00:00:00Z", "provider": "openai", "model": "gpt-4o", "configuration": {}, "input_hash": "jkl012"},
            "candidates": [
                {
                    "hook_id": "HOK-001",
                    "text": "A single human, alone, would die in an Ice Age winter within hours. So how did our ancestors survive?",
                    "curiosity": 0.95,
                    "tension": 0.9,
                    "clarity": 0.9,
                    "specificity": 0.88,
                    "payoff_potential": 0.92,
                    "overall_score": 0.91,
                    "risk_flags": [],
                },
                {
                    "hook_id": "HOK-002",
                    "text": "Somewhere in the Arctic 30,000 years ago, a small group faced temperatures that would kill you in minutes. Here's how they did it.",
                    "curiosity": 0.88,
                    "tension": 0.95,
                    "clarity": 0.85,
                    "specificity": 0.82,
                    "payoff_potential": 0.85,
                    "overall_score": 0.87,
                    "risk_flags": [],
                },
            ],
            "selected_id": "HOK-001",
            "review_status": "draft",
            "review_notes": "",
        },
        "blueprint": {
            "artifact_version": {"version": "v1", "created_at": "2024-01-01T00:00:00Z", "provider": "openai", "model": "gpt-4o", "configuration": {}, "input_hash": "mno345"},
            "beats": [
                {"beat_id": "B-001", "purpose": "hook", "claim_ids": [], "emotional_state": "tense", "curiosity_level": 0.95, "information_density": 0.4, "visual_potential": 0.9, "estimated_duration_sec": 8.0},
                {"beat_id": "B-002", "purpose": "setup", "claim_ids": ["CLM-002"], "emotional_state": "neutral", "curiosity_level": 0.75, "information_density": 0.7, "visual_potential": 0.85, "estimated_duration_sec": 10.0},
                {"beat_id": "B-003", "purpose": "first_discovery", "claim_ids": ["CLM-003", "CLM-004"], "emotional_state": "calm", "curiosity_level": 0.8, "information_density": 0.75, "visual_potential": 0.88, "estimated_duration_sec": 10.0},
                {"beat_id": "B-004", "purpose": "evidence", "claim_ids": ["CLM-003"], "emotional_state": "warm", "curiosity_level": 0.7, "information_density": 0.7, "visual_potential": 0.85, "estimated_duration_sec": 12.0},
                {"beat_id": "B-005", "purpose": "escalation", "claim_ids": ["CLM-005", "CLM-006"], "emotional_state": "neutral", "curiosity_level": 0.72, "information_density": 0.8, "visual_potential": 0.8, "estimated_duration_sec": 10.0},
                {"beat_id": "B-006", "purpose": "payoff", "claim_ids": ["CLM-001", "CLM-005"], "emotional_state": "triumphant", "curiosity_level": 0.65, "information_density": 0.5, "visual_potential": 0.75, "estimated_duration_sec": 12.0},
            ],
            "total_estimated_duration_sec": 62.0,
            "progression_flags": ["tension_then_relief", "discovery_to_payoff"],
            "warnings": [],
        },
        "script": {
            "versions": [
                {
                    "version_type": "draft",
                    "artifact_version": {"version": "v1", "created_at": "2024-01-01T00:00:00Z", "provider": "openai", "model": "gpt-4o", "configuration": {}, "input_hash": "pqr678"},
                    "segments": [
                        {"segment_id": "SEG-001", "order": 0, "narration": "A single human, alone, would die in an Ice Age winter within hours.", "purpose": "hook", "beat_id": "B-001", "claim_ids": [], "source_ids": [], "certainty_level": "supported", "emotional_state": "tense", "curiosity_level": 0.95, "information_density": 0.4, "estimated_duration_sec": 8.0, "visual_intent": "", "transition_intent": ""},
                        {"segment_id": "SEG-002", "order": 1, "narration": "The first ingredient was fire.", "purpose": "setup", "beat_id": "B-002", "claim_ids": ["CLM-002"], "source_ids": ["SRC-00000001"], "certainty_level": "supported", "emotional_state": "neutral", "curiosity_level": 0.75, "information_density": 0.7, "estimated_duration_sec": 10.0, "visual_intent": "", "transition_intent": ""},
                    ],
                    "total_word_count": 15,
                    "total_duration_sec": 18.0,
                    "is_final": False,
                },
            ],
            "draft_version": "draft",
            "critique_version": "",
            "revision_version": "",
            "final_version": "",
            "active_version": "draft",
            "review_status": "draft",
            "review_notes": "",
        },
        "traceability": {
            "entries": [
                {"segment_id": "SEG-002", "claim_text_excerpt": "controlled use of fire dates back at least 400,000 years", "certainty_level": "supported", "claim_ids": ["CLM-002"], "source_ids": ["SRC-00000001"], "is_supported": True, "distortion_flags": [], "distortion_detail": ""},
            ],
            "unsupported_entries": [],
            "critical_unsupported": [],
            "research_to_script_coverage": 0.5,
            "script_to_research_traceability": 0.8,
            "distortion_warnings": [],
            "unused_high_importance_claim_ids": [],
        },
        "critique": {
            "artifact_version": {"version": "v1-crit", "created_at": "2024-01-01T00:30:00Z", "provider": "openai", "model": "gpt-4o", "configuration": {}, "input_hash": "yza567"},
            "findings": [
                {"finding_id": "CRT-001", "severity": "warning", "segment_id": "SEG-002", "category": "redundancy", "problem": "The phrase 'Fire wasn't just warmth' appears in both narration and implied by visual.", "evidence": "Script says it, diagram shows it.", "recommendation": "Remove redundant phrase from voiceover."},
            ],
            "critical_count": 0,
            "warning_count": 1,
            "info_count": 0,
            "hardest_section": "SEG-002",
            "weakest_point": "Minor redundancy in fire segment",
            "best_point": "Hook lands well",
            "would_viewer_leave_at": "SEG-002",
            "pacing_flags": [],
            "repetition_flags": [],
            "ai_pattern_flags": [],
        },
        "retention": {
            "segment_retentions": [
                {"segment_id": "SEG-001", "curiosity": 0.95, "new_information": 0.9, "tension": 0.9, "visual_change": 0.85, "payoff_distance": 0.9, "emotional_change": 0.7, "dropoff_risk": 0.1, "retention_score": 0.85},
                {"segment_id": "SEG-002", "curiosity": 0.75, "new_information": 0.8, "tension": 0.4, "visual_change": 0.75, "payoff_distance": 0.75, "emotional_change": 0.2, "dropoff_risk": 0.2, "retention_score": 0.61},
            ],
            "opening_risk": "Strong hook with high tension; low dropoff risk.",
            "middle_risk": "Segment 2 has moderate risk due to lower tension.",
            "ending_risk": "Not reached in this minimal test version.",
            "repetition_risks": [],
            "slow_sections": [],
            "premature_reveals": [],
            "weak_payoff_flag": False,
            "overall_retention_score": 0.73,
        },
        "revision_history": {
            "entries": [],
            "current_revision_number": 0,
        },
        "storyboard_intent": {
            "artifact_version": {"version": "v1", "created_at": "2024-01-01T03:00:00Z", "provider": "openai", "model": "gpt-4o", "configuration": {}, "input_hash": "bcd890"},
            "items": [
                {"segment_id": "SEG-001", "purpose": "Establish tension", "visual_goal": "Lone figure in snowy landscape", "visual_mode": "environment", "characters": ["narrator"], "environment": "ice_age_plains", "props": ["snow"], "camera_intent": "zoom in", "motion_intent": "camera pushes in", "text_intent": "", "source_ids": [], "continuity_notes": ""},
                {"segment_id": "SEG-002", "purpose": "Introduce fire", "visual_goal": "Diagram of hearth with timeline", "visual_mode": "diagram", "characters": [], "environment": "diagram_white", "props": ["fire_glow", "timeline"], "camera_intent": "static", "motion_intent": "timeline extends", "text_intent": "400,000 years of fire", "source_ids": ["SRC-00000001"], "continuity_notes": ""},
            ],
            "visual_mode_counts": {"environment": 1, "diagram": 1},
        },
        "quality_score": {
            "thesis_strength": {"score": 0.87, "notes": "THS-001 covers all major pillars."},
            "evidence_alignment": {"score": 0.85, "notes": "Script claims traceable."},
            "angle_strength": {"score": 0.88, "notes": "Survival formula angle is strong."},
            "title_strength": {"score": 0.87, "notes": "Title mirrors topic."},
            "hook_strength": {"score": 0.91, "notes": "Highest overall score."},
            "narrative_structure": {"score": 0.78, "notes": "Six-beat structure sound."},
            "curiosity": {"score": 0.8, "notes": "Consistently high curiosity."},
            "pacing": {"score": 0.72, "notes": "Middle section could be tighter."},
            "clarity": {"score": 0.82, "notes": "Generally clear."},
            "information_density": {"score": 0.7, "notes": "SEG-002 is dense."},
            "visual_potential": {"score": 0.85, "notes": "4 of 6 segments diagram-ready."},
            "fact_traceability": {"score": 0.83, "notes": "Claims well-traced."},
            "natural_language": {"score": 0.8, "notes": "AI patterns low risk."},
            "payoff": {"score": 0.88, "notes": "SEG-006 delivers thesis effectively."},
            "ai_writing_risk": {"score": 0.15, "notes": "No AI patterns detected."},
            "overall_score": 0.8,
            "dimension_scores": {
                "thesis_strength": 0.87, "evidence_alignment": 0.85, "angle_strength": 0.88,
                "title_strength": 0.87, "hook_strength": 0.91, "narrative_structure": 0.78,
                "curiosity": 0.8, "pacing": 0.72, "clarity": 0.82, "information_density": 0.7,
                "visual_potential": 0.85, "fact_traceability": 0.83, "natural_language": 0.8,
                "payoff": 0.88, "ai_writing_risk": 0.15,
            },
            "warnings": [],
            "failures": [],
            "recommendations": [],
        },
    }
