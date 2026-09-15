"""
Application configuration loaded from environment variables (and .env).

All downstream code should import `settings` from this module rather than
reading os.environ directly. This keeps env-var names documented in one
place and makes testing easier (override via env vars).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Repository root is the parent of the `orchestrator` directory. We use this
# to resolve relative paths declared in `.env` (e.g. WORKSPACE_DIR=./workspace).
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Strongly-typed configuration for the orchestrator.

    Field types and defaults below are the source of truth for what the
    system accepts. See `.env.example` for human-friendly descriptions.
    """

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- Core -----
    app_env: str = "dev"
    log_level: str = "INFO"

    # Paths are resolved against the repo root if relative.
    workspace_dir: Path = Field(default=Path("./workspace"))
    database_url: str = "sqlite:///./workspace/app.db"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, list):
            return [x.strip() for x in v if x.strip()]
        return [x.strip() for x in v.split(",") if x.strip()]

    # ----- OpenAI -----
    openai_api_key: str = ""
    openai_llm_model: str = "gpt-4o-mini"
    openai_llm_model_large: str = "gpt-4o"
    openai_image_model: str = "dall-e-3"

    # ----- ElevenLabs -----
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    # ----- Renderer -----
    renderer_dir: Path = Field(default=Path("./renderer"))
    renderer_entry: str = "npx tsx src/index.ts"

    # ----- Video defaults -----
    default_fps: int = 30
    default_width: int = 1920
    default_height: int = 1080
    target_duration_sec: int = 120

    # ----- Cache -----
    # 'always' (default), 'never', 'missing-only'
    cache_mode: str = "always"

    # ----- Research Engine -----
    research_max_sources: int = Field(default=50, ge=5, le=200)
    research_max_claims: int = Field(default=200, ge=10, le=500)
    research_stop_margin_gain: float = Field(default=0.05, ge=0.01, le=0.5)
    research_quality_min_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    research_llm_model: str = "gpt-4o"
    research_temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    research_cache_ttl_days: int = Field(default=7, ge=1, le=30)

    # ----- Story Engine -----
    story_llm_model: str = "gpt-4o"
    story_temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    story_research_min_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    story_max_thesis_candidates: int = Field(default=5, ge=3, le=20)
    story_max_angle_candidates: int = Field(default=6, ge=3, le=20)
    story_max_title_candidates: int = Field(default=25, ge=20, le=100)
    story_max_hook_candidates: int = Field(default=8, ge=5, le=20)
    story_target_duration_sec: int = 120

    # ----- Helpers -----
    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT

    @property
    def workspace_path(self) -> Path:
        p = self.workspace_dir
        if not p.is_absolute():
            p = (_REPO_ROOT / p).resolve()
        return p

    @property
    def renderer_path(self) -> Path:
        p = self.renderer_dir
        if not p.is_absolute():
            p = (_REPO_ROOT / p).resolve()
        return p

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Import as `from app.core.config import settings`."""
    return Settings()


settings = get_settings()
