from __future__ import annotations

from typing import Callable, Optional

import flet as ft

from ..models import RECURRENCE_LABELS, Priority, Recurrence, Subtask, Task
from ..stats import Stats
from .charts import build_week_bar_chart
from .pickers import DueDatePicker


class EditDialog:
    """Owns the "edit task" AlertDialog and all of its interactive state:
    title/priority/recurrence, due date+time, tags, subtasks and notes."""

    def __init__(
        self,
        page: ft.Page,
        *,
        get_tag_colors: Callable[[], dict[str, str]],
        on_add_tag: Callable[[str], None],
        on_save: Callable[[Task], None],
    ) -> None:
        self.page = page
        self.get_tag_colors = get_tag_colors
        self.on_add_tag = on_add_tag
        self.on_save = on_save

        self.task: Optional[Task] = None
        self.draft_tags: set[str] = set()
        self.draft_subtasks: list[Subtask] = []

        self.title_field = ft.TextField(label="Название", autofocus=True)
        self.priority_dropdown = ft.Dropdown(
            label="Приоритет",
            value=Priority.MEDIUM.value,
            options=[ft.DropdownOption(p.value) for p in Priority],
            expand=True,
        )
        self.recurrence_dropdown = ft.Dropdown(
            label="Повтор",
            value=Recurrence.NONE.value,
            options=[
                ft.DropdownOption(key=r.value, text=label)
                for r, label in RECURRENCE_LABELS.items()
            ],
            expand=True,
        )
        self.notes_field = ft.TextField(
            label="Заметки",
            multiline=True,
            min_lines=2,
            max_lines=5,
        )

        self.due_picker = DueDatePicker(page)

        self.tag_row = ft.Row(controls=[], spacing=6, wrap=True)
        self.new_tag_field = ft.TextField(
            hint_text="Новый тег",
            dense=True,
            expand=True,
            on_submit=self._add_tag_from_field,
        )

        self.subtasks_column = ft.Column(controls=[], spacing=2, tight=True)
        self.new_subtask_field = ft.TextField(
            hint_text="Добавить подзадачу",
            dense=True,
            expand=True,
            on_submit=self._add_subtask_from_field,
        )

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Редактировать задачу"),
            content=ft.Column(
                controls=[
                    self.title_field,
                    ft.Row(
                        controls=[self.priority_dropdown, self.recurrence_dropdown],
                        spacing=12,
                    ),
                    ft.Row(controls=[self.due_picker.button, self.due_picker.clear_button]),
                    ft.Text("Теги", size=12, weight=ft.FontWeight.BOLD),
                    self.tag_row,
                    ft.Row(
                        controls=[
                            self.new_tag_field,
                            ft.IconButton(icon=ft.Icons.ADD_ROUNDED, on_click=self._add_tag_from_field),
                        ]
                    ),
                    ft.Text("Подзадачи", size=12, weight=ft.FontWeight.BOLD),
                    self.subtasks_column,
                    ft.Row(
                        controls=[
                            self.new_subtask_field,
                            ft.IconButton(icon=ft.Icons.ADD_ROUNDED, on_click=self._add_subtask_from_field),
                        ]
                    ),
                    self.notes_field,
                ],
                spacing=10,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                width=340,
                height=460,
            ),
            actions=[
                ft.TextButton("Отмена", on_click=self._close),
                ft.FilledButton("Сохранить", icon=ft.Icons.SAVE_ROUNDED, on_click=self._save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def open_for(self, task: Task) -> None:
        self.task = task
        self.title_field.value = task.title
        self.priority_dropdown.value = task.priority.value
        self.recurrence_dropdown.value = task.recurrence.value
        self.notes_field.value = task.notes
        self.due_picker.set(task.due_at, task.due_has_time)
        self.draft_tags = set(task.tags)
        self.draft_subtasks = [
            Subtask(title=s.title, done=s.done, id=s.id) for s in task.subtasks
        ]
        self._rebuild_tag_row()
        self._rebuild_subtasks_column()
        self.page.show_dialog(self.dialog)

    def _close(self, e: ft.Event) -> None:
        self.task = None
        self.page.pop_dialog()

    def _save(self, e: ft.Event) -> None:
        if self.task is None:
            return
        title = (self.title_field.value or "").strip()
        if not title:
            return
        task = self.task
        task.title = title
        task.priority = Priority(self.priority_dropdown.value or Priority.MEDIUM.value)
        task.recurrence = Recurrence(self.recurrence_dropdown.value or Recurrence.NONE.value)
        task.notes = (self.notes_field.value or "").strip()
        task.due_at = self.due_picker.value
        task.due_has_time = self.due_picker.has_time
        task.tags = sorted(self.draft_tags)
        task.subtasks = list(self.draft_subtasks)
        self.task = None
        self.page.pop_dialog()
        self.on_save(task)

    # --- Tags -------------------------------------------------------------
    def _rebuild_tag_row(self) -> None:
        colors = self.get_tag_colors()
        chips = []
        for name, color in colors.items():
            selected = name in self.draft_tags
            chips.append(
                ft.Chip(
                    label=ft.Text(name),
                    selected=selected,
                    selected_color=color,
                    show_checkmark=False,
                    on_select=self._make_tag_toggle(name),
                )
            )
        self.tag_row.controls = chips

    def _make_tag_toggle(self, name: str):
        def handler(e: ft.Event) -> None:
            if name in self.draft_tags:
                self.draft_tags.discard(name)
            else:
                self.draft_tags.add(name)
            self._rebuild_tag_row()
            self.page.update()

        return handler

    def _add_tag_from_field(self, e: ft.Event) -> None:
        name = (self.new_tag_field.value or "").strip()
        if not name:
            return
        self.on_add_tag(name)
        self.draft_tags.add(name)
        self.new_tag_field.value = ""
        self._rebuild_tag_row()
        self.page.update()

    # --- Subtasks -----------------------------------------------------------
    def _rebuild_subtasks_column(self) -> None:
        rows = []
        for subtask in self.draft_subtasks:
            rows.append(
                ft.Row(
                    controls=[
                        ft.Checkbox(
                            value=subtask.done,
                            scale=0.85,
                            on_change=self._make_subtask_toggle(subtask),
                        ),
                        ft.Text(subtask.title, size=13, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_size=16,
                            on_click=self._make_subtask_remove(subtask),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        self.subtasks_column.controls = rows

    def _make_subtask_toggle(self, subtask: Subtask):
        def handler(e: ft.Event) -> None:
            subtask.done = e.control.value

        return handler

    def _make_subtask_remove(self, subtask: Subtask):
        def handler(e: ft.Event) -> None:
            self.draft_subtasks = [s for s in self.draft_subtasks if s.id != subtask.id]
            self._rebuild_subtasks_column()
            self.page.update()

        return handler

    def _add_subtask_from_field(self, e: ft.Event) -> None:
        title = (self.new_subtask_field.value or "").strip()
        if not title:
            return
        self.draft_subtasks.append(Subtask(title=title))
        self.new_subtask_field.value = ""
        self._rebuild_subtasks_column()
        self.page.update()


def _stat_tile(label: str, value: str) -> ft.Control:
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(value, size=20, weight=ft.FontWeight.BOLD),
                ft.Text(label, size=10, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
            tight=True,
        ),
        padding=10,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        width=95,
    )


class StatsDialog:
    """Owns the "Статистика" AlertDialog: today/week completion counts,
    a streak counter, a 7-day bar chart and a per-priority breakdown."""

    def __init__(self, page: ft.Page, *, get_stats: Callable[[], Stats]) -> None:
        self.page = page
        self.get_stats = get_stats
        self.body = ft.Column(controls=[], spacing=14, tight=True, width=320)
        self.dialog = ft.AlertDialog(
            title=ft.Text("Статистика"),
            content=self.body,
            actions=[ft.TextButton("Закрыть", on_click=self._close)],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def open(self) -> None:
        stats = self.get_stats()
        self.body.controls = self._build_content(stats)
        self.page.show_dialog(self.dialog)

    def _close(self, e: ft.Event) -> None:
        self.page.pop_dialog()

    def _build_content(self, stats: Stats) -> list[ft.Control]:
        priority_rows = [
            ft.Row(
                controls=[ft.Text(priority.value), ft.Text(str(count), weight=ft.FontWeight.BOLD)],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            for priority, count in stats.priority_breakdown.items()
        ]
        return [
            ft.Row(
                controls=[
                    _stat_tile("Сегодня", str(stats.completed_today)),
                    _stat_tile("На неделе", str(stats.completed_this_week)),
                    _stat_tile("Дней подряд", str(stats.streak_days)),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Text("Выполнено за 7 дней", size=12, weight=ft.FontWeight.BOLD),
            build_week_bar_chart(stats.last_7_days),
            ft.Text("Задачи по приоритету", size=12, weight=ft.FontWeight.BOLD),
            ft.Column(controls=priority_rows, spacing=6, tight=True),
        ]
