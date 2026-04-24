"""按**学生**维度的聊天请求内存限流（设计 §7 / §9；任务 9）。"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone


@dataclass
class _StudentQuota:
    minute_hits: list[float] = field(default_factory=list)  # unix seconds
    day: date | None = None
    day_tokens: int = 0


def _new_quota() -> _StudentQuota:
    return _StudentQuota()


_state: dict[str, _StudentQuota] = defaultdict(_new_quota)


def _now() -> float:
    return time.time()


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _prune_minute(hits: list[float], window_s: float = 60.0) -> None:
    t0 = _now() - window_s
    while hits and hits[0] < t0:
        hits.pop(0)


def check_and_record_request(
    student_id: str,
    *,
    rpm: int,
    est_tokens: int,
    daily_budget: int,
) -> tuple[bool, str]:
    """
    返回 `(allowed, reason)`。通过时在内部记录**一次**请求与**估算** token（用于日预算）。

    日预算 `daily_budget` 为 0 时**不**限制日 token。
    """
    q = _state[student_id]
    _prune_minute(q.minute_hits)
    if len(q.minute_hits) >= max(1, rpm):
        return False, "rate_limited: too many requests per minute"

    today = _utc_today()
    if q.day != today:
        q.day = today
        q.day_tokens = 0

    if daily_budget > 0 and q.day_tokens + est_tokens > daily_budget:
        return False, "rate_limited: daily token budget exceeded"

    q.minute_hits.append(_now())
    q.day_tokens += max(0, est_tokens)
    return True, "ok"
