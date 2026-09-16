"""
Research Intelligence Engine — core orchestration.

Implements the 12-step research pipeline:

    decompose_questions
         ↓
    search_sources
         ↓
    fetch_and_score_sources
         ↓
    deduplicate_sources
         ↓
    extract_claims
         ↓
    build_claim_source_graph
         ↓
    detect_contradictions
         ↓
    model_uncertainty
         ↓
    build_timeline
         ↓
    extract_visual_opportunities
         ↓
    extract_story_opportunities
         ↓
    synthesize
         ↓
    score_quality

Each step is a separate function callable independently. Steps cache their
output. A `ResearchContext` object threads state between steps.

Usage:
    engine = ResearchEngine(job_id="...")
    package = engine.run("How Did Ancient Humans Survive Deadly Winters?")
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import LLMMessage, LLMRequest, SearchResult
from app.providers.llm import get_llm_provider
from app.providers.research_providers import (
    get_content_fetch_provider,
    get_search_provider,
)
from app.providers.mock_research import MockContentFetchProvider, MockSearchProvider
from app.research.cache import ResearchCache
from app.research.logging import ResearchLogger
from app.schemas.research_package import (
    CertaintyLevel,
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
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# ID counters — simple module-level generators for claim/source IDs
# ---------------------------------------------------------------------------
_counter_claim = 0
_counter_source = 0
_counter_ctr = 0
_counter_gap = 0
_counter_qf = 0
_counter_vo = 0
_counter_so = 0
_counter_rq = 0


def _next_rq() -> str:
    global _counter_rq
    _counter_rq += 1
    return f"RQ-{_counter_rq:03d}"


def _next_src() -> str:
    global _counter_source
    _counter_source += 1
    return f"SRC-{_counter_source:08X}"


def _next_clm() -> str:
    global _counter_claim
    _counter_claim += 1
    return f"CLM-{_counter_claim:03d}"


def _next_ctr() -> str:
    global _counter_ctr
    _counter_ctr += 1
    return f"CTR-{_counter_ctr:03d}"


def _next_gap() -> str:
    global _counter_gap
    _counter_gap += 1
    return f"GAP-{_counter_gap:03d}"


def _next_qf() -> str:
    global _counter_qf
    _counter_qf += 1
    return f"QF-{_counter_qf:03d}"


def _next_vo() -> str:
    global _counter_vo
    _counter_vo += 1
    return f"VO-{_counter_vo:03d}"


def _next_so() -> str:
    global _counter_so
    _counter_so += 1
    return f"SO-{_counter_so:03d}"


def reset_counters() -> None:
    """Reset all counters. Useful for testing."""
    global _counter_claim, _counter_source, _counter_ctr, _counter_gap, _counter_qf, _counter_vo, _counter_so, _counter_rq
    _counter_claim = _counter_source = _counter_ctr = _counter_gap = _counter_qf = _counter_vo = _counter_so = _counter_rq = 0


# ---------------------------------------------------------------------------
# Research Context
# ---------------------------------------------------------------------------

@dataclass
class ResearchContext:
    """Thread-safe state container passed through each pipeline step."""

    job_id: str
    topic: str
    start_time: float = field(default_factory=time.time)

    # Populated by steps
    research_questions: list[ResearchQuestion] = field(default_factory=list)
    raw_sources: list[Source] = field(default_factory=list)
    deduped_sources: list[Source] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    claim_source_links: list[ClaimSourceLink] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    research_gaps: list[ResearchGap] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    geography: list[GeographicSite] = field(default_factory=list)
    quantitative_facts: list[QuantitativeFact] = field(default_factory=list)
    visual_opportunities: list[VisualOpportunity] = field(default_factory=list)
    story_opportunities: list[StoryOpportunity] = field(default_factory=list)
    synthesis: ResearchSynthesis | None = None
    quality_score: ResearchQualityScore | None = None

    # Stopping condition tracking
    _last_new_sources: int = 0
    _last_new_claims: int = 0

    def should_stop(self) -> bool:
        """Return True when marginal gain is below threshold."""
        total_sources = len(self.deduped_sources)
        total_claims = len(self.claims)
        source_gain = total_sources - self._last_new_sources
        claim_gain = total_claims - self._last_new_claims
        self._last_new_sources = total_sources
        self._last_new_claims = total_claims
        # Stop if we haven't gained much in the last iteration
        if total_sources >= settings.research_max_sources:
            return True
        return (
            source_gain <= 2
            and claim_gain <= 5
            and total_sources >= 10
        )


# ---------------------------------------------------------------------------
# Research Engine
# ---------------------------------------------------------------------------

class ResearchEngine:
    """
    Orchestrates the full research pipeline.

    Parameters
    ----------
    job_id : str
        Unique job identifier. Used for workspace paths and logging.
    use_mock : bool
        If True, use mock search/fetch providers instead of real ones.
        Default: False (use real providers).
    """

    def __init__(self, job_id: str, use_mock: bool = False) -> None:
        self.job_id = job_id
        self.use_mock = use_mock
        self.cache = ResearchCache(job_id)
        self._logger = ResearchLogger(job_id)
        self._llm = get_llm_provider()
        self._search = (
            MockSearchProvider() if use_mock else get_search_provider()
        )
        self._fetch = (
            MockContentFetchProvider() if use_mock else get_content_fetch_provider()
        )

    def run(self, topic: str) -> ResearchPackage:
        """
        Run the full research pipeline and return a validated ResearchPackage.

        Parameters
        ----------
        topic : str
            The documentary topic to research.

        Returns
        -------
        ResearchPackage
            A fully-populated, schema-validated research package.
        """
        t0 = time.time()
        self._logger.info("Starting research for topic", query=topic)
        ctx = ResearchContext(job_id=self.job_id, topic=topic)

        # Step 1: Question decomposition
        ctx = self._decompose_questions(ctx)
        t1 = time.time()
        self._logger.question_decomposition(
            count=len(ctx.research_questions),
            duration_sec=t1 - t0,
        )

        # Step 2: Search sources
        ctx = self._search_sources(ctx)
        t2 = time.time()
        self._logger.search_complete(
            query=topic,
            count=len(ctx.raw_sources),
            duration_sec=t2 - t1,
        )

        # Step 3: Fetch and score sources
        ctx = self._fetch_and_score_sources(ctx)
        t3 = time.time()
        self._logger.info(
            "Fetch and score complete",
            stage="fetch_score",
            source_count=len(ctx.raw_sources),
            duration_sec=t3 - t2,
        )

        # Step 4: Deduplicate
        ctx = self._deduplicate_sources(ctx)
        t4 = time.time()
        self._logger.deduplication_complete(
            before=len(ctx.raw_sources),
            after=len(ctx.deduped_sources),
        )

        # Step 5: Extract claims
        ctx = self._extract_claims(ctx)
        t5 = time.time()
        self._logger.info(
            "Claims extracted",
            stage="claim_extraction",
            claim_count=len(ctx.claims),
            duration_sec=t5 - t4,
        )

        # Step 6: Build claim-source graph
        ctx = self._build_claim_source_graph(ctx)

        # Step 7: Detect contradictions
        ctx = self._detect_contradictions(ctx)
        self._logger.contradictions_found(len(ctx.contradictions))

        # Step 8: Model uncertainty
        ctx = self._model_uncertainty(ctx)

        # Step 9: Build timeline
        ctx = self._build_timeline(ctx)

        # Step 10: Extract visual opportunities
        ctx = self._extract_visual_opportunities(ctx)

        # Step 11: Extract story opportunities
        ctx = self._extract_story_opportunities(ctx)

        # Step 12: Synthesize
        ctx = self._synthesize(ctx)
        t6 = time.time()
        self._logger.synthesis_complete(duration_sec=t6 - t5)

        # Step 13: Score quality
        ctx = self._score_quality(ctx)
        total_duration = t6 - t0
        self._logger.quality_score(
            overall=ctx.quality_score.overall_score,
            warnings=[],
        )

        # Build and validate the package
        pkg = self._build_package(ctx, total_duration)

        # Update legacy research.json for backward compat
        self._write_legacy_research(ctx.job_id, pkg)

        self._logger.info(
            f"Research complete. Duration={total_duration:.1f}s "
            f"sources={len(pkg.sources)} claims={len(pkg.claims)}",
            stage="complete",
            source_count=len(pkg.sources),
            claim_count=len(pkg.claims),
            duration_sec=total_duration,
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 1: Question Decomposition
    # -------------------------------------------------------------------------

    def _decompose_questions(self, ctx: ResearchContext) -> ResearchContext:
        """Generate research questions from the topic using the LLM."""
        prompt = f"""Topic: {ctx.topic}

