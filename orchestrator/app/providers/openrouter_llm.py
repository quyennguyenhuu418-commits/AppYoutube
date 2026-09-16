"""
OpenRouter LLM Provider - Unified API for many models.

OpenRouter cung cấp quyền truy cập vào nhiều LLM qua 1 API.
Ưu điểm: rate limit cao hơn Groq cho input lớn, nhiều model khác nhau.

Docs: https://openrouter.ai/docs
"""
from __future__ import annotations

import json
import time

from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import LLMProvider, LLMRequest, LLMResponse

log = get_logger(__name__)


class OpenRouterLLMProvider(LLMProvider):
    name = "openrouter"

    # OpenRouter supported models (Sep 2026)
    # Claude 5 series mới nhất
    MODELS = {
        "small": "anthropic/claude-haiku-4.5",           # Fast, cheap (Sep 2026)
        "large": "anthropic/claude-sonnet-4.5",         # Strong reasoning (Sep 2026)
        "xlarge": "anthropic/claude-opus-4.5",          # Most capable (Sep 2026)
    }

    def __init__(self) -> None:
        api_key = settings.openrouter_api_key
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set; OpenRouterLLMProvider cannot be used.")

        self._client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )

    def _model_for(self, hint: str | None) -> str:
        """Map hint to OpenRouter model."""
        if hint == "xlarge":
            return self.MODELS["xlarge"]
        if hint == "large":
            return self.MODELS["large"]
        return settings.openrouter_llm_model or self.MODELS["small"]

    def complete(self, request: LLMRequest) -> LLMResponse:
        model = self._model_for(request.model_hint)
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        # OpenRouter supports JSON mode for some models
        if request.json_mode and "claude" in model:
            # Claude uses different mechanism - just instruct in prompt
            pass

        t0 = time.time()
        max_retries = 3
        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                break
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                if "429" in err_str or "rate" in err_str or "503" in err_str:
                    wait = min(2 ** attempt, 30)
                    log.warning("OpenRouter %s (attempt %d/%d) — retry in %ds",
                                exc, attempt + 1, max_retries, wait)
                    time.sleep(wait)
                    continue
                log.error("OpenRouter call failed after %.1fs: %s", time.time() - t0, exc)
                raise
        else:
            log.error("OpenRouter call failed after %d retries: %s", max_retries, last_exc)
            raise last_exc

        content = resp.choices[0].message.content or ""
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            "model": model,
            "elapsed_sec": round(time.time() - t0, 2),
        }
        parsed = None
        if request.json_mode:
            # OpenRouter có thể trả JSON trong content - parse manually
            text = content.strip()
            # Strip markdown fences nếu có
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                log.warning("OpenRouter JSON parse failed: %s", exc)

        return LLMResponse(content=content, parsed_json=parsed, usage=usage)
