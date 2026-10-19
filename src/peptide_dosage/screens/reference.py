"""Reference tab — merges the TUI's reference-tab + literature-tab.

Root: peptide list. Tapping one pushes PeptideDetailScreen with its
PubMed sources inline and a "Track" action — no separate literature-tracker
destination needed, since tracking is now reachable from the peptide that
prompted it.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import db
from ..nav import Screen
from .peptide_detail import PeptideDetailScreen


class ReferenceScreen(Screen):
    def build(self) -> toga.Box:
        self.list_box = toga.Box(style=Pack(direction=COLUMN, flex=1))
        return toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[toga.Label("Peptide Reference"), self.list_box],
        )

    def on_shown(self):
        self.list_box.clear()
        for peptide in db.get_peptides():
            self.list_box.add(toga.Box(style=Pack(direction=COLUMN, margin=(0, 0, 4, 0)), children=[
                toga.Label(peptide["name"]),
                toga.Button("View", on_press=self._make_open(peptide["name"])),
            ]))

    def _make_open(self, name):
        def handler(widget):
            self.nav.push(lambda nav: PeptideDetailScreen(nav, name))
        return handler
