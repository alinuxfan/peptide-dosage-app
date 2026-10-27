"""Protocol detail — merges the TUI's schedule-tab + dose-log-tab for one
protocol, reached by tapping a card in PatientsScreen. Replaces three TUI
tabs (patient/schedule/dose-log) with one list + this one drill-down."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import calc, db
from ..nav import Screen
from ..util import utc_now_naive, utc_to_local_display

MAX_LOG_ROWS = 20

SECTION_STYLE = Pack(font_weight="bold", font_size=14, margin=(14, 0, 4, 0))
LINE_STYLE = Pack(font_size=12, margin=(1, 0))
TITLE_STYLE = Pack(font_weight="bold", font_size=16, margin=(8, 0, 0, 0))
WARNING_STYLE = Pack(color="#ffb74d", font_weight="bold", font_size=12, margin=(4, 0))
STATUS_STYLE = Pack(color="#81c784", font_weight="bold", margin=(4, 0))
MUTED_STYLE = Pack(font_size=12, color="#8fa3b3", margin=(2, 0))


def _fmt_dose(amount) -> str:
    """250.0 -> "250", 0.25 -> "0.25" (dose amounts are floats). Fixed-point
    rather than %g so tiny/huge values never switch to exponent notation."""
    try:
        return f"{float(amount):.6f}".rstrip("0").rstrip(".") or "0"
    except (TypeError, ValueError):
        return str(amount)


class ProtocolDetailScreen(Screen):
    def __init__(self, nav, protocol_id, on_deleted=None):
        super().__init__(nav)
        self.protocol_id = protocol_id
        self.on_deleted = on_deleted  # callback to refresh the card list after delete

    def build(self) -> toga.Box:
        self.title = toga.Label("", style=TITLE_STYLE)
        self.status = toga.Label("", style=STATUS_STYLE)  # transient feedback ("Logged 250 mcg")
        self.summary_box = toga.Box(style=Pack(direction=COLUMN))
        self.vial_box = toga.Box(style=Pack(direction=COLUMN))
        self.schedule_box = toga.Box(style=Pack(direction=COLUMN))
        self.dose_log_box = toga.Box(style=Pack(direction=COLUMN, gap=4))
        self.box = toga.Box(
            style=Pack(direction=COLUMN, margin=12, gap=4),
            children=[
                toga.Button("< Back", on_press=lambda w: self.nav.pop()),
                self.title,
                self.status,
                toga.Button("Log dose now", on_press=self._log_dose_now),
                toga.Button("Log a dose (custom time/amount)", on_press=self._log_dose),
                toga.Button("Edit protocol", on_press=self._edit_protocol),
                toga.Button("Mark reconstituted (new vial)", on_press=self._mark_reconstituted),
                toga.Button("Generate titration schedule", on_press=self._generate_schedule),
                toga.Button("Delete protocol", on_press=self._delete),
                toga.Label("Summary", style=SECTION_STYLE), self.summary_box,
                toga.Label("Vial", style=SECTION_STYLE), self.vial_box,
                toga.Label("Schedule", style=SECTION_STYLE), self.schedule_box,
                toga.Label("Dose log", style=SECTION_STYLE), self.dose_log_box,
            ],
        )
        self._refresh()
        # nav.NavigationController already wraps every screen in a vertical
        # ScrollContainer, so no scroller of our own here (it would nest).
        return self.box

    def on_shown(self):
        self._refresh()

    @staticmethod
    def _fill(box, lines, style=LINE_STYLE):
        """Replace a section's contents with one Label per line."""
        box.clear()
        for line in lines:
            box.add(toga.Label(line, style=style))

    def _refresh(self):
        protocol = db.get_user_protocol_by_id(self.protocol_id)
        if protocol is None:
            self.nav.pop()
            return
        self.protocol = protocol

        adherence_by_id = {a["protocol_id"]: a for a in db.get_protocol_adherence(protocol["profile_id"])}
        a = adherence_by_id.get(self.protocol_id)
        now = utc_now_naive()
        weekly_exp = calc.parse_weekly_frequency(protocol["frequency"])

        self.title.text = protocol["peptide_name"]

        # --- Summary ---
        summary = [f"Dose: {_fmt_dose(protocol['target_dose'])} {protocol['dose_unit']} ({protocol['frequency']})"]
        if a:
            summary.append(f"Next dose: {calc.format_due_label(a['next_due_at'], now)}")
            summary.append(f"Adherence: {a['adherence_label']}")
        self._fill(self.summary_box, summary)

        # --- Vial ---
        vial = [f"Vial: {_fmt_dose(protocol['vial_mg'])} mg in {_fmt_dose(protocol['water_ml'])} mL water"]
        if a:
            vial.append(f"BUD: {calc.format_bud_label(a['bud_expiry_at'], now)}")
            vial.append(f"Remaining: {calc.format_doses_remaining(a['doses_remaining'], a['doses_total'])}")
            vial.append(
                "Vial lasts: " + calc.format_vial_duration(a["doses_total"], weekly_exp, protocol["frequency"])
            )
        vial.append(
            "Inventory needed: "
            + calc.format_inventory_projection(
                protocol.get("schedule"), protocol["target_dose"], protocol["dose_unit"],
                weekly_exp, protocol["vial_mg"],
            )
        )
        self._fill(self.vial_box, vial)
        if a and a["bud_exceeded"]:
            self.vial_box.add(toga.Label(
                f"Warning: at this dose and frequency one vial takes longer than its "
                f"{calc.DEFAULT_BUD_DAYS:g}-day beyond-use date, so the last doses may be "
                "past BUD. Consider a smaller vial or splitting it.",
                style=WARNING_STYLE,
            ))

        # --- Schedule ---
        schedule = protocol.get("schedule") or []
        if schedule:
            self._fill(self.schedule_box, [
                f"{label}: {_fmt_dose(dose)} {unit}" for label, dose, unit in schedule
            ])
        else:
            self._fill(
                self.schedule_box,
                ['No titration schedule. Use "Generate titration schedule" to add one.'],
                style=MUTED_STYLE,
            )

        # --- Dose log ---
        self.dose_log_box.clear()
        entries = [e for e in db.get_dose_log(protocol["profile_id"]) if e["protocol_id"] == self.protocol_id]
        if not entries:
            self.dose_log_box.add(toga.Label("No doses logged yet", style=MUTED_STYLE))
        for entry in entries[:MAX_LOG_ROWS]:
            text = f"{utc_to_local_display(entry['taken_at'])}  {_fmt_dose(entry['dose_amount'])} {entry['dose_unit']}"
            if entry["notes"]:
                note = entry["notes"].replace("\n", " ")
                text += f" — {note[:40]}{'…' if len(note) > 40 else ''}"
            self.dose_log_box.add(toga.Button(text, on_press=self._make_edit_entry(entry["id"])))
        if len(entries) > MAX_LOG_ROWS:
            self.dose_log_box.add(toga.Label(
                f"Showing the latest {MAX_LOG_ROWS} of {len(entries)} doses.", style=MUTED_STYLE
            ))
        elif entries:
            self.dose_log_box.add(toga.Label("Tap a dose to edit or delete it.", style=MUTED_STYLE))

    def _log_dose_now(self, widget):
        """One-tap log of the protocol's dose, timestamped now."""
        p = self.protocol
        db.log_dose(p["profile_id"], p["id"], p["peptide_name"], p["target_dose"], p["dose_unit"])
        self._refresh()
        self.status.text = f"Logged {_fmt_dose(p['target_dose'])} {p['dose_unit']} of {p['peptide_name']}."

    def _make_edit_entry(self, entry_id):
        def handler(widget):
            from ..dialogs.log_dose import LogDoseScreen
            entry = db.get_dose_log_entry_by_id(entry_id)
            if entry is None:  # deleted elsewhere since the list was drawn
                self._refresh()
                return
            self.nav.push(lambda nav: LogDoseScreen(nav, self.protocol, entry=entry))
        return handler

    def _edit_protocol(self, widget):
        from ..dialogs.protocol_form import ProtocolFormScreen
        self.nav.push(lambda nav: ProtocolFormScreen(
            nav, self.protocol["profile_id"], protocol=self.protocol, on_saved=self._refresh,
        ))

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
