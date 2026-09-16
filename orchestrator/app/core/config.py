"""
Application configuration loaded from environment variables (and .env).

All downstream code should import `settings` from this module rather than
reading os.environ directly. This keeps env-var names documented in one
place and makes testing easier (override via env vars).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            # Try JSON list first, fall back to comma-separated
            v = v.strip()
            if v.startswith("["):
                import json as _json
                try:
                    parsed = _json.loads(v)
                    return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    # ----- Groq LLM (FREE) -----
    groq_api_key: str = ""
    groq_llm_model: str = "groq/compound-mini"

    # ----- OpenRouter LLM -----
    openrouter_api_key: str = ""
    openrouter_llm_model: str = "anthropic/claude-3-haiku"

    # ----- Gemini -----
    # Hỗ trợ rotate qua nhiều key: GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3, ...
    # Khi key chính hết quota/rate limit, tự động chuyển sang key tiếp theo.
    gemini_api_key: str = ""
    gemini_api_key_2: str = ""
    gemini_api_key_3: str = ""
    gemini_api_key_4: str = ""
    gemini_api_key_5: str = ""

    # ----- Cursor SDK (Modal) -----
    cursor_api_key: str = ""
    cursor_model: str = "composer-2.5"

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
    def has_groq(self) -> bool:
        return bool(self.groq_api_key.strip())

    @property
    def has_cursor(self) -> bool:
        return bool(self.cursor_api_key.strip())

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key.strip())

    @property
    def gemini_api_keys(self) -> list[str]:
        """Trả về danh sách Gemini keys theo thứ tự ưu tiên.
        Dùng cho rotation: key 1 hết quota → dùng key 2 → ..."""
        keys = [
            self.gemini_api_key,
            self.gemini_api_key_2,
            self.gemini_api_key_3,
            self.gemini_api_key_4,
            self.gemini_api_key_5,
        ]
        return [k.strip() for k in keys if k.strip()]

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_keys)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Import as `from app.core.config import settings`."""
    return Settings()


settings = get_settings()