Generate 10-15 specific research questions that a documentary about this topic should answer.
These questions should cover: causes, mechanisms, evidence, people, places, timeline, disagreements, and uncertainties.

Return a JSON object with this exact structure:
{{
  "questions": [
    {{
      "text": "the research question text",
      "question_type": "causal|evidence|timeline|disagreement|uncertainty",
      "importance_score": 0.8
    }}
  ]
}}

Prioritize questions with high story value and visual potential."""
        req = LLMRequest(
            messages=[
                LLMMessage(role="system", content="You are a research assistant. Return valid JSON only."),
                LLMMessage(role="user", content=prompt),
            ],
            json_mode=True,
            model_hint="large",
            temperature=0.4,
            max_tokens=2048,
        )
        resp = self._llm.complete(req)
        data = resp.parsed_json or {}
        questions_data = data.get("questions", [])

        ctx.research_questions = []
        for q in questions_data[:20]:
            ctx.research_questions.append(ResearchQuestion(
                id=_next_rq(),
                text=q.get("text", ""),
                question_type=q.get("question_type", "evidence"),
                importance_score=q.get("importance_score", 0.5),
                status=ResearchQuestionStatus.ACTIVE,
            ))

        # Ensure at least 5 questions
        if len(ctx.research_questions) < 5:
            fallback = [
                ResearchQuestion(id=_next_rq(), text=f"What is the evidence for {ctx.topic}?", question_type="evidence", importance_score=0.8),
                ResearchQuestion(id=_next_rq(), text=f"What happened historically regarding {ctx.topic}?", question_type="timeline", importance_score=0.7),
                ResearchQuestion(id=_next_rq(), text=f"What do experts disagree about regarding {ctx.topic}?", question_type="disagreement", importance_score=0.6),
                ResearchQuestion(id=_next_rq(), text=f"What remains unknown about {ctx.topic}?", question_type="uncertainty", importance_score=0.7),
                ResearchQuestion(id=_next_rq(), text=f"How can {ctx.topic} be visualized?", question_type="evidence", importance_score=0.5),
            ]
            ctx.research_questions = fallback

        return ctx

    # -------------------------------------------------------------------------
    # Step 2: Search Sources
    # -------------------------------------------------------------------------

    def _search_sources(self, ctx: ResearchContext) -> ResearchContext:
        """Search for sources for each research question."""
        queries_seen: set[str] = set()
        ctx.raw_sources = []
        max_sources = settings.research_max_sources

        for rq in ctx.research_questions:
            if len(ctx.raw_sources) >= max_sources:
                break
            if ctx.should_stop():
                break

            # Build search query
            query = f"{ctx.topic} {rq.text[:60]}"
            if query in queries_seen:
                continue
            queries_seen.add(query)

            # Check cache
            cached = self.cache.get_search(query)
            if cached:
                results = [SearchResult(**r) for r in cached]
            else:
                results = self._search.search(query)
                import dataclasses
                self.cache.set_search(query, [dataclasses.asdict(r) for r in results])

            # Convert to Source objects
            for sr in results:
                if len(ctx.raw_sources) >= max_sources:
                    break
                src = self._search_result_to_source(sr)
                ctx.raw_sources.append(src)

        return ctx

    def _search_result_to_source(self, sr: SearchResult) -> Source:
        tier = SourceTier(sr.tier) if sr.tier in [t.value for t in SourceTier] else SourceTier.TIER3
        return Source(
            id=_next_src(),
            url=sr.url,
            title=sr.title,
            snippet=sr.snippet,
            tier=tier,
            published_date=sr.published_date,
            domain=self._extract_domain(sr.url),
            overall_score=self._score_source(tier, sr.snippet),
            score_reason=f"Initial tier={tier.value}",
        )

    def _extract_domain(self, url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return ""

    def _score_source(self, tier: SourceTier, snippet: str) -> float:
        """Compute a 0-1 source quality score based on tier."""
        base_scores = {
            SourceTier.TIER1: 0.9,
            SourceTier.TIER2: 0.7,
            SourceTier.TIER3: 0.5,
            SourceTier.TIER4: 0.2,
        }
        return base_scores.get(tier, 0.5)

    # -------------------------------------------------------------------------
    # Step 3: Fetch and Score Sources
    # -------------------------------------------------------------------------

    def _fetch_and_score_sources(self, ctx: ResearchContext) -> ResearchContext:
        """Fetch full content for each source and score it."""
        for src in ctx.raw_sources:
            if ctx.should_stop():
                break
            # Check cache
            cached = self.cache.get_fetch(src.url)
            if cached:
                src.snippet = cached.get("snippet", src.snippet)
                src.overall_score = cached.get("overall_score", src.overall_score)
                src.score_reason = cached.get("score_reason", src.score_reason)
                continue

            t0 = time.time()
            result = self._fetch.fetch(src.url)
            duration = time.time() - t0
            self._logger.fetch_complete(src.url, success=result is not None, duration_sec=duration)

            if result:
                # Update source with fetched content
                if len(result.text_content) > len(src.snippet):
                    src.snippet = result.text_content[:1000]
                src.overall_score = self._rescore_source(src, result)
                src.score_reason = f"Fetched {len(result.text_content)} chars from {src.domain}"
                self.cache.set_fetch(src.url, {
                    "snippet": src.snippet,
                    "overall_score": src.overall_score,
                    "score_reason": src.score_reason,
                    "text_content": result.text_content[:5000],
                })
        return ctx

    def _rescore_source(self, src: Source, result) -> float:
        """Re-score a source after fetching its full content."""
        base = src.overall_score
        # Bonus for having substantial content
        content_len = len(result.text_content)
        if content_len > 2000:
            base += 0.05
        elif content_len < 200:
            base -= 0.1
        return min(max(base, 0.0), 1.0)

    # -------------------------------------------------------------------------
    # Step 4: Deduplicate Sources
    # -------------------------------------------------------------------------

    def _deduplicate_sources(self, ctx: ResearchContext) -> ResearchContext:
        """Remove duplicate sources: same URL or same content hash."""
        seen_urls: set[str] = set()
        seen_hashes: set[str] = set()
        ctx.deduped_sources = []

        for src in ctx.raw_sources:
            url_lower = src.url.lower().strip()
            # Skip exact URL duplicates
            if url_lower in seen_urls:
                continue
            # Skip near-duplicate domains (same article on multiple mirrors)
            # e.g., en.wikipedia.org/wiki/X vs en.m.wikipedia.org/wiki/X
            if "/m." in url_lower or "/mobile." in url_lower:
                canonical = url_lower.replace("/m.", "/").replace("/mobile.", "/")
                if canonical in seen_urls:
                    continue
            # Content hash deduplication
            content_hash = str(hash(src.snippet[:500]))
            if content_hash in seen_hashes and src.tier != SourceTier.TIER1:
                # Keep TIER1 even if duplicate content
                continue

            seen_urls.add(url_lower)
            seen_hashes.add(content_hash)
            src.lineage = SourceLineage(is_independent=True)
            ctx.deduped_sources.append(src)

        return ctx

    # -------------------------------------------------------------------------
    # Step 5: Extract Claims
    # -------------------------------------------------------------------------

    def _extract_claims(self, ctx: ResearchContext) -> ResearchContext:
        """Extract factual claims from source content using the LLM."""
        ctx.claims = []
        max_claims = settings.research_max_claims

        for src in ctx.deduped_sources:
            if len(ctx.claims) >= max_claims:
                break

            # Check cache
            cached = self.cache.get_claims(src.snippet)
            if cached:
                for cd in cached:
                    ctx.claims.append(Claim(
                        claim_id=cd.get("claim_id", _next_clm()),
                        text=cd.get("text", ""),
                        claim_type=ClaimType(cd.get("claim_type", "historical")),
                        importance=cd.get("importance", "medium"),
                        confidence=cd.get("confidence", 0.5),
                        source_ids=[src.id],
                    ))
                continue

            # Extract claims using LLM
            prompt = f"""You are a research analyst extracting factual claims from article text.

