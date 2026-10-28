import os

os.environ.setdefault("TOGA_BACKEND", "toga_dummy")

import pytest

toga = pytest.importorskip("toga")

from peptide_dosage.nav import NavigationController, Screen, TabBar  # noqa: E402


class _Blank(Screen):
    def build(self):
        return toga.Box()


def test_pop_returns_false_at_root_and_reports_changes():
    nav = NavigationController(_Blank)
    changes = []
    nav.on_stack_change = lambda: changes.append(nav.can_pop)

    assert nav.can_pop is False
    assert nav.pop() is False
    nav.push(_Blank)
    nav.push(_Blank)
    assert nav.pop() is True
    assert nav.pop() is True
    assert nav.pop() is False
    assert changes == [True, True, True, False]


def test_tab_bar_exposes_active_controller_and_switch_callback():
    a, b = NavigationController(_Blank), NavigationController(_Blank)
    bar = TabBar(toga.Box(), {"A": a, "B": b})
    switched = []
    bar.on_switch = lambda: switched.append(bar.active_controller)

    bar.switch_to("A")
    bar.switch_to("B")
    assert switched == [a, b]
