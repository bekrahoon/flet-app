from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class Priority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


PRIORITY_WEIGHT = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


@dataclass
class Task:
    title: str
    priority: Priority = Priority.MEDIUM
    done: bool = False
    due_date: Optional[date] = None
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
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        due_date_raw = data.get("due_date")
        return cls(
            id=data.get("id", uuid.uuid4().hex),
            title=data.get("title", ""),
            priority=Priority(data.get("priority", Priority.MEDIUM.value)),
            done=bool(data.get("done", False)),
            due_date=date.fromisoformat(due_date_raw) if due_date_raw else None,
            created_at=data.get(
                "created_at", datetime.now().isoformat(timespec="seconds")
            ),
        )