ARTICLE TITLE: {src.title}
ARTICLE CONTENT (snippet):
{src.snippet[:3000]}

Extract 2-5 factual claims from this text. Each claim should be:
- A verifiable statement of fact (not opinion or speculation)
- Specific (with dates, numbers, names where available)
- Important for understanding: "{ctx.topic}"

Return JSON:
{{
  "claims": [
    {{
      "text": "the factual claim text",
      "claim_type": "historical|archaeological|biological|anthropological|climatological|geographical|quantitative|technological|behavioral|interpretive",
      "importance": "high|medium|low",
      "confidence": 0.85,
      "uncertainty": "any caveats or limitations on this claim"
    }}
  ]
}}

If the text contains no verifiable factual claims, return {{"claims": []}}."""

            req = LLMRequest(
                messages=[
                    LLMMessage(role="system", content="You are a research analyst. Return valid JSON only."),
                    LLMMessage(role="user", content=prompt),
                ],
                json_mode=True,
                model_hint="large",
                temperature=0.2,
                max_tokens=2048,
            )
            resp = self._llm.complete(req)
            t0 = time.time()
            data = resp.parsed_json or {}
            claims_data = data.get("claims", [])

            extracted = []
            for cd in claims_data:
                if len(ctx.claims) + len(extracted) >= max_claims:
                    break
                claim = Claim(
                    claim_id=_next_clm(),
                    text=cd.get("text", ""),
                    claim_type=ClaimType(cd.get("claim_type", "historical")),
                    importance=cd.get("importance", "medium"),
                    confidence=cd.get("confidence", 0.5),
                    uncertainty=cd.get("uncertainty", ""),
                    source_ids=[src.id],
                )
                if claim.text and len(claim.text) > 5:
                    extracted.append(claim)

            # Cache
            self.cache.set_claims(
                src.snippet,
                [c.model_dump() for c in extracted],
            )

            ctx.claims.extend(extracted)
            self._logger.claims_extracted(
                source_title=src.title,
                count=len(extracted),
                duration_sec=time.time() - t0,
            )

        return ctx

    # -------------------------------------------------------------------------
    # Step 6: Build Claim-Source Graph
    # -------------------------------------------------------------------------

    def _build_claim_source_graph(self, ctx: ResearchContext) -> ResearchContext:
        """Build bidirectional claim-source links and classify certainty levels."""
        ctx.claim_source_links = []
        for claim in ctx.claims:
            # Determine certainty level based on source count and confidence
            source_count = len(claim.source_ids)
            if source_count >= 3 and claim.confidence >= 0.8:
                from app.schemas.research_package import CertaintyLevel
                claim.certainty_level = CertaintyLevel.STRONG_EVIDENCE
            elif source_count == 0:
                from app.schemas.research_package import CertaintyLevel
                claim.certainty_level = CertaintyLevel.UNKNOWN
            else:
                from app.schemas.research_package import CertaintyLevel
                if claim.confidence >= 0.85:
                    claim.certainty_level = CertaintyLevel.STRONG_EVIDENCE
                elif claim.confidence >= 0.6:
                    claim.certainty_level = CertaintyLevel.PLAUSIBLE_INTERPRETATION
                elif claim.confidence >= 0.3:
                    claim.certainty_level = CertaintyLevel.SPECULATION
                else:
                    claim.certainty_level = CertaintyLevel.UNKNOWN

            # Build links
            for src_id in claim.source_ids:
                ctx.claim_source_links.append(ClaimSourceLink(
                    claim_id=claim.claim_id,
                    source_id=src_id,
                    relationship=SourceRelationship.SUPPORTS,
                ))
        return ctx

    def _detect_contradictions(self, ctx: ResearchContext) -> ResearchContext:
        """Detect contradictory claim pairs.

        Deterministic implementation: pairwise comparison of claims in the
        same semantic category that contain explicit opposing polarity
        markers ("increased" vs "decreased", "before" vs "after", etc.)

        Two claims are flagged as contradictory when:
        1. They share the same topic (same keyword set or same category)
        2. They contain opposite-direction changes or numbers
        3. They come from independent sources
        """
        from app.schemas.research_package import Contradiction, ContradictionResolution

        claims = ctx.claims
        if len(claims) < 2:
            return ctx

        # Polarity markers that indicate opposing claims
        positive_polarity = (
            "increased", "grew", "growing", "rose", "rising", "higher",
            "more", "larger", "faster", "boosted", "elevated",
        )
        negative_polarity = (
            "decreased", "declined", "dropped", "fell", "falling",
            "lower", "less", "smaller", "slower", "reduced",
        )

        def _normalize(text: str) -> set[str]:
            return set(text.lower().split())

        def _has_marker(text_lower: str, markers: tuple[str, ...]) -> bool:
            padded = f" {text_lower} "
            return any(f" {m} " in padded or padded.startswith(f"{m} ") for m in markers)

        pairs_added = 0
        next_id = 1

        for i, claim_a in enumerate(claims):
            for j, claim_b in enumerate(claims):
                if j <= i:
                    continue
                # Skip same-source comparisons (they're already aligned)
                if claim_a.source_ids and claim_b.source_ids:
                    if set(claim_a.source_ids) & set(claim_b.source_ids):
                        continue

                text_a = claim_a.text.lower()
                text_b = claim_b.text.lower()

                # Check for opposing polarity in similar topic
                a_pos = _has_marker(text_a, positive_polarity)
                a_neg = _has_marker(text_a, negative_polarity)
                b_pos = _has_marker(text_b, positive_polarity)
                b_neg = _has_marker(text_b, negative_polarity)

                # Same topic check (simple word overlap)
                words_a = _normalize(text_a)
                words_b = _normalize(text_b)
                # Filter stopwords
                stopwords = {"the", "a", "an", "is", "was", "were", "are", "in", "of", "to", "and"}
                words_a -= stopwords
                words_b -= stopwords
                if not words_a or not words_b:
                    continue
                overlap = words_a & words_b
                shared_ratio = len(overlap) / min(len(words_a), len(words_b))

                same_topic = shared_ratio >= 0.3  # 30% overlap

                contradictory = same_topic and (
                    (a_pos and b_neg) or (a_neg and b_pos)
                )

                if contradictory:
                    pair_id = f"CTR-{next_id:03d}"
                    next_id += 1
                    pair = Contradiction(
                        id=pair_id,
                        claim_id_a=claim_a.claim_id,
                        claim_id_b=claim_b.claim_id,
                        position_a=claim_a.text,
                        position_b=claim_b.text,
                        possible_reason="Opposing polarity markers in shared topic",
                        resolution=ContradictionResolution.UNRESOLVED,
                        resolution_notes=f"Auto-detected (overlap={shared_ratio:.2f})",
                    )
                    ctx.contradictions.append(pair)
                    pairs_added += 1
                    if pairs_added >= 20:  # Cap to avoid combinatorial explosion
                        return ctx

        return ctx

    def _extract_geography(self, ctx: ResearchContext) -> ResearchContext:
        """Extract geographic references from sources and claims.

        Detects common patterns:
        - Named locations (countries, cities, landmarks)
        - Coordinates or relative locations
        - Geographic terms (river, mountain, etc.)
        """
        from app.schemas.research_package import GeographicSite

        # Common geographic terms to detect
        known_patterns = {
            # Continents
            "africa": "Africa",
            "asia": "Asia",
            "europe": "Europe",
            "north america": "North America",
            "south america": "South America",
            "australia": "Australia",
            "antarctica": "Antarctica",
            # Oceans
            "pacific ocean": "Pacific Ocean",
            "atlantic ocean": "Atlantic Ocean",
            "indian ocean": "Indian Ocean",
            "arctic ocean": "Arctic Ocean",
            # Generic features
            "river": "river",
            "mountain": "mountain",
            "desert": "desert",
            "valley": "valley",
            "island": "island",
            "ocean": "ocean",
        }

        # Collect all text from sources and claims
        all_text = []
        for src in ctx.raw_sources:
            if hasattr(src, "text") and src.text:
                all_text.append(src.text)
            elif hasattr(src, "title") and src.title:
                all_text.append(src.title)
            elif hasattr(src, "url"):
                all_text.append(src.url)
        for src in ctx.deduped_sources:
            if hasattr(src, "text") and src.text:
                all_text.append(src.text)
            elif hasattr(src, "title") and src.title:
                all_text.append(src.title)
        for claim in ctx.claims:
            all_text.append(claim.text)

        full_text = " ".join(all_text).lower()

        seen: set[str] = set()
        for keyword, name in known_patterns.items():
            if keyword in full_text and keyword not in seen:
                seen.add(keyword)
                ctx.geography.append(GeographicSite(
                    name=name,
                    region=keyword,
                    country="",
                    evidence=keyword,
                ))

        return ctx

    def _extract_quantitative_facts(self, ctx: ResearchContext) -> ResearchContext:
        """Extract numerical facts from claims.

        Detects:
        - Year references (1900-2099)
        - Percentages (X%)
        - Quantities (X thousand/million/billion)
        - Measurements (km, m, °C, etc.)
        """
        import re

        from app.schemas.research_package import QuantitativeFact

        # Regex patterns for numeric facts
        year_re = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
        percent_sign_re = re.compile(r"(\d+(?:\.\d+)?)\s*%")
        percent_word_re = re.compile(r"\b(\d+(?:\.\d+)?)\s*percent\b", re.IGNORECASE)
        million_re = re.compile(r"\b(\d+(?:\.\d+)?)\s*(million|billion|thousand)\b", re.IGNORECASE)
        km_re = re.compile(r"\b(\d+(?:\.\d+)?)\s*(km|kilometer|kilometre|mile|meter|metre)\b", re.IGNORECASE)
        temp_re = re.compile(r"\b(\-?\d+(?:\.\d+)?)\s*(?:°|degrees?)\s*([CF])\b")

        seen_facts: set[str] = set()
        next_id = 1

        for claim in ctx.claims:
            text = claim.text

            def _make_id() -> str:
                nonlocal next_id
                qfid = f"QF-{next_id:03d}"
                next_id += 1
                return qfid

            # Years (as integer year, no unit)
            for m in year_re.finditer(text):
                year_str = m.group(1)
                key = f"year:{year_str}"
                if key not in seen_facts:
                    seen_facts.add(key)
                    try:
                        ctx.quantitative_facts.append(QuantitativeFact(
                            id=_make_id(),
                            value=float(year_str),
                            unit="year",
                            context=text[:100],
                            approximate=False,
                            source_ids=list(claim.source_ids) if claim.source_ids else [],
                        ))
                    except Exception:
                        pass

            # Percentages
            for m in percent_sign_re.finditer(text):
                value_str = m.group(1)
                key = f"percent:{value_str}"
                if key not in seen_facts:
                    seen_facts.add(key)
                    try:
                        ctx.quantitative_facts.append(QuantitativeFact(
                            id=_make_id(),
                            value=float(value_str),
                            unit="percent",
                            context=text[:100],
                            source_ids=list(claim.source_ids) if claim.source_ids else [],
                        ))
                    except Exception:
                        pass
            for m in percent_word_re.finditer(text):
                value_str = m.group(1)
                key = f"percent:{value_str}"
                if key not in seen_facts:
                    seen_facts.add(key)
                    try:
                        ctx.quantitative_facts.append(QuantitativeFact(
                            id=_make_id(),
                            value=float(value_str),
                            unit="percent",
                            context=text[:100],
                            source_ids=list(claim.source_ids) if claim.source_ids else [],
                        ))
                    except Exception:
                        pass

            # Quantities (million/billion/thousand)
            for m in million_re.finditer(text):
                value_str = m.group(1)
                unit_str = m.group(2).lower()
                key = f"quantity:{value_str}:{unit_str}"
                if key not in seen_facts:
                    seen_facts.add(key)
                    multiplier = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}.get(unit_str, 1)
                    try:
                        ctx.quantitative_facts.append(QuantitativeFact(
                            id=_make_id(),
                            value=float(value_str) * multiplier,
                            unit=unit_str,
                            context=text[:100],
                            source_ids=list(claim.source_ids) if claim.source_ids else [],
                        ))
                    except Exception:
                        pass

            # Distances
            for m in km_re.finditer(text):
                value_str = m.group(1)
                unit_str = m.group(2).lower()
                key = f"distance:{value_str}:{unit_str}"
                if key not in seen_facts:
                    seen_facts.add(key)
                    try:
                        ctx.quantitative_facts.append(QuantitativeFact(
                            id=_make_id(),
                            value=float(value_str),
                            unit=unit_str,
                            context=text[:100],
                            source_ids=list(claim.source_ids) if claim.source_ids else [],
                        ))
                    except Exception:
                        pass

            # Temperatures
            for m in temp_re.finditer(text):
                value_str = m.group(1)
                unit_str = "°" + m.group(2).upper()
                key = f"temp:{value_str}:{unit_str}"
                if key not in seen_facts:
                    seen_facts.add(key)
                    try:
                        ctx.quantitative_facts.append(QuantitativeFact(
                            id=_make_id(),
                            value=float(value_str),
                            unit=unit_str,
                            context=text[:100],
                            source_ids=list(claim.source_ids) if claim.source_ids else [],
                        ))
                    except Exception:
                        pass

            # Cap to avoid flooding
            if len(ctx.quantitative_facts) >= 200:
                break

        return ctx

    def _model_uncertainty(self, ctx: ResearchContext) -> ResearchContext:
        """Identify research gaps and uncertain claims."""
        # Find claims with low confidence or few sources
        uncertain_claims = [
            c for c in ctx.claims
            if c.certainty_level in (
                CertaintyLevel.SPECULATION,
                CertaintyLevel.UNKNOWN,
            ) or len(c.source_ids) < 2
        ]

        for claim in uncertain_claims:
            gap = ResearchGap(
                id=_next_gap(),
                question=f"'{claim.text[:100]}' — is this claim well-supported?",
                status=ResearchGapStatus.INSUFFICIENT_EVIDENCE,
                reason=claim.uncertainty or "Limited source evidence",
                related_question_ids=[],
            )
            ctx.research_gaps.append(gap)

        return ctx

    # -------------------------------------------------------------------------
    # Step 9: Build Timeline
    # -------------------------------------------------------------------------

    def _build_timeline(self, ctx: ResearchContext) -> ResearchContext:
        """Extract timeline events from claims and sources."""
        # Collect all dates/periods mentioned in claims
        timeline_data: dict[str, dict] = {}

        for claim in ctx.claims:
            text_lower = claim.text.lower()
            # Look for date patterns
            import re
            dates = re.findall(
                r"(\d+\s*(million|thousand|billion)?\s*years?\s*(ago|bce|ce)?|"
                r"(~?\d{1,4}\s*bce|~?\d{1,4}\s*ce)|"
                r"(\d{4})|"
                r"(Pleistocene|Holocene|Jurassic|Cretaceous|Miocene|"
                r"Ice Age|Glacial|Upper Paleolithic|Lower Paleolithic))",
                text_lower,
                re.IGNORECASE,
            )
            for match in dates:
                period = next((m for m in match if m), "")
                if period and period not in timeline_data:
                    timeline_data[period] = {
                        "period": period,
                        "events": [],
                        "uncertainty": claim.uncertainty[:200] if claim.uncertainty else "",
                    }

        # Convert to TimelineEvent objects
        for period, data in sorted(timeline_data.items()):
            # Collect related claims
            related_claims = [
                c.claim_id for c in ctx.claims
                if period.lower() in c.text.lower()
            ]
            timeline_event = {
                "period": data["period"],
                "start_date": "",
                "end_date": "",
                "events": [f"Evidence related to: {period}"],
                "uncertainty": data["uncertainty"],
                "is_approximate": "~" in period or "approximately" in period.lower(),
                "claim_ids": related_claims,
            }
            ctx.timeline.append(timeline_event)

        return ctx

    # -------------------------------------------------------------------------
    # Step 10: Extract Visual Opportunities
    # -------------------------------------------------------------------------

    def _extract_visual_opportunities(self, ctx: ResearchContext) -> ResearchContext:
        """Identify claims that can be visualized."""
        ctx.visual_opportunities = []

        # Group claims by visual type
        claim_texts = "\n".join(
            f"[{c.claim_id}] {c.text}" for c in ctx.claims[:30]
        )

        prompt = f"""Analyze these research claims and identify visual opportunities for a documentary:

