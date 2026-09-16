"""
LLM provider factory.

The pipeline never imports concrete providers directly; it calls
`get_llm_provider()` which returns the right one based on configuration.

Selection rules (priority order):
  1. Cursor SDK - dùng Modal của bạn (nếu có CURSOR_API_KEY)
  2. Groq - FREE, nhanh (mặc định)
  3. OpenAI - trả phí
  4. Mock - default fallback
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import LLMProvider
from app.providers.mock_llm import MockLLMProvider
from app.providers.openai_llm import OpenAILLMProvider
from app.providers.groq_llm import GroqLLMProvider

log = get_logger(__name__)


def get_cursor_agent():
    """Lazy import CursorAgentProvider - tránh import lỗi khi không dùng."""
    try:
        from app.providers.cursor_agent import CursorAgentProvider
        return CursorAgentProvider()
    except Exception as exc:
        log.debug("Cursor SDK provider not available: %s", exc)
    return None


def get_llm_provider() -> LLMProvider:
    """Trả về LLM provider. Ưu tiên Cursor SDK > Groq > OpenAI > Mock."""

    # 1. Cursor SDK (nếu có CURSOR_API_KEY)
    cursor_agent = get_cursor_agent()
    if cursor_agent and cursor_agent.is_available():
        log.info("Using Cursor SDK agent (your Modal).")
        return cursor_agent  # type: ignore

    # 2. Groq (FREE)
    if settings.has_groq:
        log.info("Using Groq LLM provider (FREE).")
        return GroqLLMProvider()

    # 3. OpenAI
    if settings.has_openai:
        log.info("Using OpenAI LLM provider.")
        return OpenAILLMProvider()

    # 4. Mock fallback
    log.warning("No LLM provider available; using MockLLMProvider (demo mode).")
    return MockLLMProvider()
