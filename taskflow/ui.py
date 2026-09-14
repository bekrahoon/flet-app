from __future__ import annotations

import flet as ft

from .models import Priority, Task
from .storage import SettingsStore, TaskStore

PRIORITY_COLOR = {
    Priority.LOW: ft.Colors.GREEN_600,
    Priority.MEDIUM: ft.Colors.AMBER_700,
    Priority.HIGH: ft.Colors.RED_400,
}

FILTERS = ("All", "Active", "Done")


class TaskFlowApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.task_store = TaskStore()
        self.settings_store = SettingsStore()

        self.tasks: list[Task] = self.task_store.load()
        self.active_filter: str = "All"

        settings = self.settings_store.load()
        page.theme_mode = (
            ft.ThemeMode.DARK
            if settings.get("dark_mode")
            else ft.ThemeMode.LIGHT
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
        page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO, use_material3=True)
        page.dark_theme = ft.Theme(
            color_scheme_seed=ft.Colors.INDIGO, use_material3=True
        )
        page.padding = 0
        page.window.width = 420
        page.window.height = 760
        page.window.min_width = 360
        page.window.min_height = 500
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
                        ft.Row(
                            controls=[self.new_task_field, self.priority_dropdown],
                            spacing=8,
                        ),
                        ft.Row(
                            controls=[self.add_button],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                        ft.Row(controls=self.filter_chips, spacing=8),
                        ft.Divider(height=1),
                        ft.Stack(
                            controls=[self.list_view, self.empty_state],
                            expand=True,
                        ),
                        ft.Divider(height=1),
                        ft.Row(
                            controls=[self.stats_text, self.clear_done_button],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=12,
                    expand=True,
                ),
                padding=ft.Padding(16, 16, 16, 16),
                expand=True,
            )
        )

    def _build_controls(self) -> None:
        self.theme_button = ft.IconButton(
            icon=self._theme_icon(),
            tooltip="Сменить тему",
            on_click=self.toggle_theme,
        )

        self.new_task_field = ft.TextField(
            hint_text="Что нужно сделать?",
            expand=True,
            border_radius=10,
            on_submit=self.add_task,
        )
        self.priority_dropdown = ft.Dropdown(
            width=130,
            value=Priority.MEDIUM.value,
            options=[ft.DropdownOption(p.value) for p in Priority],
        )
        self.add_button = ft.ElevatedButton(
            "Добавить",
            icon=ft.Icons.ADD_CIRCLE_ROUNDED,
            on_click=self.add_task,
        )

        self.filter_chips = [
            ft.Chip(
                label=ft.Text(name),
                selected=(name == self.active_filter),
                show_checkmark=False,
                on_select=self._make_filter_handler(name),
            )
            for name in FILTERS
        ]

        self.list_view = ft.ListView(expand=True, spacing=10, auto_scroll=False)
        self.empty_state = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.INBOX_ROUNDED, size=48, color=ft.Colors.OUTLINE),
                    ft.Text("Задач нет", color=ft.Colors.OUTLINE),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
            visible=False,
        )

        self.stats_text = ft.Text("", color=ft.Colors.ON_SURFACE_VARIANT)
        self.clear_done_button = ft.TextButton(
            "Очистить выполненные",
            icon=ft.Icons.DELETE_SWEEP_ROUNDED,
            on_click=self.clear_done,
        )

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
    # Event handlers
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

    async def add_task(self, e: ft.Event) -> None:
        title = self.new_task_field.value.strip() if self.new_task_field.value else ""
        if not title:
            await self.new_task_field.focus()
            return
        priority = Priority(self.priority_dropdown.value or Priority.MEDIUM.value)
        self.tasks.insert(0, Task(title=title, priority=priority))
        self.new_task_field.value = ""
        self._save_tasks()
        self.refresh()
        await self.new_task_field.focus()

    def _make_filter_handler(self, name: str):
        def handler(e: ft.Event) -> None:
            self.active_filter = name
            for chip in self.filter_chips:
                chip.selected = chip.label.value == name
            self.refresh()

        return handler

    def toggle_task(self, task: Task):
        def handler(e: ft.Event) -> None:
            task.done = e.control.value
            self._save_tasks()
            self.refresh()

        return handler

    def delete_task(self, task: Task):
        def handler(e: ft.Event) -> None:
            self.tasks.remove(task)
            self._save_tasks()
            self.refresh()

        return handler

    def clear_done(self, e: ft.Event) -> None:
        self.tasks = [task for task in self.tasks if not task.done]
        self._save_tasks()
        self.refresh()

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def _filtered_tasks(self) -> list[Task]:
        if self.active_filter == "Active":
            return [t for t in self.tasks if not t.done]
        if self.active_filter == "Done":
            return [t for t in self.tasks if t.done]
        return self.tasks

    def _build_task_card(self, task: Task) -> ft.Control:
        title_style = (
            ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)
            if task.done
            else None
        )
        return ft.Card(
            content=ft.Container(
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
                                ft.Container(
                                    content=ft.Text(
                                        task.priority.value,
                                        size=11,
                                        color=ft.Colors.WHITE,
                                    ),
                                    bgcolor=PRIORITY_COLOR[task.priority],
                                    padding=ft.Padding(8, 2, 8, 2),
                                    border_radius=20,
                                ),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                            icon_color=ft.Colors.ERROR,
                            tooltip="Удалить",
                            on_click=self.delete_task(task),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(12, 8, 4, 8),
            ),
        )

    def refresh(self) -> None:
        filtered = self._filtered_tasks()
        self.list_view.controls = [self._build_task_card(t) for t in filtered]
        self.empty_state.visible = len(filtered) == 0

        total = len(self.tasks)
        done = sum(1 for t in self.tasks if t.done)
        self.stats_text.value = f"Выполнено {done} из {total}"

        self.page.update()


def main(page: ft.Page) -> None:
    TaskFlowApp(page)
