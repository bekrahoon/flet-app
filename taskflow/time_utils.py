from __future__ import annotations

from datetime import datetime

from .models import Task


def format_due(due_at: datetime, has_time: bool) -> str:
    if has_time:
        return due_at.strftime("%d.%m.%Y, %H:%M")
    return due_at.strftime("%d.%m.%Y")


def relative_due(due_at: datetime, has_time: bool, now: datetime | None = None) -> str:
    """Short Russian relative-time label, e.g. "через 2 ч", "завтра",
    "просрочено на 1 д"."""
    now = now or datetime.now()
    days_diff = (due_at.date() - now.date()).days

    if not has_time:
        if days_diff == 0:
            return "сегодня"
        if days_diff == 1:
            return "завтра"
        if days_diff > 1:
            return f"через {days_diff} д"
        if days_diff == -1:
            return "просрочено на 1 д"
        return f"просрочено на {-days_diff} д"

    delta_minutes = (due_at - now).total_seconds() / 60
    if delta_minutes >= 0:
        if days_diff == 0:
            if delta_minutes < 1:
                return "прямо сейчас"
            if delta_minutes < 60:
                return f"через {int(delta_minutes)} мин"
            return f"через {int(delta_minutes // 60)} ч"
        if days_diff == 1:
            return "завтра"
        return f"через {days_diff} д"

    overdue_minutes = -delta_minutes
    if days_diff == 0:
        if overdue_minutes < 60:
            return f"просрочено на {int(overdue_minutes)} мин"
        return f"просрочено на {int(overdue_minutes // 60)} ч"
    return f"просрочено на {-days_diff} д"


def is_overdue(task: Task, now: datetime | None = None) -> bool:
    if task.due_at is None or task.done:
        return False
    now = now or datetime.now()
    if task.due_has_time:
        return task.due_at < now
    return task.due_at.date() < now.date()


def is_due_today(task: Task, now: datetime | None = None) -> bool:
    if task.due_at is None:
        return False
    now = now or datetime.now()
    return task.due_at.date() == now.date()


def minutes_until_due(task: Task, now: datetime | None = None) -> float | None:
    if task.due_at is None:
        return None
    now = now or datetime.now()
    return (task.due_at - now).total_seconds() / 60
