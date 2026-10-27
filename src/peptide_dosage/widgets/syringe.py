"""U-100 syringe gauge — the one part of this app that benefits from being
a real drawing instead of a terminal-art string (replaces the TUI's ASCII
make_syringe_display). Ticks mark 0/25/50/75/100% of the syringe's
capacity (30/50/100 U for the 0.3/0.5/1.0 mL U-100 syringes); the barrel
fills to the current draw and turns red past capacity, mirroring
calc.syringe_draw_status's overflow warning."""

import math

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

OK_COLOR = "#2e7d32"
OVER_COLOR = "#c62828"
BARREL_COLOR = "#9e9e9e"
TICK_COLOR = "#616161"


class SyringeGauge(toga.Box):
    def __init__(self, max_capacity: float = 100.0, style=None):
        super().__init__(style=style or Pack(direction=COLUMN))
        self.max_capacity = max_capacity
        self._units = 0.0
        self._size = (0, 0)
        self.canvas = toga.Canvas(style=Pack(flex=1, height=64), on_resize=self._on_resize)
        self.add(self.canvas)

    def _on_resize(self, widget, width, height, **kwargs):
        self._size = (width, height)
        self._draw()

    def update(self, units: float):
        self._units = units if units is not None and math.isfinite(units) and units > 0 else 0.0
        self._draw()

    def set_capacity(self, capacity: float):
        """Change the syringe size (in units) at runtime and redraw."""
        if capacity is not None and math.isfinite(capacity) and capacity > 0:
            if float(capacity) == self.max_capacity:
                return
            self.max_capacity = float(capacity)
        self._draw()

    @property
    def over_capacity(self) -> bool:
        return self.max_capacity > 0 and self._units > self.max_capacity

    @property
    def fraction(self) -> float:
        """Filled share of the barrel, always within 0.0..1.0."""
        if not self.max_capacity or self.max_capacity <= 0 or self._units <= 0:
            return 0.0
        return min(self._units / self.max_capacity, 1.0)

    def tick_marks(self) -> list[float]:
        """Graduation values: 0/25/50/75/100% of capacity."""
        return [self.max_capacity * step / 4.0 for step in range(5)]

    def _draw(self):
        c = self.canvas
        c.root_state.drawing_actions.clear()
        width, height = self._size
        if width <= 1 or height <= 1:
            c.redraw()
            return

        margin_x, tip_w = 12, 10
        barrel_left, barrel_right = margin_x + tip_w, width - margin_x
        barrel_top, barrel_bottom = height * 0.3, height * 0.7
        barrel_w, barrel_h = barrel_right - barrel_left, barrel_bottom - barrel_top

        over = self.over_capacity
        fraction = self.fraction
        fill_color = OVER_COLOR if over else OK_COLOR

        # needle tip, barrel outline
        with c.fill(color=BARREL_COLOR):
            c.move_to(margin_x, height / 2)
            c.line_to(barrel_left, barrel_top)
            c.line_to(barrel_left, barrel_bottom)
            c.close_path()
        with c.stroke(color=BARREL_COLOR, line_width=2):
            c.rect(barrel_left, barrel_top, barrel_w, barrel_h)

        # fill level (capped visually at capacity even when the real draw overflows)
        if fraction > 0:
            with c.fill(color=fill_color):
                c.rect(barrel_left, barrel_top, barrel_w * fraction, barrel_h)

        # graduation ticks at each quarter of capacity
        tick_font = toga.Font(family="sans-serif", size=9)
        for i, mark in enumerate(self.tick_marks()):
            x = barrel_left + barrel_w * (i / 4.0)
            label = f"{mark:g}"
            with c.stroke(color=TICK_COLOR, line_width=1):
                c.move_to(x, barrel_top)
                c.line_to(x, barrel_top - 6)
            with c.fill(color=TICK_COLOR):
                c.fill_text(label, x - 3 * len(label), barrel_bottom + 14, font=tick_font)

        c.redraw()