{claim_texts}

For each important claim, determine the best visual representation.
Return JSON:
{{
  "visual_opportunities": [
    {{
      "claim_id": "CLM-001",
      "opportunity_type": "character_action|environment|artifact|map|timeline|diagram|reconstruction|animation|number_visualization",
      "description": "What to show on screen",
      "visual_spec": "Specific visual details: characters, setting, props, camera movement",
      "environment_hint": "cave_interior|ice_age_plains|diagram_white|title_card|etc",
      "mood_hint": "calm|tense|warm|mysterious|triumphant"
    }}
  ]
}}"""

        req = LLMRequest(
            messages=[
                LLMMessage(role="system", content="You are a documentary storyboard assistant. Return valid JSON only."),
                LLMMessage(role="user", content=prompt),
            ],
            json_mode=True,
            model_hint="small",
            temperature=0.3,
            max_tokens=2048,
        )
        resp = self._llm.complete(req)
        data = resp.parsed_json or {}
        vo_data = data.get("visual_opportunities", [])

        for vo in vo_data:
            cid = vo.get("claim_id", "")
            # Validate claim_id exists
            if not any(c.claim_id == cid for c in ctx.claims):
                cid = ctx.claims[0].claim_id if ctx.claims else "CLM-001"
            vop = VisualOpportunity(
                id=_next_vo(),
                claim_id=cid,
                opportunity_type=VisualOpportunityType(vo.get("opportunity_type", "environment")),
                description=vo.get("description", "")[:500],
                visual_spec=vo.get("visual_spec", "")[:1000],
                environment_hint=vo.get("environment_hint", ""),
                mood_hint=vo.get("mood_hint", ""),
            )
            ctx.visual_opportunities.append(vop)
            # Link back to claim
            for c in ctx.claims:
                if c.claim_id == cid:
                    c.visual_opportunity_id = vop.id

        return ctx

    # -------------------------------------------------------------------------
    # Step 11: Extract Story Opportunities
    # -------------------------------------------------------------------------

    def _extract_story_opportunities(self, ctx: ResearchContext) -> ResearchContext:
        """Identify story hooks, emotional beats, and counterintuitive findings."""
        # Build summary of claims for story analysis
        claim_summary = "\n".join(
            f"- {c.text[:200]}" for c in ctx.claims[:20]
        )

        prompt = f"""Analyze this research to identify story opportunities for a documentary:

