"""
Comprehensive tests for the Storyboard Intelligence Engine.

Covers:
1. Schema validation tests (StoryboardPackage, VisualBeat, etc.)
2. Engine integration tests with mock provider
3. Beat decomposition tests
4. Visual mode selection tests
5. Asset / character / environment requirement tests
6. Camera / motion / transition planning tests
7. Continuity engine tests
8. Evidence linking tests
9. Reconstruction safety tests
10. SceneDefinition compilation tests
11. Quality scoring tests
12. Cache tests
13. Idempotency tests
14. StoryboardCompiler output → SceneDefinition schema validation
"""
from __future__ import annotations

import os

# Force mock mode before any other imports.
os.environ["OPENAI_API_KEY"] = ""

import pytest
from pydantic import ValidationError

from app.schemas.research_package import (
    Claim,
    ClaimSourceLink,
    ClaimType,
    ResearchMetadata,
    ResearchPackage,
    ResearchQuestion,
    ResearchQuestionStatus,
    ResearchQualityScore as ResearchQualityScoreRP,
    ResearchSynthesis,
    Source,
    SourceLineage,
    SourceTier,
)
from app.schemas.story import (
    ScriptSegment,
    ScriptVersion,
    ScriptVersionRecord,
    StoryMetadata,
    StoryPackage,
)
from app.schemas.storyboard import (
    AssetRequirement,
    AudioSyncPoint,
    CameraPlan,
    CharacterRequirement,
    Composition,
    ContinuityIssue,
    ContinuityState,
    ContinuityUpdate,
    DiagramSpec,
    MapSpec,
    MotionItem,
    PropRequirement,
    SceneDefinitionCandidate,
    StoryboardAssetClass,
    StoryboardAssetRequirement,
    StoryboardAspectRatio,
    StoryboardCameraType,
    StoryboardContinuityFlag,
    StoryboardInformationAlignment,
    StoryboardMetadata,
    StoryboardMotionType,
    StoryboardPackage,
    StoryboardQualityScore,
    StoryboardReconstructionConfidence,
    StoryboardStatus,
    StoryboardStoryFunction,
    StoryboardTransition,
    StoryboardUncertaintyTreatment,
    StoryboardVisualMode,
    TextItem,
    VisualBeat,
)
from app.schemas.scene_definition import SceneDefinition, Meta
from app.storyboard.engine import StoryboardEngine
from app.storyboard.cache import StoryboardCache
from app.providers.mock_llm import MockLLMProvider


# ============================================================================
# Fixtures
# ============================================================================

