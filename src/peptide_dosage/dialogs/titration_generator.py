"""Titration schedule generator — ports TUI's TitrationGeneratorScreen
(ModalScreen[list | None]). Builds a linear ramp via calc.generate_titration_schedule
and saves it onto the protocol via db.update_protocol_schedule, which also
syncs target_dose/dose_unit to the new maintenance level."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import calc, db
from ..nav import Screen
from ..util import num


class TitrationGeneratorScreen(Screen):
    def __init__(self, nav, protocol):
        super().__init__(nav)
        self.protocol = protocol

    def build(self) -> toga.Box:
        p = self.protocol
        self.start_dose = toga.NumberInput(value=p["target_dose"], step=1)
        self.target_dose = toga.NumberInput(value=p["target_dose"], step=1)
        self.step_increment = toga.NumberInput(value=1, min=0, step=0.5)
        self.weeks_per_step = toga.NumberInput(value=2, min=0.5, step=0.5)
        self.preview = toga.MultilineTextInput(readonly=True, style=Pack(flex=1, height=160))
        self.error = toga.Label("")

        for widget in (self.start_dose, self.target_dose, self.step_increment, self.weeks_per_step):
            widget.on_change = self._preview

        box = toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Button("< Cancel", on_press=lambda w: self.nav.pop()),
                toga.Label("Start dose"), self.start_dose,
                toga.Label("Target (maintenance) dose"), self.target_dose,
                toga.Label("Step increment"), self.step_increment,
                toga.Label("Weeks per step"), self.weeks_per_step,
                self.error,
                self.preview,
                toga.Button("Save to protocol", on_press=self._save),
            ],
        )
        self._preview(None)
        return box

    def _build_schedule(self):
        return calc.generate_titration_schedule(
            num(self.start_dose.value), num(self.target_dose.value),
            num(self.step_increment.value), num(self.weeks_per_step.value),
            self.protocol["dose_unit"],
        )

    def _preview(self, widget):
        try:
            schedule = self._build_schedule()
        except ValueError as e:
            self.error.text = str(e)
            self.preview.value = ""
            return
        self.error.text = ""
        self.preview.value = "\n".join(f"{label}: {dose} {unit}" for label, dose, unit in schedule)

    def _save(self, widget):
        try:
            schedule = self._build_schedule()
        except ValueError as e:
            self.error.text = str(e)
            return
        db.update_protocol_schedule(self.protocol["id"], schedule, num(self.target_dose.value), self.protocol["dose_unit"])
        self.nav.pop()
