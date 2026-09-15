"""
Research API — inspect, review, and re-run research packages.

Provides read access to all research package sections plus human-review
endpoints for approving sources and flagging uncertain claims.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import job_dir
from app.schemas.research_package import (
    ResearchPackage,
    Source,
    Claim,
    Contradiction,
    ResearchQualityScore,
)

log = get_logger(__name__)
router = APIRouter(prefix="/research", tags=["research"])


def _load_package(job_id: str) -> ResearchPackage:
    """Load and validate a research package from disk."""
    path = job_dir(job_id) / "research_package.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Research package not found for job {job_id}")
    import json
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return ResearchPackage.model_validate(data)


# ---- Pydantic response models ----

class SourceResponse(BaseModel):
    sources: list[Source]
    total: int
    tier1_count: int
    tier2_count: int
    tier3_count: int
    tier4_count: int


class ClaimResponse(BaseModel):
    claims: list[Claim]
    total: int


class ContradictionResponse(BaseModel):
    contradictions: list[Contradiction]
    total: int


class QualityResponse(BaseModel):
    score: ResearchQualityScore
    warnings: list[str]


class ReviewRequest(BaseModel):
    approved: bool = True
    notes: str = ""


# ---- Endpoints ----

@router.get("/{job_id}/package", response_model=ResearchPackage)
def get_package(job_id: str) -> ResearchPackage:
    """Get the full research package."""
    return _load_package(job_id)


@router.get("/{job_id}/sources", response_model=SourceResponse)
def get_sources(job_id: str, tier: str | None = None, page: int = 1, page_size: int = 20) -> SourceResponse:
    """Get paginated source list with optional tier filter."""
    pkg = _load_package(job_id)
    sources = pkg.sources
    if tier:
        from app.schemas.research_package import SourceTier
        try:
            t = SourceTier(tier.upper())
            sources = [s for s in sources if s.tier == t]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tier: {tier}")

    total = len(sources)
    start = (page - 1) * page_size
    end = start + page_size
    page_sources = sources[start:end]

    from app.schemas.research_package import SourceTier
    return SourceResponse(
        sources=page_sources,
        total=total,
        tier1_count=sum(1 for s in pkg.sources if s.tier == SourceTier.TIER1),
        tier2_count=sum(1 for s in pkg.sources if s.tier == SourceTier.TIER2),
        tier3_count=sum(1 for s in pkg.sources if s.tier == SourceTier.TIER3),
        tier4_count=sum(1 for s in pkg.sources if s.tier == SourceTier.TIER4),
    )


@router.get("/{job_id}/claims", response_model=ClaimResponse)
def get_claims(
    job_id: str,
    claim_type: str | None = None,
    certainty: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ClaimResponse:
    """Get paginated claim list with optional filters."""
    pkg = _load_package(job_id)
    claims = pkg.claims

    if claim_type:
        from app.schemas.research_package import ClaimType
        try:
            ct = ClaimType(claim_type.lower())
            claims = [c for c in claims if c.claim_type == ct]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid claim_type: {claim_type}")

    if certainty:
        from app.schemas.research_package import CertaintyLevel
        try:
            cl = CertaintyLevel(certainty.upper())
            claims = [c for c in claims if c.certainty_level == cl]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid certainty: {certainty}")

    total = len(claims)
    start = (page - 1) * page_size
    end = start + page_size
    return ClaimResponse(claims=claims[start:end], total=total)


@router.get("/{job_id}/contradictions", response_model=ContradictionResponse)
def get_contradictions(job_id: str) -> ContradictionResponse:
    """Get all detected contradictions."""
    pkg = _load_package(job_id)
    return ContradictionResponse(
        contradictions=pkg.contradictions,
        total=len(pkg.contradictions),
    )


@router.get("/{job_id}/quality", response_model=QualityResponse)
def get_quality(job_id: str) -> QualityResponse:
    """Get quality score breakdown and warnings."""
    pkg = _load_package(job_id)
    return QualityResponse(
        score=pkg.quality_score,
        warnings=pkg.metadata.quality_warnings,
    )


@router.post("/{job_id}/review/sources/{source_id}", response_model=Source)
def review_source(job_id: str, source_id: str, req: ReviewRequest) -> Source:
    """Approve or reject a source (human review)."""
    pkg = _load_package(job_id)
    for source in pkg.sources:
        if source.id == source_id:
            source.reviewed = True
            source.approved = req.approved
            _save_package(job_id, pkg)
            log.info("[research] source %s reviewed: approved=%s", source_id, req.approved)
            return source
    raise HTTPException(status_code=404, detail=f"Source {source_id} not found")


@router.post("/{job_id}/review/claims/{claim_id}", response_model=Claim)
def review_claim(job_id: str, claim_id: str, req: ReviewRequest) -> Claim:
    """Flag uncertainty or approve a claim (human review)."""
    pkg = _load_package(job_id)
    for claim in pkg.claims:
        if claim.claim_id == claim_id:
            if not req.approved:
                from app.schemas.research_package import CertaintyLevel
                claim.certainty_level = CertaintyLevel.SPECULATION
                claim.uncertainty = req.notes or "Flagged uncertain by human reviewer"
            _save_package(job_id, pkg)
            log.info("[research] claim %s reviewed: approved=%s", claim_id, req.approved)
            return claim
    raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")


def _save_package(job_id: str, pkg: ResearchPackage) -> None:
    """Persist updated package to disk."""
    from app.core.paths import job_dir as _job_dir
    import json
    path = _job_dir(job_id) / "research_package.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(pkg.model_dump(), fh, ensure_ascii=False, indent=2)
