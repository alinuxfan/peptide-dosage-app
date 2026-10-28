"""Hand-rolled bottom-tab-bar + push/pop navigation stack.

Toga has no built-in mobile navigation widget (OptionContainer renders as
desktop-style top tabs). This swaps the visible content of a single root
box between a bottom tab bar and a per-tab stack of screens, each screen
a plain toga.Box built by a factory function.

Scrolling: every screen is wrapped in a vertical-only toga.ScrollContainer
so long lists/forms stay reachable on phone-sized displays; the TabBar lives
outside the scroller so it stays pinned to the bottom. Layout notes for
screen authors: inside a scroller the height is unbounded, so a ``flex=1``
child can only grow to fill the *viewport* (Toga hands the content at least
the viewport size, and more when its natural height is larger). Flex children
without a natural height (e.g. a MultilineTextInput) therefore give no
guarantee of a useful height on short screens -- give those an explicit
``height`` in their Pack style if they need to stay usable.

View caching: the built (scroller, box) of each screen on the stack is kept
for as long as the screen is on the stack. Popping back to a screen re-shows
the same widgets (typed inputs survive; scroll position survives unless the
screen itself clears and refills its widgets) and then calls
``on_shown`` so it can refresh any data that changed meanwhile. Screens must
therefore do their data refreshing in ``on_shown``, not only in ``build``.

Android hardware Back: Toga 0.5 (toga-android) exposes no back-press hook
(no ``on_back``/``onBackPressed`` on App or Window). ``on_stack_change`` /
``TabBar.on_switch`` tell the app when the active stack's depth may have
changed so it can register a platform back-callback (see android_support.py).
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
        self._views = {}  # screen -> ScrollContainer, for screens on the stack
        self.on_stack_change = None  # optional callback, after every push/pop
        self.content = toga.Box(style=Pack(direction=COLUMN, flex=1))
        self._render()

    def push(self, screen_factory):
        screen = screen_factory(self)
        self._stack.append(screen)
        try:
            self._render()
        except Exception:
            # build() failed: keep the stack consistent with what is visible.
            if screen in self._stack:
                self._stack.remove(screen)
            self._views.pop(screen, None)
            raise
        self._stack_changed()

    def pop(self):
        """Go back one screen. Returns False (doing nothing) at the root."""
        if len(self._stack) <= 1:
            return False
        self._views.pop(self._stack.pop(), None)
        self._render()
        self.notify_shown()
        self._stack_changed()
        return True

    @property
    def can_pop(self) -> bool:
        return len(self._stack) > 1

    def _stack_changed(self):
        if self.on_stack_change:
            self.on_stack_change()

    def notify_shown(self):
        """Tell the visible screen it (re)appeared; called after rendering."""
        self._stack[-1].on_shown()

    def _view_for(self, screen) -> toga.ScrollContainer:
        view = self._views.get(screen)
        if view is None:
            view = toga.ScrollContainer(content=screen.build(), horizontal=False, style=Pack(flex=1))
            self._views[screen] = view
        return view

    def _render(self):
        screen = self._stack[-1]
        view = self._view_for(screen)
        if self._stack[-1] is not screen:
            # build() popped its own screen (e.g. its record no longer
            # exists); the previous screen has already been rendered.
            self._views.pop(screen, None)
            return
        self.content.clear()
        self.content.add(view)


class TabBar:
    """Bottom row of buttons, one per destination; swaps root.content."""

    def __init__(self, root_content: toga.Box, destinations: dict):
        # destinations: {label: NavigationController}
        self.root_content = root_content
        self.destinations = destinations
        self.on_switch = None  # optional callback, after the active tab changes
        self.buttons = {
            label: toga.Button(label, on_press=self._make_switch(label), style=INACTIVE_STYLE.copy())
            for label in destinations
        }
        self.bar = toga.Box(style=Pack(direction=ROW, background_color=BAR_BG), children=list(self.buttons.values()))
        self._active = None

    @property
    def active_controller(self):
        return self.destinations.get(self._active)

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
        self.destinations[label].notify_shown()
        if self.on_switch:
            self.on_switch()
