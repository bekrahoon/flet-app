from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .models import DEFAULT_TAGS, Task

APP_DIR = Path.home() / ".taskflow"
TASKS_FILE = APP_DIR / "tasks.json"
SETTINGS_FILE = APP_DIR / "settings.json"
TAGS_FILE = APP_DIR / "tags.json"
HISTORY_FILE = APP_DIR / "history.json"


class JsonFile:
    """Small helper that reads/writes a JSON file, tolerating a missing
    or corrupted file by falling back to a default value."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def read(self, default):
        if not self._path.exists():
            return default
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    def write(self, data) -> None:
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


class TaskStore:
    def __init__(self, path: Path = TASKS_FILE) -> None:
        self._file = JsonFile(path)

    def load(self) -> list[Task]:
        return [Task.from_dict(item) for item in self._file.read([])]

    def save(self, tasks: list[Task]) -> None:
        self._file.write([task.to_dict() for task in tasks])


class SettingsStore:
    def __init__(self, path: Path = SETTINGS_FILE) -> None:
        self._file = JsonFile(path)

    def load(self) -> dict:
        return self._file.read({})

    def save(self, settings: dict) -> None:
        self._file.write(settings)


class TagStore:
    """Persists the name -> hex color mapping for task tags/categories."""

    def __init__(self, path: Path = TAGS_FILE) -> None:
        self._file = JsonFile(path)

    def load(self) -> dict[str, str]:
        data = self._file.read(None)
        if not data:
            return dict(DEFAULT_TAGS)
        return data

    def save(self, tags: dict[str, str]) -> None:
        self._file.write(tags)


class HistoryStore:
    """Append-only log of task-completion events (one ISO date per
    completion), kept independent of the tasks themselves so statistics
    (streaks, weekly charts) survive task deletion."""

    def __init__(self, path: Path = HISTORY_FILE) -> None:
        self._file = JsonFile(path)

    def load(self) -> list[str]:
        return self._file.read([])

    def save(self, entries: list[str]) -> None:
        self._file.write(entries)

    def add_completion(self, when: datetime) -> None:
        entries = self.load()
        entries.append(when.date().isoformat())
        self.save(entries)

    def completions_on(self, day: date) -> int:
        iso = day.isoformat()
        return sum(1 for entry in self.load() if entry == iso)
