from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .models import Priority, Task
from .storage import HistoryStore


@dataclass
class Stats:
    completed_today: int
    completed_this_week: int
    streak_days: int
    last_7_days: list[tuple[date, int]]
    priority_breakdown: dict[Priority, int]


def compute_stats(tasks: list[Task], history: HistoryStore, today: date | None = None) -> Stats:
    today = today or date.today()
    entries = history.load()

    def count_on(day: date) -> int:
        iso = day.isoformat()
        return sum(1 for entry in entries if entry == iso)

    completed_today = count_on(today)

    week_start = today - timedelta(days=today.weekday())  # Monday
    completed_this_week = sum(
        count_on(week_start + timedelta(days=offset))
        for offset in range((today - week_start).days + 1)
    )

    # A streak isn't "broken" until a full day passes with zero completions,
    # so if today has none yet we still count backward starting yesterday.
    streak = 0
    day = today if count_on(today) > 0 else today - timedelta(days=1)
    while count_on(day) > 0:
        streak += 1
        day -= timedelta(days=1)

    last_7_days = [
        (today - timedelta(days=offset), count_on(today - timedelta(days=offset)))
        for offset in range(6, -1, -1)
    ]

    priority_breakdown = {p: 0 for p in Priority}
    for task in tasks:
        priority_breakdown[task.priority] += 1

    return Stats(
        completed_today=completed_today,
        completed_this_week=completed_this_week,
        streak_days=streak,
        last_7_days=last_7_days,
        priority_breakdown=priority_breakdown,
    )
