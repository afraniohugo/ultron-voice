"""Core data models for Ultron Voice: jobs, checksums, history entries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class Checksums:
    """SHA-256 per pipeline artifact."""

    input: str | None = None
    output: str | None = None
    steps: dict[str, str] = field(default_factory=dict)

    def record(self, step: str, path: str | None) -> None:
        if path is None:
            return
        self.steps[step] = path  # path supplied by caller after write
