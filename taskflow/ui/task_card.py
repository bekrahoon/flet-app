from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

import flet as ft

from ..models import PRIORITY_WEIGHT, Priority, Recurrence, Subtask, Task
from ..time_utils import format_due, is_due_today, is_overdue, relative_due

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


class TaskCardCallbacks:
    """Bundles the event handlers a task card needs, so `build_task_card`
    doesn't have to take a dozen separate callback parameters."""

    def __init__(
        self,
        on_toggle: Callable[[Task], Callable],
        on_edit: Callable[[Task], Callable],
        on_delete: Callable[[Task], Callable],
        on_pin: Callable[[Task], Callable],
        on_toggle_expand: Callable[[Task], Callable],
        on_subtask_toggle: Callable[[Task, Subtask], Callable],
    ) -> None:
        self.on_toggle = on_toggle
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_pin = on_pin
        self.on_toggle_expand = on_toggle_expand
        self.on_subtask_toggle = on_subtask_toggle


def _due_chip(task: Task, now: datetime, tag_colors: dict[str, str]) -> Optional[ft.Control]:
    if not task.due_at:
        return None
    overdue = is_overdue(task, now)
    today = (not task.done) and is_due_today(task, now)
    if overdue:
        color = ft.Colors.RED_400
        icon = ft.Icons.WARNING_AMBER_ROUNDED
    elif today:
        color = ft.Colors.AMBER_700
        icon = ft.Icons.SCHEDULE_ROUNDED
    else:
        color = ft.Colors.ON_SURFACE_VARIANT
        icon = ft.Icons.EVENT_ROUNDED
    label = f"{format_due(task.due_at, task.due_has_time)} · {relative_due(task.due_at, task.due_has_time, now)}"
    return ft.Row(
        controls=[
            ft.Icon(icon, size=13, color=color),
            ft.Text(label, size=11, color=color),
        ],
        spacing=3,
        tight=True,
    )


def _tag_chip(name: str, color: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(name, size=10, color=ft.Colors.WHITE),
        bgcolor=color,
        padding=ft.Padding(7, 1, 7, 1),
        border_radius=10,
    )


def build_task_card(
    task: Task,
    callbacks: TaskCardCallbacks,
    tag_colors: dict[str, str],
    expanded: bool,
    now: Optional[datetime] = None,
) -> ft.Control:
    now = now or datetime.now()
    title_style = (
        ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if task.done else None
    )

    badges: list[ft.Control] = [
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
    due_chip = _due_chip(task, now, tag_colors)
    if due_chip:
        badges.append(due_chip)
    if task.recurrence != Recurrence.NONE:
        badges.append(ft.Icon(ft.Icons.REPEAT_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT))
    for tag in task.tags:
        badges.append(_tag_chip(tag, tag_colors.get(tag, ft.Colors.BLUE_GREY_400)))
    if task.subtasks:
        done_count = sum(1 for s in task.subtasks if s.done)
        badges.append(
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECKLIST_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(
                        f"{done_count}/{len(task.subtasks)}",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=2,
                tight=True,
            )
        )

    trailing_buttons = [
        ft.IconButton(
            icon=ft.Icons.PUSH_PIN_ROUNDED if task.pinned else ft.Icons.PUSH_PIN_OUTLINED,
            icon_size=18,
            icon_color=ft.Colors.AMBER_700 if task.pinned else None,
            tooltip="Открепить" if task.pinned else "Закрепить",
            on_click=callbacks.on_pin(task),
        ),
    ]
    if task.subtasks:
        trailing_buttons.append(
            ft.IconButton(
                icon=ft.Icons.EXPAND_LESS_ROUNDED if expanded else ft.Icons.EXPAND_MORE_ROUNDED,
                icon_size=20,
                tooltip="Подзадачи",
                on_click=callbacks.on_toggle_expand(task),
            )
        )
    trailing_buttons.extend(
        [
            ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_size=18,
                tooltip="Редактировать",
                on_click=callbacks.on_edit(task),
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                icon_size=20,
                icon_color=ft.Colors.ERROR,
                tooltip="Удалить",
                on_click=callbacks.on_delete(task),
            ),
        ]
    )

    main_row = ft.Row(
        controls=[
            ft.Checkbox(value=task.done, on_change=callbacks.on_toggle(task)),
            ft.Column(
                controls=[
                    ft.Text(
                        task.title,
                        style=title_style,
                        color=ft.Colors.ON_SURFACE_VARIANT if task.done else None,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Row(controls=badges, spacing=6, wrap=True),
                ],
                spacing=6,
                expand=True,
            ),
            *trailing_buttons,
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    column_controls: list[ft.Control] = [main_row]
    if expanded and task.subtasks:
        subtask_rows = [
            ft.Row(
                controls=[
                    ft.Checkbox(
                        value=subtask.done,
                        scale=0.85,
                        on_change=callbacks.on_subtask_toggle(task, subtask),
                    ),
                    ft.Text(
                        subtask.title,
                        size=13,
                        style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)
                        if subtask.done
                        else None,
                        color=ft.Colors.ON_SURFACE_VARIANT if subtask.done else None,
                        expand=True,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            for subtask in task.subtasks
        ]
        column_controls.append(
            ft.Container(
                content=ft.Column(controls=subtask_rows, spacing=0, tight=True),
                padding=ft.Padding(38, 0, 4, 4),
            )
        )
    if task.notes:
        column_controls.append(
            ft.Container(
                content=ft.Text(task.notes, size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                padding=ft.Padding(38, 0, 4, 4),
            )
        )

    return ft.Card(
        elevation=0,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        shape=ft.RoundedRectangleBorder(radius=14),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Container(
            border=ft.Border(left=ft.BorderSide(5, PRIORITY_COLOR[task.priority])),
            padding=ft.Padding(10, 8, 4, 8),
            content=ft.Column(controls=column_controls, spacing=4, tight=True),
        ),
    )
