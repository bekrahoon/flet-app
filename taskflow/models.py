from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Optional


class Priority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


PRIORITY_WEIGHT = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


class Recurrence(str, Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


RECURRENCE_LABELS = {
    Recurrence.NONE: "Не повторяется",
    Recurrence.DAILY: "Ежедневно",
    Recurrence.WEEKLY: "Еженедельно",
    Recurrence.MONTHLY: "Ежемесячно",
}

DEFAULT_TAGS: dict[str, str] = {
    "Учёба": "#3B82F6",
    "Работа": "#F59E0B",
    "Личное": "#10B981",
}

TAG_PALETTE = [
    "#3B82F6",
    "#F59E0B",
    "#10B981",
    "#EF4444",
    "#8B5CF6",
    "#EC4899",
    "#14B8A6",
    "#F97316",
]


def color_for_new_tag(existing: dict[str, str]) -> str:
    return TAG_PALETTE[len(existing) % len(TAG_PALETTE)]


@dataclass
class Subtask:
    title: str
    done: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "done": self.done}

    @classmethod
    def from_dict(cls, data: dict) -> "Subtask":
        return cls(
            id=data.get("id", uuid.uuid4().hex),
            title=data.get("title", ""),
            done=bool(data.get("done", False)),
        )


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = d.day
    while True:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1


@dataclass
class Task:
    title: str
    priority: Priority = Priority.MEDIUM
    done: bool = False
    due_at: Optional[datetime] = None
    due_has_time: bool = False
    pinned: bool = False
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    subtasks: list[Subtask] = field(default_factory=list)
    recurrence: Recurrence = Recurrence.NONE
    completed_at: Optional[str] = None
    notified_soon: bool = False
    notified_overdue: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority.value,
            "done": self.done,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "due_has_time": self.due_has_time,
            "pinned": self.pinned,
            "tags": list(self.tags),
            "notes": self.notes,
            "subtasks": [s.to_dict() for s in self.subtasks],
            "recurrence": self.recurrence.value,
            "completed_at": self.completed_at,
            "notified_soon": self.notified_soon,
            "notified_overdue": self.notified_overdue,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        due_at_raw = data.get("due_at")
        due_has_time = bool(data.get("due_has_time", False))
        due_at: Optional[datetime]
        if due_at_raw:
            due_at = datetime.fromisoformat(due_at_raw)
        else:
            # Migration from the pre-time schema, where only a plain date
            # ("due_date") was stored.
            legacy_due = data.get("due_date")
            if legacy_due:
                due_at = datetime.combine(date.fromisoformat(legacy_due), time.min)
                due_has_time = False
            else:
                due_at = None

        return cls(
            id=data.get("id", uuid.uuid4().hex),
            title=data.get("title", ""),
            priority=Priority(data.get("priority", Priority.MEDIUM.value)),
            done=bool(data.get("done", False)),
            due_at=due_at,
            due_has_time=due_has_time,
            pinned=bool(data.get("pinned", False)),
            tags=list(data.get("tags", [])),
            notes=data.get("notes", ""),
            subtasks=[Subtask.from_dict(s) for s in data.get("subtasks", [])],
            recurrence=Recurrence(data.get("recurrence", Recurrence.NONE.value)),
            completed_at=data.get("completed_at"),
            notified_soon=bool(data.get("notified_soon", False)),
            notified_overdue=bool(data.get("notified_overdue", False)),
            created_at=data.get(
                "created_at", datetime.now().isoformat(timespec="seconds")
            ),
        )


def advance_due_date(due_at: datetime, recurrence: Recurrence) -> datetime:
    """Computes the due datetime of the next occurrence of a recurring task."""
    if recurrence == Recurrence.DAILY:
        d = date.fromordinal(due_at.date().toordinal() + 1)
    elif recurrence == Recurrence.WEEKLY:
        d = date.fromordinal(due_at.date().toordinal() + 7)
    elif recurrence == Recurrence.MONTHLY:
        d = _add_months(due_at.date(), 1)
    else:
        return due_at
    return datetime.combine(d, due_at.time())
