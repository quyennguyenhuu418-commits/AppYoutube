"""
Cursor SDK Provider - Dùng Modal Agent của Cursor.

⚠️ YÊU CẦU: CURSOR_API_KEY (lấy từ https://cursor.cursor.com/dashboard/integrations)

Tận dụng sức mạnh của Cursor agent (Claude Sonnet, GPT-5, Composer) để chạy
các task phức tạp như research, viết script, storyboard.

Cách dùng:
    from app.providers.cursor_agent import CursorAgentProvider
    provider = CursorAgentProvider()
    result = provider.research_topic("AI history")
"""
from __future__ import annotations

import os
import time
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class CursorAgentProvider:
    """
    Provider dùng Cursor SDK làm AI agent.

    Lợi thế:
    - Dùng được model mạnh nhất (Claude Sonnet, GPT-5 qua Cursor Modal)
    - Agent có thể tự search, đọc file, viết code
    - Phù hợp cho các task phức tạp cần planning nhiều bước

    Nhược điểm:
    - Cần CURSOR_API_KEY (lấy từ web dashboard)
    - Chậm hơn direct API call
    - Tốn request của user
    """

    name = "cursor_agent"

    def __init__(self) -> None:
        api_key = settings.cursor_api_key or os.environ.get("CURSOR_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "CURSOR_API_KEY is not set.\n"
                "Get one at: https://cursor.com/dashboard/integrations\n"
                "Then add to .env: CURSOR_API_KEY=cursor_xxxxxxxxxx"
            )

        # Lazy import - SDK rất nặng, chỉ load khi cần
        try:
            from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
        except ImportError as exc:
            raise RuntimeError(
                "cursor-sdk is not installed. Run: pip install cursor-sdk"
            ) from exc

        self._api_key = api_key
        self._model = settings.cursor_model or "composer-2.5"
        self._Agent = Agent
        self._AgentOptions = AgentOptions
        self._LocalAgentOptions = LocalAgentOptions

    def is_available(self) -> bool:
        """Kiểm tra xem có dùng được không."""
        return bool(self._api_key)

    def run_task(
        self,
        prompt: str,
        cwd: str | None = None,
        system_prompt: str | None = None,
        timeout_sec: int = 600,
    ) -> dict[str, Any]:
        """
        Chạy một task qua Cursor agent.

        Args:
            prompt: Yêu cầu chính
            cwd: Thư mục làm việc (mặc định: cwd hiện tại)
            system_prompt: System prompt bổ sung
            timeout_sec: Thời gian chờ tối đa

        Returns:
            dict với keys: status, result, agent_id, run_id
        """
        from cursor_sdk import CursorAgentError

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        t0 = time.time()
        log.info("Cursor agent starting task (model=%s)...", self._model)

        try:
            with self._Agent.create(
                api_key=self._api_key,
                model=self._model,
                local=self._LocalAgentOptions(cwd=cwd or os.getcwd()),
            ) as agent:
                run = agent.send(full_prompt)
                agent_id = getattr(agent, "agent_id", None) or getattr(agent, "agentId", None)
                run_id = getattr(run, "id", None)

                log.info("Agent=%s Run=%s", agent_id, run_id)

                # Stream output
                text_parts: list[str] = []
                try:
                    for event in run.messages():
                        if getattr(event, "type", None) == "assistant":
                            msg = getattr(event, "message", None)
                            if msg:
                                for block in getattr(msg, "content", []) or []:
                                    if getattr(block, "type", None) == "text":
                                        chunk = block.text or ""
                                        text_parts.append(chunk)
                                        print(chunk, end="", flush=True)
                except Exception as stream_exc:
                    log.warning("Stream warning (continuing): %s", stream_exc)

                print()  # newline
                result = run.wait()
                elapsed = time.time() - t0

                # Get final text
                try:
                    final_text = run.text()
                except Exception:
                    final_text = "".join(text_parts)

                log.info("Cursor agent finished in %.1fs status=%s", elapsed, result.status)

                return {
                    "status": result.status,
                    "result": final_text,
                    "agent_id": agent_id,
                    "run_id": run_id,
                    "elapsed_sec": elapsed,
                }

        except CursorAgentError as exc:
            log.error("Cursor agent failed to start: %s (retryable=%s)",
                      exc.message, getattr(exc, "is_retryable", None))
            raise RuntimeError(f"Cursor agent error: {exc.message}") from exc

    def research_topic(self, topic: str, depth: int = 3) -> dict[str, Any]:
        """Research một chủ đề bằng Cursor agent."""
        prompt = f"""Research the following topic thoroughly:

TOPIC: {topic}

Please provide:
1. A concise summary (3-5 sentences)
2. 5-10 key facts with citations (URLs)
3. Historical context and background
4. Current state of the topic
5. Interesting angles for a YouTube documentary

Be factual. Cite real sources. Use the internet if available.
"""
        return self.run_task(prompt, system_prompt="You are a research analyst.")

    def write_script(self, topic: str, research_summary: str, duration_sec: int = 120) -> dict[str, Any]:
        """Viết script video bằng Cursor agent."""
        prompt = f"""Write a YouTube documentary script.

TOPIC: {topic}
DURATION: {duration_sec} seconds (~{duration_sec // 60} minutes)
AUDIENCE: curious general viewers

RESEARCH SUMMARY:
{research_summary}

Requirements:
- Open with a strong hook (question, paradox, or surprising fact)
- Conversational, second-person ("you") tone
- Short sentences
- End each section on a question or tension
- Total word count: ~{duration_sec * 2} words
- Return the script as plain text, no markdown
"""
        return self.run_task(prompt, system_prompt="You are a documentary scriptwriter.")
