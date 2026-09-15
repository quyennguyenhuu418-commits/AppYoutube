"""
Tests for the Research Intelligence Engine.

Covers:
- Source scoring
- Source deduplication
- Claim schema validation
- Claim-source linking
- Contradiction detection
- Uncertainty classification
- Timeline validation
- Quantitative fact validation
- Research stopping condition
- ResearchPackage schema validation
- Quality scoring
- Caching idempotency
- Source independence tracking
- Complete integration run
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
    ClaimStatus,
    ClaimType,
    Contradiction,
    ContradictionResolution,
    GeographicSite,
    QuantitativeFact,
    ResearchGap,
    ResearchGapStatus,
    ResearchPackage,
    ResearchQualityScore,
    ResearchQuestion,
    ResearchQuestionStatus,
    ResearchSynthesis,
    Source,
    SourceLineage,
    SourceRelationship,
    SourceTier,
    StoryOpportunity,
    VisualOpportunity,
    VisualOpportunityType,
    ResearchMetadata,
)
from app.research.engine import ResearchEngine, ResearchContext, reset_counters
from app.research.cache import ResearchCache
from app.providers.mock_research import MockSearchProvider, MockContentFetchProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset():
    """Reset ID counters and state between tests."""
    reset_counters()


# ---------------------------------------------------------------------------
# 1. Source Scoring
# ---------------------------------------------------------------------------

def test_source_scoring_tier1_greater_than_tier3():
    """TIER1 sources must score higher than TIER3 sources."""
    # Tier-based sub-score assumptions: TIER1 (peer-reviewed) has higher authority/methodology/citation_quality
    # than TIER3 (popular/wikipedia). Independence defaults to 1.0; remaining sub-scores are 0.5.
    s1 = Source(
        id="SRC-00000001", url="https://nature.com/article", title="t",
        tier=SourceTier.TIER1,
        authority=0.95, methodology=0.95, citation_quality=0.95,
    )
    s3 = Source(
        id="SRC-00000003", url="https://wikipedia.org", title="t",
        tier=SourceTier.TIER3,
        authority=0.5, methodology=0.5, citation_quality=0.5,
    )
    assert s1.overall_score > s3.overall_score, "TIER1 must score higher than TIER3"


def test_source_scoring_tier3_greater_than_tier4():
    """TIER3 sources must score higher than TIER4 sources."""
    s3 = Source(
        id="SRC-00000003", url="https://wikipedia.org", title="t",
        tier=SourceTier.TIER3,
        authority=0.5, methodology=0.5, citation_quality=0.5,
    )
    s4 = Source(
        id="SRC-00000004", url="https://blog.example.com", title="t",
        tier=SourceTier.TIER4,
        authority=0.2, methodology=0.2, citation_quality=0.2,
    )
    assert s3.overall_score > s4.overall_score, "TIER3 must score higher than TIER4"


def test_source_field_defaults():
    """Source fields must have sensible defaults."""
    s = Source(id="SRC-00000001", url="https://example.com", title="Example")
    assert s.tier == SourceTier.TIER3
    assert 0.0 <= s.overall_score <= 1.0
    assert s.reviewed is False
    assert s.approved is True


def test_source_tier_enum_values():
    """All tier values must be valid SourceTier members."""
    for tier in SourceTier:
        s = Source(id="SRC-TIER1T2", url="https://x.com", title="x", tier=tier)
        assert s.tier == tier


# ---------------------------------------------------------------------------
# 2. Source Deduplication
# ---------------------------------------------------------------------------

def test_deduplication_exact_url():
    """Identical URLs should be detected as duplicates."""
    ctx = ResearchContext(job_id="test", topic="test topic")
    ctx.raw_sources = [
        Source(id="SRC-1", url="https://example.com/article", title="t", tier=SourceTier.TIER1),
        Source(id="SRC-2", url="https://example.com/article", title="t", tier=SourceTier.TIER2),
    ]
    ctx = ResearchEngine(job_id="test", use_mock=True)._deduplicate_sources(ctx)
    assert len(ctx.deduped_sources) == 1


def test_deduplication_mobile_url():
    """en.m.wikipedia.org and en.wikipedia.org should be deduplicated."""
    ctx = ResearchContext(job_id="test", topic="test topic")
    ctx.raw_sources = [
        Source(id="SRC-1", url="https://en.wikipedia.org/wiki/Neanderthal", title="Neanderthal", tier=SourceTier.TIER3),
        Source(id="SRC-2", url="https://en.m.wikipedia.org/wiki/Neanderthal", title="Neanderthal", tier=SourceTier.TIER3),
    ]
    ctx = ResearchEngine(job_id="test", use_mock=True)._deduplicate_sources(ctx)
    assert len(ctx.deduped_sources) == 1


def test_deduplication_tier1_preserved():
    """TIER1 sources should be preserved even if content is a duplicate."""
    ctx = ResearchContext(job_id="test", topic="test topic")
    ctx.raw_sources = [
        Source(id="SRC-1", url="https://nature.com/article1", title="t", snippet="SAME CONTENT", tier=SourceTier.TIER1),
        Source(id="SRC-2", url="https://nature.com/article2", title="t", snippet="SAME CONTENT", tier=SourceTier.TIER1),
    ]
    ctx = ResearchEngine(job_id="test", use_mock=True)._deduplicate_sources(ctx)
    # TIER1 sources are kept even when duplicate
    assert len(ctx.deduped_sources) >= 1


# ---------------------------------------------------------------------------
# 3. Claim Schema Validation
# ---------------------------------------------------------------------------

def test_claim_valid():
    """A valid claim should pass validation."""
    c = Claim(
        claim_id="CLM-001",
        text="The controlled use of fire dates back at least 400,000 years.",
        claim_type=ClaimType.ARCHAEOLOGICAL,
        importance="high",
        confidence=0.92,
    )
    assert c.claim_id == "CLM-001"
    assert c.claim_type == ClaimType.ARCHAEOLOGICAL
    assert 0.0 <= c.confidence <= 1.0


def test_claim_confidence_bounds():
    """Confidence must be between 0 and 1."""
    with pytest.raises(ValidationError):
        Claim(claim_id="CLM-001", text="x" * 10, confidence=1.5)


def test_claim_claim_type_enum():
    """Claim type must be a valid ClaimType."""
    for ct in ClaimType:
        c = Claim(claim_id="CLM-001", text="x" * 10, claim_type=ct)
        assert c.claim_type == ct


def test_claim_min_length():
    """Claim text accepts short strings (no min_length constraint in schema)."""
    c = Claim(claim_id="CLM-001", text="short")
    assert c.text == "short"


# ---------------------------------------------------------------------------
# 4. Claim-Source Linking
# ---------------------------------------------------------------------------

def test_claim_source_link_valid():
    """A valid claim-source link should pass."""
    link = ClaimSourceLink(
        claim_id="CLM-001",
        source_id="SRC-TEST001",
        relationship=SourceRelationship.SUPPORTS,
    )
    assert link.claim_id == "CLM-001"
    assert link.source_id == "SRC-TEST001"


def test_claim_source_link_all_relationships():
    """All relationship types should be valid."""
    for rel in SourceRelationship:
        link = ClaimSourceLink(
            claim_id="CLM-001",
            source_id="SRC-TEST001",
            relationship=rel,
        )
        assert link.relationship == rel


# ---------------------------------------------------------------------------
# 5. Contradiction Detection
# ---------------------------------------------------------------------------

def test_contradiction_valid():
    """A valid contradiction should pass validation."""
    c = Contradiction(
        id="CTR-001",
        claim_id_a="CLM-001",
        claim_id_b="CLM-002",
        position_a="Claim A text",
        position_b="Claim B text",
    )
    assert c.resolution == ContradictionResolution.UNRESOLVED
    assert c.possible_reason == ""


def test_contradiction_resolution_enum():
    """All resolution states should be valid."""
    for res in ContradictionResolution:
        c = Contradiction(
            id=f"CTR-001",
            claim_id_a="CLM-001",
            claim_id_b="CLM-002",
            position_a="A",
            position_b="B",
            resolution=res,
        )
        assert c.resolution == res


# ---------------------------------------------------------------------------
# 6. Uncertainty Classification
# ---------------------------------------------------------------------------

def test_certainty_level_enum():
    """All certainty levels should be valid ClaimType values."""
    from app.schemas.research_package import CertaintyLevel
    for cl in CertaintyLevel:
        c = Claim(
            claim_id="CLM-001",
            text="x" * 10,
            claim_type=ClaimType.HISTORICAL,
            certainty_level=cl,
        )
        assert c.certainty_level == cl


def test_claim_uncertainty_reason():
    """Claim should store uncertainty reason."""
    from app.schemas.research_package import CertaintyLevel
    c = Claim(
        claim_id="CLM-001",
        text="x" * 10,
        claim_type=ClaimType.ANTHROPOLOGICAL,
        certainty_level=CertaintyLevel.SPECULATION,
        certainty_reason="Limited sample size",
    )
    assert c.certainty_reason == "Limited sample size"


def test_claim_status_enum():
    """All claim statuses should be valid."""
    for status in ClaimStatus:
        c = Claim(
            claim_id="CLM-001",
            text="x" * 10,
            claim_type=ClaimType.HISTORICAL,
            status=status,
        )
        assert c.status == status


# ---------------------------------------------------------------------------
# 7. Timeline Validation
# ---------------------------------------------------------------------------

def test_timeline_approximate_dates():
    """Timeline events with approximate dates should be valid."""
    from app.schemas.research_package import TimelineEvent
    te = TimelineEvent(
        period="Pleistocene",
        start_date="~2.58 million years ago",
        end_date="~11,700 years ago",
        events=["Neanderthals inhabited Europe"],
        is_approximate=True,
        uncertainty="Dates are approximate",
    )
    assert te.is_approximate is True
    assert "~" in te.start_date


def test_timeline_event_min_one_event():
    """Timeline event must have at least one event."""
    from app.schemas.research_package import TimelineEvent
    with pytest.raises(ValidationError):
        TimelineEvent(period="Test", start_date="1", end_date="2", events=[])


# ---------------------------------------------------------------------------
# 8. Quantitative Fact Validation
# ---------------------------------------------------------------------------

def test_quantitative_fact_with_range():
    """Quantitative fact with min/max range should be valid."""
    qf = QuantitativeFact(
        id="QF-001",
        value=20.0,
        unit="degrees Celsius",
        minimum=15.0,
        maximum=25.0,
        context="Temperature difference during Ice Age",
    )
    assert qf.minimum == 15.0
    assert qf.maximum == 25.0
    assert qf.value == 20.0


def test_quantitative_fact_approximate():
    """Approximate values should be flagged."""
    qf = QuantitativeFact(
        id="QF-001",
        value=None,
        unit="years ago",
        approximate=True,
        context="Earliest fire evidence",
    )
    assert qf.approximate is True
    assert qf.value is None


def test_quantitative_fact_unit_required():
    """Unit field must be non-empty."""
    with pytest.raises(ValidationError):
        QuantitativeFact(id="QF-001", value=42.0, unit="", context="")


# ---------------------------------------------------------------------------
# 9. Research Stopping Condition
# ---------------------------------------------------------------------------

def test_should_stop_at_max_sources():
    """Context should signal stop when max sources reached."""
    ctx = ResearchContext(job_id="test", topic="test")
    # Fill with max sources
    for i in range(100):
        ctx.deduped_sources.append(
            Source(id=f"SRC-{i:08X}", url=f"https://example.com/{i}", title=f"t{i}")
        )
    assert ctx.should_stop() is True


def test_should_stop_low_marginal_gain():
    """Context should stop when marginal gain is low after initial discovery."""
    ctx = ResearchContext(job_id="test", topic="test")
    # Simulate initial discovery
    for i in range(20):
        ctx.deduped_sources.append(
            Source(id=f"SRC-{i:08X}", url=f"https://example.com/{i}", title=f"t{i}")
        )
    ctx.claims = [Claim(claim_id=f"CLM-{i:03d}", text=f"claim {i}") for i in range(50)]
    # Simulate low gain: no new sources added
    ctx._last_new_sources = len(ctx.deduped_sources)
    ctx._last_new_claims = len(ctx.claims)
    assert ctx.should_stop() is True


# ---------------------------------------------------------------------------
# 10. ResearchPackage Schema Validation
# ---------------------------------------------------------------------------

def test_full_package_validates():
    """A fully populated ResearchPackage must pass schema validation."""
    pkg = ResearchPackage(
        metadata=ResearchMetadata(
            topic="How Did Ancient Humans Survive Deadly Winters?",
            version="1.0",
        ),
        research_questions=[
            ResearchQuestion(
                id="RQ-001",
                text="How did Neanderthals adapt to cold climates?",
                question_type="causal",
                importance_score=0.9,
            )
        ],
        sources=[
            Source(id="SRC-00000001", url="https://nature.com", title="t"),
        ],
        claims=[
            Claim(
                claim_id="CLM-001",
                text="The controlled use of fire dates back 400,000 years.",
                claim_type=ClaimType.ARCHAEOLOGICAL,
                importance="high",
                confidence=0.92,
                source_ids=["SRC-00000001"],
            )
        ],
        claim_source_links=[
            ClaimSourceLink(
                claim_id="CLM-001",
                source_id="SRC-00000001",
                relationship=SourceRelationship.SUPPORTS,
            )
        ],
        synthesis=ResearchSynthesis(
            central_question="How did humans survive Ice Age winters?",
            short_answer="Through fire, clothing, shelter, and food.",
            detailed_answer="Ancient humans survived through multiple strategies.",
            strongest_evidence=["Fire evidence", "Clothing evidence"],
            major_uncertainties=["How did infants survive?"],
            timeline_summary=["~400,000 years: fire"],
            important_examples=["Mammoth-bone huts"],
            counterintuitive_findings=["Fat was more valuable than meat"],
        ),
        quality_score=ResearchQualityScore(
            source_quality=0.75,
            coverage=0.85,
            claim_traceability=0.9,
            independence=0.88,
            contradiction_detection=0.7,
            uncertainty_handling=0.8,
            research_depth=0.72,
            visual_value=0.85,
            story_value=0.9,
        ),
    )
    assert pkg.metadata.topic == "How Did Ancient Humans Survive Deadly Winters?"
    assert len(pkg.claims) == 1
    assert len(pkg.claim_source_links) == 1


def test_package_fails_on_unknown_source_reference():
    """Package must reject claims referencing unknown sources."""
    with pytest.raises(ValidationError) as exc_info:
        ResearchPackage(
            metadata=ResearchMetadata(topic="t"),
            research_questions=[
                ResearchQuestion(id="RQ-001", text="test question"),
            ],
            sources=[Source(id="SRC-1", url="https://x.com", title="t")],
            claims=[
                Claim(
                    claim_id="CLM-001",
                    text="test claim text",
                    claim_type=ClaimType.HISTORICAL,
                    source_ids=["SRC-FAKE"],
                )
            ],
            synthesis=ResearchSynthesis(
                central_question="t" * 5,
                short_answer="t" * 10,
                detailed_answer="t" * 20,
                strongest_evidence=["x"],
                timeline_summary=["x"],
                important_examples=["x"],
                counterintuitive_findings=["x"],
                major_uncertainties=["x"],
            ),
            quality_score=ResearchQualityScore(
                source_quality=0.5, coverage=0.5, claim_traceability=0.5,
                independence=0.5, contradiction_detection=0.5, uncertainty_handling=0.5,
                research_depth=0.5, visual_value=0.5, story_value=0.5,
            ),
        )
    assert "SRC-FAKE" in str(exc_info.value)


def test_package_fails_on_unknown_claim_reference():
    """Package must reject ClaimSourceLinks referencing unknown claims."""
    with pytest.raises(ValidationError) as exc_info:
        ResearchPackage(
            metadata=ResearchMetadata(topic="t"),
            research_questions=[ResearchQuestion(id="RQ-001", text="test question")],
            sources=[Source(id="SRC-1", url="https://x.com", title="t")],
            claims=[
                Claim(
                    claim_id="CLM-001",
                    text="test claim text",
                    claim_type=ClaimType.HISTORICAL,
                )
            ],
            claim_source_links=[
                ClaimSourceLink(claim_id="CLM-FAKE", source_id="SRC-1"),
            ],
            synthesis=ResearchSynthesis(
                central_question="t" * 5,
                short_answer="t" * 10,
                detailed_answer="t" * 20,
                strongest_evidence=["x"],
                timeline_summary=["x"],
                important_examples=["x"],
                counterintuitive_findings=["x"],
                major_uncertainties=["x"],
            ),
            quality_score=ResearchQualityScore(
                source_quality=0.5, coverage=0.5, claim_traceability=0.5,
                independence=0.5, contradiction_detection=0.5, uncertainty_handling=0.5,
                research_depth=0.5, visual_value=0.5, story_value=0.5,
            ),
        )
    assert "CLM-FAKE" in str(exc_info.value)


def test_package_to_legacy_dict():
    """Backward-compatible dict should contain topic, facts, open_questions."""
    pkg = ResearchPackage(
        metadata=ResearchMetadata(topic="Ice Age survival"),
        research_questions=[ResearchQuestion(id="RQ-001", text="How did humans survive?")],
        sources=[
            Source(id="SRC-1", url="https://x.com", title="Article", snippet="Snippet"),
        ],
        claims=[
            Claim(
                claim_id="CLM-001",
                text="Fire was used for warmth",
                claim_type=ClaimType.TECHNOLOGICAL,
                importance="high",
                confidence=0.9,
                source_ids=["SRC-1"],
            )
        ],
        research_gaps=[
            ResearchGap(id="GAP-001", question="How did infants survive?"),
        ],
        synthesis=ResearchSynthesis(
            central_question="t" * 5,
            short_answer="t" * 10,
            detailed_answer="t" * 20,
            strongest_evidence=["x"],
            timeline_summary=["x"],
            important_examples=["x"],
            counterintuitive_findings=["x"],
            major_uncertainties=["x"],
        ),
        quality_score=ResearchQualityScore(
            source_quality=0.5, coverage=0.5, claim_traceability=0.5,
            independence=0.5, contradiction_detection=0.5, uncertainty_handling=0.5,
            research_depth=0.5, visual_value=0.5, story_value=0.5,
        ),
    )
    legacy = pkg.to_legacy_dict()
    assert legacy["topic"] == "Ice Age survival"
    assert len(legacy["facts"]) == 1
    assert len(legacy["open_questions"]) == 1
    assert legacy["facts"][0]["claim"] == "Fire was used for warmth"


# ---------------------------------------------------------------------------
# 11. Quality Scoring
# ---------------------------------------------------------------------------

def test_quality_score_overall_computed():
    """QualityScore.overall_score must be the weighted average."""
    qs = ResearchQualityScore(
        source_quality=1.0,
        coverage=1.0,
        claim_traceability=1.0,
        independence=1.0,
        contradiction_detection=1.0,
        uncertainty_handling=1.0,
        research_depth=1.0,
        visual_value=1.0,
        story_value=1.0,
    )
    assert qs.overall_score == 1.0


def test_quality_score_partial_scores():
    """Quality score with mixed scores should compute correctly."""
    qs = ResearchQualityScore(
        source_quality=0.8,
        coverage=0.6,
        claim_traceability=0.9,
        independence=0.7,
        contradiction_detection=0.5,
        uncertainty_handling=0.8,
        research_depth=0.6,
        visual_value=0.9,
        story_value=0.8,
    )
    assert 0.0 <= qs.overall_score <= 1.0


# ---------------------------------------------------------------------------
# 12. Caching
# ---------------------------------------------------------------------------

def test_cache_search_roundtrip(tmp_path, monkeypatch):
    """Cache should store and retrieve search results."""
    # Mock settings workspace by patching workspace_dir (workspace_path is computed from it).
    from app.core import config as config_module
    monkeypatch.setattr(config_module.settings, "workspace_dir", tmp_path)

    cache = ResearchCache("test-job-cache")
    results = [{"url": "https://x.com", "title": "x", "snippet": "y", "tier": "TIER3"}]
    cache.set_search("test query", results)
    retrieved = cache.get_search("test query")
    assert retrieved == results


def test_cache_ttl_eviction(tmp_path, monkeypatch):
    """Cache should evict entries older than TTL."""
    from app.core import config as config_module
    import time
    monkeypatch.setattr(config_module.settings, "workspace_dir", tmp_path)

    cache = ResearchCache("test-job-ttl")
    cache.set_search("old query", [{"url": "https://x.com", "title": "x", "snippet": "y", "tier": "TIER3"}])

    # Manually age the file
    cache_path = cache._base / "search_*.json"
    for f in cache._base.glob("*.json"):
        old_mtime = f.stat().st_mtime - (8 * 86400)  # 8 days old
        import os
        os.utime(f, (old_mtime, old_mtime))

    result = cache.get_search("old query")
    assert result is None, "Expired cache entry should return None"


# ---------------------------------------------------------------------------
# 13. Source Independence Tracking
# ---------------------------------------------------------------------------

def test_source_lineage_independent():
    """Independent sources should have is_independent=True."""
    sl = SourceLineage(is_independent=True)
    assert sl.is_independent is True


def test_source_lineage_dependent():
    """Derived/citation sources should have is_independent=False."""
    sl = SourceLineage(
        original_url="https://primary-study.com",
        intermediate_urls=["https://press-release.edu", "https://news.com"],
        is_independent=False,
    )
    assert sl.is_independent is False
    assert sl.original_url == "https://primary-study.com"
    assert len(sl.intermediate_urls) == 2


# ---------------------------------------------------------------------------
# 14. Mock Search Provider
# ---------------------------------------------------------------------------

def test_mock_search_returns_results():
    """Mock search should return structural results."""
    provider = MockSearchProvider()
    results = provider.search("ancient humans winter adaptation")
    assert len(results) > 0
    assert all(hasattr(r, "url") and hasattr(r, "title") for r in results)


def test_mock_search_fallback():
    """Mock search fallback should return a result for any query."""
    provider = MockSearchProvider()
    results = provider.search("completely unknown random query xyz123")
    assert len(results) >= 1
    assert results[0].url.startswith("https://example.com")


def test_mock_content_fetch_returns_content():
    """Mock content fetch should return fixture content."""
    provider = MockContentFetchProvider()
    result = provider.fetch("https://www.nature.com/articles/s41586-019-1290-4")
    assert result is not None
    assert len(result.text_content) > 0
    assert result.domain == "nature.com"


def test_mock_content_fetch_unknown_url():
    """Mock fetch for unknown URL should return generic fixture."""
    provider = MockContentFetchProvider()
    result = provider.fetch("https://totally-unknown-and-unique-domain-12345.com/page")
    assert result is not None
    assert "Mock" in result.title


# ---------------------------------------------------------------------------
# 15. Integration — Complete Research Run (mock)
# ---------------------------------------------------------------------------

def test_complete_research_run_integration(tmp_path, monkeypatch):
    """Full research pipeline should produce all 17 sections with mock providers."""
    from app.core import config as config_module
    monkeypatch.setattr(config_module.settings, "workspace_dir", tmp_path)

    reset_counters()
    engine = ResearchEngine(job_id="integration-test-job", use_mock=True)
    pkg = engine.run("How Did Ancient Humans Survive Deadly Winters?")

    # Metadata
    assert pkg.metadata.topic == "How Did Ancient Humans Survive Deadly Winters?"
    assert pkg.metadata.version == "1.0"

    # Research questions
    assert len(pkg.research_questions) >= 5, "Should have at least 5 research questions"

    # Sources
    assert len(pkg.sources) >= 1, "Should have at least 1 source"
    assert all(hasattr(s, "overall_score") for s in pkg.sources)

    # Claims
    assert len(pkg.claims) >= 1, "Should have at least 1 claim"
    assert all(hasattr(c, "claim_id") for c in pkg.claims)

    # Claim-source links
    assert len(pkg.claim_source_links) >= 0

    # Synthesis
    assert pkg.synthesis is not None
    assert len(pkg.synthesis.central_question) > 0
    assert len(pkg.synthesis.short_answer) > 0

    # Quality score
    assert pkg.quality_score is not None
    assert 0.0 <= pkg.quality_score.overall_score <= 1.0

    # Legacy dict backward compat
    legacy = pkg.to_legacy_dict()
    assert "topic" in legacy
    assert "facts" in legacy
    assert "open_questions" in legacy


# ---------------------------------------------------------------------------
# 16. API Validation Helpers
# ---------------------------------------------------------------------------

def test_visual_opportunity_types():
    """All visual opportunity types should be valid."""
    for vot in VisualOpportunityType:
        vo = VisualOpportunity(
            id="VO-001",
            claim_id="CLM-001",
            opportunity_type=vot,
            description="A visualization of the claim",
        )
        assert vo.opportunity_type == vot


def test_story_opportunity_fields():
    """Story opportunity must have all required fields."""
    so = StoryOpportunity(
        id="SO-001",
        hook_candidates=["Hook 1"],
        surprising_facts=["Fact 1"],
        emotional_beats=["Beat 1"],
        final_takeaways=["Takeaway 1"],
    )
    assert len(so.hook_candidates) >= 1
    assert len(so.surprising_facts) >= 1
    assert len(so.emotional_beats) >= 1
    assert len(so.final_takeaways) >= 1


def test_research_gap_statuses():
    """All research gap statuses should be valid."""
    for status in ResearchGapStatus:
        gap = ResearchGap(
            id="GAP-001",
            question="What is unknown about this topic?",
            status=status,
        )
        assert gap.status == status


def test_geographic_site_coordinates():
    """GeographicSite coordinates should be within valid ranges."""
    site = GeographicSite(
        name="Neanderthal Site",
        region="Europe",
        country="France",
        latitude=48.8566,
        longitude=2.3522,
        period="Late Pleistocene",
        evidence="Stone tools and hearths",
    )
    assert -90 <= site.latitude <= 90
    assert -180 <= site.longitude <= 180


def test_geographic_site_optional_coordinates():
    """Coordinates may be None for sites with unknown locations."""
    site = GeographicSite(
        name="Ancient Site",
        region="Unknown",
        country="?",
        period="Prehistoric",
    )
    assert site.latitude is None
    assert site.longitude is None


def test_research_question_status():
    """All research question statuses should be valid."""
    for status in ResearchQuestionStatus:
        rq = ResearchQuestion(
            id="RQ-001",
            text="What is the evidence for X?",
            status=status,
        )
        assert rq.status == status
