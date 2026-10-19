"""Vial-split what-if — a pushed full-screen sheet, not a floating modal.

Ports TUI's VialSplitScreen(ModalScreen[None]): read-only, no save action.
Mobile modals are full-screen with a back button rather than a small
floating window, so this is just another Screen on the nav stack.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import calc
from ..nav import Screen


class VialSplitScreen(Screen):
    def __init__(self, nav, vial_mg: float, water_ml: float):
        super().__init__(nav)
        self.vial_mg = vial_mg
        self.water_ml = water_ml

    def build(self) -> toga.Box:
        self.splits = toga.NumberInput(value=2, min=1, step=1, on_change=self._recalculate)
        self.result = toga.MultilineTextInput(readonly=True, style=Pack(flex=1))

        box = toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Button("< Back", on_press=lambda w: self.nav.pop()),
                toga.Label("Split into how many aliquots?"),
                self.splits,
                self.result,
            ],
        )
        self._recalculate(None)
        return box

    def _recalculate(self, widget):
        try:
            r = calc.split_vial_aliquots(self.vial_mg, self.water_ml, int(self.splits.value or 1))
        except ValueError as e:
            self.result.value = str(e)
            return
        self.result.value = (
            f"Per aliquot: {r['aliquot_mg']:.2f} mg in {r['aliquot_ml']:.2f} mL\n"
            f"Concentration (unchanged): {r['concentration_mg_ml']:.2f} mg/mL"
        )
