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

from .. import calc
from ..nav import Screen
from ..util import num
from ..widgets.syringe import SyringeGauge

UNITS = ["mg", "mcg"]

SECTION_LABEL = Pack(font_weight="bold", font_size=13, margin=(12, 0, 4, 0))
CARD_STYLE = Pack(direction=COLUMN, background_color="#1f2d3a", margin=12, gap=6)
CARD_HEADLINE = Pack(font_size=20, font_weight="bold", color="#e8eef3")
CARD_SUBLINE = Pack(font_size=12, color="#b8c4ce")
ERROR_STYLE = Pack(color="#ff8a80", font_weight="bold")


class CalculatorScreen(Screen):
    def build(self) -> toga.Box:
        self.vial_mg = toga.NumberInput(value=5, min=0, step=0.1, on_change=self._on_change, style=Pack(flex=1))
        self.water_ml = toga.NumberInput(value=2, min=0, step=0.1, on_change=self._on_change, style=Pack(flex=1))
        self.dose = toga.NumberInput(value=250, min=0, step=1, on_change=self._on_change, style=Pack(flex=1))
        self.unit = toga.Selection(items=UNITS, value="mcg", on_change=self._on_change, style=Pack(flex=1))

        self.error_label = toga.Label("", style=ERROR_STYLE)
        self.headline = toga.Label("", style=CARD_HEADLINE)
        self.gauge = SyringeGauge(max_capacity=100.0)
        self.draw_status = toga.Label("", style=CARD_SUBLINE)
        self.subline = toga.Label("", style=CARD_SUBLINE)

        self.card = toga.Box(style=CARD_STYLE, children=[
            self.headline, self.gauge, self.draw_status, self.subline,
        ])

        box = toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
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
                self.error_label,
                self.card,
                toga.Button("Split vial (what-if)", on_press=self._open_vial_split, style=Pack(margin=(8, 12))),
            ],
        )
        self._recalculate()
        return box

    def _on_change(self, widget):
        self._recalculate()

    def _recalculate(self):
        vial_mg, water_ml, dose, unit = (
            num(self.vial_mg.value), num(self.water_ml.value),
            num(self.dose.value), self.unit.value,
        )
        problem = calc.validate_reconstitution_inputs(vial_mg, water_ml, dose, unit)
        if problem:
            self.error_label.text = problem
            self.card.style.visibility = "hidden"
            return
        self.error_label.text = ""
        self.card.style.visibility = "visible"

        conc = calc.concentration_mg_ml(vial_mg, water_ml)
        dose_mg = calc.dose_to_mg(dose, unit)
        draw_ml = calc.draw_volume_ml(dose_mg, conc)
        units = calc.syringe_units(draw_ml)
        doses = calc.doses_per_vial(vial_mg, dose_mg)
        draw_label, draw_status_msg = calc.syringe_draw_status(units)

        self.headline.text = draw_label
        self.gauge.update(units)
        self.draw_status.text = draw_status_msg
        self.subline.text = (
            f"Concentration {conc:.2f} mg/mL   ·   Draw {draw_ml:.3f} mL   ·   {doses:.1f} doses/vial"
        )

    def _open_vial_split(self, widget):
        from ..dialogs.vial_split import VialSplitScreen
        self.nav.push(lambda nav: VialSplitScreen(
            nav, vial_mg=num(self.vial_mg.value), water_ml=num(self.water_ml.value),
        ))
