"""Job lifecycle schemas — used by the API to expose job state to the webapp."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageInfo(BaseModel):
    name: str
    label: str
    status: StageStatus = StageStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    output_path: str | None = None


class JobCreateRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    title_hint: str | None = Field(default=None, max_length=120)


class JobSummary(BaseModel):
    id: str
    topic: str
    title: str | None = None
    status: JobStatus
    created_at: datetime
    finished_at: datetime | None = None
    error: str | None = None


class JobDetail(JobSummary):
    stages: list[StageInfo] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
