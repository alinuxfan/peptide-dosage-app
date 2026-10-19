"""Log-dose sheet — ports the TUI's log-dose action (and EditDoseScreen,
since both just write amount/unit/taken_at/notes through calc.parse_dose_timestamp)."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN
from datetime import datetime, timezone

from .. import calc, db
from ..nav import Screen
from ..util import num

UNITS = ["mg", "mcg"]


class LogDoseScreen(Screen):
    def __init__(self, nav, protocol, entry=None):
        """entry=None logs a new dose; pass an existing dose_log row dict to edit it."""
        super().__init__(nav)
        self.protocol = protocol
        self.entry = entry

    def build(self) -> toga.Box:
        e = self.entry
        self.amount = toga.NumberInput(value=e["dose_amount"] if e else self.protocol["target_dose"], step=1)
        self.unit = toga.Selection(items=UNITS, value=e["dose_unit"] if e else self.protocol["dose_unit"])
        self.taken_at = toga.TextInput(value=e["taken_at"] if e else "", placeholder="blank = now, or YYYY-MM-DD HH:MM")
        self.notes = toga.TextInput(value=e["notes"] if e else "")
        self.error = toga.Label("")

        return toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Button("< Cancel", on_press=lambda w: self.nav.pop()),
                toga.Label("Amount"), self.amount,
                toga.Label("Unit"), self.unit,
                toga.Label("Taken at"), self.taken_at,
                toga.Label("Notes"), self.notes,
                self.error,
                toga.Button("Save", on_press=self._save),
            ],
        )

    def _save(self, widget):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            parsed = calc.parse_dose_timestamp(self.taken_at.value or "", now)
        except ValueError as e:
            self.error.text = str(e)
            return

        if self.entry is None:
            db.log_dose(
                self.protocol["profile_id"], self.protocol["id"], self.protocol["peptide_name"],
                num(self.amount.value), self.unit.value, self.notes.value or "", taken_at=parsed,
            )
        else:
            db.update_dose_log_entry(
                self.entry["id"], num(self.amount.value), self.unit.value,
                parsed or self.entry["taken_at"], self.notes.value or "",
            )
        self.nav.pop()
