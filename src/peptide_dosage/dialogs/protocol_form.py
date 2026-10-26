"""Create/edit-protocol sheet.

A pushed screen (Toga has no native form dialogs), in the same style as
add_profile.py. db.add_or_update_user_protocol upserts keyed on
(profile, peptide name), so the peptide name is locked while editing —
renaming would silently create a second row instead of renaming.

`prefill` is an optional dict (peptide_name, vial_mg, water_ml, target_dose,
dose_unit, frequency, notes) used to pre-populate a NEW protocol, e.g. from
the calculator or a peptide's catalog page.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from .. import calc, db
from ..nav import Screen
from ..util import num

UNITS = ["mg", "mcg"]
CUSTOM_CHOICE = "Other (type a name)..."

SECTION_LABEL = Pack(font_weight="bold", font_size=13, margin=(12, 0, 4, 0))
ERROR_STYLE = Pack(color="#ff8a80", font_weight="bold")


class ProtocolFormScreen(Screen):
    def __init__(self, nav, profile_id, protocol=None, prefill=None, on_saved=None):
        super().__init__(nav)
        self.profile_id = profile_id
        self.protocol = protocol
        self.prefill = prefill or {}
        self.on_saved = on_saved
        self._catalog = {}
        self._loading = False
        self._auto_notes = ""

    def build(self) -> toga.Box:
        p = self.protocol or self.prefill
        editing = self.protocol is not None

        self._catalog = {e["name"]: e for e in db.get_peptides()}
        name = p.get("peptide_name") or ""

        self._loading = True  # suppress catalog prefill while setting initial values
        try:
            self.peptide = toga.Selection(
                items=[CUSTOM_CHOICE] + list(self._catalog), on_change=self._on_peptide_change,
            )
            self.custom_name = toga.TextInput(placeholder="Peptide name", style=Pack(flex=1))
            if name in self._catalog:
                self.peptide.value = name
            else:
                self.peptide.value = CUSTOM_CHOICE
                self.custom_name.value = name
        finally:
            self._loading = False
        self.custom_name.enabled = self.peptide.value == CUSTOM_CHOICE

        self.vial_mg = toga.NumberInput(value=p.get("vial_mg") or 5, min=0, step=0.01, style=Pack(flex=1))
        self.water_ml = toga.NumberInput(value=p.get("water_ml") or 2, min=0, step=0.01, style=Pack(flex=1))
        self.dose = toga.NumberInput(value=p.get("target_dose") or 250, min=0, step=0.01, style=Pack(flex=1))
        unit = p.get("dose_unit")
        self.unit = toga.Selection(items=UNITS, value=unit if unit in UNITS else "mcg", style=Pack(flex=1))
        self.frequency = toga.TextInput(
            value=p.get("frequency") or "", placeholder="e.g. 3x weekly, daily, every 3 days",
        )
        self.notes = toga.TextInput(value=p.get("notes") or "")
        self.error = toga.Label("", style=ERROR_STYLE)

        if editing:
            peptide_rows = [toga.Label(self.protocol["peptide_name"], style=Pack(font_weight="bold"))]
        else:
            peptide_rows = [self.peptide, self.custom_name]

        return toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Button("< Cancel", on_press=lambda w: self.nav.pop()),
                toga.Label("Edit protocol" if editing else "New protocol", style=SECTION_LABEL),
                toga.Label("Peptide"), *peptide_rows,
                toga.Box(style=Pack(direction=ROW, gap=10), children=[
                    toga.Box(style=Pack(direction=COLUMN, flex=1), children=[toga.Label("Vial size (mg)"), self.vial_mg]),
                    toga.Box(style=Pack(direction=COLUMN, flex=1), children=[toga.Label("BAC water (mL)"), self.water_ml]),
                ]),
                toga.Box(style=Pack(direction=ROW, gap=10), children=[
                    toga.Box(style=Pack(direction=COLUMN, flex=1), children=[toga.Label("Target dose"), self.dose]),
                    toga.Box(style=Pack(direction=COLUMN, flex=1), children=[toga.Label("Unit"), self.unit]),
                ]),
                toga.Label("Frequency"), self.frequency,
                toga.Label("Notes"), self.notes,
                self.error,
                toga.Button("Save changes" if editing else "Save protocol", on_press=self._save),
            ],
        )

    def _on_peptide_change(self, widget):
        """Picking a catalog peptide prefills the fields from its entry."""
        if self._loading:
            return
        choice = self.peptide.value
        self.custom_name.enabled = choice == CUSTOM_CHOICE
        entry = self._catalog.get(choice)
        if entry is None:
            return
        if entry.get("vial_mg"):
            self.vial_mg.value = entry["vial_mg"]
        if entry.get("water_ml"):
            self.water_ml.value = entry["water_ml"]
        if entry.get("dose"):
            self.dose.value = entry["dose"]
        if entry.get("unit") in UNITS:
            self.unit.value = entry["unit"]
        if entry.get("freq"):
            self.frequency.value = entry["freq"]
        # Replace notes only if blank or still our own previous autofill.
        current = (self.notes.value or "").strip()
        if not current or current == self._auto_notes:
            self._auto_notes = (entry.get("notes") or "").strip()
            self.notes.value = self._auto_notes

    def _save(self, widget):
        if self.protocol is not None:
            name = self.protocol["peptide_name"]
        elif self.peptide.value == CUSTOM_CHOICE:
            name = (self.custom_name.value or "").strip()
        else:
            name = self.peptide.value or ""
        if not name:
            self.error.text = "Choose a peptide or type a name."
            return

        vial_mg, water_ml, dose = num(self.vial_mg.value), num(self.water_ml.value), num(self.dose.value)
        unit = self.unit.value
        problem = calc.validate_reconstitution_inputs(vial_mg, water_ml, dose, unit)
        if problem:
            self.error.text = problem
            return

        if self.protocol is None:
            existing = {p["peptide_name"].lower() for p in db.get_user_protocols(self.profile_id)}
            if name.lower() in existing:
                self.error.text = f"This profile already has a {name} protocol. Open it and use Edit protocol."
                return
            canonical = next((n for n in self._catalog if n.lower() == name.lower()), None)
            if canonical:
                name = canonical  # keep catalog spelling so schedule/sources attach
            catalog_entry = self._catalog.get(name) or {}
            schedule = catalog_entry.get("schedule", [])
            sources = catalog_entry.get("sources", [])
        else:
            schedule = self.protocol.get("schedule", [])
            sources = self.protocol.get("sources", [])

        db.add_or_update_user_protocol(
            self.profile_id, name, vial_mg, water_ml, dose, unit,
            (self.frequency.value or "").strip(), (self.notes.value or "").strip(),
            schedule, sources,
        )
        if self.on_saved:
            self.on_saved()
        self.nav.pop()
