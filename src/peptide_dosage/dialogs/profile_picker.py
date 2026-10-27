"""Entry point for "Save as protocol" / "Add to profile" actions that start a
new protocol from somewhere other than the Patients tab. With a single profile
it opens the protocol form directly; with several it first asks which profile
the protocol belongs to."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import db
from ..nav import Screen
from .protocol_form import ProtocolFormScreen


class ProfilePickerScreen(Screen):
    def __init__(self, nav, prefill):
        super().__init__(nav)
        self.prefill = prefill

    def build(self) -> toga.Box:
        children = [
            toga.Button("< Cancel", on_press=lambda w: self.nav.pop()),
            toga.Label("Add to which profile?", style=Pack(font_weight="bold", margin=(8, 0))),
        ]
        for profile in db.get_profiles():
            children.append(toga.Button(profile["name"], on_press=self._make_choose(profile["id"])))
        return toga.Box(style=Pack(direction=COLUMN, margin=12, gap=6), children=children)

    def _make_choose(self, profile_id):
        def handler(widget):
            # Replace the picker with the form so Cancel/Save return to the origin screen.
            self.nav.pop()
            self.nav.push(lambda nav: ProtocolFormScreen(nav, profile_id, prefill=self.prefill))
        return handler


def start_protocol_form(nav, prefill):
    profiles = db.get_profiles()
    if len(profiles) == 1:
        nav.push(lambda n: ProtocolFormScreen(n, profiles[0]["id"], prefill=prefill))
    elif profiles:
        nav.push(lambda n: ProfilePickerScreen(n, prefill))
