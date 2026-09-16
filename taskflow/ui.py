from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import flet as ft

from .models import PRIORITY_WEIGHT, Priority, Task
from .storage import SettingsStore, TaskStore

PRIORITY_COLOR = {
    Priority.LOW: ft.Colors.GREEN_600,
    Priority.MEDIUM: ft.Colors.AMBER_700,
    Priority.HIGH: ft.Colors.RED_400,
}
PRIORITY_ICON = {
    Priority.LOW: ft.Icons.ARROW_DOWNWARD_ROUNDED,
    Priority.MEDIUM: ft.Icons.REMOVE_ROUNDED,
    Priority.HIGH: ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
}

FILTERS = ("All", "Active", "Done")
FILTER_LABELS = {"All": "Все", "Active": "Активные", "Done": "Готовые"}

SORT_LABELS = {
    "created": "Сначала новые",
    "priority": "По приоритету",
    "due": "По сроку",
    "title": "По алфавиту",
}


def _today() -> date:
    return datetime.now().date()


def _fmt_due(d: date) -> str:
    return d.strftime("%d.%m.%Y")


class TaskFlowApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.task_store = TaskStore()
        self.settings_store = SettingsStore()

        self.tasks: list[Task] = self.task_store.load()
        self.active_filter: str = "All"
        self.sort_mode: str = "created"
        self.search_query: str = ""

        self._new_due_date: Optional[date] = None
        self._editing_task: Optional[Task] = None
        self._editing_due_date: Optional[date] = None
        self._date_target: str = "new"  # "new" | "edit"
        self._undo_snapshot: Optional[list[Task]] = None

        settings = self.settings_store.load()
        page.theme_mode = (
            ft.ThemeMode.DARK if settings.get("dark_mode") else ft.ThemeMode.LIGHT
        )

        self._build_controls()
        self._setup_page()
        self.refresh()

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
        page.padding = 0
        page.window.width = 460
        page.window.height = 840
        page.window.min_width = 380
        page.window.min_height = 560
        page.appbar = ft.AppBar(
            title=ft.Text("TaskFlow", weight=ft.FontWeight.BOLD),
            center_title=False,
            bgcolor=ft.Colors.SURFACE,
            actions=[self.theme_button, ft.Container(width=8)],
        )
        page.add(
            ft.Container(
                content=ft.Column(
                    controls=[
                        self.progress_card,
                        self.compose_card,
                        ft.Row(controls=[self.search_field, self.sort_button], spacing=8),
                        ft.Row(controls=self.filter_chips, spacing=8),
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
                        controls=[self.progress_title_text, self.progress_subtitle_text],
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
        self.due_date_button = ft.TextButton(
            content=ft.Text("Без срока"),
            icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
            on_click=lambda e: self.open_date_picker("new"),
        )
        self.due_date_clear_button = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=16,
            tooltip="Убрать срок",
            visible=False,
            on_click=self.clear_new_due_date,
        )
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
                            self.due_date_button,
                            self.due_date_clear_button,
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

        # --- Shared dialogs / pickers ---------------------------------------
        self.date_picker = ft.DatePicker(
            first_date=date(2020, 1, 1),
            last_date=date(2100, 12, 31),
            on_change=self.on_date_picked,
        )

        self.edit_title_field = ft.TextField(label="Название", autofocus=True)
        self.edit_priority_dropdown = ft.Dropdown(
            label="Приоритет",
            value=Priority.MEDIUM.value,
            options=[ft.DropdownOption(p.value) for p in Priority],
        )
        self.edit_due_button = ft.TextButton(
            content=ft.Text("Без срока"),
            icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
            on_click=lambda e: self.open_date_picker("edit"),
        )
        self.edit_due_clear_button = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=16,
            tooltip="Убрать срок",
            visible=False,
            on_click=self.clear_edit_due_date,
        )
        self.edit_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Редактировать задачу"),
            content=ft.Column(
                controls=[
                    self.edit_title_field,
                    self.edit_priority_dropdown,
                    ft.Row(controls=[self.edit_due_button, self.edit_due_clear_button]),
                ],
                spacing=12,
                tight=True,
                width=320,
            ),
            actions=[
                ft.TextButton("Отмена", on_click=self.close_edit_dialog),
                ft.FilledButton(
                    "Сохранить", icon=ft.Icons.SAVE_ROUNDED, on_click=self.save_edit
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

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
            {"dark_mode": self.page.theme_mode == ft.ThemeMode.DARK}
        )

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
            0, Task(title=title, priority=priority, due_date=self._new_due_date)
        )
        self.new_task_field.value = ""
        self._new_due_date = None
        self.due_date_button.content.value = "Без срока"
        self.due_date_clear_button.visible = False
        self._save_tasks()
        self.refresh()
        await self.new_task_field.focus()

    def clear_new_due_date(self, e: ft.Event) -> None:
        self._new_due_date = None
        self.due_date_button.content.value = "Без срока"
        self.due_date_clear_button.visible = False
        self.page.update()

    # ------------------------------------------------------------------ #
    # Date picker (shared between "add" and "edit" flows)
    # ------------------------------------------------------------------ #
    def open_date_picker(self, target: str) -> None:
        self._date_target = target
        current = self._new_due_date if target == "new" else self._editing_due_date
        self.date_picker.value = current or _today()
        self.page.show_dialog(self.date_picker)

    def on_date_picked(self, e: ft.Event) -> None:
        value = self.date_picker.value
        if value is None:
            return
        chosen = value.date() if isinstance(value, datetime) else value
        if self._date_target == "new":
            self._new_due_date = chosen
            self.due_date_button.content.value = _fmt_due(chosen)
            self.due_date_clear_button.visible = True
        else:
            self._editing_due_date = chosen
            self.edit_due_button.content.value = _fmt_due(chosen)
            self.edit_due_clear_button.visible = True
        self.page.update()

    # ------------------------------------------------------------------ #
    # Filters / search / sort
    # ------------------------------------------------------------------ #
    def _make_filter_handler(self, name: str):
        def handler(e: ft.Event) -> None:
            self.active_filter = name
            for chip in self.filter_chips:
                chip.selected = FILTER_LABELS[name] == chip.label.value
            self.refresh()

        return handler

    def on_search_change(self, e: ft.Event) -> None:
        self.search_query = (self.search_field.value or "").strip().lower()
        self.refresh()

    def _make_sort_handler(self, mode: str):
        def handler(e: ft.Event) -> None:
            self.sort_mode = mode
            self.sort_button.items = self._build_sort_items()
            self.refresh()

        return handler

    # ------------------------------------------------------------------ #
    # Task actions
    # ------------------------------------------------------------------ #
    def toggle_task(self, task: Task):
        def handler(e: ft.Event) -> None:
            task.done = e.control.value
            self._save_tasks()
            self.refresh()

        return handler

    def delete_task(self, task: Task):
        def handler(e: ft.Event) -> None:
            self._undo_snapshot = list(self.tasks)
            self.tasks.remove(task)
            self._save_tasks()
            self.refresh()
            self._show_undo_snackbar(f'Задача «{task.title}» удалена')

        return handler

    def clear_done(self, e: ft.Event) -> None:
        done_count = sum(1 for t in self.tasks if t.done)
        if done_count == 0:
            return
        self._undo_snapshot = list(self.tasks)
        self.tasks = [task for task in self.tasks if not task.done]
        self._save_tasks()
        self.refresh()
        self._show_undo_snackbar(f"Выполненные задачи очищены ({done_count})")

    def _show_undo_snackbar(self, message: str) -> None:
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            action="ОТМЕНИТЬ",
            on_action=self.undo_last_action,
        )
        self.page.show_dialog(snackbar)

    def undo_last_action(self, e: ft.Event) -> None:
        if self._undo_snapshot is None:
            return
        self.tasks = self._undo_snapshot
        self._undo_snapshot = None
        self._save_tasks()
        self.refresh()

    # --- Edit dialog -----------------------------------------------------
    def open_edit_dialog(self, task: Task):
        def handler(e: ft.Event) -> None:
            self._editing_task = task
            self._editing_due_date = task.due_date
            self.edit_title_field.value = task.title
            self.edit_priority_dropdown.value = task.priority.value
            self.edit_due_button.content.value = (
                _fmt_due(task.due_date) if task.due_date else "Без срока"
            )
            self.edit_due_clear_button.visible = task.due_date is not None
            self.page.show_dialog(self.edit_dialog)

        return handler

    def clear_edit_due_date(self, e: ft.Event) -> None:
        self._editing_due_date = None
        self.edit_due_button.content.value = "Без срока"
        self.edit_due_clear_button.visible = False
        self.page.update()

    def close_edit_dialog(self, e: ft.Event) -> None:
        self._editing_task = None
        self.page.pop_dialog()

    def save_edit(self, e: ft.Event) -> None:
        task = self._editing_task
        if task is None:
            return
        title = (self.edit_title_field.value or "").strip()
        if not title:
            return
        task.title = title
        task.priority = Priority(self.edit_priority_dropdown.value or Priority.MEDIUM.value)
        task.due_date = self._editing_due_date
        self._editing_task = None
        self._save_tasks()
        self.page.pop_dialog()
        self.refresh()

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def _status_filtered(self) -> list[Task]:
        if self.active_filter == "Active":
            return [t for t in self.tasks if not t.done]
        if self.active_filter == "Done":
            return [t for t in self.tasks if t.done]
        return list(self.tasks)

    def _visible_tasks(self) -> list[Task]:
        tasks = self._status_filtered()
        if self.search_query:
            tasks = [t for t in tasks if self.search_query in t.title.lower()]

        if self.sort_mode == "priority":
            tasks = sorted(tasks, key=lambda t: PRIORITY_WEIGHT[t.priority])
        elif self.sort_mode == "due":
            tasks = sorted(tasks, key=lambda t: (t.due_date is None, t.due_date or date.max))
        elif self.sort_mode == "title":
            tasks = sorted(tasks, key=lambda t: t.title.lower())
        return tasks

    def _due_chip(self, task: Task) -> Optional[ft.Control]:
        if not task.due_date:
            return None
        overdue = (not task.done) and task.due_date < _today()
        today = (not task.done) and task.due_date == _today()
        if overdue:
            color = ft.Colors.RED_400
            icon = ft.Icons.WARNING_AMBER_ROUNDED
        elif today:
            color = ft.Colors.AMBER_700
            icon = ft.Icons.SCHEDULE_ROUNDED
        else:
            color = ft.Colors.ON_SURFACE_VARIANT
            icon = ft.Icons.EVENT_ROUNDED
        return ft.Row(
            controls=[
                ft.Icon(icon, size=13, color=color),
                ft.Text(_fmt_due(task.due_date), size=11, color=color),
            ],
            spacing=3,
            tight=True,
        )

    def _build_task_card(self, task: Task) -> ft.Control:
        title_style = (
            ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if task.done else None
        )
        badges = [
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(PRIORITY_ICON[task.priority], size=12, color=ft.Colors.WHITE),
                        ft.Text(task.priority.value, size=11, color=ft.Colors.WHITE),
                    ],
                    spacing=2,
                    tight=True,
                ),
                bgcolor=PRIORITY_COLOR[task.priority],
                padding=ft.Padding(8, 2, 8, 2),
                border_radius=20,
            )
        ]
        due_chip = self._due_chip(task)
        if due_chip:
            badges.append(due_chip)

        return ft.Card(
            elevation=0,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            shape=ft.RoundedRectangleBorder(radius=14),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Container(
                border=ft.Border(left=ft.BorderSide(5, PRIORITY_COLOR[task.priority])),
                padding=ft.Padding(10, 8, 4, 8),
                content=ft.Row(
                    controls=[
                        ft.Checkbox(value=task.done, on_change=self.toggle_task(task)),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    task.title,
                                    style=title_style,
                                    color=ft.Colors.ON_SURFACE_VARIANT
                                    if task.done
                                    else None,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Row(controls=badges, spacing=6, wrap=True),
                            ],
                            spacing=6,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_size=18,
                            tooltip="Редактировать",
                            on_click=self.open_edit_dialog(task),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                            icon_size=20,
                            icon_color=ft.Colors.ERROR,
                            tooltip="Удалить",
                            on_click=self.delete_task(task),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )

    def refresh(self) -> None:
        visible = self._visible_tasks()
        self.list_view.controls = [self._build_task_card(t) for t in visible]
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
            if name == "All":
                count = total
            elif name == "Active":
                count = total - done
            else:
                count = done
            chip.label.value = f"{FILTER_LABELS[name]} ({count})"

        self.progress_ring.value = percent / 100
        self.progress_percent_text.value = f"{percent}%"
        self.progress_subtitle_text.value = f"{done} из {total} задач выполнено"
        if total == 0:
            self.progress_title_text.value = "Добавьте первую задачу"
        elif done == total:
            self.progress_title_text.value = "Все задачи выполнены! 🎉"
        else:
            self.progress_title_text.value = "Ваш прогресс"

        self.visible_count_text.value = f"Показано: {len(visible)}"

        self.page.update()


def main(page: ft.Page) -> None:
    TaskFlowApp(page)
