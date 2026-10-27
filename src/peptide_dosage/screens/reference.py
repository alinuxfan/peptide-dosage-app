"""Reference tab — merges the TUI's reference-tab + literature-tab.

Root: searchable peptide list. Tapping one pushes PeptideDetailScreen with its
dosing info and PubMed sources inline and a "Track" action. A "Tracked
articles" button leads to LiteratureScreen, the saved-article library.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import db
from ..nav import Screen
from .literature import LiteratureScreen
from .peptide_detail import PeptideDetailScreen

ROW_STYLE = Pack(margin=(0, 0, 4, 0))


class ReferenceScreen(Screen):
    def __init__(self, nav, on_add_to_profile=None):
        super().__init__(nav)
        # Optional hook (peptide_name) -> None, forwarded to the detail screen
        # so the app can offer "Add to profile" from the reference.
        self.on_add_to_profile = on_add_to_profile
        self._peptides = []
        self._query = ""  # survives nav pop(), which rebuilds the widgets
        self._load_error = ""

    def build(self) -> toga.Box:
        self.list_box = toga.Box(style=Pack(direction=COLUMN))
        self.empty_label = toga.Label("")
        self.search = toga.TextInput(
            value=self._query,
            placeholder="Search peptides",
            on_change=self._on_search,
            style=Pack(margin=(0, 0, 8, 0)),
        )
        self._load_peptides()
        self._render_list()
        return toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Label("Peptide Reference", style=Pack(font_size=16, font_weight="bold", margin=(0, 0, 8, 0))),
                toga.Button("Tracked articles", on_press=self._open_literature, style=Pack(margin=(0, 0, 8, 0))),
                self.search,
                self.empty_label,
                toga.ScrollContainer(content=self.list_box, horizontal=False, style=Pack(flex=1)),
            ],
        )

    def on_shown(self):
        self._load_peptides()
        self._render_list()

    def _load_peptides(self):
        try:
            self._peptides = db.get_peptides()
            self._load_error = ""
        except Exception as e:  # keep whatever list we already had
            self._load_error = f"Couldn't load peptides: {e}"

    def _on_search(self, widget):
        self._render_list()

    def _render_list(self):
        self._query = self.search.value or ""
        query = self._query.strip().lower()
        matches = [p for p in self._peptides if query in p["name"].lower()]
        self.list_box.clear()
        for peptide in matches:
            self.list_box.add(toga.Button(
                peptide["name"], on_press=self._make_open(peptide["name"]), style=ROW_STYLE,
            ))
        if self._load_error:
            self.empty_label.text = self._load_error
        elif not self._peptides:
            self.empty_label.text = "No peptides in the catalog."
        elif not matches:
            self.empty_label.text = "No matches"
        else:
            self.empty_label.text = ""

    def _make_open(self, name):
        def handler(widget):
            self.nav.push(lambda nav: PeptideDetailScreen(nav, name, on_add_to_profile=self.on_add_to_profile))
        return handler

    def _open_literature(self, widget):
        self.nav.push(lambda nav: LiteratureScreen(nav))
