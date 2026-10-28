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
from ..util import num

MAX_SPLITS = 50


class VialSplitScreen(Screen):
    def __init__(
        self, nav, vial_mg: float, water_ml: float, dose_mg: float | None = None,
        syringe_capacity: float = 100.0,
    ):
        super().__init__(nav)
        self.syringe_capacity = syringe_capacity  # units; 30/50/100 U-100 syringes
        self.vial_mg = vial_mg
        self.water_ml = water_ml
        self.dose_mg = dose_mg  # optional: enables per-aliquot draw/dose lines

    def build(self) -> toga.Box:
        self.splits = toga.NumberInput(value=2, min=1, step=1, on_change=self._recalculate)
        self.result = toga.MultilineTextInput(readonly=True, style=Pack(flex=1, height=160))

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
        raw = num(self.splits.value, default=0.0)
        note = ""
        if raw != raw or raw < 1:  # blank, zero, negative or NaN
            splits, note = 1, "Enter at least 1 aliquot (showing 1).\n\n"
        elif raw > MAX_SPLITS:
            splits, note = MAX_SPLITS, f"Maximum is {MAX_SPLITS} aliquots (showing {MAX_SPLITS}).\n\n"
        else:
            splits = int(raw)
            if splits != raw:
                note = f"Whole aliquots only (showing {splits}).\n\n"

        try:
            r = calc.split_vial_aliquots(self.vial_mg, self.water_ml, splits)
        except ValueError as e:
            self.result.value = str(e)
            return

        lines = [
            f"Per aliquot: {r['aliquot_mg']:.2f} mg in {r['aliquot_ml']:.2f} mL",
            f"Concentration (unchanged): {r['concentration_mg_ml']:.2f} mg/mL",
        ]
        if self.dose_mg and self.dose_mg > 0:
            draw_ml = calc.draw_volume_ml(self.dose_mg, r["concentration_mg_ml"])
            units = calc.syringe_units(draw_ml)
            doses = calc.doses_per_vial(r["aliquot_mg"], self.dose_mg)
            lines.append("")
            dose_mcg = calc.convert_dose(self.dose_mg, "mg", "mcg")
            dose_txt = f"{dose_mcg / 1000:.4g} mg" if dose_mcg >= 1000 else f"{dose_mcg:.4g} mcg"
            lines.append(f"For a {dose_txt} dose:")
            lines.append(f"  Draw {units:.1f} units ({draw_ml:.3f} mL) per dose")
            _, status = calc.syringe_draw_status(units, self.syringe_capacity)
            lines.append(f"  {status}")
            lines.append(f"  {doses:.1f} doses per aliquot ({doses * splits:.1f} total)")
        self.result.value = note + "\n".join(lines)
