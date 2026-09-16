"""
Groq LLM Provider - Miễn phí, nhanh!

Groq API tương thích với OpenAI SDK format.
Docs: https://console.groq.com/docs/models
"""
from __future__ import annotations

import json
import time

from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import LLMProvider, LLMRequest, LLMResponse

log = get_logger(__name__)


class GroqLLMProvider(LLMProvider):
    name = "groq"

    # Groq supported models (free tier, Sep 2026)
    # NOTE: gpt-oss-120b hỗ trợ 65k output tokens (vs qwen chỉ ~1k/min TPM)
    MODELS = {
        "small": "groq/compound-mini",        # Fast chat, 30 RPM
        "large": "openai/gpt-oss-120b",         # Reasoning, 65k output tokens, 30 RPM
    }

    def __init__(self) -> None:
        api_key = settings.groq_api_key
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set; GroqLLMProvider cannot be used.")

        self._client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"  # Groq endpoint
        )

    def _model_for(self, hint: str | None) -> str:
        """Map hint to Groq model."""
        if hint == "large":
            return self.MODELS["large"]
        return settings.groq_llm_model or self.MODELS["small"]

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
        # Retry với exponential backoff khi gặp 429 (rate limit / TPM)
        max_retries = 5
        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                break  # Success
            except Exception as exc:
                last_exc = exc
                err_str = str(exc)
                # Retry cho 429 (rate limit) và 5xx (server error)
                if "429" in err_str or "rate_limit" in err_str or "503" in err_str or "502" in err_str:
                    # Parse retry-after nếu có
                    wait = min(2 ** attempt, 30)  # 1s, 2s, 4s, 8s, 16s
                    log.warning(
                        "Groq %s (attempt %d/%d) — retrying in %ds",
                        exc, attempt + 1, max_retries, wait
                    )
                    time.sleep(wait)
                    continue
                # Các lỗi khác (400, 401, 404, ...) → không retry
                log.error("Groq call failed after %.1fs: %s", time.time() - t0, exc)
                raise
        else:
            # Hết retries
            log.error("Groq call failed after %d retries: %s", max_retries, last_exc)
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
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                log.warning("JSON parse failed: %s", exc)

        return LLMResponse(content=content, parsed_json=parsed, usage=usage)
