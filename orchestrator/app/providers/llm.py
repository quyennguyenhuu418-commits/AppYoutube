"""
LLM provider factory.

The pipeline never imports concrete providers directly; it calls
`get_llm_provider()` which returns the right one based on configuration.

Selection rules:
  - If `OPENAI_API_KEY` is set -> OpenAI provider.
  - Otherwise -> Mock provider (still produces a full demo video).
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import LLMProvider
from app.providers.mock_llm import MockLLMProvider
from app.providers.openai_llm import OpenAILLMProvider

log = get_logger(__name__)


def get_llm_provider() -> LLMProvider:
    if settings.has_openai:
        log.info("Using OpenAI LLM provider.")
        return OpenAILLMProvider()
    log.warning("OPENAI_API_KEY not set; using MockLLMProvider (demo mode).")
    return MockLLMProvider()
