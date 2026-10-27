"""Add-profile sheet. Toga has no built-in text-input dialog (only
confirm/info/error/file/folder pickers), so this is a pushed screen rather
than a native prompt — consistent with the full-screen-sheet pattern used
for every other form in this app."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import db
from ..nav import Screen


MAX_NAME_LENGTH = 60
MAX_NOTES_LENGTH = 500
ERROR_STYLE = Pack(color="#ff8a80", font_weight="bold")


class AddProfileScreen(Screen):
    def __init__(self, nav, on_added=None):
        super().__init__(nav)
        self.on_added = on_added

    def build(self) -> toga.Box:
        self.name = toga.TextInput()
        self.notes = toga.TextInput()
        self.error = toga.Label("", style=ERROR_STYLE)
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
        name = " ".join((self.name.value or "").split())
        if not name:
            self.error.text = "Name can't be blank."
            return
        if len(name) > MAX_NAME_LENGTH:
            self.error.text = f"Name must be {MAX_NAME_LENGTH} characters or fewer."
            return
        notes = (self.notes.value or "").strip()
        if len(notes) > MAX_NOTES_LENGTH:
            self.error.text = f"Notes must be {MAX_NOTES_LENGTH} characters or fewer."
            return
        # Names are unique case-sensitively in the DB, but exports are named
        # from a lowercased form, so "Bob" and "bob" would overwrite each other.
        if any(p["name"].casefold() == name.casefold() for p in db.get_profiles()):
            self.error.text = "A profile with that name already exists."
            return
        if db.add_profile(name, notes) is None:
            self.error.text = "A profile with that name already exists."
            return
        if self.on_added:
            self.on_added()
        self.nav.pop()
