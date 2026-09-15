"""Shared base for pipeline stages. Each stage gets a `ctx` dict and returns its output dict."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class StageContext:
    """Per-run context passed between stages.

    Stages read from and write to `state` (a plain dict) so cross-stage
    data flow is explicit and easy to log.
    """
    job_id: str
    topic: str
    state: dict[str, Any]


class Stage(ABC):
    name: str
    label: str

    @abstractmethod
    def run(self, ctx: StageContext) -> dict: ...
