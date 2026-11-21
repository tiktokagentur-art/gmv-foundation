"""In-memory offline budget simulation; not a billing or production ledger."""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock

from .models import BudgetPolicy


class MockBudgetLedger:
    def __init__(self, policy: BudgetPolicy | None = None) -> None:
        self.policy = policy or BudgetPolicy()
        self._lock = Lock()
        self._reservations: dict[str, tuple[str, str, int]] = {}

    def reserve(self, *, request_id: str, workitem_id: str, amount_cents: int, now: datetime) -> bool:
        if not request_id or not workitem_id or not isinstance(amount_cents, int) or isinstance(amount_cents, bool):
            return False
        if amount_cents <= 0 or now.tzinfo is None:
            return False
        day = now.astimezone(timezone.utc).date().isoformat()
        with self._lock:
            existing = self._reservations.get(request_id)
            if existing is not None:
                return existing == (workitem_id, day, amount_cents)
            total = sum(v[2] for v in self._reservations.values())
            daily = sum(v[2] for v in self._reservations.values() if v[1] == day)
            workitem = sum(v[2] for v in self._reservations.values() if v[0] == workitem_id)
            if (total + amount_cents > self.policy.pilot_total_limit_cents
                or daily + amount_cents > self.policy.daily_limit_cents
                or workitem + amount_cents > self.policy.workitem_limit_cents):
                return False
            self._reservations[request_id] = (workitem_id, day, amount_cents)
            return True

    def reserved_cents(self) -> int:
        with self._lock:
            return sum(v[2] for v in self._reservations.values())
