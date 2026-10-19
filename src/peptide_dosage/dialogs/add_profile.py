"""Add-profile sheet. Toga has no built-in text-input dialog (only
confirm/info/error/file/folder pickers), so this is a pushed screen rather
than a native prompt — consistent with the full-screen-sheet pattern used
for every other form in this app."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import db
from ..nav import Screen


class AddProfileScreen(Screen):
    def __init__(self, nav, on_added=None):
        super().__init__(nav)
        self.on_added = on_added

    def build(self) -> toga.Box:
        self.name = toga.TextInput()
        self.notes = toga.TextInput()
        self.error = toga.Label("")
        return toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Button("< Cancel", on_press=lambda w: self.nav.pop()),
                toga.Label("Name"), self.name,
                toga.Label("Notes"), self.notes,
                self.error,
                toga.Button("Add profile", on_press=self._save),
            ],
        )

    def _save(self, widget):
        name = (self.name.value or "").strip()
        if not name:
            self.error.text = "Name can't be blank."
            return
        db.add_profile(name, self.notes.value or "")
        if self.on_added:
            self.on_added()
        self.nav.pop()
