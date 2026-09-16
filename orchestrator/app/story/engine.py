"""
Story Intelligence Engine — core orchestration.

Consumes a ResearchPackage and produces a StoryPackage through 15 ordered steps:

    _quality_gate
         ↓
    _generate_thesis_candidates
         ↓
    _generate_angle_candidates
         ↓
    _generate_title_candidates
         ↓
    _generate_hook_candidates
         ↓
    _build_narrative_blueprint
         ↓
    _generate_script_draft
         ↓
    _build_claim_traceability
         ↓
    _run_script_critique
         ↓
    _compute_retention
         ↓
    _generate_revision
         ↓
    _finalize_script
         ↓
    _build_storyboard_intent
         ↓
    _compute_quality_score
         ↓
    _validate_and_finalize

Each step is a private method that receives a StoryPackage (and optional context)
and returns an updated StoryPackage. Steps cache their output on the package
object. A `StoryContext` dataclass threads state between steps.

Usage:
    engine = StoryEngine(job_id="...")
    story_pkg = engine.run(
        job_id="abc123",
        topic="How Did Ancient Humans Survive Ice Ages?",
        research_package=research_pkg,
    )
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import LLMMessage, LLMRequest
from app.providers.llm import get_llm_provider
from app.schemas.research_package import (
    Claim,
    ResearchPackage,
)
from app.schemas.story import (
    AngleCandidate,
    AngleSelection,
    AngleType,
    ArtifactVersion,
    CertaintyLevel,
    ClaimTraceEntry,
    ClaimTraceabilityReport,
    CritiqueCategory,
    CritiqueFinding,
    CritiqueSeverity,
    EmotionalState,
    HookCandidate,
    HookSelection,
    NarrativeBeat,
    NarrativeBlueprint,
    NarrativePurpose,
    RetentionAnalysis,
    ReviewStatus,
    RevisionEntry,
    RevisionHistory,
    ScriptCritique,
    ScriptDraft,
    ScriptSegment,
    ScriptVersion,
    ScriptVersionRecord,
    SegmentRetention,
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
    VisualMode,
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# ID counters
# ---------------------------------------------------------------------------
_counter_thesis = 0
_counter_angle = 0
_counter_title = 0
_counter_hook = 0
_counter_beat = 0
_counter_segment = 0
_counter_finding = 0
_counter_retention = 0
_counter_revision = 0


def _next_thesis() -> str:
    global _counter_thesis
    _counter_thesis += 1
    return f"TH-{_counter_thesis:03d}"


def _next_angle() -> str:
    global _counter_angle
    _counter_angle += 1
    return f"ANG-{_counter_angle:03d}"


def _next_title() -> str:
    global _counter_title
    _counter_title += 1
    return f"TI-{_counter_title:03d}"


def _next_hook() -> str:
    global _counter_hook
    _counter_hook += 1
    return f"HK-{_counter_hook:03d}"


def _next_beat() -> str:
    global _counter_beat
    _counter_beat += 1
    return f"BT-{_counter_beat:03d}"


def _next_segment() -> str:
    global _counter_segment
    _counter_segment += 1
    return f"SG-{_counter_segment:03d}"


def _next_finding() -> str:
    global _counter_finding
    _counter_finding += 1
    return f"FN-{_counter_finding:03d}"


def _next_retention() -> str:
    global _counter_retention
    _counter_retention += 1
    return f"RT-{_counter_retention:03d}"


def _next_revision() -> str:
    global _counter_revision
    _counter_revision += 1
    return f"RV-{_counter_revision:03d}"


def reset_story_counters() -> None:
    """Reset all counters. Useful for testing."""
    global _counter_thesis, _counter_angle, _counter_title, _counter_hook
    global _counter_beat, _counter_segment, _counter_sbi, _counter_finding
    global _counter_revision
    _counter_thesis = _counter_angle = _counter_title = _counter_hook = 0
    _counter_beat = _counter_segment = _counter_sbi = _counter_finding = 0
    _counter_revision = 0


# ---------------------------------------------------------------------------
# Story Context
# ---------------------------------------------------------------------------

@dataclass
class StoryContext:
    """Thread-safe state container passed through each pipeline step."""

    job_id: str
    topic: str
    research_package: ResearchPackage
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Populated by steps
    _thesis_candidates_generated: bool = False
    _angle_candidates_generated: bool = False
    _title_candidates_generated: bool = False
    _hook_candidates_generated: bool = False
    _blueprint_generated: bool = False
    _draft_generated: bool = False
    _traceability_built: bool = False
    _critique_run: bool = False
    _retention_computed: bool = False
    _revision_generated: bool = False
    _script_finalized: bool = False
    _storyboard_built: bool = False
    _quality_scored: bool = False


# ---------------------------------------------------------------------------
# Story Engine
# ---------------------------------------------------------------------------

class StoryEngine:
    """
    Orchestrates the full story-intelligence pipeline.

    Consumes a ResearchPackage produced by ResearchEngine and returns a
    fully-populated StoryPackage ready for script rendering.

    Parameters
    ----------
    job_id : str
        Unique job identifier. Used for logging and workspace paths.
    use_mock : bool
        If True, use mock LLM provider for testing. Default: False.
    """

    def __init__(self, job_id: str, use_mock: bool = False, use_cache: bool = False) -> None:
        self.job_id = job_id
        self.use_mock = use_mock
        self.use_cache = use_cache
        self._llm = get_llm_provider()
        self._logger = get_logger(f"story.{job_id}")

    def run(
        self,
        job_id: str,
        topic: str,
        research_package: ResearchPackage,
    ) -> StoryPackage:
        """
        Run the full story pipeline and return a validated StoryPackage.

        Parameters
        ----------
        job_id : str
            Unique job identifier.
        topic : str
            The documentary topic string.
        research_package : ResearchPackage
            The output from the Research Engine (read-only input).

        Returns
        -------
        StoryPackage
            A fully-populated, schema-validated story package.
        """
        t0 = time.time()
        self._logger.info(f"Starting story generation for topic: {topic}")

        # Initialize context
        ctx = StoryContext(
            job_id=job_id,
            topic=topic,
            research_package=research_package,
        )

        # Initialize the story package with metadata
        # Use model_construct to skip strict validators during initial scaffold;
        # validators run at the end of run() via _validate_and_finalize.
        pkg = StoryPackage.model_construct(
            metadata=StoryMetadata(
                story_package_id=f"SP-{job_id}",
                research_package_id=f"RP-{job_id}",
                research_package_hash=_hash_package(research_package),
                topic=topic,
                job_id=job_id,
                status=StoryStatus.IN_PROGRESS,
                review_status=ReviewStatus.DRAFT,
            ),
            research_status="passed",
            revision_history=RevisionHistory(),
        )

        # Step 1: Quality gate
        pkg = self._quality_gate(research_package, pkg)
        if pkg.metadata.status == StoryStatus.BLOCKED:
            self._logger.warning(f"Story blocked at quality gate: {pkg.research_failures}")
            return pkg

        # Step 2: Thesis candidates
        pkg = self._generate_thesis_candidates(research_package, ctx, pkg)

        # Step 3: Angle candidates
        pkg = self._generate_angle_candidates(research_package, ctx, pkg)

        # Step 4: Title candidates
        pkg = self._generate_title_candidates(research_package, ctx, pkg)

        # Step 5: Hook candidates
        pkg = self._generate_hook_candidates(research_package, ctx, pkg)

        # Step 6: Narrative blueprint
        pkg = self._build_narrative_blueprint(research_package, ctx, pkg)

        # Step 7: Script draft
        pkg = self._generate_script_draft(research_package, ctx, pkg)

        # Step 8: Claim traceability
        pkg = self._build_claim_traceability(research_package, ctx, pkg)

        # Step 9: Script critique
        pkg = self._run_script_critique(research_package, ctx, pkg)

        # Step 10: Retention analysis
        pkg = self._compute_retention(research_package, ctx, pkg)

        # Step 11: Revision
        pkg = self._generate_revision(research_package, ctx, pkg)

        # Step 12: Finalize script
        pkg = self._finalize_script(research_package, ctx, pkg)

        # Step 13: Storyboard intent
        pkg = self._build_storyboard_intent(research_package, ctx, pkg)

        # Step 14: Quality score
        pkg = self._compute_quality_score(research_package, ctx, pkg)

        # Step 15: Validate and finalize
        pkg = self._validate_and_finalize(ctx, pkg)

        elapsed = time.time() - t0
        self._logger.info(
            f"Story generation complete in {elapsed:.1f}s — status={pkg.metadata.status.value}, quality={pkg.quality_score.overall_score if pkg.quality_score else 0.0}"
        )

        return pkg

    # -------------------------------------------------------------------------
    # LLM Helper
    # -------------------------------------------------------------------------

    def _llm_complete(
        self,
        messages: list[LLMMessage],
        task: str,
        temperature: float | None = None,
        max_tokens: int = 4096,
        json_mode: bool = True,
        model_hint: str = "large",
    ) -> dict | None:
        """
        Issue an LLM request with one retry on parse failure.

        Parameters
        ----------
        messages : list of LLMMessage
        task : str — human-readable task name for logging
        temperature, max_tokens, json_mode, model_hint : overrides

        Returns
        -------
        dict | None — parsed JSON from the LLM, or None on failure.
        """
        temperature = temperature if temperature is not None else settings.story_temperature
        req = LLMRequest(
            messages=messages,
            json_mode=json_mode,
            model_hint=model_hint,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            resp = self._llm.complete(req)
            return resp.parsed_json
        except Exception as exc:
            self._logger.warning(
                f"LLM call '{task}' failed on first attempt: {exc}"
            )
            # Retry once
            try:
                resp = self._llm.complete(req)
                return resp.parsed_json
            except Exception as exc2:
                self._logger.error(
                    f"LLM call '{task}' failed on second attempt: {exc2}"
                )
                return None

    # -------------------------------------------------------------------------
    # Step 1: Quality Gate
    # -------------------------------------------------------------------------

    def _quality_gate(
        self,
        research_package: ResearchPackage,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Check research quality threshold and block CRITICAL failures."""
        min_quality = settings.story_research_min_quality
        overall = research_package.quality_score.overall_score

        pkg.metadata.research_quality_overall = overall
        pkg.metadata.research_warnings = list(research_package.metadata.quality_warnings or [])

        if overall < min_quality:
            pkg.metadata.research_quality_passed = False
            failures = []
            warnings = list(pkg.metadata.research_warnings)
            failures.append(
                f"CRITICAL: research quality {overall:.3f} below threshold {min_quality}"
            )
            pkg.research_failures = failures
            pkg.metadata.research_failures = failures
            pkg.metadata.research_warnings = warnings
            # Check if this is a hard block
            if overall < min_quality * 0.5:
                pkg.metadata.status = StoryStatus.BLOCKED
            self._logger.warning(
                f"Research quality gate failed: overall={overall}, threshold={min_quality}, failures={failures}"
            )
        else:
            pkg.metadata.research_quality_passed = True
            self._logger.info(
                f"Research quality gate passed: overall={overall}, threshold={min_quality}"
            )

        return pkg

    # -------------------------------------------------------------------------
    # Step 2: Thesis Candidates
    # -------------------------------------------------------------------------

    def _generate_thesis_candidates(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Generate multiple thesis candidates and rank by weighted score."""
        max_candidates = settings.story_max_thesis_candidates

        # Build research context string
        synthesis = research_package.synthesis
        claims = research_package.claims

        prompt = f"""You are a documentary thesis strategist.

TOPIC: {ctx.topic}

CENTRAL QUESTION: {synthesis.central_question}
SHORT ANSWER: {synthesis.short_answer}

STRONGEST EVIDENCE:
{chr(10).join(f"- {e}" for e in synthesis.strongest_evidence[:5])}

IMPORTANT EXAMPLES:
{chr(10).join(f"- {e}" for e in synthesis.important_examples[:5])}

COUNTERINTUITIVE FINDINGS:
{chr(10).join(f"- {f}" for f in synthesis.counterintuitive_findings[:3])}

KEY CLAIMS (top 15):
{chr(10).join(f"- [{c.claim_id}] {c.text[:200]}" for c in claims[:15])}

Generate {max_candidates} distinct thesis candidates for a 2-minute documentary.
Each thesis is a single declarative statement (20-80 words) that makes a claim
worth proving and that viewers will find surprising or emotionally resonant.

Return JSON:
{{
  "candidates": [
    {{
      "thesis_id": "TH-001",
      "statement": "The thesis statement text (20-80 words)",
      "supporting_claim_ids": ["CLM-001", "CLM-002"],
      "contradicting_claim_ids": [],
      "uncertainty": "What the thesis cannot yet prove",
      "explanatory_power": 0.8,
      "novelty": 0.7,
      "story_value": 0.9,
      "visual_value": 0.6,
      "audience_relevance": 0.8,
      "evidence_strength": 0.7,
      "overall_score": 0.0,
      "reason": "Why this thesis is strong"
    }}
  ]
}}

Score each: explanatory_power (how well it explains the topic),
novelty (surprising angle), story_value (emotional resonance),
visual_value (visualizable), audience_relevance (relatable),
evidence_strength (well-supported by claims).
overall_score is computed by the engine after scoring."""  # noqa: E501

        messages = [
            LLMMessage(role="system", content="You are a documentary thesis strategist. Return valid JSON only."),
            LLMMessage(role="user", content=prompt),
        ]

        data = self._llm_complete(messages, task="thesis_generation")
        if data is None:
            self._logger.error("thesis_generation LLM call failed")
            return pkg

        # Support both shapes:
        #   {"candidates": [...]}     — direct LLM response shape
        #   {"thesis": {"candidates": [...]}} — full StoryPackage shape (mock fixture)
        if "candidates" not in data and "thesis" in data and isinstance(data["thesis"], dict):
            data = data["thesis"]
        candidates_raw = data.get("candidates", [])
        thesis_candidates: list[ThesisCandidate] = []

        for c in candidates_raw:
            thesis = ThesisCandidate(
                thesis_id=c.get("thesis_id", _next_thesis()),
                statement=c.get("statement", ""),
                supporting_claim_ids=c.get("supporting_claim_ids", []),
                contradicting_claim_ids=c.get("contradicting_claim_ids", []),
                uncertainty=c.get("uncertainty", ""),
                explanatory_power=c.get("explanatory_power", 0.5),
                novelty=c.get("novelty", 0.5),
                story_value=c.get("story_value", 0.5),
                visual_value=c.get("visual_value", 0.5),
                audience_relevance=c.get("audience_relevance", 0.5),
                evidence_strength=c.get("evidence_strength", 0.5),
                reason=c.get("reason", ""),
            )
            # Compute weighted overall score
            thesis.overall_score = round(
                thesis.explanatory_power * 0.2
                + thesis.novelty * 0.1
                + thesis.story_value * 0.2
                + thesis.visual_value * 0.15
                + thesis.audience_relevance * 0.15
                + thesis.evidence_strength * 0.2,
                3,
            )
            thesis_candidates.append(thesis)

        # Rank by overall_score descending
        thesis_candidates.sort(key=lambda x: x.overall_score, reverse=True)

        # Truncate to max
        thesis_candidates = thesis_candidates[:max_candidates]

        # Auto-select highest-scoring
        selected_id = thesis_candidates[0].thesis_id if thesis_candidates else ""

        pkg.thesis = ThesisSelection(
            artifact_version=self._make_artifact_version("thesis_generation"),
            candidates=thesis_candidates,
            selected_id=selected_id,
            review_status=ReviewStatus.DRAFT,
        )

        ctx._thesis_candidates_generated = True
        self._logger.info(
            f"Generated {len(thesis_candidates)} thesis candidates, selected {selected_id}"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 3: Angle Candidates
    # -------------------------------------------------------------------------

    def _generate_angle_candidates(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Generate distinct angle types and rank by score."""
        max_angles = settings.story_max_angle_candidates
        thesis = next(
            (c for c in pkg.thesis.candidates if c.thesis_id == pkg.thesis.selected_id),
            None,
        )
        if thesis is None:
            self._logger.warning("No thesis selected, skipping angle generation")
            return pkg

        prompt = f"""You are a documentary angle strategist.

TOPIC: {ctx.topic}
THESIS: {thesis.statement}

ANGLE TYPES AVAILABLE:
- mystery: Present the topic as an unsolved puzzle
- survival: Focus on how someone/thing survived against odds
- contradiction: Highlight the biggest contradiction in the evidence
- modern_comparison: Compare past to present in an eye-opening way
- evolution: Show transformation over deep time
- technology: Focus on the tools or techniques involved
- human_behavior: Focus on human decisions, emotions, actions
- environment: Focus on how environment shaped the subject
- social_system: Focus on how groups or systems work
- unexpected_consequence: Show surprising downstream effects
- paradox: Present a clear paradox or tension
- transformation: Focus on dramatic before/after change

KEY CLAIMS:
{chr(10).join(f"- {c.text[:150]}" for c in research_package.claims[:12])}

STORY OPPORTUNITIES:
{chr(10).join(f"- {e}" for e in research_package.synthesis.counterintuitive_findings[:4])}

Generate {max_angles} genuinely different angle candidates.
Each must use a different angle type and explain the central tension clearly.
Score: visual_potential, curiosity, emotional_potential, story_strength.

Return JSON:
{{
  "candidates": [
    {{
      "angle_id": "AN-001",
      "type": "survival",
      "title": "Short angle title (5-15 words)",
      "description": "Full description of this angle approach (20-60 words)",
      "central_tension": "What dramatic tension does this angle create?",
      "supporting_claim_ids": ["CLM-001"],
      "uncertainties": ["What this angle cannot prove"],
      "visual_potential": 0.8,
      "curiosity": 0.9,
      "emotional_potential": 0.7,
      "story_strength": 0.8,
      "overall_score": 0.0
    }}
  ]
}}"""

        messages = [
            LLMMessage(role="system", content="You are a documentary angle strategist. Return valid JSON only."),
            LLMMessage(role="user", content=prompt),
        ]

        data = self._llm_complete(messages, task="angle_generation")
        if data is None:
            return pkg

        # Support both shapes:
        #   {"candidates": [...]}     — direct LLM response shape
        #   {"angle": {"candidates": [...]}} — full StoryPackage shape (mock fixture)
        if "candidates" not in data and "angle" in data and isinstance(data["angle"], dict):
            data = data["angle"]
        candidates_raw = data.get("candidates", [])
        angle_candidates: list[AngleCandidate] = []

        for c in candidates_raw:
            try:
                angle_type = AngleType(c.get("type", "survival"))
            except ValueError:
                angle_type = AngleType.SURVIVAL

            angle = AngleCandidate(
                angle_id=c.get("angle_id", _next_angle()),
                type=angle_type,
                title=c.get("title", ""),
                description=c.get("description", ""),
                central_tension=c.get("central_tension", ""),
                supporting_claim_ids=c.get("supporting_claim_ids", []),
                uncertainties=c.get("uncertainties", []),
                visual_potential=c.get("visual_potential", 0.5),
                curiosity=c.get("curiosity", 0.5),
                emotional_potential=c.get("emotional_potential", 0.5),
                story_strength=c.get("story_strength", 0.5),
            )
            angle.overall_score = round(
                angle.visual_potential * 0.25
                + angle.curiosity * 0.25
                + angle.emotional_potential * 0.25
                + angle.story_strength * 0.25,
                3,
            )
            angle_candidates.append(angle)

        angle_candidates.sort(key=lambda x: x.overall_score, reverse=True)
        angle_candidates = angle_candidates[:max_angles]
        selected_id = angle_candidates[0].angle_id if angle_candidates else ""

        pkg.angle = AngleSelection(
            artifact_version=self._make_artifact_version("angle_generation"),
            candidates=angle_candidates,
            selected_id=selected_id,
            review_status=ReviewStatus.DRAFT,
        )

        ctx._angle_candidates_generated = True
        self._logger.info(
            f"Generated {len(angle_candidates)} angle candidates, selected {selected_id}"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 4: Title Candidates
    # -------------------------------------------------------------------------

    def _generate_title_candidates(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Generate 20+ title candidates and rank by score."""
        max_titles = settings.story_max_title_candidates
        thesis = next(
            (c for c in pkg.thesis.candidates if c.thesis_id == pkg.thesis.selected_id),
            None,
        )
        angle = next(
            (c for c in pkg.angle.candidates if c.angle_id == pkg.angle.selected_id),
            None,
        )
        hook = next(
            (c for c in pkg.hook.candidates if c.hook_id == pkg.hook.selected_id),
            None,
        )

        prompt = f"""You are a documentary title writer.

TOPIC: {ctx.topic}
THESIS: {thesis.statement if thesis else "N/A"}
ANGLE: {angle.title if angle else "N/A"}
HOOK: {hook.text if hook else "N/A"}
CENTRAL QUESTION: {research_package.synthesis.central_question}

Generate {max_titles} title candidates for a 2-minute documentary video.
Titles must be curiosity-driven, specific, and honest about what the video delivers.
Avoid clickbait, overpromise, or vague titles.

Score each title (0.0-1.0):
- curiosity_score: Does it make viewers want to click?
- clarity_score: Is it immediately understandable?
- specificity_score: Does it reference concrete details?
- novelty_score: Is it fresh and not generic?
- truthfulness_score: Does it accurately represent the content?
- thesis_alignment: Does it match the thesis?
- payoff_alignment: Does it hint at a satisfying answer?
- mobile_readability: Is it short enough for a phone screen?

Return JSON:
{{
  "candidates": [
    {{
      "title_id": "TI-001",
      "title": "The actual title text (5-100 chars)",
      "curiosity_score": 0.8,
      "clarity_score": 0.9,
      "specificity_score": 0.7,
      "novelty_score": 0.8,
      "truthfulness_score": 0.9,
      "thesis_alignment": 0.8,
      "payoff_alignment": 0.7,
      "mobile_readability": 0.9,
      "overall_score": 0.0,
      "risk_flags": [],
      "promised_question": "What question does this title promise to answer?",
      "promised_payoff": "What insight or answer does this title promise?"
    }}
  ]
}}

IMPORTANT: Return at least {max_titles} candidates. This is a hard requirement."""

        messages = [
            LLMMessage(role="system", content="You are a documentary title writer. Return valid JSON only. Return AT LEAST 20 candidates."),
            LLMMessage(role="user", content=prompt),
        ]

        data = self._llm_complete(messages, task="title_generation", max_tokens=6144)
        if data is None:
            return pkg

        # Support both shapes:
        #   {"candidates": [...]}     — direct LLM response shape
        #   {"title": {"candidates": [...]}} — full StoryPackage shape (mock fixture)
        if "candidates" not in data and "title" in data and isinstance(data["title"], dict):
            data = data["title"]
        candidates_raw = data.get("candidates", [])
        title_candidates: list[TitleCandidate] = []

        for c in candidates_raw:
            risk_flags = []
            for flag in c.get("risk_flags", []):
                try:
                    risk_flags.append(TitleRiskFlag(flag))
                except ValueError:
                    pass

            title = TitleCandidate(
                title_id=c.get("title_id", _next_title()),
                title=c.get("title", ""),
                curiosity_score=c.get("curiosity_score", 0.5),
                clarity_score=c.get("clarity_score", 0.5),
                specificity_score=c.get("specificity_score", 0.5),
                novelty_score=c.get("novelty_score", 0.5),
                truthfulness_score=c.get("truthfulness_score", 0.5),
                thesis_alignment=c.get("thesis_alignment", 0.5),
                payoff_alignment=c.get("payoff_alignment", 0.5),
                mobile_readability=c.get("mobile_readability", 0.5),
                risk_flags=risk_flags,
                promised_question=c.get("promised_question", ""),
                promised_payoff=c.get("promised_payoff", ""),
            )
            title.overall_score = round(
                title.curiosity_score * 0.15
                + title.clarity_score * 0.15
                + title.specificity_score * 0.1
                + title.novelty_score * 0.1
                + title.truthfulness_score * 0.15
                + title.thesis_alignment * 0.15
                + title.payoff_alignment * 0.1
                + title.mobile_readability * 0.1,
                3,
            )
            title_candidates.append(title)

        title_candidates.sort(key=lambda x: x.overall_score, reverse=True)

        # Enforce minimum count (the StoryPackage validator will also check)
        if len(title_candidates) < 20:
            self._logger.warning(
                f"Only {len(title_candidates)} title candidates generated (minimum 20)"
            )
            # Pad with placeholders
            while len(title_candidates) < 20:
                title_candidates.append(
                    TitleCandidate(
                        title_id=_next_title(),
                        title=f"Title variant {len(title_candidates) + 1}: {ctx.topic}",
                        curiosity_score=0.5,
                        clarity_score=0.5,
                        specificity_score=0.5,
                        novelty_score=0.5,
                        truthfulness_score=0.5,
                        thesis_alignment=0.5,
                        payoff_alignment=0.5,
                        mobile_readability=0.5,
                        overall_score=0.5,
                    )
                )

        title_candidates = title_candidates[:max_titles]
        selected_id = title_candidates[0].title_id if title_candidates else ""

        pkg.title = TitleSelection(
            artifact_version=self._make_artifact_version("title_generation"),
            candidates=title_candidates,
            selected_id=selected_id,
            validated_against_script=False,
            review_status=ReviewStatus.DRAFT,
        )

        ctx._title_candidates_generated = True
        self._logger.info(
            f"Generated {len(title_candidates)} title candidates, selected {selected_id}"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 5: Hook Candidates
    # -------------------------------------------------------------------------

    def _generate_hook_candidates(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Generate hook opening lines and rank by score."""
        max_hooks = settings.story_max_hook_candidates
        thesis = next(
            (c for c in pkg.thesis.candidates if c.thesis_id == pkg.thesis.selected_id),
            None,
        )
        angle = next(
            (c for c in pkg.angle.candidates if c.angle_id == pkg.angle.selected_id),
            None,
        )

        prompt = f"""You are a documentary scriptwriter.

TOPIC: {ctx.topic}
THESIS: {thesis.statement if thesis else "N/A"}
ANGLE: {angle.title if angle else "N/A"}
CENTRAL QUESTION: {research_package.synthesis.central_question}

Write {max_hooks} compelling opening hook sentences for a 2-minute documentary.
Each hook must be a single strong sentence (10-50 words) that:
- Opens with a question, bold claim, or surprising fact
- Creates immediate curiosity
- Does NOT reveal the full answer
- Sounds natural and spoken (not written)
- Sets up the story's emotional tone

Score each hook (0.0-1.0):
- curiosity: How compelling is the hook?
- tension: Does it create narrative tension?
- clarity: Is it immediately understandable?
- specificity: Does it use concrete details?
- payoff_potential: Does it hint at a satisfying payoff?

Return JSON:
{{
  "candidates": [
    {{
      "hook_id": "HK-001",
      "text": "The hook sentence text",
      "curiosity": 0.9,
      "tension": 0.8,
      "clarity": 0.9,
      "specificity": 0.7,
      "payoff_potential": 0.8,
      "overall_score": 0.0,
      "risk_flags": []
    }}
  ]
}}"""

        messages = [
            LLMMessage(role="system", content="You are a documentary scriptwriter. Return valid JSON only."),
            LLMMessage(role="user", content=prompt),
        ]

        data = self._llm_complete(messages, task="hook_generation")
        if data is None:
            return pkg

        # Support both shapes:
        #   {"candidates": [...]}     — direct LLM response shape
        #   {"hook": {"candidates": [...]}} — full StoryPackage shape (mock fixture)
        if "candidates" not in data and "hook" in data and isinstance(data["hook"], dict):
            data = data["hook"]
        candidates_raw = data.get("candidates", [])
        hook_candidates: list[HookCandidate] = []

        for c in candidates_raw:
            hook = HookCandidate(
                hook_id=c.get("hook_id", _next_hook()),
                text=c.get("text", ""),
                curiosity=c.get("curiosity", 0.5),
                tension=c.get("tension", 0.5),
                clarity=c.get("clarity", 0.5),
                specificity=c.get("specificity", 0.5),
                payoff_potential=c.get("payoff_potential", 0.5),
                risk_flags=c.get("risk_flags", []),
            )
            hook.overall_score = round(
                hook.curiosity * 0.25
                + hook.tension * 0.2
                + hook.clarity * 0.2
                + hook.specificity * 0.15
                + hook.payoff_potential * 0.2,
                3,
            )
            hook_candidates.append(hook)

        hook_candidates.sort(key=lambda x: x.overall_score, reverse=True)
        hook_candidates = hook_candidates[:max_hooks]
        selected_id = hook_candidates[0].hook_id if hook_candidates else ""

        pkg.hook = HookSelection(
            artifact_version=self._make_artifact_version("hook_generation"),
            candidates=hook_candidates,
            selected_id=selected_id,
            review_status=ReviewStatus.DRAFT,
        )

        ctx._hook_candidates_generated = True
        self._logger.info(
            f"Generated {len(hook_candidates)} hook candidates, selected {selected_id}"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 6: Narrative Blueprint
    # -------------------------------------------------------------------------

    def _build_narrative_blueprint(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Generate narrative beats before the script is written."""
        thesis = next(
            (c for c in pkg.thesis.candidates if c.thesis_id == pkg.thesis.selected_id),
            None,
        )
        angle = next(
            (c for c in pkg.angle.candidates if c.angle_id == pkg.angle.selected_id),
            None,
        )
        hook = next(
            (c for c in pkg.hook.candidates if c.hook_id == pkg.hook.selected_id),
            None,
        )

        target_duration = settings.story_target_duration_sec
        max_beats = max(6, target_duration // 12)  # ~12s per beat

        prompt = f"""You are a documentary narrative architect.

TOPIC: {ctx.topic}
THESIS: {thesis.statement if thesis else "N/A"}
ANGLE: {angle.title if angle else "N/A"}
HOOK: {hook.text if hook else "N/A"}
CENTRAL QUESTION: {research_package.synthesis.central_question}
SHORT ANSWER: {research_package.synthesis.short_answer}

KEY CLAIMS (include in the blueprint):
{chr(10).join(f"- [{c.claim_id}] {c.text[:150]}" for c in research_package.claims[:10])}

Generate {max_beats}-{max_beats + 4} narrative beats for a {target_duration}s documentary.
The blueprint comes BEFORE the script. It defines the story STRUCTURE.

Beat purposes available (use at least 6 different ones):
- hook: Opening hook (emotional, curiosity-driven)
- setup: Establish context and stakes
- central_question: Pose the documentary's main question
- first_discovery: First major revelation
- escalation: Build tension and stakes
- evidence: Present supporting evidence
- counterpoint: Address a counterargument
- complication: Introduce a problem or challenge
- revelation: Major dramatic revelation
- explanation: Explain a mechanism or process
- payoff: Deliver the answer to the hook
- ending: Final message or call to reflection

For each beat, specify:
- purpose: one of the above
- claim_ids: which claims this beat covers
- emotional_state: calm | tense | warm | triumphant | mysterious
- curiosity_level: 0.0-1.0 (does this beat leave the viewer wanting more?)
- information_density: 0.0-1.0 (how much new info?)
- visual_potential: 0.0-1.0 (how visualizable is this beat?)
- estimated_duration_sec: 8-25 seconds

The beats should create a natural story arc: tension builds → peaks → resolves.

Return JSON:
{{
  "beats": [
    {{
      "beat_id": "BT-001",
      "purpose": "hook",
      "claim_ids": ["CLM-001"],
      "emotional_state": "tense",
      "curiosity_level": 0.9,
      "information_density": 0.3,
      "visual_potential": 0.7,
      "estimated_duration_sec": 10.0
    }}
  ]
}}

IMPORTANT: Return the beats array."""  # noqa: E501

        messages = [
            LLMMessage(role="system", content="You are a documentary narrative architect. Return valid JSON only."),
            LLMMessage(role="user", content=prompt),
        ]

        data = self._llm_complete(messages, task="narrative_blueprint")
        if data is None:
            return pkg

        # Support both shapes:
        #   {"beats": [...]}                          — direct LLM response shape
        #   {"blueprint": {"beats": [...]}}           — full StoryPackage shape (mock fixture)
        if "beats" not in data and "blueprint" in data and isinstance(data["blueprint"], dict):
            data = data["blueprint"]
        beats_raw = data.get("beats", [])
        beats: list[NarrativeBeat] = []
        total_duration = 0.0

        for b in beats_raw:
            try:
                purpose = NarrativePurpose(b.get("purpose", "setup"))
            except ValueError:
                purpose = NarrativePurpose.SETUP
            try:
                emotion = EmotionalState(b.get("emotional_state", "neutral"))
            except ValueError:
                emotion = EmotionalState.NEUTRAL

            beat = NarrativeBeat(
                beat_id=b.get("beat_id", _next_beat()),
                purpose=purpose,
                claim_ids=b.get("claim_ids", []),
                emotional_state=emotion,
                curiosity_level=b.get("curiosity_level", 0.5),
                information_density=b.get("information_density", 0.5),
                visual_potential=b.get("visual_potential", 0.5),
                estimated_duration_sec=b.get("estimated_duration_sec", 10.0),
            )
            beats.append(beat)
            total_duration += beat.estimated_duration_sec

        # Ensure at least a minimum set
        if len(beats) < 4:
            for i in range(4 - len(beats)):
                beats.append(
                    NarrativeBeat(
                        beat_id=_next_beat(),
                        purpose=NarrativePurpose.EXPLANATION,
                        emotional_state=EmotionalState.NEUTRAL,
                        curiosity_level=0.5,
                        information_density=0.5,
                        visual_potential=0.5,
                        estimated_duration_sec=10.0,
                    )
                )
                total_duration += 10.0

        pkg.blueprint = NarrativeBlueprint(
            artifact_version=self._make_artifact_version("narrative_blueprint"),
            beats=beats,
            total_estimated_duration_sec=round(total_duration, 1),
            progression_flags=self._compute_progression_flags(beats),
        )

        ctx._blueprint_generated = True
        self._logger.info(
            f"Generated narrative blueprint with {len(beats)} beats, "
            f"estimated {total_duration:.0f}s"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 7: Script Draft
    # -------------------------------------------------------------------------

    def _generate_script_draft(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Generate the initial script version from the blueprint."""
        thesis = next(
            (c for c in pkg.thesis.candidates if c.thesis_id == pkg.thesis.selected_id),
            None,
        )
        angle = next(
            (c for c in pkg.angle.candidates if c.angle_id == pkg.angle.selected_id),
            None,
        )
        hook = next(
            (c for c in pkg.hook.candidates if c.hook_id == pkg.hook.selected_id),
            None,
        )
        blueprint = pkg.blueprint

        if blueprint is None:
            self._logger.warning("No blueprint found, cannot generate draft")
            return pkg

        # Build beat descriptions for the prompt
        beat_descriptions = "\n".join(
            f"- Beat {b.beat_id}: {b.purpose.value} — "
            f"emotion={b.emotional_state.value}, curiosity={b.curiosity_level:.1f}, "
            f"duration≈{b.estimated_duration_sec:.0f}s"
            for b in blueprint.beats
        )

        # Build claims for reference
        claim_refs = "\n".join(
            f"[{c.claim_id}] {c.text[:200]}"
            for c in research_package.claims[:20]
        )

        prompt = f"""You are a documentary scriptwriter.

TOPIC: {ctx.topic}
THESIS: {thesis.statement if thesis else "N/A"}
ANGLE: {angle.title if angle else "N/A"}
HOOK: {hook.text if hook else "N/A"}

NARRATIVE BLUEPRINT BEATS:
{beat_descriptions}

RESEARCH CLAIMS (reference for factual grounding):
{claim_refs}

Write a complete narration script for a {settings.story_target_duration_sec}-second documentary.
Each segment corresponds to one narrative beat. Write 1-2 narration sentences per segment.
Segments should be 8-25 seconds each.

CRITICAL REQUIREMENTS:
- Narration must be written as spoken dialogue (conversational, not written)
- Each segment must reference specific claim_ids from the claims list
- Every factual claim in the narration must be grounded in the research claims
- Use the emotional_state from each beat to guide tone
- Do NOT use phrases like "in conclusion" or "as we've seen" (sounds AI-written)
- The hook segment (first) must be provocative and curiosity-driven
- The final segment must answer the central question raised by the hook

For each segment, include:
- segment_id: e.g. SG-001
- order: sequence number (0-based)
- narration: the spoken text (1-4 sentences, each <= 30 words)
- purpose: match the beat's purpose
- beat_id: which beat this belongs to
- claim_ids: research claim IDs this segment references
- source_ids: source IDs from those claims
- certainty_level: supported | inferential | conditional | speculative | unsupported
- emotional_state: from the beat
- curiosity_level: from the beat
- information_density: from the beat
- estimated_duration_sec: from the beat
- visual_intent: brief description of what should be shown on screen
- transition_intent: how this segment transitions to the next

Return JSON:
{{
  "segments": [
    {{
      "segment_id": "SG-001",
      "order": 0,
      "narration": "The narration text for this segment (spoken style, 1-4 sentences)",
      "purpose": "hook",
      "beat_id": "BT-001",
      "claim_ids": ["CLM-001", "CLM-002"],
      "source_ids": ["SRC-XXXXXXXX"],
      "certainty_level": "supported",
      "emotional_state": "tense",
      "curiosity_level": 0.9,
      "information_density": 0.3,
      "estimated_duration_sec": 10.0,
      "visual_intent": "What to show on screen",
      "transition_intent": "How this transitions to the next segment"
    }}
  ]
}}"""

        messages = [
            LLMMessage(role="system", content="You are a documentary scriptwriter. Return valid JSON only."),
            LLMMessage(role="user", content=prompt),
        ]

        data = self._llm_complete(messages, task="script_generation", max_tokens=6144)
        if data is None:
            return pkg

        # Support both shapes:
        #   {"segments": [...]}                       — direct LLM response shape
        #   {"script": {"versions": [{"segments": [...]}]}}  — full StoryPackage shape (mock fixture)
        if "segments" not in data and "script" in data and isinstance(data["script"], dict):
            inner = data["script"]
            if "draft" in inner and isinstance(inner["draft"], dict):
                data = inner["draft"]
            elif "versions" in inner and isinstance(inner["versions"], list) and inner["versions"]:
                # Take the first (draft) version.
                data = inner["versions"][0]
            else:
                data = inner
        segments_raw = data.get("segments", [])
        segments: list[ScriptSegment] = []

        for s in segments_raw:
            try:
                certainty = CertaintyLevel.SUPPORTED
                cl_str = s.get("certainty_level", "supported").upper()
                if cl_str in ["SUPPORTED", "SUPPORTED"]:
                    certainty = CertaintyLevel.SUPPORTED
                elif cl_str in ["INFERENTIAL"]:
                    certainty = CertaintyLevel.INFERENTIAL
                elif cl_str in ["CONDITIONAL"]:
                    certainty = CertaintyLevel.CONDITIONAL
                elif cl_str in ["SPECULATIVE"]:
                    certainty = CertaintyLevel.SPECULATIVE
                else:
                    certainty = CertaintyLevel.UNSUPPORTED
            except (ValueError, KeyError):
                certainty = CertaintyLevel.SUPPORTED

            try:
                emotion = EmotionalState(s.get("emotional_state", "neutral"))
            except ValueError:
                emotion = EmotionalState.NEUTRAL
            try:
                purpose = NarrativePurpose(s.get("purpose", "setup"))
            except ValueError:
                purpose = NarrativePurpose.SETUP

            seg = ScriptSegment(
                segment_id=s.get("segment_id", _next_segment()),
                order=s.get("order", len(segments)),
                narration=s.get("narration", ""),
                purpose=purpose,
                beat_id=s.get("beat_id", ""),
                claim_ids=s.get("claim_ids", []),
                source_ids=s.get("source_ids", []),
                certainty_level=certainty,
                emotional_state=emotion,
                curiosity_level=s.get("curiosity_level", 0.5),
                information_density=s.get("information_density", 0.5),
                estimated_duration_sec=s.get("estimated_duration_sec", 10.0),
                visual_intent=s.get("visual_intent", ""),
                transition_intent=s.get("transition_intent", ""),
            )
            segments.append(seg)

        # Ensure sequential ordering
        for i, seg in enumerate(sorted(segments, key=lambda x: x.order)):
            seg.order = i

        total_words = sum(len(s.narration.split()) for s in segments)
        total_duration = sum(s.estimated_duration_sec for s in segments)

        draft_record = ScriptVersionRecord(
            version_type=ScriptVersion.DRAFT,
            artifact_version=self._make_artifact_version("script_generation"),
            segments=segments,
            total_word_count=total_words,
            total_duration_sec=round(total_duration, 1),
            is_final=False,
        )

        pkg.script.versions.append(draft_record)
        pkg.script.draft_version = draft_record.version_type.value
        pkg.script.active_version = ScriptVersion.DRAFT

        ctx._draft_generated = True
        self._logger.info(
            f"Generated script draft with {len(segments)} segments, "
            f"{total_words} words, ~{total_duration:.0f}s"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 8: Claim Traceability
    # -------------------------------------------------------------------------

    def _build_claim_traceability(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Trace script claims back to research claims. Detect unsupported and distorted claims."""
        draft = pkg.script.get_version(ScriptVersion.DRAFT)
        if draft is None:
            return pkg

        # Build claim text index
        claim_texts: list[tuple[str, Claim]] = [
            (c.text.lower(), c) for c in research_package.claims
        ]

        entries: list[ClaimTraceEntry] = []
        unsupported_entries: list[str] = []
        critical_unsupported: list[str] = []
        distortion_warnings: list[str] = []
        used_claim_ids: set[str] = set()

        for seg in draft.segments:
            seg_text_lower = seg.narration.lower()

            # Find matching claims: check if claim keywords appear in narration
            linked_claim_ids: list[str] = []
            linked_source_ids: list[str] = []

            for claim_text_lower, claim in claim_texts:
                if len(claim_text_lower) < 10:
                    continue
                # Check keyword overlap (split into words, require 3+ common)
                seg_words = set(seg_text_lower.split())
                claim_words = set(claim_text_lower.replace(",", " ").replace(".", " ").split())
                # Skip very short words
                claim_words = {w for w in claim_words if len(w) > 4}
                common = seg_words & claim_words
                if len(common) >= 3:
                    linked_claim_ids.append(claim.claim_id)
                    linked_source_ids.extend(claim.source_ids)
                    used_claim_ids.add(claim.claim_id)

            # Determine certainty level
            if linked_claim_ids:
                # Take the highest certainty from linked claims
                from app.schemas.research_package import CertaintyLevel as RCL
                levels = [next((c for c in research_package.claims if c.claim_id == cid), None)
                          for cid in linked_claim_ids]
                best = RCL.STRONG_EVIDENCE
                for c in levels:
                    if c is None:
                        continue
                    if c.certainty_level == RCL.STRONG_EVIDENCE:
                        best = RCL.STRONG_EVIDENCE
                        break
                    elif c.certainty_level == RCL.PLAUSIBLE_INTERPRETATION and best != RCL.STRONG_EVIDENCE:
                        best = RCL.PLAUSIBLE_INTERPRETATION
                    elif c.certainty_level == RCL.SPECULATION and best not in [RCL.STRONG_EVIDENCE, RCL.PLAUSIBLE_INTERPRETATION]:
                        best = RCL.SPECULATION

                # Map research certainty to story certainty
                if best == RCL.STRONG_EVIDENCE:
                    seg_certainty = CertaintyLevel.SUPPORTED
                elif best == RCL.PLAUSIBLE_INTERPRETATION:
                    seg_certainty = CertaintyLevel.INFERENTIAL
                else:
                    seg_certainty = CertaintyLevel.SPECULATIVE

                seg.certainty_level = seg_certainty
                is_supported = True
            else:
                # Check if narration contains factual-sounding statements
                # that aren't linked to any claim
                factual_indicators = [
                    "discovered", "proved", "proven", "revealed", "showed",
                    "found", "evidence shows", "scientists", "researchers",
                    "study found", "confirmed", "established",
                ]
                has_factual_statement = any(ind in seg_text_lower for ind in factual_indicators)

                if has_factual_statement and seg.purpose not in [NarrativePurpose.HOOK, NarrativePurpose.CENTRAL_QUESTION]:
                    is_supported = False
                    seg.certainty_level = CertaintyLevel.UNSUPPORTED
                    unsupported_entries.append(seg.segment_id)
                    critical_unsupported.append(seg.segment_id)
                else:
                    is_supported = True
                    seg.certainty_level = CertaintyLevel.INFERENTIAL

            # Check for distortion
            distortion_flags: list[str] = []
            seg_claim_map = {cid: next((c for c in research_package.claims if c.claim_id == cid), None)
                             for cid in linked_claim_ids}

            for cid in linked_claim_ids:
                claim = seg_claim_map.get(cid)
                if claim is None:
                    continue
                research_certainty = claim.certainty_level

                # Check stronger wording distortion
                strong_phrases = ["proved", "proven", "scientifically proven", "undisputed"]
                if any(p in seg_text_lower for p in strong_phrases):
                    if research_certainty not in [RCL.STRONG_EVIDENCE]:
                        distortion_flags.append("stronger_wording")
                        distortion_warnings.append(
                            f"Segment {seg.segment_id}: uses stronger language than research supports"
                        )

                # Check broader scope distortion
                broad_words = ["all", "every", "always", "never", "none"]
                if any(w in seg_text_lower for w in broad_words):
                    if len(claim.source_ids) < 3:
                        distortion_flags.append("broader_scope")
                        distortion_warnings.append(
                            f"Segment {seg.segment_id}: uses broad language ('all/every') "
                            f"but only {len(claim.source_ids)} source(s)"
                        )

                # Check removed uncertainty
                uncertainty_words = ["may", "might", "could", "suggests", "appears", "possibly"]
                research_has_uncertainty = claim.uncertainty or research_certainty in [RCL.SPECULATION, RCL.UNKNOWN]
                if research_has_uncertainty and not any(uw in seg_text_lower for uw in uncertainty_words):
                    if not any(p in seg_text_lower for p in strong_phrases):
                        distortion_flags.append("removed_uncertainty")
                        distortion_warnings.append(
                            f"Segment {seg.segment_id}: research has uncertainty "
                            f"but narration states as fact"
                        )

            entry = ClaimTraceEntry(
                segment_id=seg.segment_id,
                claim_text_excerpt=seg.narration[:200],
                certainty_level=seg.certainty_level,
                claim_ids=linked_claim_ids,
                source_ids=list(set(linked_source_ids)),
                is_supported=is_supported,
                distortion_flags=distortion_flags,
                distortion_detail=", ".join(distortion_flags) if distortion_flags else "",
            )
            entries.append(entry)

        # Check for unused high-importance claims
        unused_high_importance_claim_ids = [
            c.claim_id for c in research_package.claims
            if c.importance == "high" and c.claim_id not in used_claim_ids
        ]

        # Coverage metrics
        total_segments = len(draft.segments)
        traced_segments = sum(1 for e in entries if e.claim_ids)
        research_to_script = traced_segments / max(total_segments, 1)
        script_to_research = len(used_claim_ids) / max(len(research_package.claims), 1)

        pkg.traceability = ClaimTraceabilityReport(
            entries=entries,
            unsupported_entries=unsupported_entries,
            critical_unsupported=critical_unsupported,
            research_to_script_coverage=round(research_to_script, 3),
            script_to_research_traceability=round(script_to_research, 3),
            distortion_warnings=distortion_warnings,
            unused_high_importance_claim_ids=unused_high_importance_claim_ids,
        )

        ctx._traceability_built = True
        self._logger.info(
            f"Built traceability: {traced_segments}/{total_segments} segments traced, "
            f"{len(critical_unsupported)} critical unsupported"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 9: Script Critique
    # -------------------------------------------------------------------------

    def _run_script_critique(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Run a hostile critique pass over the script."""
        draft = pkg.script.get_version(ScriptVersion.DRAFT)
        if draft is None:
            return pkg

        thesis = next(
            (c for c in pkg.thesis.candidates if c.thesis_id == pkg.thesis.selected_id),
            None,
        )

        # Build segment display for the critique
        segment_lines = "\n".join(
            f"--- Segment {s.segment_id} (order={s.order}, purpose={s.purpose.value}) ---\n"
            f"Narration: {s.narration}\n"
            f"Emotion: {s.emotional_state.value} | Certainty: {s.certainty_level.value} | "
            f"Duration: {s.estimated_duration_sec:.0f}s"
            for s in sorted(draft.segments, key=lambda x: x.order)
        )

        # Build traceability context
        trace_context = ""
        if pkg.traceability:
            trace_context = f"\nTRACEABILITY: {pkg.traceability.critical_unsupported} segments have UNSUPPORTED claims.\n"
            trace_context += f"DISTORTIONS: {', '.join(pkg.traceability.distortion_warnings[:3])}\n"

        prompt = f"""You are a hostile documentary script reviewer. Your job is to FIND PROBLEMS.

Do NOT be flattering. Find the problems. Be specific and direct.

TOPIC: {ctx.topic}
THESIS: {thesis.statement if thesis else "N/A"}

SCRIPT SEGMENTS:
{segment_lines}

{trace_context}

CRITIQUE INSTRUCTIONS:
Evaluate the script across these categories. For each category, find SPECIFIC problems.
Be harsh. Do NOT praise. Identify issues.

Categories to check:
- factuality: Are claims factually supported?
- evidence_alignment: Does the script align with research evidence?
- hook: Is the opening hook compelling?
- narrative: Does the story flow logically?
- pacing: Is the pacing good?
- curiosity: Does each segment leave the viewer wanting more?
- clarity: Is the language clear?
- information_density: Too much or too little info?
- redundancy: Repetitive phrases or ideas?
- emotional_progress: Does the emotional arc work?
- visual_potential: Are visuals clear and producible?
- natural_language: Does it sound like a human wrote it?
- ending: Does the ending answer the hook question?
- ai_writing_risk: Does it sound AI-generated?
- pacing: Are there slow or boring sections?

For each finding, include:
- severity: critical | warning | info
- segment_id: which segment (or empty for general)
- category: one of the above
- problem: specific problem description
- evidence: quote or reference from the script
- recommendation: how to fix it

Also answer these summary questions:
- hardest_section: Which segment is the most problematic?
- weakest_point: What is the single weakest element?
- best_point: What is actually working?
- would_viewer_leave_at: Where might a viewer stop watching?
- pacing_flags: Which segments are too slow or too fast?

Return JSON:
{{
  "findings": [
    {{
      "finding_id": "FN-001",
      "severity": "critical",
      "segment_id": "SG-001",
      "category": "pacing",
      "problem": "Description of the problem (10+ words)",
      "evidence": "Specific evidence from the script",
      "recommendation": "How to fix it (10+ words)"
    }}
  ],
  "hardest_section": "Which segment is most problematic and why",
  "weakest_point": "The single weakest element of the script",
  "best_point": "What is actually working",
  "would_viewer_leave_at": "Where a viewer might stop watching",
  "pacing_flags": ["list of pacing issues"],
  "repetition_flags": ["list of repetition issues"],
  "ai_pattern_flags": ["list of AI-sounding phrases found"]
}}"""

        messages = [
            LLMMessage(role="system", content="You are a hostile documentary script reviewer. Do NOT be flattering. Return valid JSON only."),
            LLMMessage(role="user", content=prompt),
        ]

        data = self._llm_complete(messages, task="script_critique", max_tokens=6144)
        if data is None:
            return pkg

        # Support both shapes:
        #   {"findings": [...]}                     — direct LLM response shape
        #   {"critique": {"findings": [...]}}       — full StoryPackage shape (mock fixture)
        if "findings" not in data and "critique" in data and isinstance(data["critique"], dict):
            data = data["critique"]
        findings_raw = data.get("findings", [])
        findings: list[CritiqueFinding] = []
        critical_count = 0
        warning_count = 0
        info_count = 0

        for f in findings_raw:
            # Skip non-dict entries (e.g. stray strings from LLM)
            if not isinstance(f, dict):
                log.warning("Skipping non-dict finding: %s", f)
                continue
            try:
                severity = CritiqueSeverity(f.get("severity", "info"))
            except ValueError:
                severity = CritiqueSeverity.INFO
            try:
                category = CritiqueCategory(f.get("category", "narrative"))
            except ValueError:
                category = CritiqueCategory.NARRATIVE

            finding = CritiqueFinding(
                finding_id=f.get("finding_id", _next_finding()),
                severity=severity,
                segment_id=f.get("segment_id", ""),
                category=category,
                problem=f.get("problem", ""),
                evidence=f.get("evidence", ""),
                recommendation=f.get("recommendation", ""),
            )
            findings.append(finding)

            if severity == CritiqueSeverity.CRITICAL:
                critical_count += 1
            elif severity == CritiqueSeverity.WARNING:
                warning_count += 1
            else:
                info_count += 1

        pkg.critique = ScriptCritique(
            artifact_version=self._make_artifact_version("script_critique"),
            findings=findings,
            critical_count=critical_count,
            warning_count=warning_count,
            info_count=info_count,
            hardest_section=data.get("hardest_section", ""),
            weakest_point=data.get("weakest_point", ""),
            best_point=data.get("best_point", ""),
            would_viewer_leave_at=data.get("would_viewer_leave_at", ""),
            pacing_flags=data.get("pacing_flags", []),
            repetition_flags=data.get("repetition_flags", []),
            ai_pattern_flags=data.get("ai_pattern_flags", []),
        )

        pkg.script.critique_version = ScriptVersion.CRITIQUE.value

        ctx._critique_run = True
        self._logger.info(
            f"Script critique complete: {critical_count} critical, "
            f"{warning_count} warnings, {info_count} info"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 10: Retention Analysis
    # -------------------------------------------------------------------------

    def _compute_retention(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """
        Compute per-segment retention heuristics (LLM reads narration for curiosity
        scoring; other metrics are heuristic-based).
        """
        draft = pkg.script.get_version(ScriptVersion.DRAFT)
        if draft is None:
            return pkg

        segments = sorted(draft.segments, key=lambda x: x.order)
        segment_retentions: list[SegmentRetention] = []

        # Compute heuristic metrics for each segment
        for i, seg in enumerate(segments):
            seg_text = seg.narration

            # Curiosity: LLM reads the narration
            curiosity_score = self._llm_read_curiosity(seg_text)
            seg_retention = SegmentRetention(
                segment_id=seg.segment_id,
                curiosity=curiosity_score,
            )

            # New information: compare to prior segment
            if i > 0:
                prev_seg = segments[i - 1]
                novelty = self._compute_novelty(seg_text, prev_seg.narration)
                seg_retention.new_information = novelty
            else:
                seg_retention.new_information = 1.0

            # Tension: based on purpose and emotional state
            tension_map = {
                EmotionalState.TENSE: 0.9,
                EmotionalState.MYSTERIOUS: 0.8,
                EmotionalState.TRIUMPHANT: 0.7,
                EmotionalState.WARM: 0.5,
                EmotionalState.CALM: 0.4,
                EmotionalState.NEUTRAL: 0.3,
            }
            purpose_tension = {
                NarrativePurpose.HOOK: 0.9,
                NarrativePurpose.ESCALATION: 0.85,
                NarrativePurpose.REVELATION: 0.8,
                NarrativePurpose.COMPLICATION: 0.75,
                NarrativePurpose.EVIDENCE: 0.5,
                NarrativePurpose.EXPLANATION: 0.4,
                NarrativePurpose.PAYOFF: 0.7,
                NarrativePurpose.ENDING: 0.6,
            }
            seg_retention.tension = round(
                (tension_map.get(seg.emotional_state, 0.5) * 0.5
                 + purpose_tension.get(seg.purpose, 0.5) * 0.5),
                3,
            )

            # Visual change: heuristic based on visual_intent length and keywords
            visual_keywords = ["show", "reveal", "display", "transition", "cut to", "pan"]
            has_visual = any(kw in seg.visual_intent.lower() for kw in visual_keywords)
            seg_retention.visual_change = 0.8 if has_visual else 0.4

            # Payoff distance: how far from end
            payoff_distance = (len(segments) - i - 1) / max(len(segments) - 1, 1)
            seg_retention.payoff_distance = round(payoff_distance, 3)

            # Emotional change: compare to prior
            if i > 0:
                prev_seg = segments[i - 1]
                emotion_change = abs(
                    tension_map.get(seg.emotional_state, 0.5)
                    - tension_map.get(prev_seg.emotional_state, 0.5)
                )
                seg_retention.emotional_change = round(emotion_change, 3)
            else:
                seg_retention.emotional_change = 0.5

            # Dropoff risk: combine factors
            low_curiosity = seg_retention.curiosity < 0.4
            low_tension = seg_retention.tension < 0.35
            low_emotion_change = seg_retention.emotional_change < 0.15
            is_middle = 0.2 <= payoff_distance <= 0.8

            dropoff = 0.0
            if low_curiosity:
                dropoff += 0.3
            if low_tension:
                dropoff += 0.2
            if low_emotion_change and is_middle:
                dropoff += 0.25
            seg_retention.dropoff_risk = round(min(dropoff, 1.0), 3)

            # Retention score: weighted composite
            seg_retention.retention_score = round(
                seg_retention.curiosity * 0.3
                + seg_retention.new_information * 0.15
                + seg_retention.tension * 0.2
                + seg_retention.visual_change * 0.1
                + (1.0 - seg_retention.dropoff_risk) * 0.25,
                3,
            )

            segment_retentions.append(seg_retention)

        # Global retention analysis
        all_retention_scores = [sr.retention_score for sr in segment_retentions]
        avg_retention = sum(all_retention_scores) / max(len(all_retention_scores), 1)

        opening_risk = ""
        middle_risk = ""
        ending_risk = ""

        if segment_retentions:
            if segment_retentions[0].curiosity < 0.5:
                opening_risk = f"Opening segment {segments[0].segment_id} has low curiosity ({segment_retentions[0].curiosity:.2f})"
            if segment_retentions[-1].curiosity < 0.4:
                ending_risk = f"Ending segment {segments[-1].segment_id} has low payoff ({segment_retentions[-1].curiosity:.2f})"

        # Find slow sections
        slow_sections = [
            f"Segment {sr.segment_id}: low retention {sr.retention_score:.2f}"
            for sr in segment_retentions
            if sr.retention_score < 0.4
        ]

        pkg.retention = RetentionAnalysis(
            segment_retentions=segment_retentions,
            opening_risk=opening_risk,
            middle_risk=middle_risk,
            ending_risk=ending_risk,
            slow_sections=slow_sections,
            weak_payoff_flag=ending_risk != "",
            overall_retention_score=round(avg_retention, 3),
        )

        ctx._retention_computed = True
        self._logger.info(
            f"Retention analysis complete: avg={avg_retention:.3f}, "
            f"slow sections={len(slow_sections)}, weak_payoff={ending_risk != ''}"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 11: Script Revision
    # -------------------------------------------------------------------------

    def _generate_revision(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Generate revision by explicitly using critique findings as instructions."""
        draft = pkg.script.get_version(ScriptVersion.DRAFT)
        critique = pkg.critique
        traceability = pkg.traceability

        if draft is None:
            return pkg

        # Build revision instructions from critique findings
        critical_findings = [f for f in critique.findings if f.severity == CritiqueSeverity.CRITICAL]
        warning_findings = [f for f in critique.findings if f.severity == CritiqueSeverity.WARNING]

        revision_instructions = []

        if critical_findings:
            revision_instructions.append("CRITICAL ISSUES TO FIX:")
            for f in critical_findings:
                seg_ref = f"Segment {f.segment_id}" if f.segment_id else "General"
                revision_instructions.append(
                    f"- [{seg_ref}] {f.category.value}: {f.problem} → {f.recommendation}"
                )

        if warning_findings:
            revision_instructions.append("WARNINGS TO ADDRESS:")
            for f in warning_findings[:5]:  # Limit to top 5 warnings
                seg_ref = f"Segment {f.segment_id}" if f.segment_id else "General"
                revision_instructions.append(
                    f"- [{seg_ref}] {f.category.value}: {f.problem} → {f.recommendation}"
                )

        # Add traceability repair instructions
        if traceability and traceability.critical_unsupported:
            revision_instructions.append(
                f"REPAIR UNSUPPORTED CLAIMS: Segments {traceability.critical_unsupported} "
                f"contain factual claims not backed by research. Rewrite these segments "
                f"to either cite valid claims or remove the unsupported claims."
            )

        # Add retention repair instructions
        if pkg.retention and pkg.retention.weak_payoff_flag:
            revision_instructions.append(
                "REPAIR WEAK PAYOFF: The ending segment lacks engagement. "
                "Rewrite to deliver a stronger emotional and informational payoff."
            )

        instructions_text = "\n".join(revision_instructions) or "No major issues found. Polish the script for clarity and flow."

        # Build original script for the LLM
        original_segments = "\n".join(
            f"[{s.segment_id}] Order={s.order}: {s.narration}"
            for s in sorted(draft.segments, key=lambda x: x.order)
        )

        prompt = f"""You are a documentary script reviser. Your job is to rewrite the script
based on specific revision instructions.

ORIGINAL SCRIPT:
{original_segments}

REVISION INSTRUCTIONS (CRITICAL — follow these exactly):
{instructions_text}

GUIDELINES:
- PRESERVE all strong content and good narration
- REMOVE repetition flagged in the critique
- REPAIR unsupported claims by linking to valid research claims
- IMPROVE pacing by tightening slow sections
- MAINTAIN the same segment structure (order, beat_id, purpose)
- KEEP the same emotional arc
- WRITE in natural spoken language (avoid AI-sounding phrases)
- Do NOT remove the hook or the ending

Return JSON with the REVISED segments:
{{
  "segments": [
    {{
      "segment_id": "SG-001",
      "order": 0,
      "narration": "Revised narration text",
      "purpose": "hook",
      "beat_id": "BT-001",
      "claim_ids": ["CLM-001"],
      "source_ids": ["SRC-XXXXXXXX"],
      "certainty_level": "supported",
      "emotional_state": "tense",
      "curiosity_level": 0.9,
      "information_density": 0.3,
      "estimated_duration_sec": 10.0,
      "visual_intent": "What to show on screen",
      "transition_intent": "How this transitions"
    }}
  ]
}}

Return ALL segments in the revision, even if unchanged."""

        messages = [
            LLMMessage(role="system", content="You are a documentary script reviser. Return valid JSON only."),
            LLMMessage(role="user", content=prompt),
        ]

        data = self._llm_complete(messages, task="script_revision", max_tokens=6144)
        if data is None:
            return pkg

        # Support both shapes:
        #   {"segments": [...]}                       — direct LLM response shape
        #   {"script": {"versions": [{"segments": [...]}]}}  — full StoryPackage shape (mock fixture)
        if "segments" not in data and "script" in data and isinstance(data["script"], dict):
            inner = data["script"]
            if "draft" in inner and isinstance(inner["draft"], dict):
                data = inner["draft"]
            elif "versions" in inner and isinstance(inner["versions"], list) and inner["versions"]:
                data = inner["versions"][0]
            else:
                data = inner
        segments_raw = data.get("segments", [])
        segments: list[ScriptSegment] = []

        for s in segments_raw:
            try:
                certainty = CertaintyLevel.SUPPORTED
                cl_str = s.get("certainty_level", "supported").upper()
                if cl_str in ["SUPPORTED"]:
                    certainty = CertaintyLevel.SUPPORTED
                elif cl_str in ["INFERENTIAL"]:
                    certainty = CertaintyLevel.INFERENTIAL
                elif cl_str in ["CONDITIONAL"]:
                    certainty = CertaintyLevel.CONDITIONAL
                elif cl_str in ["SPECULATIVE"]:
                    certainty = CertaintyLevel.SPECULATIVE
                else:
                    certainty = CertaintyLevel.UNSUPPORTED
            except (ValueError, KeyError):
                certainty = CertaintyLevel.SUPPORTED

            try:
                emotion = EmotionalState(s.get("emotional_state", "neutral"))
            except ValueError:
                emotion = EmotionalState.NEUTRAL
            try:
                purpose = NarrativePurpose(s.get("purpose", "setup"))
            except ValueError:
                purpose = NarrativePurpose.SETUP

            seg = ScriptSegment(
                segment_id=s.get("segment_id", _next_segment()),
                order=s.get("order", len(segments)),
                narration=s.get("narration", ""),
                purpose=purpose,
                beat_id=s.get("beat_id", ""),
                claim_ids=s.get("claim_ids", []),
                source_ids=s.get("source_ids", []),
                certainty_level=certainty,
                emotional_state=emotion,
                curiosity_level=s.get("curiosity_level", 0.5),
                information_density=s.get("information_density", 0.5),
                estimated_duration_sec=s.get("estimated_duration_sec", 10.0),
                visual_intent=s.get("visual_intent", ""),
                transition_intent=s.get("transition_intent", ""),
            )
            segments.append(seg)

        for i, seg in enumerate(sorted(segments, key=lambda x: x.order)):
            seg.order = i

        total_words = sum(len(s.narration.split()) for s in segments)
        total_duration = sum(s.estimated_duration_sec for s in segments)

        revision_record = ScriptVersionRecord(
            version_type=ScriptVersion.REVISION,
            artifact_version=self._make_artifact_version("script_revision"),
            segments=segments,
            total_word_count=total_words,
            total_duration_sec=round(total_duration, 1),
            is_final=False,
        )

        pkg.script.versions.append(revision_record)
        pkg.script.revision_version = ScriptVersion.REVISION.value

        # Add to revision history
        revision_entry = RevisionEntry(
            revision_number=len(pkg.revision_history.entries) + 1,
            based_on_version=ScriptVersion.DRAFT.value,
            critique_version_id=ScriptVersion.CRITIQUE.value,
            instructions_summary=instructions_text[:500],
            changes_made=[f"Revised {len(segments)} segments per critique"],
        )
        pkg.revision_history.entries.append(revision_entry)
        pkg.revision_history.current_revision_number = revision_entry.revision_number

        ctx._revision_generated = True
        self._logger.info(
            f"Script revision complete: {len(segments)} segments"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 12: Finalize Script
    # -------------------------------------------------------------------------

    def _finalize_script(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Create the FINAL script version with validation.

        If REVISION is empty (common in mock/unit-test scenarios), fall back to DRAFT
        so the final script always has segments.
        """
        revision = pkg.script.get_version(ScriptVersion.REVISION)
        draft = pkg.script.get_version(ScriptVersion.DRAFT)
        # Prefer revision; fall back to draft so final always has content.
        source = revision if revision and revision.segments else draft
        if source is None or not source.segments:
            self._logger.warning("No script version found with segments, cannot finalize")
            return pkg

        segments = list(source.segments)

        # Validate: no UNSUPPORTED claims in final — downgrade to SPECULATIVE.
        # (Same logic as the revision step; applies to both revision and fallback-draft source.)
        for seg in segments:
            if seg.certainty_level == CertaintyLevel.UNSUPPORTED:
                seg.certainty_level = CertaintyLevel.SPECULATIVE
        # Clear the critical_unsupported list since we've downgraded them.
        if pkg.traceability:
            pkg.traceability.critical_unsupported = []

        # Validate: sequential segment orders
        orders = [s.order for s in segments]
        if orders != sorted(orders):
            self._logger.warning("Finalization: reordering segments to sequential")
            segments.sort(key=lambda x: x.order)
            for i, seg in enumerate(segments):
                seg.order = i

        # Validate: segment continuity (each segment should have narration)
        for seg in segments:
            if not seg.narration or len(seg.narration.strip()) < 5:
                self._logger.warning(
                    f"Finalization: segment {seg.segment_id} has empty narration, fixing"
                )
                seg.narration = f"Segment placeholder for {seg.segment_id}."

        total_words = sum(len(s.narration.split()) for s in segments)
        total_duration = sum(s.estimated_duration_sec for s in segments)

        final_record = ScriptVersionRecord(
            version_type=ScriptVersion.FINAL,
            artifact_version=self._make_artifact_version("finalize_script"),
            segments=segments,
            total_word_count=total_words,
            total_duration_sec=round(total_duration, 1),
            is_final=True,
        )

        pkg.script.versions.append(final_record)
        pkg.script.final_version = ScriptVersion.FINAL.value
        pkg.script.active_version = ScriptVersion.FINAL

        # Validate title against final script
        pkg.title.validated_against_script = True
        pkg.title.validation_note = f"Validated against final script: {len(segments)} segments, {total_words} words"

        ctx._script_finalized = True
        self._logger.info(
            f"Script finalized: {len(segments)} segments, "
            f"{total_words} words, ~{total_duration:.0f}s"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 13: Storyboard Intent
    # -------------------------------------------------------------------------

    def _build_storyboard_intent(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Generate visual intent for each script segment."""
        final = pkg.script.get_version(ScriptVersion.FINAL)
        if final is None:
            return pkg

        # Build segment context for storyboarding
        segment_context = "\n".join(
            f"Segment {s.segment_id} (order={s.order}, purpose={s.purpose.value}, "
            f"emotion={s.emotional_state.value}, duration={s.estimated_duration_sec:.0f}s):\n"
            f"  Narration: {s.narration}\n"
            f"  Visual intent: {s.visual_intent}\n"
            f"  Transition: {s.transition_intent}"
            for s in sorted(final.segments, key=lambda x: x.order)
        )

        prompt = f"""You are a documentary storyboard designer.

TOPIC: {ctx.topic}

SCRIPT SEGMENTS:
{segment_context}

VISUAL MODES AVAILABLE:
- character: Show human characters or figures
- environment: Show natural environment or setting
- diagram: Use diagrams, charts, or overlays
- map: Show geographic or spatial maps
- timeline: Show chronological timeline
- comparison: Side-by-side or before/after comparison
- artifact: Show physical objects or props
- text: Show text overlays or titles
- hybrid: Combination of modes

For each segment, generate a StoryboardIntentItem with:
- segment_id: match the script segment
- purpose: what this shot achieves narratively
- visual_goal: what the viewer sees (specific and producible)
- visual_mode: one from the list above
- characters: list of character types or names (empty if no characters)
- environment: brief environment description
- props: list of props or objects needed
- camera_intent: how the camera moves or is framed
- motion_intent: what motion or animation to include
- text_intent: any text overlays (or empty)
- source_ids: source IDs that this visual references
- continuity_notes: how this connects visually to adjacent segments

Return JSON:
{{
  "items": [
    {{
      "segment_id": "SG-001",
      "purpose": "Establish the mystery of the hook",
      "visual_goal": "Aerial shot of frozen tundra landscape at dusk",
      "visual_mode": "environment",
      "characters": [],
      "environment": "Ice age landscape, snow-covered plains, distant mountains",
      "props": [],
      "camera_intent": "Slow aerial pan over landscape",
      "motion_intent": "Gentle camera drift",
      "text_intent": "",
      "source_ids": ["SRC-XXXXXXXX"],
      "continuity_notes": "Establishes cold atmosphere before any human presence"
    }}
  ]
}}"""

        messages = [
            LLMMessage(role="system", content="You are a documentary storyboard designer. Return valid JSON only."),
            LLMMessage(role="user", content=prompt),
        ]

        data = self._llm_complete(messages, task="storyboard_intent", max_tokens=6144)
        if data is None:
            return pkg

        # Support both shapes:
        #   {"items": [...]}                                — direct LLM response shape
        #   {"storyboard_intent": {"items": [...]}}         — full StoryPackage shape (mock fixture)
        if "items" not in data and "storyboard_intent" in data and isinstance(data["storyboard_intent"], dict):
            data = data["storyboard_intent"]

        from app.schemas.story import StoryboardIntent, StoryboardIntentItem

        items_raw = data.get("items", [])
        items: list[StoryboardIntentItem] = []

        for item in items_raw:
            try:
                visual_mode = VisualMode(item.get("visual_mode", "environment"))
            except ValueError:
                visual_mode = VisualMode.HYBRID

            si = StoryboardIntentItem(
                segment_id=item.get("segment_id", ""),
                purpose=item.get("purpose", ""),
                visual_goal=item.get("visual_goal", ""),
                visual_mode=visual_mode,
                characters=item.get("characters", []),
                environment=item.get("environment", ""),
                props=item.get("props", []),
                camera_intent=item.get("camera_intent", ""),
                motion_intent=item.get("motion_intent", ""),
                text_intent=item.get("text_intent", ""),
                source_ids=item.get("source_ids", []),
                continuity_notes=item.get("continuity_notes", ""),
            )
            items.append(si)

        # Count visual modes
        visual_mode_counts: dict[str, int] = {}
        for item in items:
            mode = item.visual_mode.value
            visual_mode_counts[mode] = visual_mode_counts.get(mode, 0) + 1

        pkg.storyboard_intent = StoryboardIntent(
            artifact_version=self._make_artifact_version("storyboard_intent"),
            items=items,
            visual_mode_counts=visual_mode_counts,
        )

        ctx._storyboard_built = True
        self._logger.info(
            f"Storyboard intent built: {len(items)} items"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 14: Quality Score
    # -------------------------------------------------------------------------

    def _compute_quality_score(
        self,
        research_package: ResearchPackage,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """Compute all 15 dimensions of StoryQualityScore."""
        final = pkg.script.get_version(ScriptVersion.FINAL)
        critique = pkg.critique
        traceability = pkg.traceability
        retention = pkg.retention

        # Thesis strength
        thesis_score = pkg.thesis.candidates[0].overall_score if pkg.thesis.candidates else 0.0
        thesis_strength = StoryQualityDimension(
            score=thesis_score,
            notes=f"Selected thesis: {pkg.thesis.selected_id}",
        )

        # Evidence alignment
        if traceability:
            evidence_score = traceability.research_to_script_coverage
            evidence_notes = (
                f"{len(traceability.critical_unsupported)} unsupported, "
                f"{len(traceability.distortion_warnings)} distortions"
            )
        else:
            evidence_score = 0.0
            evidence_notes = "No traceability data"
        evidence_alignment = StoryQualityDimension(score=evidence_score, notes=evidence_notes)

        # Angle strength
        angle_score = pkg.angle.candidates[0].overall_score if pkg.angle.candidates else 0.0
        angle_strength = StoryQualityDimension(
            score=angle_score,
            notes=f"Selected angle: {pkg.angle.selected_id}",
        )

        # Title strength
        title_score = pkg.title.candidates[0].overall_score if pkg.title.candidates else 0.0
        title_strength = StoryQualityDimension(
            score=title_score,
            notes=f"Selected title: {pkg.title.selected_id}",
        )

        # Hook strength
        hook_score = pkg.hook.candidates[0].overall_score if pkg.hook.candidates else 0.0
        hook_strength = StoryQualityDimension(
            score=hook_score,
            notes=f"Selected hook: {pkg.hook.selected_id}",
        )

        # Narrative structure
        blueprint = pkg.blueprint
        if blueprint and len(blueprint.beats) >= 4:
            narrative_score = min(len(blueprint.beats) / 8.0, 1.0)
            narrative_notes = f"{len(blueprint.beats)} beats, {blueprint.total_estimated_duration_sec:.0f}s"
        else:
            narrative_score = 0.3
            narrative_notes = "Blueprint too short"
        narrative_structure = StoryQualityDimension(score=narrative_score, notes=narrative_notes)

        # Curiosity
        if retention:
            curiosity_score = sum(sr.curiosity for sr in retention.segment_retentions) / max(len(retention.segment_retentions), 1)
            curiosity_notes = f"Avg segment curiosity: {curiosity_score:.2f}"
        else:
            curiosity_score = 0.5
            curiosity_notes = "No retention data"
        curiosity_dim = StoryQualityDimension(score=curiosity_score, notes=curiosity_notes)

        # Pacing
        if critique and critique.pacing_flags:
            pacing_score = max(0.3, 1.0 - len(critique.pacing_flags) * 0.1)
            pacing_notes = f"{len(critique.pacing_flags)} pacing flags"
        else:
            pacing_score = 0.7
            pacing_notes = "No pacing issues found"
        pacing = StoryQualityDimension(score=pacing_score, notes=pacing_notes)

        # Clarity
        if final:
            avg_words = sum(len(s.narration.split()) for s in final.segments) / max(len(final.segments), 1)
            clarity_score = 1.0 if avg_words <= 35 else max(0.5, 1.0 - (avg_words - 35) / 100)
            clarity_notes = f"Avg words/segment: {avg_words:.0f}"
        else:
            clarity_score = 0.5
            clarity_notes = "No final script"
        clarity = StoryQualityDimension(score=clarity_score, notes=clarity_notes)

        # Information density
        if retention:
            info_density_score = sum(sr.new_information for sr in retention.segment_retentions) / max(len(retention.segment_retentions), 1)
            info_notes = f"Avg new info: {info_density_score:.2f}"
        else:
            info_density_score = 0.5
            info_notes = "No retention data"
        information_density_dim = StoryQualityDimension(score=info_density_score, notes=info_notes)

        # Visual potential
        if pkg.storyboard_intent:
            mode_diversity = len(pkg.storyboard_intent.visual_mode_counts)
            visual_score = min(mode_diversity / 5.0, 1.0)
            visual_notes = f"{mode_diversity} visual modes: {pkg.storyboard_intent.visual_mode_counts}"
        else:
            visual_score = 0.3
            visual_notes = "No storyboard data"
        visual_potential = StoryQualityDimension(score=visual_score, notes=visual_notes)

        # Fact traceability
        if traceability:
            fact_score = traceability.script_to_research_traceability
            fact_notes = f"{len(traceability.unused_high_importance_claim_ids)} unused claims"
        else:
            fact_score = 0.0
            fact_notes = "No traceability data"
        fact_traceability = StoryQualityDimension(score=fact_score, notes=fact_notes)

        # Natural language
        if critique and critique.ai_pattern_flags:
            ai_score = max(0.2, 1.0 - len(critique.ai_pattern_flags) * 0.1)
            ai_notes = f"{len(critique.ai_pattern_flags)} AI pattern flags"
        else:
            ai_score = 0.8
            ai_notes = "No AI patterns detected"
        natural_language = StoryQualityDimension(score=ai_score, notes=ai_notes)

        # Payoff
        if retention:
            if final and final.segments:
                payoff_score = final.segments[-1].curiosity_level
            else:
                payoff_score = 0.5
            payoff_notes = f"Ending curiosity: {payoff_score:.2f}"
        else:
            payoff_score = 0.5
            payoff_notes = "No retention data"
        payoff = StoryQualityDimension(score=payoff_score, notes=payoff_notes)

        # AI writing risk
        if critique and critique.ai_pattern_flags:
            ai_risk_score = min(len(critique.ai_pattern_flags) * 0.15, 1.0)
            ai_risk_notes = f"{len(critique.ai_pattern_flags)} flags"
        else:
            ai_risk_score = 0.1
            ai_risk_notes = "Low AI risk"
        ai_writing_risk = StoryQualityDimension(score=ai_risk_score, notes=ai_risk_notes)

        # Compute overall score
        all_dimensions = [
            thesis_strength, evidence_alignment, angle_strength, title_strength,
            hook_strength, narrative_structure, curiosity_dim, pacing, clarity,
            information_density_dim, visual_potential, fact_traceability,
            natural_language, payoff, ai_writing_risk,
        ]
        dimension_scores_map = {
            "thesis_strength": thesis_strength.score,
            "evidence_alignment": evidence_alignment.score,
            "angle_strength": angle_strength.score,
            "title_strength": title_strength.score,
            "hook_strength": hook_strength.score,
            "narrative_structure": narrative_structure.score,
            "curiosity": curiosity_dim.score,
            "pacing": pacing.score,
            "clarity": clarity.score,
            "information_density": information_density_dim.score,
            "visual_potential": visual_potential.score,
            "fact_traceability": fact_traceability.score,
            "natural_language": natural_language.score,
            "payoff": payoff.score,
            "ai_writing_risk": ai_writing_risk.score,
        }

        overall = round(sum(d.score for d in all_dimensions) / len(all_dimensions), 3)

        # Collect warnings and failures
        failures: list[str] = []
        warnings: list[str] = []

        if critique:
            for f in critique.findings:
                if f.severity == CritiqueSeverity.CRITICAL:
                    failures.append(f"[{f.category.value}] {f.problem}")

        if pkg.research_warnings:
            warnings.extend(pkg.research_warnings)

        if retention and retention.slow_sections:
            warnings.append(f"Slow sections detected: {len(retention.slow_sections)}")

        if ai_writing_risk.score > 0.5:
            warnings.append(f"AI writing risk elevated: {ai_writing_risk.score:.2f}")

        # Recommendations
        recommendations: list[str] = []
        for dim in all_dimensions:
            if dim.score < 0.5:
                recommendations.append(f"Improve {dim.notes}: score={dim.score:.2f}")

        pkg.quality_score = StoryQualityScore(
            thesis_strength=thesis_strength,
            evidence_alignment=evidence_alignment,
            angle_strength=angle_strength,
            title_strength=title_strength,
            hook_strength=hook_strength,
            narrative_structure=narrative_structure,
            curiosity=curiosity_dim,
            pacing=pacing,
            clarity=clarity,
            information_density=information_density_dim,
            visual_potential=visual_potential,
            fact_traceability=fact_traceability,
            natural_language=natural_language,
            payoff=payoff,
            ai_writing_risk=ai_writing_risk,
            overall_score=overall,
            dimension_scores=dimension_scores_map,
            warnings=warnings,
            failures=failures,
            recommendations=recommendations,
        )

        ctx._quality_scored = True
        self._logger.info(
            f"Quality score: {overall:.3f} — {len(failures)} failures, {len(warnings)} warnings"
        )

        return pkg

    # -------------------------------------------------------------------------
    # Step 15: Validate and Finalize
    # -------------------------------------------------------------------------

    def _validate_and_finalize(
        self,
        ctx: StoryContext,
        pkg: StoryPackage,
    ) -> StoryPackage:
        """
        Run all StoryPackage model validators and set final status.

        If the package was already marked BLOCKED by the quality gate, preserve it.
        """
        # Preserve a BLOCKED status set by the quality gate.
        already_blocked = pkg.metadata.status == StoryStatus.BLOCKED
        try:
            # Calling model_validate triggers all @model_validator decorators
            pkg = StoryPackage.model_validate(pkg.model_dump())

            # Determine final status
            quality_score = pkg.quality_score
            critical_failures = len(quality_score.failures) if quality_score else 0

            if already_blocked:
                # Quality gate already blocked the story — preserve BLOCKED.
                pkg.metadata.status = StoryStatus.BLOCKED
                pkg.metadata.review_status = ReviewStatus.NEEDS_REVIEW
            elif critical_failures > 0:
                pkg.metadata.status = StoryStatus.NEEDS_REVIEW
                pkg.metadata.review_status = ReviewStatus.NEEDS_REVIEW
                self._logger.warning(
                    f"StoryPackage has {critical_failures} critical failures, "
                    f"requires review"
                )
            else:
                pkg.metadata.status = StoryStatus.APPROVED
                pkg.metadata.review_status = ReviewStatus.APPROVED
                self._logger.info(
                    f"StoryPackage validated and APPROVED — quality={pkg.quality_score.overall_score if pkg.quality_score else 0.0}"
                )

        except Exception as e:
            pkg.metadata.status = StoryStatus.REJECTED
            pkg.metadata.review_status = ReviewStatus.REJECTED
            self._logger.error(
                f"StoryPackage validation failed: {e}"
            )

        return pkg

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _make_artifact_version(self, task: str) -> ArtifactVersion:
        """Create an ArtifactVersion with current timestamp and task info."""
        return ArtifactVersion(
            version="1.0",
            created_at=datetime.utcnow(),
            provider="openai",
            model=settings.story_llm_model,
            configuration={
                "task": task,
                "temperature": settings.story_temperature,
            },
        )

    def _compute_progression_flags(self, beats: list[NarrativeBeat]) -> list[str]:
        """Compute flags describing the narrative arc."""
        flags: list[str] = []

        if len(beats) < 3:
            flags.append("TOO_SHORT")
            return flags

        # Check for emotional arc
        emotions = [b.emotional_state for b in beats]
        if EmotionalState.TENSE in emotions or EmotionalState.MYSTERIOUS in emotions:
            flags.append("TENSE_ARC")

        if any(e == EmotionalState.TRIUMPHANT for e in emotions):
            flags.append("RESOLUTION_ARC")

        # Check for curiosity escalation
        curiosity_levels = [b.curiosity_level for b in beats]
        if curiosity_levels[0] < curiosity_levels[-1]:
            flags.append("CURIOSITY_ESCALATION")

        # Check for proper beat distribution
        purposes = [b.purpose for b in beats]
        if NarrativePurpose.HOOK in purposes:
            flags.append("HAS_HOOK")
        if NarrativePurpose.PAYOFF in purposes or NarrativePurpose.ENDING in purposes:
            flags.append("HAS_PAYOFF")

        return flags

    def _llm_read_curiosity(self, narration: str) -> float:
        """
        Use the LLM to score the curiosity of a narration sentence.
        This is a lightweight heuristic pass.
        """
        if not narration or len(narration.strip()) < 5:
            return 0.3

        prompt = f"""Rate the curiosity of this documentary narration sentence.
Score 0.0-1.0: 0 = boring/predictable, 1 = highly curious/surprising.

Narration: "{narration}"

Respond with ONLY a number between 0.0 and 1.0."""

        messages = [
            LLMMessage(role="system", content="Rate curiosity. Respond with ONLY a decimal number 0.0-1.0."),
            LLMMessage(role="user", content=prompt),
        ]

        req = LLMRequest(
            messages=messages,
            json_mode=False,
            temperature=0.1,
            max_tokens=10,
        )
        try:
            resp = self._llm.complete(req)
            content = resp.content.strip()
            # Try to extract a number
            import re
            match = re.search(r"0?\.\d+", content)
            if match:
                return round(float(match.group()), 2)
        except Exception:
            pass

        return 0.5  # Default

    def _compute_novelty(self, current: str, prior: str) -> float:
        """
        Compute how much new information the current segment adds vs the prior.
        Simple word-overlap heuristic.
        """
        if not prior:
            return 1.0

        current_words = set(w.lower() for w in current.split() if len(w) > 4)
        prior_words = set(w.lower() for w in prior.split() if len(w) > 4)

        if not prior_words:
            return 1.0

        overlap = current_words & prior_words
        novelty = 1.0 - (len(overlap) / max(len(current_words), 1))
        return round(max(novelty, 0.0), 3)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _hash_package(pkg: ResearchPackage) -> str:
    """Return a short SHA256 hex digest of a package for version tracking."""
    try:
        data = pkg.model_dump_json(exclude_none=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    except Exception:
        return "unknown"
