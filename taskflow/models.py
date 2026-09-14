from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Priority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass
class Task:
    title: str
    priority: Priority = Priority.MEDIUM
    done: bool = False
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
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data.get("id", uuid.uuid4().hex),
            title=data.get("title", ""),
            priority=Priority(data.get("priority", Priority.MEDIUM.value)),
            done=bool(data.get("done", False)),
            created_at=data.get(
                "created_at", datetime.now().isoformat(timespec="seconds")
            ),
        )
