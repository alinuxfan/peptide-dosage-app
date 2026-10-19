"""Protocol detail — merges the TUI's schedule-tab + dose-log-tab for one
protocol, reached by tapping a card in PatientsScreen. Replaces three TUI
tabs (patient/schedule/dose-log) with one list + this one drill-down."""

from datetime import datetime, timezone

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import calc, db
from ..nav import Screen


class ProtocolDetailScreen(Screen):
    def __init__(self, nav, protocol_id, on_deleted=None):
        super().__init__(nav)
        self.protocol_id = protocol_id
        self.on_deleted = on_deleted  # callback to refresh the card list after delete

    def build(self) -> toga.Box:
        self.status = toga.Label("")
        self.dose_log_box = toga.Box(style=Pack(direction=COLUMN))
        self.box = toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Button("< Back", on_press=lambda w: self.nav.pop()),
                self.status,
                toga.Button("Log a dose", on_press=self._log_dose),
                toga.Button("Mark reconstituted (new vial)", on_press=self._mark_reconstituted),
                toga.Button("Generate titration schedule", on_press=self._generate_schedule),
                toga.Button("Delete protocol", on_press=self._delete),
                toga.Label("Dose log"),
                self.dose_log_box,
            ],
        )
        self._refresh()
        return self.box

    def on_shown(self):
        self._refresh()

    def _refresh(self):
        protocol = db.get_user_protocol_by_id(self.protocol_id)
        if protocol is None:
            self.nav.pop()
            return
        self.protocol = protocol

        adherence_by_id = {a["protocol_id"]: a for a in db.get_protocol_adherence(protocol["profile_id"])}
        a = adherence_by_id.get(self.protocol_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        lines = [
            f"{protocol['peptide_name']} — {protocol['target_dose']} {protocol['dose_unit']} ({protocol['frequency']})",
        ]
        if a:
            lines.append(f"BUD: {calc.format_bud_label(a['bud_expiry_at'], now)}")
            lines.append(calc.format_doses_remaining(a["doses_remaining"], a["doses_total"]))
            lines.append(f"Adherence: {a['adherence_label']}")
        self.status.text = "\n".join(lines)

        self.dose_log_box.clear()
        entries = [e for e in db.get_dose_log(protocol["profile_id"]) if e["protocol_id"] == self.protocol_id]
        for entry in entries[:20]:
            row = toga.Box(style=Pack(direction=COLUMN, margin=(0, 0, 6, 0)), children=[
                toga.Label(f"{entry['taken_at']}  {entry['dose_amount']}{entry['dose_unit']}"
                           + (f" — {entry['notes']}" if entry["notes"] else "")),
            ])
            self.dose_log_box.add(row)

    def _log_dose(self, widget):
        from ..dialogs.log_dose import LogDoseScreen
        self.nav.push(lambda nav: LogDoseScreen(nav, self.protocol))

    async def _mark_reconstituted(self, widget):
        if await self.nav.window.confirm_dialog(
            "Mark reconstituted",
            "Start a fresh vial? This resets the dose-inventory count but keeps dose history.",
        ):
            db.set_protocol_reconstituted(self.protocol_id)
            self._refresh()

    def _generate_schedule(self, widget):
        from ..dialogs.titration_generator import TitrationGeneratorScreen
        self.nav.push(lambda nav: TitrationGeneratorScreen(nav, self.protocol))

    async def _delete(self, widget):
        if await self.nav.window.confirm_dialog(
            "Delete protocol", f"Delete the {self.protocol['peptide_name']} protocol? Dose history is kept."
        ):
            db.delete_user_protocol(self.protocol_id)
            if self.on_deleted:
                self.on_deleted()
            self.nav.pop()