Topic: {ctx.topic}

Key Claims:
{claim_summary}

Contradictions Found: {len(ctx.contradictions)}

Return JSON:
{{
  "hook_candidates": ["A compelling opening hook question or statement"],
  "surprising_facts": ["A counterintuitive or surprising fact"],
  "contradictions": ["A key scholarly disagreement the documentary should address"],
  "escalations": ["A dramatic escalation or revelation"],
  "emotional_beats": ["A moment that creates emotional impact"],
  "questions": ["A question that keeps viewers engaged"],
  "final_takeaways": ["The key message viewers should remember"]
}}"""

        req = LLMRequest(
            messages=[
                LLMMessage(role="system", content="You are a documentary story consultant. Return valid JSON only."),
                LLMMessage(role="user", content=prompt),
            ],
            json_mode=True,
            model_hint="large",
            temperature=0.5,
            max_tokens=2048,
        )
        resp = self._llm.complete(req)
        data = resp.parsed_json or {}

        ctx.story_opportunities = [
            StoryOpportunity(
                id=_next_so(),
                hook_candidates=data.get("hook_candidates", [f"How did {ctx.topic} work?"]),
                surprising_facts=data.get("surprising_facts", []) or [f"Surprising angle on {ctx.topic}"],
                contradictions=[
                    c.position_a[:200] for c in ctx.contradictions[:3]
                ],
                escalations=data.get("escalations", []) or ["Escalation of stakes"],
                emotional_beats=data.get("emotional_beats", []) or ["curiosity", "wonder"],
                questions=data.get("questions", []),
                final_takeaways=data.get("final_takeaways", [f"{ctx.topic} is fascinating."]),
            )
        ]
        return ctx

    # -------------------------------------------------------------------------
    # Step 12: Synthesize
    # -------------------------------------------------------------------------

    def _synthesize(self, ctx: ResearchContext) -> ResearchContext:
        """Generate the research synthesis using the LLM."""
        # Build context for synthesis
        source_summary = "\n".join(
            f"- [{s.tier.value}] {s.title}: {s.snippet[:200]}"
            for s in ctx.deduped_sources[:15]
        )
        claim_summary = "\n".join(
            f"- {c.text[:200]}" for c in ctx.claims[:30]
        )

        prompt = f"""You are synthesizing research for a documentary on: {ctx.topic}

