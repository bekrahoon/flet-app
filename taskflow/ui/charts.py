from __future__ import annotations

from datetime import date

import flet as ft

WEEKDAY_LABELS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def build_week_bar_chart(data: list[tuple[date, int]], *, max_bar_height: int = 110) -> ft.Control:
    """A minimal bar chart built from plain Containers (this Flet version
    has no BarChart control) showing daily counts for the given days."""
    max_value = max((count for _, count in data), default=0) or 1
    bars = []
    for day, count in data:
        bar_height = max(4, round(max_bar_height * count / max_value)) if count else 4
        bars.append(
            ft.Column(
                controls=[
                    ft.Text(str(count), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(
                        height=bar_height,
                        width=22,
                        border_radius=6,
                        bgcolor=ft.Colors.DEEP_PURPLE_300 if count else ft.Colors.OUTLINE_VARIANT,
                    ),
                    ft.Text(WEEKDAY_LABELS_RU[day.weekday()], size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            )
        )
    return ft.Row(
        controls=bars,
        alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        vertical_alignment=ft.CrossAxisAlignment.END,
        height=max_bar_height + 40,
    )
