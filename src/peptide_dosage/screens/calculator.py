"""Calculator screen — single-column port of the TUI's calc-tab.

Mirrors main.py's pattern: inputs don't auto-derive anything, each
on_change handler explicitly calls recalculate(). The syringe gauge
(widgets/syringe.py) replaces the TUI's ASCII make_syringe_display with
an actual drawing, which is the one part of this port worth doing as a
real graphic rather than a text port.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from .. import calc, db
from ..nav import Screen
from ..util import num
from ..widgets.syringe import SyringeGauge

UNITS = ["mg", "mcg"]
# U-100 insulin syringes: 0.3 / 0.5 / 1.0 mL hold 30 / 50 / 100 units.
SYRINGES = {"30 U (0.3 mL)": 30.0, "50 U (0.5 mL)": 50.0, "100 U (1 mL)": 100.0}
DEFAULT_SYRINGE = "100 U (1 mL)"
CUSTOM = "Custom"

SECTION_LABEL = Pack(font_weight="bold", font_size=13, margin=(12, 0, 4, 0))
CARD_STYLE = Pack(direction=COLUMN, background_color="#1f2d3a", margin=12, gap=6)
CARD_HEADLINE = Pack(font_size=20, font_weight="bold", color="#e8eef3")
CARD_SUBLINE = Pack(font_size=12, color="#b8c4ce")
ERROR_STYLE = Pack(color="#ff8a80", font_weight="bold")
HINT_STYLE = Pack(font_size=12, margin=(2, 0, 0, 0))


def _fmt(value: float) -> str:
    """Compact number: 0.25 -> '0.25', 250.0 -> '250', no trailing zeros."""
    return f"{value:.4f}".rstrip("0").rstrip(".") or "0"


class CalculatorScreen(Screen):
    def __init__(self, nav):
        super().__init__(nav)
        # NavigationController re-runs build() whenever a pushed screen is
        # popped, so remember the inputs and restore them in build().
        self._saved: dict = {}
        self._freq = ""
        self._loading = False

    def build(self) -> toga.Box:
        saved = self._saved
        self._loading = True
        self.vial_mg = toga.NumberInput(value=saved.get("vial_mg", 5), min=0, step=0.1, on_change=self._on_change, style=Pack(flex=1))
        self.water_ml = toga.NumberInput(value=saved.get("water_ml", 2), min=0, step=0.1, on_change=self._on_change, style=Pack(flex=1))
        self.dose = toga.NumberInput(value=saved.get("dose", 250), min=0, step=1, on_change=self._on_change, style=Pack(flex=1))
        self.unit = toga.Selection(items=UNITS, value=saved.get("unit", "mcg"), on_change=self._on_change, style=Pack(flex=1))
        self.syringe_size = toga.Selection(
            items=list(SYRINGES), value=saved.get("syringe", DEFAULT_SYRINGE),
            on_change=self._on_change, style=Pack(flex=1),
        )

        try:
            self._presets = {p["name"]: p for p in db.get_peptides() if p["name"] != CUSTOM}
        except Exception:  # db not ready / unreadable: calculator still works as "Custom"
            self._presets = {}
        self.preset = toga.Selection(
            items=[CUSTOM, *self._presets], on_change=self._on_preset, style=Pack(flex=1),
        )
        preset_name = saved.get("preset", CUSTOM)
        if preset_name in self._presets:
            self.preset.value = preset_name
        else:
            self._freq = ""

        self.equiv_label = toga.Label("", style=HINT_STYLE)
        self.error_label = toga.Label("", style=ERROR_STYLE)
        self.headline = toga.Label("", style=CARD_HEADLINE)
        self.gauge = SyringeGauge(max_capacity=SYRINGES[self.syringe_size.value])
        self.draw_status = toga.Label("", style=CARD_SUBLINE)
        self.subline = toga.Label("", style=CARD_SUBLINE)
        self.duration_label = toga.Label("", style=CARD_SUBLINE)

        self.card = toga.Box(style=CARD_STYLE, children=[
            self.headline, self.gauge, self.draw_status, self.subline, self.duration_label,
        ])

        box = toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Label("Peptide preset (optional)", style=SECTION_LABEL),
                self.preset,
                toga.Label("Reconstitution", style=SECTION_LABEL),
                toga.Box(style=Pack(direction=ROW, gap=10), children=[
                    toga.Box(style=Pack(direction=COLUMN, flex=1), children=[
                        toga.Label("Vial size (mg)"), self.vial_mg,
                    ]),
                    toga.Box(style=Pack(direction=COLUMN, flex=1), children=[
                        toga.Label("BAC water (mL)"), self.water_ml,
                    ]),
                ]),
                toga.Label("Dose", style=SECTION_LABEL),
                toga.Box(style=Pack(direction=ROW, gap=10), children=[
                    toga.Box(style=Pack(direction=COLUMN, flex=1), children=[
                        toga.Label("Target dose"), self.dose,
                    ]),
                    toga.Box(style=Pack(direction=COLUMN, flex=1), children=[
                        toga.Label("Unit"), self.unit,
                    ]),
                ]),
                self.equiv_label,
                toga.Label("Syringe", style=SECTION_LABEL),
                self.syringe_size,
                self.error_label,
                self.card,
                toga.Button("Split vial (what-if)", on_press=self._open_vial_split, style=Pack(margin=(8, 12))),
                toga.Button("Save as protocol", on_press=self._save_as_protocol, style=Pack(margin=(0, 12, 8, 12))),
            ],
        )
        self._loading = False
        self._recalculate()
        return box

    def _on_change(self, widget):
        self._recalculate()

    def _on_preset(self, widget):
        """Prefill the inputs from a catalog peptide; 'Custom' leaves them alone."""
        if self._loading:
            return
        p = self._presets.get(self.preset.value)
        if p is None:
            self._freq = ""
            self._recalculate()
            return
        self._loading = True
        try:
            if p.get("vial_mg"):
                self.vial_mg.value = p["vial_mg"]
            if p.get("water_ml"):
                self.water_ml.value = p["water_ml"]
            # dose and unit go together: a bare number in the wrong unit is worse than none
            if p.get("dose") and p.get("unit") in UNITS:
                self.dose.value = p["dose"]
                self.unit.value = p["unit"]
        finally:
            self._loading = False
        self._freq = p.get("freq") or ""
        self._recalculate()

    def _clear_card(self):
        self.headline.text = ""
        self.draw_status.text = ""
        self.subline.text = ""
        self.duration_label.text = ""
        self.gauge.update(0.0)
        self.card.style.visibility = "hidden"

    def _recalculate(self):
        if self._loading:
            return
        vial_mg, water_ml, dose, unit = (
            num(self.vial_mg.value), num(self.water_ml.value),
            num(self.dose.value), self.unit.value,
        )
        capacity = SYRINGES.get(self.syringe_size.value, 100.0)
        self.gauge.set_capacity(capacity)
        self._saved = {
            "vial_mg": self.vial_mg.value, "water_ml": self.water_ml.value,
            "dose": self.dose.value, "unit": unit, "syringe": self.syringe_size.value,
            "preset": self.preset.value,
        }

        # Equivalent dose in the other unit, shown whenever a dose is entered.
        if dose > 0 and unit in UNITS:
            other = "mg" if unit == "mcg" else "mcg"
            self.equiv_label.text = f"{_fmt(dose)} {unit} = {_fmt(calc.convert_dose(dose, unit, other))} {other}"
        else:
            self.equiv_label.text = ""

        blank = next((msg for msg, v in (
            ("Enter the vial size (mg).", vial_mg),
            ("Enter the BAC water volume (mL).", water_ml),
            ("Enter the target dose.", dose),
        ) if v <= 0), None)
        problem = blank or calc.validate_reconstitution_inputs(vial_mg, water_ml, dose, unit)
        if problem:
            self.error_label.text = problem
            self._clear_card()
            return
        self.error_label.text = ""
        self.card.style.visibility = "visible"

        conc = calc.concentration_mg_ml(vial_mg, water_ml)
        dose_mg = calc.dose_to_mg(dose, unit)
        draw_ml = calc.draw_volume_ml(dose_mg, conc)
        units = calc.syringe_units(draw_ml)
        doses = calc.doses_per_vial(vial_mg, dose_mg)
        draw_label, draw_status_msg = calc.syringe_draw_status(units, capacity)
        if units > capacity and units <= 100.0 and capacity < 100.0:
            draw_status_msg += " - try a larger syringe"

        self.headline.text = draw_label
        self.gauge.update(units)
        self.draw_status.text = draw_status_msg
        self.subline.text = (
            f"Concentration {conc:.2f} mg/mL   ·   Draw {draw_ml:.3f} mL   ·   {doses:.1f} doses/vial"
        )
        weekly = calc.parse_weekly_frequency(self._freq)
        if weekly:
            self.duration_label.text = (
                f"Vial lasts {calc.format_vial_duration(doses, weekly, self._freq)} at {self._freq}"
            )
        else:
            self.duration_label.text = ""

    def _save_as_protocol(self, widget):
        from ..dialogs.profile_picker import start_protocol_form
        preset = self.preset.value
        prefill = {
            "vial_mg": num(self.vial_mg.value), "water_ml": num(self.water_ml.value),
            "target_dose": num(self.dose.value), "dose_unit": self.unit.value,
        }
        if preset in self._presets:
            prefill["peptide_name"] = preset
            prefill["frequency"] = self._presets[preset].get("frequency") or ""
        start_protocol_form(self.nav, prefill)

    def _open_vial_split(self, widget):
        from ..dialogs.vial_split import VialSplitScreen
        vial_mg, water_ml = num(self.vial_mg.value), num(self.water_ml.value)
        dose = num(self.dose.value)
        dose_mg = calc.dose_to_mg(dose, self.unit.value) if dose > 0 else None
        capacity = SYRINGES.get(self.syringe_size.value, 100.0)
        self.nav.push(lambda nav: VialSplitScreen(
            nav, vial_mg=vial_mg, water_ml=water_ml, dose_mg=dose_mg, syringe_capacity=capacity,
        ))
