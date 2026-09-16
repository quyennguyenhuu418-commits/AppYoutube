"""
Gemini Provider - Google Gemini API với KEY ROTATION.

Tự động xoay vòng qua các key trong .env:
  GEMINI_API_KEY    (key 1 - ưu tiên cao nhất)
  GEMINI_API_KEY_2  (key 2 - khi key 1 hết quota)
  GEMINI_API_KEY_3  (key 3)
  GEMINI_API_KEY_4  (key 4)
  GEMINI_API_KEY_5  (key 5)

Mỗi lần gặp lỗi quota (429, RESOURCE_EXHAUSTED), sẽ chuyển sang key tiếp theo.
"""
from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


# Gemini API free tier quotas (per minute)
# Pro models: 2 req/min
# Flash models: 15 req/min
# Flash-Lite: 30 req/min


class GeminiRotatingProvider:
    """
    Google Gemini provider với auto-rotation qua nhiều API keys.

    Khi key chính bị rate-limited hoặc exhausted, tự động chuyển sang key tiếp theo.
    Nếu tất cả keys đều fail, raise exception.
    """

    name = "gemini"

    # Models đề xuất (Sep 2026)
    MODELS = {
        "flash": "gemini-3.6-flash",          # Flash mới nhất (Sep 2026)
        "pro": "gemini-3-pro",                # Pro mới nhất
        "flash_lite": "gemini-3.6-flash-lite", # Lite mới nhất
        "vision": "gemini-3.6-flash",         # Vision
        # Fallback cũ nếu 3.6 không khả dụng
        "flash_legacy": "gemini-2.5-flash",
        "pro_legacy": "gemini-2.5-pro",
    }

    def __init__(self, model: str | None = None) -> None:
        self._model = model or self.MODELS["flash"]
        self._keys = settings.gemini_api_keys
        self._key_index = 0
        self._error_count_per_key: dict[str, int] = {}

        if not self._keys:
            raise RuntimeError(
                "No Gemini API keys configured.\n"
                "Add to .env:\n"
                "  GEMINI_API_KEY=your_key\n"
                "  GEMINI_API_KEY_2=another_key (optional, for rotation)\n"
                "Get keys at: https://aistudio.google.com/apikey"
            )

        log.info("Gemini provider: %d key(s) configured, model=%s",
                 len(self._keys), self._model)

    def is_available(self) -> bool:
        return bool(self._keys)

    def _current_key(self) -> str:
        return self._keys[self._key_index % len(self._keys)]

    def _rotate_key(self, reason: str) -> None:
        """Chuyển sang key tiếp theo."""
        old_idx = self._key_index
        old_key = self._keys[old_idx]
        self._error_count_per_key[old_key] = self._error_count_per_key.get(old_key, 0) + 1

        if len(self._keys) > 1:
            self._key_index = (self._key_index + 1) % len(self._keys)
            log.warning("Rotating Gemini key: %d -> %d (reason: %s)",
                        old_idx, self._key_index, reason)
        else:
            log.error("Only 1 Gemini key, can't rotate (reason: %s)", reason)

    def generate(
        self,
        prompt: str,
        max_output_tokens: int = 1024,
        temperature: float = 0.7,
        image_data: bytes | None = None,
        image_mime: str = "image/png",
        max_retries: int | None = None,
    ) -> str:
        """
        Generate content. Tự động retry với key khác nếu fail.

        Args:
            prompt: Text prompt
            max_output_tokens: Giới hạn output
            temperature: 0.0 - 1.0
            image_data: Optional image bytes (cho vision)
            image_mime: image/png, image/jpeg, ...
            max_retries: Số lần retry (mặc định = số keys)

        Returns:
            Generated text
        """
        if max_retries is None:
            max_retries = len(self._keys)

        last_error: Exception | None = None

        for attempt in range(max_retries):
            key = self._current_key()
            try:
                return self._call_api(key, prompt, max_output_tokens, temperature,
                                      image_data, image_mime)
            except Exception as exc:
                last_error = exc
                err_str = str(exc).lower()

                # Detect quota/rate-limit errors
                if any(s in err_str for s in ["429", "quota", "rate", "exhaust", "resource"]):
                    self._rotate_key(f"quota: {str(exc)[:60]}")
                    time.sleep(1)  # Backoff
                    continue
                # Auth errors → don't retry
                elif "401" in err_str or "403" in err_str or "api key" in err_str:
                    if "invalid" in err_str or "expired" in err_str or "401" in err_str:
                        self._rotate_key(f"auth: {str(exc)[:60]}")
                        continue
                    else:
                        raise  # Permission denied, không phải rotate
                else:
                    # Unknown error → rotate anyway nếu còn key
                    self._rotate_key(f"unknown: {str(exc)[:60]}")
                    continue

        raise RuntimeError(f"All {len(self._keys)} Gemini keys failed. Last error: {last_error}")

    def _call_api(
        self,
        key: str,
        prompt: str,
        max_output_tokens: int,
        temperature: float,
        image_data: bytes | None,
        image_mime: str,
    ) -> str:
        """Call Gemini REST API directly."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"

        # Build parts
        parts: list[dict[str, Any]] = [{"text": prompt}]
        if image_data:
            parts.append({
                "inline_data": {
                    "mime_type": image_mime,
                    "data": base64.b64encode(image_data).decode("ascii"),
                }
            })

        body = {
            "contents": [{"parts": parts, "role": "user"}],
            "generationConfig": {
                "maxOutputTokens": max_output_tokens,
                "temperature": temperature,
            },
        }

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{url}?key={key}",
                json=body,
                headers={"Content-Type": "application/json"},
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Gemini API error {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        try:
            # Gemini 3.x trả về "thoughts" riêng (thinking mode) + content parts
            # Lấy text từ content parts (bỏ qua thoughts)
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"No candidates in Gemini response: {data}")
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            # Filter: chỉ lấy parts có "text" (bỏ thoughts)
            text_parts = [p["text"] for p in parts if "text" in p]
            if not text_parts:
                raise RuntimeError(
                    f"No text in Gemini response parts: {data}"
                )
            return "".join(text_parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected Gemini response: {data}") from exc

    def get_status(self) -> dict[str, Any]:
        """Trả về trạng thái rotation để debug."""
        return {
            "total_keys": len(self._keys),
            "current_key_index": self._key_index % len(self._keys) if self._keys else -1,
            "errors_per_key": dict(self._error_count_per_key),
            "model": self._model,
        }
