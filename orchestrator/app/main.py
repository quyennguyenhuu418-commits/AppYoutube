"""
FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assets, characters, jobs
from app.api.research import router as research_router
from app.api.story import router as story_router
from app.api.storyboard import router as storyboard_router
from app.api.render import router as render_router
from app.api.shorts_thumbnails import router as shorts_thumbnails_router
from app.api.publishing import router as publishing_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("videoAI orchestrator starting (env=%s, openai=%s, elevenlabs=%s)",
             settings.app_env, settings.has_openai, settings.has_elevenlabs)
    yield


app = FastAPI(
    title="AI Documentary Animation Factory",
    description=(
        "Backend orchestrator for AI-generated documentary videos. "
        "POST a topic to /jobs, then poll /jobs/{id} for progress."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(assets.router)
app.include_router(research_router)
app.include_router(story_router)
app.include_router(storyboard_router)
app.include_router(characters.router)
app.include_router(render_router)
app.include_router(shorts_thumbnails_router)
app.include_router(publishing_router)


@app.get("/health")
def health() -> dict:
    """Liveness check. Returns provider status so users can confirm
    whether they're in real or mock mode at a glance."""
    return {
        "status": "ok",
        "openai_configured": settings.has_openai,
        "groq_configured": settings.has_groq,
        "cursor_configured": settings.has_cursor,
        "elevenlabs_configured": settings.has_elevenlabs,
        "cache_mode": settings.cache_mode,
        "groq_model": settings.groq_llm_model,
    }