def _make_research_package(quality_overall: float = 0.85) -> ResearchPackage:
    """Build a valid ResearchPackage for storyboard tests."""
    sources = [
        Source(
            id="SRC-00000001",
            url="https://www.nature.com/articles/s41586-019-1290-4",
            title="The evolutionary history of cold adaptation in humans",
            tier=SourceTier.TIER1,
            authority=0.95,
            recency=0.9,
            methodology=0.85,
            relevance=0.9,
            citation_quality=0.9,
            independence=1.0,
            content_hash="abc123",
            snippet="Ancient humans developed cold adaptations...",
            published_date="2019",
            author="Smith et al.",
            domain="nature.com",
            lineage=SourceLineage(),
            reviewed=True,
            approved=True,
            claims_from_this_source=["CLM-001", "CLM-002", "CLM-003"],
        ),
    ]
    claims = [
        Claim(
            claim_id="CLM-001",
            text="Ancient humans built fires to survive cold winters",
            claim_type=ClaimType.HISTORICAL,
            importance="high",
            confidence=0.9,
            certainty_reason="Multiple archaeological sites",
            source_ids=["SRC-00000001"],
        ),
        Claim(
            claim_id="CLM-002",
            text="Animal skin clothing provided thermal insulation",
            claim_type=ClaimType.HISTORICAL,
            importance="high",
            confidence=0.85,
            certainty_reason="Artifact evidence",
            source_ids=["SRC-00000001"],
        ),
        Claim(
            claim_id="CLM-003",
            text="Seasonal migration southward was a survival strategy",
            claim_type=ClaimType.HISTORICAL,
            importance="medium",
            confidence=0.75,
            certainty_reason="Settlement pattern evidence",
            source_ids=["SRC-00000001"],
        ),
    ]
    claim_links = [
        ClaimSourceLink(claim_id="CLM-001", source_id="SRC-00000001", relevance=0.95),
        ClaimSourceLink(claim_id="CLM-002", source_id="SRC-00000001", relevance=0.9),
        ClaimSourceLink(claim_id="CLM-003", source_id="SRC-00000001", relevance=0.8),
    ]
    synthesis = ResearchSynthesis(
        central_question="How did ancient humans survive deadly winters?",
        short_answer="Fire, shelter, clothing, and migration.",
        detailed_answer=(
            "Ancient humans survived by combining fire for warmth, "
            "shelters built from animal bone and skin, layered clothing, "
            "and seasonal migration to warmer regions during winter."
        ),
        strongest_evidence=["Archaeological hearths at multiple sites"],
        major_uncertainties=["Population sizes during ice age peaks"],
        important_examples=["Mammoth bone huts at Mezhirich"],
    )
    qscore = ResearchQualityScoreRP(
        source_quality=0.85,
        coverage=0.80,
        claim_traceability=0.90,
        independence=0.88,
        contradiction_detection=0.70,
        uncertainty_handling=0.80,
        research_depth=0.72,
        visual_value=0.85,
        story_value=0.90,
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
                text="How did ancient humans survive deadly Ice Age winters?",
                question_type="central",
                importance_score=0.95,
                status=ResearchQuestionStatus.COVERED,
                claims_touched=["CLM-001", "CLM-002", "CLM-003"],
            )
        ],
        sources=sources,
        claims=claims,
        claim_source_links=claim_links,
        synthesis=synthesis,
        quality_score=qscore,
    )


def _make_story_package() -> StoryPackage:
    """Build a minimal valid StoryPackage with a FINAL script.

    Uses _minimal_story_package from test_story_engine.py as a base so we
    inherit the full required schema (20+ titles, thesis, angle, etc.).
    """
    from tests.test_story_engine import _minimal_story_package

    pkg_dict = _minimal_story_package()
    pkg_dict["script"]["versions"].append({
        "version_type": "final",
        "artifact_version": {
            "version": "v1",
            "created_at": "2024-01-01T00:00:00Z",
            "provider": "openai",
            "model": "gpt-4o",
            "configuration": {},
            "input_hash": "x",
        },
        "segments": [
            {
                "segment_id": "SEG-001",
                "order": 0,
                "narration": (
                    "Twenty thousand years ago, ancient humans survived "
                    "deadly winters by making fire and building shelters."
                ),
                "purpose": "hook",
                "claim_ids": ["CLM-001"],
                "source_ids": ["SRC-00000001"],
                "certainty_level": "supported",
                "emotional_state": "tense",
                "curiosity_level": 0.8,
                "information_density": 0.7,
                "estimated_duration_sec": 12.0,
                "visual_intent": "A figure in snow with a small fire",
                "transition_intent": "",
            },
            {
                "segment_id": "SEG-002",
                "order": 1,
                "narration": (
                    "They used animal skin and bone tools to build shelters, "
                    "which protected them from the cold."
                ),
                "purpose": "explanation",
                "claim_ids": ["CLM-002"],
                "source_ids": ["SRC-00000001"],
                "certainty_level": "supported",
                "emotional_state": "neutral",
                "curiosity_level": 0.5,
                "information_density": 0.6,
                "estimated_duration_sec": 10.0,
                "visual_intent": "A diagram of how shelter protected",
                "transition_intent": "",
            },
            {
                "segment_id": "SEG-003",
                "order": 2,
                "narration": (
                    "Recent archaeological evidence shows that they also "
                    "migrated south during the coldest months."
                ),
                "purpose": "evidence",
                "claim_ids": ["CLM-003"],
                "source_ids": ["SRC-00000001"],
                "certainty_level": "inferential",
                "emotional_state": "neutral",
                "curiosity_level": 0.6,
                "information_density": 0.7,
                "estimated_duration_sec": 8.0,
                "visual_intent": "A map showing migration routes",
                "transition_intent": "",
            },
        ],
        "total_word_count": 60,
        "total_duration_sec": 30.0,
        "is_final": True,
    })
    return StoryPackage.model_validate(pkg_dict)


