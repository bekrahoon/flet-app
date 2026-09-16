from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import flet as ft

from ..models import (
    PRIORITY_WEIGHT,
    Priority,
    Recurrence,
    Subtask,
    Task,
    advance_due_date,
    color_for_new_tag,
)
from ..stats import compute_stats
from ..storage import HistoryStore, SettingsStore, TagStore, TaskStore
from ..time_utils import is_due_today, is_overdue, minutes_until_due
from .dialogs import EditDialog, StatsDialog
from .pickers import DueDatePicker
from .task_card import TaskCardCallbacks, build_task_card

FILTERS = ("All", "Active", "Done", "Today", "Overdue")
FILTER_LABELS = {
    "All": "Все",
    "Active": "Активные",
    "Done": "Готовые",
    "Today": "Сегодня",
    "Overdue": "Просроченные",
}

SORT_LABELS = {
    "created": "Сначала новые",
    "priority": "По приоритету",
    "due": "По сроку",
    "title": "По алфавиту",
}

REMINDER_CHECK_SECONDS = 60
REMINDER_SOON_MINUTES = 30


class TaskFlowApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.task_store = TaskStore()
        self.settings_store = SettingsStore()
        self.tag_store = TagStore()
        self.history_store = HistoryStore()

        self.tasks: list[Task] = self.task_store.load()
        self.tag_colors: dict[str, str] = self.tag_store.load()

        settings = self.settings_store.load()
        self.active_filter: str = "All"
        self.active_tag_filter: Optional[str] = None
        self.sort_mode: str = settings.get("sort_mode", "created")
        self.search_query: str = ""
        self.expanded_task_ids: set[str] = set()
        self._undo_tasks: Optional[list[Task]] = None

        page.theme_mode = (
            ft.ThemeMode.DARK if settings.get("dark_mode") else ft.ThemeMode.LIGHT
        )

        self._build_controls()
        self._setup_page()
        self.refresh()
        page.run_task(self._reminder_loop)

    # ------------------------------------------------------------------ #
    # Setup
    # ------------------------------------------------------------------ #
    def _setup_page(self) -> None:
        page = self.page
        page.title = "TaskFlow"
        page.theme = ft.Theme(color_scheme_seed=ft.Colors.DEEP_PURPLE, use_material3=True)
        page.dark_theme = ft.Theme(
            color_scheme_seed=ft.Colors.DEEP_PURPLE, use_material3=True
        )
        page.locale_configuration = ft.LocaleConfiguration(
            supported_locales=[ft.Locale("ru", "RU"), ft.Locale("en", "US")],
            current_locale=ft.Locale("ru", "RU"),
        )
        page.padding = 0
        page.window.width = 460
        page.window.height = 840
        page.window.min_width = 380
        page.window.min_height = 560
        page.appbar = ft.AppBar(
            title=ft.Text("TaskFlow", weight=ft.FontWeight.BOLD),
            center_title=False,
            bgcolor=ft.Colors.SURFACE,
            actions=[self.stats_button, self.theme_button, ft.Container(width=8)],
        )
        page.add(
            ft.Container(
                content=ft.Column(
                    controls=[
                        self.progress_card,
                        self.compose_card,
                        ft.Row(controls=[self.search_field, self.sort_button], spacing=8),
                        ft.Row(controls=self.filter_chips, spacing=8, wrap=True),
                        self.tag_filter_row,
                        ft.Divider(height=1),
                        ft.Stack(
                            controls=[self.list_view, self.empty_state],
                            expand=True,
                        ),
                        ft.Divider(height=1),
                        ft.Row(
                            controls=[self.visible_count_text, self.clear_done_button],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=14,
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
                padding=ft.Padding(16, 16, 16, 12),
                expand=True,
            )
        )

    def _build_controls(self) -> None:
        # --- App bar ---------------------------------------------------
        self.theme_button = ft.IconButton(
            icon=self._theme_icon(), tooltip="Сменить тему", on_click=self.toggle_theme
        )
        self.stats_button = ft.IconButton(
            icon=ft.Icons.BAR_CHART_ROUNDED,
            tooltip="Статистика",
            on_click=lambda e: self.stats_dialog.open(),
        )

        # --- Progress header --------------------------------------------
        self.progress_ring = ft.ProgressRing(
            value=0,
            width=56,
            height=56,
            stroke_width=6,
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.WHITE24,
        )
        self.progress_percent_text = ft.Text(
            "0%", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
        )
        self.progress_title_text = ft.Text(
            "Добавьте первую задачу", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
        )
        self.congrats_switcher = ft.AnimatedSwitcher(
            content=ft.Container(width=0, height=0, key="idle"),
            duration=400,
            transition=ft.AnimatedSwitcherTransition.SCALE,
        )
        self.progress_subtitle_text = ft.Text(
            "0 из 0 задач выполнено", size=12, color=ft.Colors.WHITE70
        )
        self.progress_card = ft.Container(
            padding=18,
            border_radius=18,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[ft.Colors.DEEP_PURPLE_600, ft.Colors.INDIGO_400],
            ),
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Row(
                                controls=[self.progress_title_text, self.congrats_switcher],
                                spacing=6,
                            ),
                            self.progress_subtitle_text,
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    ft.Stack(
                        controls=[
                            self.progress_ring,
                            ft.Container(
                                content=self.progress_percent_text,
                                width=56,
                                height=56,
                                alignment=ft.Alignment.CENTER,
                            ),
                        ],
                        width=56,
                        height=56,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # --- Compose (add task) card ------------------------------------
        self.new_task_field = ft.TextField(
            hint_text="Что нужно сделать?",
            border=ft.InputBorder.NONE,
            filled=True,
            bgcolor=ft.Colors.TRANSPARENT,
            content_padding=ft.Padding(4, 8, 4, 8),
            prefix_icon=ft.Icons.EDIT_NOTE_ROUNDED,
            on_submit=self.add_task,
        )
        self.priority_dropdown = ft.Dropdown(
            width=140,
            value=Priority.MEDIUM.value,
            dense=True,
            options=[ft.DropdownOption(p.value) for p in Priority],
        )
        self.new_due_picker = DueDatePicker(self.page)
        self.add_button = ft.FilledButton(
            "Добавить", icon=ft.Icons.ADD_ROUNDED, on_click=self.add_task
        )
        self.compose_card = ft.Container(
            padding=ft.Padding(14, 6, 14, 10),
            border_radius=16,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            content=ft.Column(
                controls=[
                    self.new_task_field,
                    ft.Row(
                        controls=[
                            self.priority_dropdown,
                            self.new_due_picker.button,
                            self.new_due_picker.clear_button,
                            self.add_button,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                ],
                spacing=2,
            ),
        )

        # --- Search + sort -------------------------------------------------
        self.search_field = ft.TextField(
            hint_text="Поиск задач",
            expand=True,
            dense=True,
            border=ft.InputBorder.OUTLINE,
            border_radius=24,
            content_padding=ft.Padding(16, 8, 8, 8),
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            on_change=self.on_search_change,
        )
        self.sort_button = ft.PopupMenuButton(
            icon=ft.Icons.SWAP_VERT_ROUNDED,
            tooltip="Сортировка",
            items=self._build_sort_items(),
        )

        # --- Filters -------------------------------------------------------
        self.filter_chips = [
            ft.Chip(
                label=ft.Text(FILTER_LABELS[name]),
                selected=(name == self.active_filter),
                show_checkmark=False,
                on_select=self._make_filter_handler(name),
            )
            for name in FILTERS
        ]
        self.tag_filter_row = ft.Row(controls=[], spacing=6, wrap=True)

        # --- Task list -------------------------------------------------------
        self.list_view = ft.ListView(expand=True, spacing=10, auto_scroll=False)
        self.empty_state = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.INBOX_ROUNDED, size=48, color=ft.Colors.OUTLINE),
                    ft.Text("Ничего нет", color=ft.Colors.OUTLINE),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
            visible=False,
        )

        self.visible_count_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.clear_done_button = ft.TextButton(
            "Очистить выполненные",
            icon=ft.Icons.DELETE_SWEEP_ROUNDED,
            on_click=self.clear_done,
        )

        # --- Dialogs ---------------------------------------------------------
        self.edit_dialog = EditDialog(
            self.page,
            get_tag_colors=lambda: self.tag_colors,
            on_add_tag=self._add_tag,
            on_save=self._on_task_edited,
        )
        self.stats_dialog = StatsDialog(self.page, get_stats=self._compute_stats)

    def _build_sort_items(self) -> list[ft.PopupMenuItem]:
        return [
            ft.PopupMenuItem(
                content=ft.Text(label),
                checked=(mode == self.sort_mode),
                on_click=self._make_sort_handler(mode),
            )
            for mode, label in SORT_LABELS.items()
        ]

    # ------------------------------------------------------------------ #
    # Persistence helpers
    # ------------------------------------------------------------------ #
    def _save_tasks(self) -> None:
        self.task_store.save(self.tasks)

    def _save_settings(self) -> None:
        self.settings_store.save(
            {
                "dark_mode": self.page.theme_mode == ft.ThemeMode.DARK,
                "sort_mode": self.sort_mode,
            }
        )

    def _add_tag(self, name: str) -> None:
        if name not in self.tag_colors:
            self.tag_colors[name] = color_for_new_tag(self.tag_colors)
            self.tag_store.save(self.tag_colors)

    def _theme_icon(self) -> str:
        return (
            ft.Icons.LIGHT_MODE_ROUNDED
            if self.page.theme_mode == ft.ThemeMode.DARK
            else ft.Icons.DARK_MODE_ROUNDED
        )

    # ------------------------------------------------------------------ #
    # Theme
    # ------------------------------------------------------------------ #
    def toggle_theme(self, e: ft.Event) -> None:
        self.page.theme_mode = (
            ft.ThemeMode.LIGHT
            if self.page.theme_mode == ft.ThemeMode.DARK
            else ft.ThemeMode.DARK
        )
        self.theme_button.icon = self._theme_icon()
        self._save_settings()
        self.page.update()

    # ------------------------------------------------------------------ #
    # Add task
    # ------------------------------------------------------------------ #
    async def add_task(self, e: ft.Event) -> None:
        title = self.new_task_field.value.strip() if self.new_task_field.value else ""
        if not title:
            await self.new_task_field.focus()
            return
        priority = Priority(self.priority_dropdown.value or Priority.MEDIUM.value)
        self.tasks.insert(
            0,
            Task(
                title=title,
                priority=priority,
                due_at=self.new_due_picker.value,
                due_has_time=self.new_due_picker.has_time,
            ),
        )
        self.new_task_field.value = ""
        self.new_due_picker.clear()
        self._save_tasks()
        self.refresh()
        await self.new_task_field.focus()

    # ------------------------------------------------------------------ #
    # Filters / search / sort / tags
    # ------------------------------------------------------------------ #
    def _make_filter_handler(self, name: str):
        def handler(e: ft.Event) -> None:
            self.active_filter = name
            for chip in self.filter_chips:
                chip.selected = chip.data == name
            self.refresh()

        return handler

    def on_search_change(self, e: ft.Event) -> None:
        self.search_query = (self.search_field.value or "").strip().lower()
        self.refresh()

    def _make_sort_handler(self, mode: str):
        def handler(e: ft.Event) -> None:
            self.sort_mode = mode
            self.sort_button.items = self._build_sort_items()
            self._save_settings()
            self.refresh()

        return handler

    def _make_tag_filter_handler(self, name: str):
        def handler(e: ft.Event) -> None:
            self.active_tag_filter = None if self.active_tag_filter == name else name
            self.refresh()

        return handler

    # ------------------------------------------------------------------ #
    # Task actions
    # ------------------------------------------------------------------ #
    def toggle_task(self, task: Task):
        def handler(e: ft.Event) -> None:
            was_done = task.done
            task.done = bool(e.control.value)
            if task.done and not was_done:
                now = datetime.now()
                task.completed_at = now.isoformat(timespec="seconds")
                self.history_store.add_completion(now)
                self._spawn_recurrence_if_needed(task)
            elif not task.done and was_done:
                task.completed_at = None
            self._save_tasks()
            self.refresh()

        return handler

    def _spawn_recurrence_if_needed(self, task: Task) -> None:
        if task.recurrence == Recurrence.NONE or task.due_at is None:
            return
        next_due = advance_due_date(task.due_at, task.recurrence)
        self.tasks.insert(
            0,
            Task(
                title=task.title,
                priority=task.priority,
                due_at=next_due,
                due_has_time=task.due_has_time,
                tags=list(task.tags),
                notes=task.notes,
                subtasks=[Subtask(title=s.title) for s in task.subtasks],
                recurrence=task.recurrence,
            ),
        )

    def toggle_pin(self, task: Task):
        def handler(e: ft.Event) -> None:
            task.pinned = not task.pinned
            self._save_tasks()
            self.refresh()

        return handler

    def toggle_expand(self, task: Task):
        def handler(e: ft.Event) -> None:
            if task.id in self.expanded_task_ids:
                self.expanded_task_ids.discard(task.id)
            else:
                self.expanded_task_ids.add(task.id)
            self.refresh()

        return handler

    def toggle_subtask(self, task: Task, subtask: Subtask):
        def handler(e: ft.Event) -> None:
            subtask.done = bool(e.control.value)
            self._save_tasks()
            self.refresh()

        return handler

    def delete_task(self, task: Task):
        def handler(e: ft.Event) -> None:
            self._undo_tasks = list(self.tasks)
            self.tasks.remove(task)
            self._save_tasks()
            self.refresh()
            self._show_snackbar(
                "Задача удалена",
                action="Отменить",
                on_action=self.undo_last_action,
                duration_ms=5000,
            )

        return handler

    def clear_done(self, e: ft.Event) -> None:
        done_count = sum(1 for t in self.tasks if t.done)
        if done_count == 0:
            return
        self._undo_tasks = list(self.tasks)
        self.tasks = [task for task in self.tasks if not task.done]
        self._save_tasks()
        self.refresh()
        self._show_snackbar(
            f"Выполненные задачи очищены ({done_count})",
            action="Отменить",
            on_action=self.undo_last_action,
            duration_ms=5000,
        )

    def _show_snackbar(
        self,
        message: str,
        *,
        action: Optional[str] = None,
        on_action=None,
        duration_ms: int = 4000,
    ) -> None:
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            action=action,
            on_action=on_action,
            duration=duration_ms,
        )
        self.page.show_dialog(snackbar)

    def undo_last_action(self, e: ft.Event) -> None:
        if self._undo_tasks is None:
            return
        self.tasks = self._undo_tasks
        self._undo_tasks = None
        self._save_tasks()
        self.refresh()

    # --- Edit dialog -----------------------------------------------------
    def open_edit_dialog(self, task: Task):
        def handler(e: ft.Event) -> None:
            self.edit_dialog.open_for(task)

        return handler

    def _on_task_edited(self, task: Task) -> None:
        self._save_tasks()
        self.refresh()

    # ------------------------------------------------------------------ #
    # Reminders
    # ------------------------------------------------------------------ #
    async def _reminder_loop(self) -> None:
        while True:
            self._check_reminders()
            await asyncio.sleep(REMINDER_CHECK_SECONDS)

    def _check_reminders(self) -> None:
        now = datetime.now()
        changed = False
        for task in self.tasks:
            if task.done or task.due_at is None:
                continue
            minutes = minutes_until_due(task, now)
            if minutes is None:
                continue
            if minutes < 0:
                if not task.notified_overdue:
                    self._show_snackbar(
                        f'Просрочено: «{task.title}»', duration_ms=6000
                    )
                    task.notified_overdue = True
                    changed = True
            elif minutes <= REMINDER_SOON_MINUTES and not task.notified_soon:
                self._show_snackbar(
                    f'Скоро дедлайн: «{task.title}» через {int(minutes)} мин',
                    duration_ms=6000,
                )
                task.notified_soon = True
                changed = True
        if changed:
            self._save_tasks()

    # ------------------------------------------------------------------ #
    # Statistics
    # ------------------------------------------------------------------ #
    def _compute_stats(self):
        return compute_stats(self.tasks, self.history_store)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def _status_filtered(self) -> list[Task]:
        now = datetime.now()
        if self.active_filter == "Active":
            return [t for t in self.tasks if not t.done]
        if self.active_filter == "Done":
            return [t for t in self.tasks if t.done]
        if self.active_filter == "Today":
            return [t for t in self.tasks if is_due_today(t, now)]
        if self.active_filter == "Overdue":
            return [t for t in self.tasks if is_overdue(t, now)]
        return list(self.tasks)

    def _visible_tasks(self) -> list[Task]:
        tasks = self._status_filtered()
        if self.active_tag_filter:
            tasks = [t for t in tasks if self.active_tag_filter in t.tags]
        if self.search_query:
            tasks = [t for t in tasks if self.search_query in t.title.lower()]

        if self.sort_mode == "priority":
            tasks = sorted(tasks, key=lambda t: PRIORITY_WEIGHT[t.priority])
        elif self.sort_mode == "due":
            tasks = sorted(
                tasks, key=lambda t: (t.due_at is None, t.due_at or datetime.max)
            )
        elif self.sort_mode == "title":
            tasks = sorted(tasks, key=lambda t: t.title.lower())
        else:  # "created"
            tasks = sorted(tasks, key=lambda t: t.created_at, reverse=True)

        # Stable partition keeps the chosen sort order within each group.
        tasks.sort(key=lambda t: not t.pinned)
        return tasks

    def _build_task_callbacks(self) -> TaskCardCallbacks:
        return TaskCardCallbacks(
            on_toggle=self.toggle_task,
            on_edit=self.open_edit_dialog,
            on_delete=self.delete_task,
            on_pin=self.toggle_pin,
            on_toggle_expand=self.toggle_expand,
            on_subtask_toggle=self.toggle_subtask,
        )

    def refresh(self) -> None:
        now = datetime.now()
        visible = self._visible_tasks()
        callbacks = self._build_task_callbacks()
        self.list_view.controls = [
            build_task_card(
                t, callbacks, self.tag_colors, t.id in self.expanded_task_ids, now
            )
            for t in visible
        ]
        self.empty_state.visible = len(visible) == 0
        if not self.tasks:
            self.empty_state.content.controls[1].value = "Задач пока нет — добавьте первую"
        elif self.search_query:
            self.empty_state.content.controls[1].value = "Ничего не найдено"
        else:
            self.empty_state.content.controls[1].value = "Здесь пусто"

        total = len(self.tasks)
        done = sum(1 for t in self.tasks if t.done)
        percent = int(done / total * 100) if total else 0

        for name, chip in zip(FILTERS, self.filter_chips):
            chip.data = name
            if name == "All":
                count = total
            elif name == "Active":
                count = total - done
            elif name == "Done":
                count = done
            elif name == "Today":
                count = sum(1 for t in self.tasks if is_due_today(t, now))
            else:  # "Overdue"
                count = sum(1 for t in self.tasks if is_overdue(t, now))
            chip.label.value = f"{FILTER_LABELS[name]} ({count})"

        self.tag_filter_row.controls = [
            ft.Chip(
                label=ft.Text(name),
                selected=(name == self.active_tag_filter),
                selected_color=color,
                show_checkmark=False,
                on_select=self._make_tag_filter_handler(name),
            )
            for name, color in self.tag_colors.items()
        ]

        self.progress_ring.value = percent / 100
        self.progress_percent_text.value = f"{percent}%"
        self.progress_subtitle_text.value = f"{done} из {total} задач выполнено"
        all_done = total > 0 and done == total
        if total == 0:
            self.progress_title_text.value = "Добавьте первую задачу"
        elif all_done:
            self.progress_title_text.value = "Все задачи выполнены!"
        else:
            self.progress_title_text.value = "Ваш прогресс"
        self.congrats_switcher.content = (
            ft.Icon(ft.Icons.CELEBRATION_ROUNDED, color=ft.Colors.WHITE, size=24, key="celebrate")
            if all_done
            else ft.Container(width=0, height=0, key="idle")
        )

        self.visible_count_text.value = f"Показано: {len(visible)}"

        self.page.update()


def main(page: ft.Page) -> None:
    TaskFlowApp(page)
