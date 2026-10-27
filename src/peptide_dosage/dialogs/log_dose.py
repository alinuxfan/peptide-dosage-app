"""Log-dose sheet — ports the TUI's log-dose action (and EditDoseScreen,
since both just write amount/unit/taken_at/notes through calc.parse_dose_timestamp).

Times are typed and shown in the user's LOCAL time; the database stores naive
UTC, so util.local_input_to_utc / util.utc_to_local_input convert at the edge."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import db
from ..nav import Screen
from ..util import local_input_to_utc, num, utc_to_local_input

UNITS = ["mg", "mcg"]

ERROR_STYLE = Pack(color="#ff8a80", font_weight="bold")


class LogDoseScreen(Screen):
    def __init__(self, nav, protocol, entry=None):
        """entry=None logs a new dose; pass an existing dose_log row dict to edit it."""
        super().__init__(nav)
        self.protocol = protocol
        self.entry = entry

    def build(self) -> toga.Box:
        e = self.entry
        # Shown in local time; remembered so an untouched field keeps the
        # stored value (and its seconds) instead of being re-parsed.
        self._initial_taken_at = utc_to_local_input(e["taken_at"]) if e else ""
        self.amount = toga.NumberInput(value=e["dose_amount"] if e else self.protocol["target_dose"], step=1)
        self.unit = toga.Selection(items=UNITS, value=e["dose_unit"] if e else self.protocol["dose_unit"])
        self.taken_at = toga.TextInput(
            value=self._initial_taken_at,
            placeholder=("blank = keep current time" if e else "blank = now")
            + ", or YYYY-MM-DD HH:MM (your local time)",
        )
        self.notes = toga.TextInput(value=(e["notes"] or "") if e else "")
        self.error = toga.Label("", style=ERROR_STYLE)

        children = [
            toga.Button("< Cancel", on_press=lambda w: self.nav.pop()),
            toga.Label(f"{'Edit dose' if e else 'Log dose'} — {self.protocol['peptide_name']}",
                       style=Pack(font_weight="bold", font_size=15, margin=(8, 0))),
            toga.Label("Amount"), self.amount,
            toga.Label("Unit"), self.unit,
            toga.Label("Taken at (local time)"), self.taken_at,
            toga.Label("Notes"), self.notes,
            self.error,
            toga.Button("Save", on_press=self._save),
        ]
        if e is None:
            children.append(toga.Button("Log now", on_press=self._log_now))
        else:
            children.append(toga.Button("Delete this dose", on_press=self._delete))
        return toga.Box(style=Pack(direction=COLUMN, margin=12, gap=4), children=children)

    def _validated_amount(self):
        amount = num(self.amount.value)
        if amount <= 0:
            self.error.text = "Enter a dose amount greater than zero."
            return None
        return amount

    def _log_now(self, widget):
        """Fast path: log with the current amount/unit/notes, timestamped now."""
        if (self.taken_at.value or "").strip():
            # Don't silently discard a typed time; Save honours it.
            self.error.text = 'Clear the "Taken at" field to log now, or tap Save to use that time.'
            return
        amount = self._validated_amount()
        if amount is None:
            return
        db.log_dose(
            self.protocol["profile_id"], self.protocol["id"], self.protocol["peptide_name"],
            amount, self.unit.value, self.notes.value or "",
        )
        self.nav.pop()

    def _save(self, widget):
        text = (self.taken_at.value or "").strip()
        if self.entry is not None and text == self._initial_taken_at:
            taken_at = self.entry["taken_at"]  # unchanged: keep the stored UTC value exactly
        else:
            try:
                taken_at = local_input_to_utc(text)
            except ValueError as e:
                self.error.text = str(e)
                return

        amount = self._validated_amount()
        if amount is None:
            return

        if self.entry is None:
            db.log_dose(
                self.protocol["profile_id"], self.protocol["id"], self.protocol["peptide_name"],
                amount, self.unit.value, self.notes.value or "", taken_at=taken_at,
            )
        else:
            db.update_dose_log_entry(
                self.entry["id"], amount, self.unit.value,
                taken_at or self.entry["taken_at"], self.notes.value or "",
            )
        self.nav.pop()

    async def _delete(self, widget):
        if await self.nav.window.confirm_dialog(
            "Delete dose", "Delete this logged dose? This can't be undone."
        ):
            db.delete_dose_log_entry(self.entry["id"])
            self.nav.pop()
