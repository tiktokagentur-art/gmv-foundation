"""Bounded, isolated mock execution without network, secrets or external calls."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import BoundedSemaphore

from .policy import MockPolicyRequest, evaluate_action


@dataclass(frozen=True)
class MockResult:
    accepted: bool
    workitem_id: str
    message: str


class MockRuntime:
    def __init__(self, *, started_at: datetime, max_workers: int = 2, window_minutes: int = 60):
        if started_at.tzinfo is None or max_workers != 2 or window_minutes != 60:
            raise ValueError("fixed pilot bounds required")
        self.started_at = started_at.astimezone(timezone.utc)
        self._slots = BoundedSemaphore(2)

    def execute(self, request: MockPolicyRequest, *, now: datetime) -> MockResult:
        if now.tzinfo is None:
            return MockResult(False, request.workitem_id, "invalid time")
        current = now.astimezone(timezone.utc)
        if not (self.started_at <= current < self.started_at + timedelta(minutes=60)):
            return MockResult(False, request.workitem_id, "outside pilot window")
        if not evaluate_action(request):
            return MockResult(False, request.workitem_id, "denied")
        if not self._slots.acquire(blocking=False):
            return MockResult(False, request.workitem_id, "capacity exceeded")
        try:
            return MockResult(True, request.workitem_id, "offline mock completed")
        finally:
            self._slots.release()
