from __future__ import annotations

from datetime import date, datetime, time as time_cls
from typing import Callable, Optional

import flet as ft

from ..time_utils import format_due


class DueDatePicker:
    """Owns a DatePicker + TimePicker pair and drives a "due date" button's
    label and its adjacent clear (x) button.

    Flow: opening shows the DatePicker; once a date is confirmed, the
    TimePicker opens right away. Confirming the TimePicker stores a
    date+time deadline; dismissing/cancelling it keeps the date only.
    """

    def __init__(self, page: ft.Page, on_change: Optional[Callable[[], None]] = None) -> None:
        self.page = page
        self.on_change = on_change
        self.value: Optional[datetime] = None
        self.has_time: bool = False
        self._pending_date: Optional[date] = None

        self.date_picker = ft.DatePicker(
            first_date=date(2020, 1, 1),
            last_date=date(2100, 12, 31),
            on_change=self._on_date_picked,
        )
        self.time_picker = ft.TimePicker(
            hour_format=ft.TimePickerHourFormat.H24,
            on_change=self._on_time_picked,
            on_dismiss=self._on_time_dismissed,
        )
        self.button = ft.TextButton(
            content=ft.Text("Без срока"),
            icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
            on_click=lambda e: self.open(),
        )
        self.clear_button = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=16,
            tooltip="Убрать срок",
            visible=False,
            on_click=lambda e: self.clear(),
        )

    def open(self) -> None:
        self.date_picker.value = self.value or datetime.now()
        self.page.show_dialog(self.date_picker)

    def _on_date_picked(self, e: ft.Event) -> None:
        picked = self.date_picker.value
        if picked is None:
            return
        self._pending_date = picked.date() if isinstance(picked, datetime) else picked
        self.time_picker.value = self.value.time() if self.value else datetime.now().time()
        self.page.show_dialog(self.time_picker)

    def _on_time_picked(self, e: ft.Event) -> None:
        if self._pending_date is None:
            return
        picked_time = self.time_picker.value or datetime.now().time()
        self.value = datetime.combine(self._pending_date, picked_time)
        self.has_time = True
        self._pending_date = None
        self._refresh_label()

    def _on_time_dismissed(self, e: ft.Event) -> None:
        if self._pending_date is None:
            return  # already handled by _on_time_picked (confirmed pick)
        self.value = datetime.combine(self._pending_date, time_cls.min)
        self.has_time = False
        self._pending_date = None
        self._refresh_label()

    def clear(self) -> None:
        self.value = None
        self.has_time = False
        self._refresh_label()

    def set(self, value: Optional[datetime], has_time: bool) -> None:
        self.value = value
        self.has_time = has_time
        self._refresh_label()

    def _refresh_label(self) -> None:
        if self.value is None:
            self.button.content.value = "Без срока"
            self.clear_button.visible = False
        else:
            self.button.content.value = format_due(self.value, self.has_time)
            self.clear_button.visible = True
        self.page.update()
        if self.on_change:
            self.on_change()
