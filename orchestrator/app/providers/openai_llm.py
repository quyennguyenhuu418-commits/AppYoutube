"""
OpenAI LLM provider.

Uses the official `openai` Python SDK. We request JSON output when the
prompt needs structured parsing downstream, otherwise plain text.

If `OPENAI_API_KEY` is missing, the factory in `llm.py` will substitute the
`MockLLMProvider` instead. This file does not need to handle that case.
"""
from __future__ import annotations

import json
import time

from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import LLMProvider, LLMRequest, LLMResponse

log = get_logger(__name__)


# System prompts the pipeline reuses. Keeping them here makes them easy to
# review and tweak without hunting through stage code.

SYSTEM_RESEARCH = """You are a meticulous research analyst. You gather verifiable
facts and cite real public sources. Avoid speculation. If you cannot find a
source for a claim, lower the confidence score and flag it."""


SYSTEM_SCRIPTWRITER = """You are a documentary scriptwriter inspired by the pacing
and curiosity-driven hooks of modern educational channels. Write in a
conversational, second-person ("you") tone. Keep sentences short. End each
section on a question or tension."""


SYSTEM_JSON_AGENT = """You are a precise JSON emitter. You always return a single
JSON object that matches the requested schema. Never wrap JSON in markdown
code fences. Never add commentary."""


SYSTEM_STORYBOARD = """You are a visual storyboard artist. You break a narration
script into 6-15 scenes. Each scene has a single visual idea and a clear
camera intent. Vary the camera (pan, zoom) so the video feels alive."""


SYSTEM_TITLES = """You are a YouTube title specialist. You write titles that are
curiosity-driven, concrete, and under 70 characters. You avoid clickbait
patterns like 'You won't believe'."""


class OpenAILLMProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.has_openai:
            raise RuntimeError(
                "OPENAI_API_KEY is not set; OpenAILLMProvider cannot be used."
            )
        self._client = OpenAI(api_key=settings.openai_api_key)

    def _model_for(self, hint: str | None) -> str:
        if hint == "large":
            return settings.openai_llm_model_large
        return settings.openai_llm_model

    def complete(self, request: LLMRequest) -> LLMResponse:
        model = self._model_for(request.model_hint)

        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        t0 = time.time()
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # network, auth, rate limit, ...
            log.error("OpenAI call failed after %.1fs: %s", time.time() - t0, exc)
            raise

        content = resp.choices[0].message.content or ""
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            "model": model,
            "elapsed_sec": round(time.time() - t0, 2),
        }
        parsed = None
        if request.json_mode:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                log.error("Failed to parse JSON from model: %s\nContent: %s", exc, content[:500])
                raise
        return LLMResponse(content=content, parsed_json=parsed, usage=usage)
