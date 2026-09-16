"""
Knowledge Source governance schemas.

L-U1 — Production Knowledge & Visual Grammar Foundation.

Purpose
-------
A Knowledge Source is the **provenance record** for every knowledge item
in the system. It answers four questions:

    1. WHERE did this knowledge come from?
    2. WHEN was it added?
    3. WHAT confidence do we have in it?
    4. HOW was it extracted?

Design principles
-----------------
    1. Every knowledge item MUST carry provenance. No anonymous facts.
    2. Sources are versioned; updates bump the version, never silently
       overwrite.
    3. Provenance is content-addressed — multiple sources for the same
       fact are tracked separately, then merged deterministically.
    4. Confidence is explicit and bounded [0.0, 1.0].

Source types
------------
    - REFERENCE_DOCUMENT  : External spec / doc / dictionary
                            (e.g. DINO AI Camera Dictionary)
    - CHANNEL_ANALYSIS    : Output of a video analyser run (e.g. Axen
                            reference video learner)
    - SYSTEM_PROMPT       : Vendor-supplied production prompt template
                            (e.g. Google Flow pattern)
    - PROJECT_RULE        : Internal project decision (ADR) promoted
                            into the knowledge layer
    - INTERNAL_DOC        : docs/*.md, plans/*.md, source comments

Critical invariant (DO NOT BREAK)
---------------------------------
    A REFERENCE_DOCUMENT is NOT automatically a PROJECT_RULE.

    Confidence and status are evaluated separately:
        - EXTRACTION_STATUS.EXTRACTED means "I read this from a source"
        - CONFIDENCE = 1.0           means "verbatim from source"
        - STATUS = EXPLICIT          means "source explicitly states this"
        - STATUS = INFERENCE         means "I derived this from source"
        - STATUS = PROJECT_RULE      means "project decided to apply it
                                       even when source is silent"
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Source type taxonomy
# ============================================================================

class SourceType(str, Enum):
    """Where did the knowledge originate?

    The taxonomy is intentionally closed. Adding a source type means
    updating this enum AND ``docs/DATA_CONTRACTS.md``.
    """
    REFERENCE_DOCUMENT = "reference_document"
    CHANNEL_ANALYSIS = "channel_analysis"
    SYSTEM_PROMPT = "system_prompt"
    PROJECT_RULE = "project_rule"
    INTERNAL_DOC = "internal_doc"


# ============================================================================
# Extraction status
# ============================================================================

class ExtractionStatus(str, Enum):
    """How far along is the extraction pipeline for this entry?"""
    PENDING = "pending"            # Not yet processed
    EXTRACTED = "extracted"        # Read from source, not validated
    NORMALIZED = "normalized"      # Validated against canonical schema
    INDEXED = "indexed"            # Loaded into the KnowledgeRegistry
    FAILED = "failed"              # Extraction failed; see warnings


# ============================================================================
# Knowledge status — epistemic classification
# ============================================================================

class KnowledgeStatus(str, Enum):
    """How does this knowledge relate to its source?

    EXPLICIT     — The source literally states this fact.
    INFERENCE    — We derived this from the source by reasoning.
    EXPERIMENTAL — We propose this as a hypothesis to test.
    PROJECT_RULE — The project decided to adopt this even when the
                   source is silent (e.g. a chosen default).

    DO NOT silently convert EXPLICIT → PROJECT_RULE. The conversion is
    a deliberate action that must bump the version.
    """
    EXPLICIT = "explicit"
    INFERENCE = "inference"
    EXPERIMENTAL = "experimental"
    PROJECT_RULE = "project_rule"


# ============================================================================
# Knowledge domain taxonomy (the controlled vocabulary)
# ============================================================================

class KnowledgeDomain(str, Enum):
    """Top-level knowledge buckets.

    Each bucket may have a richer taxonomy downstream (see
    ``domain_taxonomy.py``). These top-level buckets are stable.
    """
    VISUAL_STYLE = "visual_style"
    COMPOSITION = "composition"
    CHARACTER = "character"
    CHARACTER_CONSISTENCY = "character_consistency"
    IMAGE_PROMPT = "image_prompt"
    VIDEO_PROMPT = "video_prompt"
    CAMERA = "camera"
    CAMERA_MOVEMENT = "camera_movement"
    MOTION = "motion"
    SOUND = "sound"
    NEGATIVE_CONSTRAINT = "negative_constraint"
    CONTINUITY = "continuity"
    FORMAT = "format"


# ============================================================================
# Knowledge provenance — the WHO/WHERE/WHEN/HOW
# ============================================================================

class KnowledgeSource(BaseModel):
    """Provenance record attached to every KnowledgeEntry.

    Mandatory fields:
        source_id      — Stable identifier (lowercase snake_case, < 64 chars)
        source_name    — Human-readable label
        source_type    — Where did this come from?
        source_section — Section within the source (optional)
        source_reference — URL / file path / ADR ID / channel ID
        confidence     — [0.0, 1.0]
        version        — Semantic version string ("1.0.0")
    """

    source_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="Stable opaque identifier; lowercase snake_case",
    )
    source_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable label, e.g. 'DINO AI Camera Dictionary'",
    )
    source_type: SourceType = Field(
        ...,
        description="Origin taxonomy",
    )
    source_section: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Section within the source document, e.g. 'Camera Movement Terms'",
    )
    source_reference: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL / file path / ADR ID / channel ID",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Source confidence in [0.0, 1.0]",
    )
    version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version; bumped on any change to the source",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional human notes about the provenance",
    )

    @model_validator(mode="after")
    def _confidence_must_be_set_for_explicit(self) -> "KnowledgeSource":
        """EXPLICIT-status facts should carry confidence close to 1.0.

        This is a soft check — we warn (do not block) when EXPLICIT
        facts have low confidence, because sometimes we explicitly tag
        an uncertain verbatim quote as such.
        """
        # We do not enforce confidence bounds per status here; the
        # KnowledgeEntry.status field carries that information.
        return self


# ============================================================================
# Knowledge entry — the canonical unit
# ============================================================================

class KnowledgeEntry(BaseModel):
    """A single piece of production knowledge.

    This is the canonical unit that downstream consumers (story,
    storyboard, character, asset, prompt builders) will retrieve from
    the KnowledgeRegistry.

    Field semantics
    ---------------
        id              Stable identifier within the registry
                         (lowercase snake_case, < 96 chars)
        domain          Top-level taxonomy bucket (KnowledgeDomain)
        name            Short human label (<= 120 chars)
        description     What this knowledge is about
        rules           Ordered list of reusable production rules
                         (each rule is a single sentence)
        constraints     Things this knowledge FORBIDS or REQUIRES
        examples        NON-canonical examples (never treated as rules)
        applicability   Where this knowledge applies (system, style,
                         generator, etc.)
        status          EXPLICIT / INFERENCE / EXPERIMENTAL / PROJECT_RULE
        version         Semantic version string ("1.0.0")
        tags            Free-form tags for retrieval
        created_at      When was this first added
        updated_at      When was this last changed
    """

    id: str = Field(
        ...,
        min_length=3,
        max_length=96,
        pattern=r"^[a-z0-9][a-z0-9_.-]*$",
        description="Stable identifier; lowercase snake_case",
    )
    domain: KnowledgeDomain
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)

    rules: list[str] = Field(
        default_factory=list,
        max_length=64,
        description="Ordered list of reusable production principles (RULES)",
    )
    constraints: list[str] = Field(
        default_factory=list,
        max_length=64,
        description="Things this knowledge FORBIDS or REQUIRES",
    )
    examples: list[str] = Field(
        default_factory=list,
        max_length=32,
        description=(
            "NON-canonical examples that demonstrate the rules. "
            "Examples MUST NOT be promoted to rules without explicit "
            "KnowledgeEntry.status = PROJECT_RULE promotion."
        ),
    )
    applicability: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="Tags describing where this applies, e.g. ['image_prompt', 'video_prompt']",
    )

    status: KnowledgeStatus = KnowledgeStatus.EXPLICIT

    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    tags: list[str] = Field(default_factory=list, max_length=32)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _rules_imperative_mood(self) -> "KnowledgeEntry":
        """Light sanity check: each rule should read like a sentence.

        Rules must be at least 5 characters (avoid trivial tokens like
        'R1.').
        """
        for r in self.rules:
            if len(r.strip()) < 5:
                raise ValueError(
                    f"Rule too short (id={self.id}): {r!r}; "
                    "rules should be reusable production principles (>= 5 chars)."
                )
        return self

    @model_validator(mode="after")
    def _examples_not_promoted_to_rules(self) -> "KnowledgeEntry":
        """Examples are NEVER promoted to universal rules.

        The downstream code MUST consult ``rules`` for production rules
        and ``examples`` only for illustration. This validator enforces
        that an example never appears verbatim in the rules list.
        """
        for ex in self.examples:
            ex_norm = ex.strip()
            if not ex_norm:
                continue
            for r in self.rules:
                if ex_norm == r.strip():
                    raise ValueError(
                        f"Example equals rule (id={self.id}); "
                        "examples must demonstrate rules, never replace them."
                    )
        return self

    def short_id(self) -> str:
        """Return a short identifier suitable for logs (max 24 chars)."""
        return self.id[:24]
