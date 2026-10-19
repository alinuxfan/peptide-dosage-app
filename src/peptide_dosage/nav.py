"""Hand-rolled bottom-tab-bar + push/pop navigation stack.

Toga has no built-in mobile navigation widget (OptionContainer renders as
desktop-style top tabs). This swaps the visible content of a single root
box between a bottom tab bar and a per-tab stack of screens, each screen
a plain toga.Box built by a factory function.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

BAR_BG = "#17212b"
INACTIVE_STYLE = Pack(flex=1, background_color=BAR_BG, color="#8fa3b3", margin=8)
ACTIVE_STYLE = Pack(flex=1, background_color=BAR_BG, color="#4fc3f7", font_weight="bold", margin=8)


class Screen:
    """One pushable unit of UI. Subclass and override build()/on_shown()."""

    def __init__(self, nav):
        self.nav = nav

    def build(self) -> toga.Box:
        raise NotImplementedError

    def on_shown(self):
        """Called every time this screen becomes visible again (e.g. after
        a child screen is popped) — use it to refresh data, mirroring the
        TUI's explicit recalculate()/update_*_table() calls."""


class NavigationController:
    """One push/pop stack, scoped to a single bottom-tab destination."""

    def __init__(self, root_factory, window=None):
        self.window = window  # set by the App, so screens can show dialogs
        self._stack = [root_factory(self)]
        self.content = toga.Box(style=Pack(direction=COLUMN, flex=1))
        self._render()

    def push(self, screen_factory):
        self._stack.append(screen_factory(self))
        self._render()

    def pop(self):
        if len(self._stack) > 1:
            self._stack.pop()
            self._render()
            self._stack[-1].on_shown()

    def _render(self):
        self.content.clear()
        self.content.add(self._stack[-1].build())


class TabBar:
    """Bottom row of buttons, one per destination; swaps root.content."""

    def __init__(self, root_content: toga.Box, destinations: dict):
        # destinations: {label: NavigationController}
        self.root_content = root_content
        self.destinations = destinations
        self.buttons = {
            label: toga.Button(label, on_press=self._make_switch(label), style=INACTIVE_STYLE.copy())
            for label in destinations
        }
        self.bar = toga.Box(style=Pack(direction=ROW, background_color=BAR_BG), children=list(self.buttons.values()))
        self._active = None

    def _make_switch(self, label):
        def handler(widget):
            self.switch_to(label)
        return handler

    def switch_to(self, label):
        if self._active is not None:
            self.buttons[self._active].style.update(**INACTIVE_STYLE.copy())
        self.buttons[label].style.update(**ACTIVE_STYLE.copy())
        self._active = label

        self.root_content.clear()
        self.root_content.add(self.destinations[label].content)
        self.root_content.add(self.bar)
        self.destinations[label]._stack[-1].on_shown()