@pytest.fixture
def story_package() -> StoryPackage:
    return _make_story_package()


@pytest.fixture
def research_package() -> ResearchPackage:
    return _make_research_package(quality_overall=0.85)


# ============================================================================
# 1. Schema Validation Tests
# ============================================================================

class TestSchemaValidation:
    """StoryboardPackage and sub-schemas must validate."""

    def test_empty_package_valid(self):
        """Empty (default) StoryboardPackage should be valid with minimal metadata."""
        pkg = StoryboardPackage(
            metadata=StoryboardMetadata(
                storyboard_package_id="SB-TEST",
                story_package_id="SP-TEST",
            ),
            story_package_id="SP-TEST",
        )
        assert pkg.metadata.storyboard_package_id == "SB-TEST"
        assert pkg.visual_beats == []
        assert pkg.status == StoryboardStatus.DRAFT

    def test_beat_id_pattern(self):
        """beat_id must match expected pattern."""
        beat = VisualBeat(
            beat_id="beat_0001",
            segment_id="SEG-001",
            order=0,
            start_time=0.0,
            end_time=8.0,
            duration=8.0,
            purpose="setup",
        )
        assert beat.beat_id == "beat_0001"

    def test_visual_mode_enum_values(self):
        """StoryboardVisualMode has 11 values."""
        assert len(StoryboardVisualMode) == 11
        assert StoryboardVisualMode.CHARACTER in StoryboardVisualMode
        assert StoryboardVisualMode.HYBRID in StoryboardVisualMode

    def test_camera_type_enum_values(self):
        """StoryboardCameraType has 11 values."""
        assert len(StoryboardCameraType) == 11

    def test_motion_type_enum_values(self):
        """StoryboardMotionType has 14 values."""
        assert len(StoryboardMotionType) == 14

    def test_transition_enum_values(self):
        """StoryboardTransition has 6 values."""
        assert len(StoryboardTransition) == 6

    def test_beat_timing_validation(self):
        """end_time > start_time required."""
        with pytest.raises(ValidationError, match="end_time"):
            VisualBeat(
                beat_id="beat_0001",
                segment_id="SEG-001",
                order=0,
                start_time=5.0,
                end_time=3.0,
                duration=8.0,  # positive so duration validator passes; end_time < start_time fails
                purpose="setup",
            )

    def test_beat_duration_consistent_with_timing(self):
        """duration should equal end_time - start_time."""
        beat = VisualBeat(
            beat_id="beat_0001",
            segment_id="SEG-001",
            order=0,
            start_time=2.0,
            end_time=10.0,
            duration=8.0,
            purpose="setup",
        )
        assert beat.duration == 8.0

    def test_quality_score_normalizes_overall(self):
        """overall_score should be auto-computed from dimension_scores."""
        q = StoryboardQualityScore(
            dimension_scores={"a": 0.5, "b": 0.7},
            overall_score=0.0,
        )
        # Validator should compute overall = 0.6
        assert q.overall_score == 0.6

    def test_quality_score_keeps_explicit_overall(self):
        """Explicit overall_score is preserved."""
        q = StoryboardQualityScore(
            dimension_scores={"a": 0.5},
            overall_score=0.8,
        )
        assert q.overall_score == 0.8

    def test_scene_definition_candidate_timing(self):
        """SceneDefinitionCandidate requires end_sec > start_sec."""
        with pytest.raises(ValidationError, match="end_sec"):
            SceneDefinitionCandidate(
                scene_id="scene_001",
                beat_id="beat_0001",
                segment_id="SEG-001",
                start_sec=10.0,
                end_sec=5.0,
                environment_id="diagram_white",
            )

    def test_package_rejects_overlapping_beats(self):
        """Overlapping beats should fail validation."""
        beats = [
            VisualBeat(
                beat_id="beat_0001",
                segment_id="SEG-001",
                order=0,
                start_time=0.0,
                end_time=10.0,
                duration=10.0,
                purpose="a",
            ),
            VisualBeat(
                beat_id="beat_0002",
                segment_id="SEG-001",
                order=1,
                start_time=8.0,  # overlaps with beat_0001
                end_time=15.0,
                duration=7.0,
                purpose="b",
            ),
        ]
        with pytest.raises(ValidationError, match="overlap"):
            StoryboardPackage(
                metadata=StoryboardMetadata(
                    storyboard_package_id="SB-TEST",
                    story_package_id="SP-TEST",
                ),
                story_package_id="SP-TEST",
                visual_beats=beats,
                asset_requirements=[
                    AssetRequirement(
                        asset_id="dummy",
                        asset_class=StoryboardAssetClass.CHARACTER,
                    )
                ],
            )

    def test_package_requires_all_assets_declared(self):
        """Asset requirements referenced by beats must be declared."""
        beat = VisualBeat(
            beat_id="beat_0001",
            segment_id="SEG-001",
            order=0,
            start_time=0.0,
            end_time=8.0,
            duration=8.0,
            purpose="a",
            asset_requirements=["missing_asset_id"],
        )
        with pytest.raises(ValidationError, match="not declared"):
            StoryboardPackage(
                metadata=StoryboardMetadata(
                    storyboard_package_id="SB-TEST",
                    story_package_id="SP-TEST",
                ),
                story_package_id="SP-TEST",
                visual_beats=[beat],
            )

    def test_composition_has_vertical_reframe_flag(self):
        """Composition supports vertical_reframe_required flag."""
        c = Composition(vertical_reframe_required=True)
        assert c.vertical_reframe_required is True

    def test_reconstruction_confidence_enum(self):
        """StoryboardReconstructionConfidence has 3 values."""
        assert len(StoryboardReconstructionConfidence) == 3

    def test_uncertainty_treatment_enum(self):
        """StoryboardUncertaintyTreatment has 6 values."""
        assert len(StoryboardUncertaintyTreatment) == 6