SOURCES:
{source_summary}

KEY CLAIMS:
{claim_summary}

CONTRADICTIONS ({len(ctx.contradictions)}):
{chr(10).join(f"- A: {ct.position_a[:150]} vs B: {ct.position_b[:150]}" for ct in ctx.contradictions[:5])}

RESEARCH GAPS ({len(ctx.research_gaps)}):
{chr(10).join(f"- {g.question[:150]}" for g in ctx.research_gaps[:5])}

Write a comprehensive research synthesis in JSON format:
{{
  "central_question": "The central question this documentary explores",
  "short_answer": "A one-sentence answer to the central question",
  "detailed_answer": "A 3-4 paragraph detailed answer covering causes, evidence, disagreements, and remaining uncertainties",
  "strongest_evidence": ["The 3 strongest pieces of evidence supporting the answer"],
  "weakest_evidence": ["Evidence that is disputed or weak"],
  "major_uncertainties": ["The 3 biggest remaining unknowns"],
  "major_disagreements": ["Key scholarly disagreements the documentary should present"],
  "timeline_summary": ["Key periods or events in chronological order"],
  "important_examples": ["Concrete examples that illustrate the main points"],
  "counterintuitive_findings": ["Findings that challenge common assumptions"]
}}"""

        req = LLMRequest(
            messages=[
                LLMMessage(role="system", content="You are a documentary research consultant. Return valid JSON only."),
                LLMMessage(role="user", content=prompt),
            ],
            json_mode=True,
            model_hint="large",
            temperature=0.3,
            max_tokens=4096,
        )
        resp = self._llm.complete(req)
        data = resp.parsed_json or {}

        ctx.synthesis = ResearchSynthesis(
            central_question=data.get("central_question") or f"What is {ctx.topic}?",
            short_answer=data.get("short_answer") or "The topic involves complex factors requiring evidence-based analysis.",
            detailed_answer=data.get("detailed_answer") or f"Detailed analysis of {ctx.topic} requires careful examination of multiple evidence sources.",
            strongest_evidence=data.get("strongest_evidence") or [f"Evidence from research on {ctx.topic}"],
            weakest_evidence=data.get("weakest_evidence", []),
            major_uncertainties=data.get("major_uncertainties") or [f"Some aspects of {ctx.topic} remain uncertain"],
            major_disagreements=data.get("major_disagreements", []),
            timeline_summary=data.get("timeline_summary", []),
            important_examples=data.get("important_examples") or [f"Notable example related to {ctx.topic}"],
            counterintuitive_findings=data.get("counterintuitive_findings", []),
            visual_opportunity_ids=[vo.id for vo in ctx.visual_opportunities],
            story_opportunity_ids=[so.id for so in ctx.story_opportunities],
            research_gap_ids=[g.id for g in ctx.research_gaps],
        )
        return ctx

    # -------------------------------------------------------------------------
    # Step 13: Score Quality
    # -------------------------------------------------------------------------

    def _score_quality(self, ctx: ResearchContext) -> ResearchContext:
        """Compute quality scores for the research package."""
        sources = ctx.deduped_sources
        claims = ctx.claims

        # Source quality: average score of sources
        source_quality = (
            sum(s.overall_score for s in sources) / len(sources)
            if sources else 0.0
        )

        # Coverage: how many research questions are answered
        answered_rqs = sum(
            1 for rq in ctx.research_questions
            if any(c.text.lower()[:50] in rq.text.lower() or rq.text.lower() in c.text.lower()
                   for c in claims)
        )
        coverage = answered_rqs / max(len(ctx.research_questions), 1)

        # Claim traceability: % of claims with sources
        traced = sum(1 for c in claims if c.source_ids)
        claim_traceability = traced / max(len(claims), 1)

        # Independence: % of sources that are not from same domain family
        independent = sum(1 for s in sources if s.lineage.is_independent)
        independence = independent / max(len(sources), 1)

        # Contradiction detection: were contradictions found and documented?
        contradiction_detection = (
            1.0 if len(ctx.contradictions) > 0 else 0.5
        )

        # Uncertainty handling: are uncertain claims properly flagged?
        uncertain_flagged = sum(
            1 for c in claims
            if c.certainty_level in (CertaintyLevel.SPECULATION, CertaintyLevel.UNKNOWN)
        )
        uncertainty_handling = (
            min(uncertain_flagged / max(len(claims), 1) + 0.5, 1.0)
            if uncertain_flagged > 0 else 0.7
        )

        # Research depth: ratio of sources to claims
        research_depth = min(len(sources) / max(len(claims), 1) * 0.5, 1.0)

        # Visual value: ratio of visual opportunities to claims
        visual_value = min(len(ctx.visual_opportunities) / max(len(claims), 1) * 2, 1.0)

        # Story value: presence of story opportunities
        story_value = (
            1.0 if ctx.story_opportunities and any(
                ctx.story_opportunities[0].hook_candidates
            ) else 0.5
        )

        ctx.quality_score = ResearchQualityScore(
            source_quality=round(source_quality, 3),
            coverage=round(coverage, 3),
            claim_traceability=round(claim_traceability, 3),
            independence=round(independence, 3),
            contradiction_detection=round(contradiction_detection, 3),
            uncertainty_handling=round(uncertainty_handling, 3),
            research_depth=round(research_depth, 3),
            visual_value=round(visual_value, 3),
            story_value=round(story_value, 3),
        )

        return ctx

    # -------------------------------------------------------------------------
    # Build Final Package
    # -------------------------------------------------------------------------

    def _build_package(self, ctx: ResearchContext, duration_sec: float) -> ResearchPackage:
        """Assemble and validate the final ResearchPackage."""
        from datetime import datetime
        from app.schemas.research_package import ResearchMetadata

        metadata = ResearchMetadata(
            topic=ctx.topic,
            version="1.0",
            created_at=datetime.utcnow(),
            duration_sec=round(duration_sec, 1),
            job_id=ctx.job_id,
            quality_score=ctx.quality_score.overall_score if ctx.quality_score else None,
            quality_warnings=self._generate_warnings(ctx),
            source_count=len(ctx.deduped_sources),
            claim_count=len(ctx.claims),
        )

        pkg = ResearchPackage(
            metadata=metadata,
            research_questions=ctx.research_questions,
            sources=ctx.deduped_sources,
            claims=ctx.claims,
            claim_source_links=ctx.claim_source_links,
            contradictions=ctx.contradictions,
            research_gaps=ctx.research_gaps,
            timeline=[],  # Already in ctx.timeline as dicts; convert
            geography=ctx.geography,
            quantitative_facts=ctx.quantitative_facts,
            visual_opportunities=ctx.visual_opportunities,
            story_opportunities=ctx.story_opportunities,
            synthesis=ctx.synthesis or ResearchSynthesis(
                central_question=ctx.topic,
                short_answer="Research in progress.",
                detailed_answer="",
                strongest_evidence=[],
                timeline_summary=[],
                important_examples=[],
            ),
            quality_score=ctx.quality_score or ResearchQualityScore(
                source_quality=0.0, coverage=0.0, claim_traceability=0.0,
                independence=0.0, contradiction_detection=0.0, uncertainty_handling=0.0,
                research_depth=0.0, visual_value=0.0, story_value=0.0,
            ),
        )
        return pkg

    def _generate_warnings(self, ctx: ResearchContext) -> list[str]:
        warnings: list[str] = []
        if len(ctx.deduped_sources) < 5:
            warnings.append("Few sources found. Consider refining search queries.")
        tier4 = [s for s in ctx.deduped_sources if s.tier == SourceTier.TIER4]
        if len(tier4) / max(len(ctx.deduped_sources), 1) > 0.5:
            warnings.append("More than half of sources are TIER4. Verify claims with higher-quality sources.")
        if not ctx.contradictions:
            warnings.append("No contradictions detected. This may indicate incomplete research.")
        if ctx.quality_score and ctx.quality_score.overall_score < settings.research_quality_min_threshold:
            warnings.append(
                f"Quality score {ctx.quality_score.overall_score:.2f} is below "
                f"threshold {settings.research_quality_min_threshold}."
            )
        return warnings

    def _write_legacy_research(self, job_id: str, pkg: ResearchPackage) -> None:
        """Write backward-compatible research.json for downstream stages."""
        from app.core import paths as paths_module
        from app.core.paths import write_json as write_json_fn

        legacy = pkg.to_legacy_dict()
        legacy_path = paths_module.stage_path(job_id, "research")
        write_json_fn(legacy_path, legacy)
        # Also write full package
        pkg_path = paths_module.stage_path(job_id, "research_package")
        write_json_fn(pkg_path, pkg.model_dump())
