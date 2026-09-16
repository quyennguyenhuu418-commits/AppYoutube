"""
Orchestrator REST API entrypoint.

This stage exposes endpoints for the AI Documentary Animation Factory.
The Character System endpoints are mounted at /api/characters.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.assets import router as assets_router
from app.api.characters import router as characters_router
from app.api.jobs import router as jobs_router
from app.api.research import router as research_router
from app.api.story import router as story_router
from app.api.storyboard import router as storyboard_router
from app.api.render import router as render_router
from app.api.shorts_thumbnails import router as shorts_thumbnails_router
from app.api.publishing import router as publishing_router

router = APIRouter()
router.include_router(assets_router)
router.include_router(characters_router)
router.include_router(jobs_router)
router.include_router(research_router)
router.include_router(story_router)
router.include_router(storyboard_router)
router.include_router(render_router)
router.include_router(shorts_thumbnails_router)
router.include_router(publishing_router)

__all__ = [
    "router",
    "assets_router",
    "characters_router",
    "jobs_router",
    "research_router",
    "story_router",
    "storyboard_router",
    "render_router",
    "shorts_thumbnails_router",
    "publishing_router",
]