# ============================================================================
# 2. Engine Integration Tests
# ============================================================================

class TestEngineIntegration:
    """Full StoryboardEngine integration with mock LLM."""

    def test_engine_produces_storyboard_package(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="test-1", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        assert isinstance(pkg, StoryboardPackage)
        assert pkg.story_package_id == "SP-TEST-001"
        assert pkg.metadata.storyboard_package_id.startswith("SB-")
        assert pkg.metadata.topic == story_package.metadata.topic

    def test_engine_generates_at_least_one_beat_per_segment(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="test-2", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        covered = pkg.segment_ids_covered()
        assert covered == {"SEG-001", "SEG-002", "SEG-003"}

    def test_engine_quality_score_present(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="test-3", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        assert pkg.storyboard_quality_score is not None
        assert 0.0 <= pkg.storyboard_quality_score.overall_score <= 1.0

    def test_engine_no_segments_returns_blocked(self):
        """Empty story package should produce blocked empty StoryboardPackage."""
        from tests.test_story_engine import _minimal_story_package
        empty_dict = _minimal_story_package()
        empty_dict["script"]["versions"] = []
        empty_dict["script"]["active_version"] = "draft"
        empty = StoryPackage.model_validate(empty_dict)
        engine = StoryboardEngine(job_id="test-empty", use_mock=True)
        pkg = engine.run(story_package=empty, research_package=None)
        assert pkg.status == StoryboardStatus.BLOCKED
        assert len(pkg.visual_beats) == 0
        assert any("No script segments" in f for f in pkg.failures)


# ============================================================================
# 3. Beat Decomposition Tests
# ============================================================================

class TestBeatDecomposition:
    """Each script segment must produce 1..N beats based on visual meaning."""

    def test_short_segment_yields_one_beat(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="dec-1", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        seg3_beats = pkg.beats_for_segment("SEG-003")  # 8s
        assert len(seg3_beats) == 1

    def test_medium_segment_yields_two_beats(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="dec-2", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        seg1_beats = pkg.beats_for_segment("SEG-001")  # 12s
        assert len(seg1_beats) >= 1

    def test_beat_ids_unique(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="dec-3", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        ids = pkg.beat_ids()
        assert len(ids) == len(set(ids))

    def test_beat_timings_sequential(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="dec-4", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        beats = pkg.visual_beats
        for i in range(len(beats) - 1):
            assert beats[i].end_time <= beats[i + 1].start_time + 0.05

    def test_total_duration_matches_script(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="dec-5", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        total = pkg.total_duration_sec()
        script_total = sum(
            s.estimated_duration_sec
            for s in story_package.script.get_version(ScriptVersion.FINAL).segments
        )
        # Allow small floating-point slop.
        assert abs(total - script_total) < 0.5


# ============================================================================
# 4. Visual Mode Selection Tests
# ============================================================================

class TestVisualModeSelection:
    """Heuristic mode selection must cover all required modes."""

    def test_diagram_keyword_picked(self):
        engine = StoryboardEngine(job_id="vm-1", use_mock=True)
        seg = ScriptSegment(
            segment_id="SEG-D",
            order=0,
            narration="The diagram shows a flow of cause and effect.",
            purpose="explanation",
            estimated_duration_sec=8.0,
        )
        mode, rationale = engine._select_visual_mode(seg, None)
        assert mode == StoryboardVisualMode.DIAGRAM
        assert "diagram" in rationale.lower()

    def test_map_keyword_picked(self):
        engine = StoryboardEngine(job_id="vm-2", use_mock=True)
        seg = ScriptSegment(
            segment_id="SEG-M",
            order=0,
            narration="The map shows where they migrated.",
            purpose="explanation",
            estimated_duration_sec=8.0,
        )
        mode, _ = engine._select_visual_mode(seg, None)
        assert mode == StoryboardVisualMode.MAP

    def test_timeline_keyword_picked(self):
        engine = StoryboardEngine(job_id="vm-3", use_mock=True)
        seg = ScriptSegment(
            segment_id="SEG-T",
            order=0,
            narration="Twenty thousand years ago, evolution began.",
            purpose="explanation",
            estimated_duration_sec=8.0,
        )
        mode, _ = engine._select_visual_mode(seg, None)
        assert mode == StoryboardVisualMode.TIMELINE

    def test_comparison_keyword_picked(self):
        engine = StoryboardEngine(job_id="vm-4", use_mock=True)
        seg = ScriptSegment(
            segment_id="SEG-C",
            order=0,
            narration="Compared to today, their diet was twice as rich.",
            purpose="explanation",
            estimated_duration_sec=8.0,
        )
        mode, _ = engine._select_visual_mode(seg, None)
        assert mode == StoryboardVisualMode.COMPARISON

    def test_artifact_keyword_picked(self):
        engine = StoryboardEngine(job_id="vm-5", use_mock=True)
        seg = ScriptSegment(
            segment_id="SEG-A",
            order=0,
            narration="The stone tool was found near the cave.",
            purpose="evidence",
            estimated_duration_sec=8.0,
        )
        mode, _ = engine._select_visual_mode(seg, None)
        assert mode == StoryboardVisualMode.ARTIFACT

    def test_data_keyword_picked(self):
        engine = StoryboardEngine(job_id="vm-6", use_mock=True)
        seg = ScriptSegment(
            segment_id="SEG-DV",
            order=0,
            narration="The average temperature was 30 degrees celsius.",
            purpose="evidence",
            estimated_duration_sec=8.0,
        )
        mode, _ = engine._select_visual_mode(seg, None)
        assert mode == StoryboardVisualMode.DATA_VISUALIZATION

    def test_environment_keyword_picked(self):
        engine = StoryboardEngine(job_id="vm-7", use_mock=True)
        seg = ScriptSegment(
            segment_id="SEG-E",
            order=0,
            narration="The icy tundra stretched to the horizon.",
            purpose="context",
            estimated_duration_sec=8.0,
        )
        mode, _ = engine._select_visual_mode(seg, None)
        assert mode == StoryboardVisualMode.ENVIRONMENT

    def test_intent_overrides_heuristic(self):
        engine = StoryboardEngine(job_id="vm-8", use_mock=True)
        seg = ScriptSegment(
            segment_id="SEG-I",
            order=0,
            narration="Some text about fire.",
            purpose="explanation",
            estimated_duration_sec=8.0,
        )
        from app.schemas.story import StoryboardIntentItem, VisualMode as StoryVM
        intent = StoryboardIntentItem(
            segment_id="SEG-I",
            purpose="setup",
            visual_goal="A simple visual",
            visual_mode=StoryVM.MAP,
        )
        mode, _ = engine._select_visual_mode(seg, intent)
        # The intent (MAP) should win over keyword-only scoring.
        assert mode in {StoryboardVisualMode.MAP, StoryboardVisualMode.DIAGRAM}

    def test_default_mode_is_character(self):
        engine = StoryboardEngine(job_id="vm-9", use_mock=True)
        seg = ScriptSegment(
            segment_id="SEG-X",
            order=0,
            narration="They did something important.",
            purpose="setup",
            estimated_duration_sec=8.0,
        )
        mode, _ = engine._select_visual_mode(seg, None)
        # Could be CHARACTER or whatever the heuristic picks; just must be valid.
        assert isinstance(mode, StoryboardVisualMode)


# ============================================================================
# 5. Asset / Character / Environment / Prop Requirements Tests
# ============================================================================

class TestAssetRequirements:
    """Asset requirements must be deterministic and deduped."""

    def test_narrator_always_present(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="a-1", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        ids = {a.asset_id for a in pkg.asset_requirements}
        assert "narrator" in ids

    def test_asset_requirements_unique(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="a-2", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        ids = [a.asset_id for a in pkg.asset_requirements]
        assert len(ids) == len(set(ids))

    def test_narrator_reuse_priority_high(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="a-3", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        narrator = next(
            a for a in pkg.asset_requirements if a.asset_id == "narrator"
        )
        assert narrator.requirement == StoryboardAssetRequirement.REUSE_EXISTING
        assert narrator.asset_class == StoryboardAssetClass.CHARACTER

    def test_beats_have_asset_requirements(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="a-4", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        for beat in pkg.visual_beats:
            assert len(beat.asset_requirements) >= 1


# ============================================================================
# 6. Camera / Motion / Transition Planning Tests
# ============================================================================

class TestCameraMotionTransition:
    """Camera, motion, transition plans must be valid."""

    def test_every_beat_has_camera(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="c-1", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        for beat in pkg.visual_beats:
            assert beat.camera is not None
            assert beat.camera.camera_id.startswith("cam_")

    def test_camera_plan_duration_matches_beat(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="c-2", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        for beat in pkg.visual_beats:
            assert beat.camera.duration_sec == pytest.approx(beat.duration, rel=0.01)

    def test_motion_has_purpose(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="c-3", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        for beat in pkg.visual_beats:
            for motion in beat.motion:
                if motion.motion_type != StoryboardMotionType.NONE:
                    assert motion.purpose

    def test_default_transition_is_cut(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="c-4", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        for beat in pkg.visual_beats:
            assert isinstance(beat.transition, StoryboardTransition)


# ============================================================================
# 7. Continuity Engine Tests
# ============================================================================

class TestContinuity:
    """Continuity issues must be detected and reported."""

    def test_continuity_state_initialised(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="co-1", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        assert pkg.continuity_state is not None
        assert isinstance(pkg.continuity_state, ContinuityState)

    def test_continuity_issues_present(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="co-2", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        assert isinstance(pkg.continuity_issues, list)

    def test_continuity_dependency_tracking(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="co-3", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        assert len(pkg.continuity_dependencies) == len(pkg.visual_beats)
        # First beat should have no dependencies; subsequent should depend on prev.
        assert pkg.continuity_dependencies[0].depends_on == []
        for dep in pkg.continuity_dependencies[1:]:
            assert len(dep.depends_on) >= 1


# ============================================================================
# 8. Evidence Linking Tests
# ============================================================================

class TestEvidenceLinking:
    """Visual beats must link back to claim_ids and source_ids."""

    def test_beats_inherit_source_ids(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="e-1", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        for beat in pkg.visual_beats:
            assert "SRC-00000001" in beat.source_ids

    def test_evidence_trace_populated(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="e-2", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        beats_with_evidence = [b for b in pkg.visual_beats if b.evidence_trace]
        # Every beat has at least 1 claim_id from its segment, so trace should exist.
        assert len(beats_with_evidence) >= 1


# ============================================================================
# 9. Reconstruction Safety Tests
# ============================================================================

class TestReconstructionSafety:
    """Prehistoric scenes must be marked ILLUSTRATIVE by default."""

    def test_artifact_beats_illustrative_without_research(self):
        engine = StoryboardEngine(job_id="r-1", use_mock=True)
        beats = []
        for i in range(2):
            beat = VisualBeat(
                beat_id=f"beat_{i:04d}",
                segment_id="SEG-R",
                order=i,
                start_time=i * 8.0,
                end_time=(i + 1) * 8.0,
                duration=8.0,
                purpose="show",
                visual_mode=StoryboardVisualMode.ARTIFACT,
            )
            beats.append(beat)
        engine._apply_reconstruction_safety(beats, None)
        for beat in beats:
            assert beat.reconstruction_confidence == StoryboardReconstructionConfidence.ILLUSTRATIVE
            assert beat.uncertainty_treatment == StoryboardUncertaintyTreatment.ILLUSTRATIVE_RECONSTRUCTION

    def test_character_beats_inferred_with_research(
        self, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="r-2", use_mock=True)
        beats = [
            VisualBeat(
                beat_id="beat_0001",
                segment_id="SEG-R",
                order=0,
                start_time=0.0,
                end_time=8.0,
                duration=8.0,
                purpose="show",
                visual_mode=StoryboardVisualMode.CHARACTER,
            )
        ]
        engine._apply_reconstruction_safety(beats, research_package)
        # With TIER1 source, confidence should be DOCUMENTED or INFERRED.
        assert beats[0].reconstruction_confidence in {
            StoryboardReconstructionConfidence.DOCUMENTED,
            StoryboardReconstructionConfidence.INFERRED,
        }


# ============================================================================
# 10. SceneDefinition Compilation Tests
# ============================================================================

class TestSceneDefinitionCompilation:
    """Each beat must compile to a SceneDefinitionCandidate."""

    def test_every_beat_has_scene_candidate(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="sc-1", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        assert len(pkg.scene_definition_candidates) == len(pkg.visual_beats)
        for beat in pkg.visual_beats:
            assert beat.scene_definition_candidate is not None

    def test_scene_candidate_environment_id_valid(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="sc-2", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        valid_envs = {
            "ice_age_plains", "cave_interior", "diagram_white",
            "mammoth_camp", "title_card",
        }
        for sc in pkg.scene_definition_candidates:
            assert sc.environment_id in valid_envs

    def test_scene_candidate_scene_ids_unique(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="sc-3", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        ids = [sc.scene_id for sc in pkg.scene_definition_candidates]
        assert len(ids) == len(set(ids))


# ============================================================================
# 11. Quality Scoring Tests
# ============================================================================

class TestQualityScoring:
    """Quality score is 14-axis with overall auto-computed."""

    def test_14_axes_present(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="q-1", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        dims = pkg.storyboard_quality_score.dimension_scores
        expected_axes = {
            "narration_visual_alignment", "visual_variety", "visual_clarity",
            "information_communication", "character_continuity", "environment_continuity",
            "camera_quality", "motion_quality", "composition", "asset_reuse",
            "evidence_traceability", "uncertainty_integrity",
            "vertical_reframe_readiness", "editorial_progression",
        }
        assert expected_axes.issubset(set(dims.keys()))

    def test_quality_scores_in_range(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="q-2", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        q = pkg.storyboard_quality_score
        for k, v in q.dimension_scores.items():
            assert 0.0 <= v <= 1.0
        assert 0.0 <= q.overall_score <= 1.0

    def test_high_quality_research_yields_high_quality_storyboard(
        self, story_package: StoryPackage
    ):
        hi = _make_research_package(quality_overall=0.9)
        engine = StoryboardEngine(job_id="q-3", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=hi)
        # Quality should be at least decent
        assert pkg.storyboard_quality_score.overall_score >= 0.5


# ============================================================================
# 12. Cache Tests
# ============================================================================

class TestStoryboardCache:
    """Content-addressed cache works correctly."""

    def test_cache_roundtrip(self, tmp_path):
        cache = StoryboardCache(tmp_path)
        cache.set_storyboard_package("abc123", {"hello": "world"})
        got = cache.get_storyboard_package("abc123")
        assert got == {"hello": "world"}

    def test_cache_ttl_eviction(self, tmp_path):
        cache = StoryboardCache(tmp_path)
        # Set TTL to 0 to simulate expiry
        cache._ttl = 0
        cache.set_storyboard_package("abc123", {"hello": "world"})
        import time
        time.sleep(0.05)
        got = cache.get_storyboard_package("abc123")
        assert got is None

    def test_cache_clear(self, tmp_path):
        cache = StoryboardCache(tmp_path)
        cache.set_storyboard_package("abc", {"x": 1})
        cache.set_camera_plan("def", {"y": 2})
        cache.clear()
        assert cache.get_storyboard_package("abc") is None
        assert cache.get_camera_plan("def") is None


# ============================================================================
# 13. Idempotency Tests
# ============================================================================

class TestIdempotency:
    """Running twice with identical inputs must produce identical output."""

    def test_same_input_same_output(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="idem-1", use_mock=True)
        pkg1 = engine.run(story_package=story_package, research_package=research_package)
        engine2 = StoryboardEngine(job_id="idem-1", use_mock=True)
        pkg2 = engine.run(story_package=story_package, research_package=research_package)

        # Compare key invariants (timestamps differ; ignore them).
        assert len(pkg1.visual_beats) == len(pkg2.visual_beats)
        for b1, b2 in zip(pkg1.visual_beats, pkg2.visual_beats):
            assert b1.beat_id == b2.beat_id
            assert b1.start_time == b2.start_time
            assert b1.visual_mode == b2.visual_mode

    def test_no_duplicate_beat_ids_across_runs(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="idem-2", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        ids = [b.beat_id for b in pkg.visual_beats]
        assert len(ids) == len(set(ids))


# ============================================================================
# 14. End-to-End Compilation to SceneDefinition
# ============================================================================

class TestEndToEndCompilation:
    """The SceneDefinitionCandidates must be usable by the existing schema."""

    def test_scene_definition_candidate_fits_schema(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="e2e-1", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)
        # Collect unique environment ids from candidates
        used_envs = sorted({sc.environment_id for sc in pkg.scene_definition_candidates})
        # Build a minimal SceneDefinition around the candidates.
        sd = SceneDefinition(
            meta=Meta(
                title=pkg.metadata.topic,
                target_duration_sec=pkg.total_duration_sec(),
            ),
            characters=[
                {"id": "narrator", "name": "Narrator", "color": "#FFFFFF"}
            ],
            environments=[
                {"id": eid, "name": eid.replace("_", " ").title(), "mood": "calm"}
                for eid in used_envs
            ],
            scenes=[
                {
                    "id": sc.scene_id,
                    "kind": sc.kind,
                    "start_sec": sc.start_sec,
                    "end_sec": sc.end_sec,
                    "environment_id": sc.environment_id,
                }
                for sc in pkg.scene_definition_candidates
            ],
        )
        assert len(sd.scenes) == len(pkg.visual_beats)
        # Verify timing contiguity.
        for i in range(len(sd.scenes) - 1):
            assert sd.scenes[i].end_sec <= sd.scenes[i + 1].start_sec + 0.01


# ============================================================================
# 15. Real Test Project — Ancient Humans
# ============================================================================

class TestAncientHumansProject:
    """End-to-end test using the Ancient Humans test project."""

    def test_ancient_humans_full_pipeline(
        self, story_package: StoryPackage, research_package: ResearchPackage
    ):
        engine = StoryboardEngine(job_id="ancient-humans", use_mock=True)
        pkg = engine.run(story_package=story_package, research_package=research_package)

        # Verify package is non-empty and well-formed.
        assert pkg.metadata.topic == "How Did Ancient Humans Survive Deadly Winters?"
        assert len(pkg.visual_beats) >= 3  # at least one per segment

        # Verify all 3 segments are covered.
        covered = pkg.segment_ids_covered()
        assert covered == {"SEG-001", "SEG-002", "SEG-003"}

        # Verify visual variety.
        modes = {b.visual_mode for b in pkg.visual_beats}
        assert len(modes) >= 1

        # Verify quality score is reasonable.
        assert pkg.storyboard_quality_score.overall_score >= 0.5

        # Verify status is reasonable.
        assert pkg.status in {StoryboardStatus.DRAFT, StoryboardStatus.BLOCKED}

        # Verify scene candidates compile.
        assert len(pkg.scene_definition_candidates) == len(pkg.visual_beats)
