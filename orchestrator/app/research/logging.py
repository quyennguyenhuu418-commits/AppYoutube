"""
Structured logging for the Research Engine.

Provides research_log() — a helper that emits a consistent JSON log entry
with research-specific fields: source_count, claim_count, stage, duration, etc.

Logs are written both to stdout (via the standard logger) and to
workspace/{job_id}/research.log for persistence.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings


class ResearchLogger:
    """
    Structured logger that writes research events to both stdout and a
    workspace file. Each entry is a single-line JSON object.
    """

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self._file_path = settings.workspace_path / job_id / "research.log"
        self._logger = logging.getLogger(f"research.{job_id}")
        # Ensure parent dir exists
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    def _emit(
        self,
        level: str,
        message: str,
        *,
        stage: str = "",
        query: str | None = None,
        source_count: int | None = None,
        claim_count: int | None = None,
        duration_sec: float | None = None,
        errors: str | None = None,
        retry_count: int | None = None,
        provider: str | None = None,
        model: str | None = None,
        token_count: int | None = None,
        **metadata: Any,
    ) -> None:
        """Construct and write a JSON log entry."""
        entry: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.upper(),
            "job_id": self.job_id,
            "message": message,
        }
        # Only include fields that are non-None
        for name, val in [
            ("stage", stage),
            ("query", query),
            ("source_count", source_count),
            ("claim_count", claim_count),
            ("duration_sec", duration_sec),
            ("errors", errors),
            ("retry_count", retry_count),
            ("provider", provider),
            ("model", model),
            ("token_count", token_count),
        ]:
            if val is not None:
                entry[name] = val
        if metadata:
            entry["metadata"] = metadata

        line = json.dumps(entry, ensure_ascii=False)

        # Write to file
        try:
            with open(self._file_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass  # Non-fatal

        # Emit to stdout logger
        std_level = getattr(logging, level.upper(), logging.INFO)
        self._logger.log(std_level, line)

    # Convenience methods

    def debug(self, message: str, **kwargs: Any) -> None:
        self._emit("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._emit("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._emit("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._emit("ERROR", message, **kwargs)

    # Named stage log helpers

    def question_decomposition(self, count: int, duration_sec: float) -> None:
        self.info(
            "Question decomposition complete",
            stage="question_decomposition",
            claim_count=count,
            duration_sec=round(duration_sec, 2),
        )

    def search_complete(self, query: str, count: int, duration_sec: float) -> None:
        self.info(
            f"Search complete: {count} results for '{query}'",
            stage="search",
            query=query,
            source_count=count,
            duration_sec=round(duration_sec, 2),
        )

    def fetch_complete(self, url: str, success: bool, duration_sec: float) -> None:
        self.info(
            f"Fetch {'ok' if success else 'failed'}: {url[:80]}",
            stage="fetch",
            query=url,
            source_count=1 if success else 0,
            duration_sec=round(duration_sec, 2),
        )

    def deduplication_complete(self, before: int, after: int) -> None:
        self.info(
            f"Deduplication: {before} raw → {after} unique sources",
            stage="deduplication",
            source_count=before,
        )

    def claims_extracted(self, source_title: str, count: int, duration_sec: float) -> None:
        self.info(
            f"Extracted {count} claims from '{source_title[:60]}'",
            stage="claim_extraction",
            claim_count=count,
            duration_sec=round(duration_sec, 2),
        )

    def contradictions_found(self, count: int) -> None:
        self.info(
            f"Found {count} contradictions",
            stage="contradiction_detection",
            claim_count=count,
        )

    def synthesis_complete(self, duration_sec: float, quality_score: float | None = None) -> None:
        self.info(
            "Synthesis complete",
            stage="synthesis",
            duration_sec=round(duration_sec, 2),
            metadata={"quality_score": quality_score} if quality_score else {},
        )

    def quality_score(self, overall: float, warnings: list[str]) -> None:
        self.info(
            f"Quality score: {overall:.3f}",
            stage="quality_scoring",
            metadata={"overall": overall, "warnings": warnings},
        )

    def stage_error(self, stage: str, error: str, retry_count: int = 0) -> None:
        self.error(
            f"Stage '{stage}' failed: {error}",
            stage=stage,
            errors=error,
            retry_count=retry_count,
        )
