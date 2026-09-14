from __future__ import annotations

import json
from pathlib import Path

from .models import Task

APP_DIR = Path.home() / ".taskflow"
TASKS_FILE = APP_DIR / "tasks.json"
SETTINGS_FILE = APP_DIR / "settings.json"


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
