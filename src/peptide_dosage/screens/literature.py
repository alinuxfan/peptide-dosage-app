"""Literature — the saved-article library (the TUI's Literature Tracker tab).

LiteratureScreen lists tracked PubMed articles with an optional peptide
filter and a "Track by PMID" input. Tapping an article pushes ArticleScreen
with the full record (authors, abstract, link, editable notes) and a delete
action.
"""

import re
import webbrowser

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from .. import db, ncbi
from ..nav import Screen
from .peptide_detail import HEADING_STYLE

ALL_PEPTIDES = "All peptides"


def _year(pub_date) -> str:
    match = re.search(r"\d{4}", pub_date or "")
    return match.group(0) if match else ""


def article_summary(article: dict) -> str:
    parts = [article.get("journal") or "", _year(article.get("pub_date")), article.get("peptide_name") or ""]
    return " · ".join(p for p in parts if p)


class LiteratureScreen(Screen):
    def __init__(self, nav):
        super().__init__(nav)
        self._updating = False
        self._filter = ALL_PEPTIDES  # survives nav pop(), which rebuilds the widgets

    def build(self) -> toga.Box:
        self.status = toga.Label("")
        self.pmid_input = toga.TextInput(placeholder="PubMed ID (e.g. 40756949)", style=Pack(flex=1))
        self.track_button = toga.Button("Track", on_press=self._track_pmid)
        self.filter_select = toga.Selection(items=[ALL_PEPTIDES], on_change=self._on_filter)
        self.list_box = toga.Box(style=Pack(direction=COLUMN))
        self.clear_button = toga.Button("Clear all", on_press=self._clear_all)
        self._refresh()
        return toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Button("< Back", on_press=lambda w: self.nav.pop()),
                toga.Label("Tracked articles", style=Pack(font_size=16, font_weight="bold", margin=(0, 0, 8, 0))),
                toga.Box(style=Pack(direction=ROW), children=[self.pmid_input, self.track_button]),
                self.status,
                self.filter_select,
                toga.ScrollContainer(content=self.list_box, horizontal=False, style=Pack(flex=1)),
                self.clear_button,
            ],
        )

    def on_shown(self):
        self._refresh()

    def _on_filter(self, widget):
        if not self._updating:
            self._filter = self.filter_select.value or ALL_PEPTIDES
            self._refresh()

    def _refresh(self):
        if self.status.text.startswith("Couldn't load"):
            self.status.text = ""
        try:
            articles = db.get_tracked_literature()
        except Exception as e:
            articles = []
            self.status.text = f"Couldn't load articles: {e}"

        names = sorted({a["peptide_name"] for a in articles if a.get("peptide_name")})
        current = self._filter
        self._updating = True
        try:
            self.filter_select.items = [ALL_PEPTIDES] + names
            self.filter_select.value = current if current in names else ALL_PEPTIDES
        finally:
            self._updating = False
        selected = self._filter = self.filter_select.value or ALL_PEPTIDES
        shown = [a for a in articles if selected in (None, ALL_PEPTIDES) or a.get("peptide_name") == selected]

        self.list_box.clear()
        if not shown:
            self.list_box.add(toga.Label("No tracked articles yet" if not articles else "No articles for this peptide"))
        for article in shown:
            self.list_box.add(toga.Box(style=Pack(direction=COLUMN, margin=(0, 0, 8, 0)), children=[
                toga.Button(article.get("title") or f"PMID {article['pmid']}",
                            on_press=self._make_open(article["pmid"]), style=Pack(flex=1)),
                toga.Label(article_summary(article)),
            ]))
        self.clear_button.enabled = bool(articles)

    def _make_open(self, pmid):
        def handler(widget):
            self.nav.push(lambda nav: ArticleScreen(nav, pmid))
        return handler

    async def _track_pmid(self, widget):
        try:
            pmid = ncbi.validate_pmid(self.pmid_input.value or "")
        except ValueError as e:
            self.status.text = str(e)
            return
        widget.enabled = False
        self.status.text = f"Fetching PMID {pmid}..."
        try:
            try:
                article = await ncbi.fetch_pubmed_article(pmid)
            except Exception as e:  # network, parse, anything: never leave "Fetching..." stuck
                self.status.text = f"Failed: {e}"
                return
            try:
                prior = db.get_tracked_article_by_pmid(pmid)  # keep any notes the user wrote
                db.save_tracked_article(
                    pmid=article["pmid"], title=article["title"], authors=article["authors"],
                    abstract=article["abstract"], journal=article["journal"],
                    pub_date=article["pub_date"], url=article["url"],
                    notes=(prior or {}).get("notes") or "",
                )
            except Exception as e:
                self.status.text = f"Couldn't save PMID {pmid}: {e}"
                return
            self.pmid_input.value = ""
            self.status.text = f"Tracked PMID {pmid}."
            self._refresh()
        finally:
            widget.enabled = True

    async def _clear_all(self, widget):
        if await self.nav.window.confirm_dialog(
            "Clear all", "Remove all tracked articles? This can't be undone."
        ):
            try:
                db.clear_tracked_literature()
            except Exception as e:
                self.status.text = f"Couldn't clear articles: {e}"
                return
            self.status.text = "Cleared all tracked articles."
            self._refresh()


class ArticleScreen(Screen):
    def __init__(self, nav, pmid):
        super().__init__(nav)
        self.pmid = pmid
        self.article = None

    def build(self) -> toga.Box:
        self.status = toga.Label("")
        back = toga.Button("< Back", on_press=lambda w: self.nav.pop())
        try:
            self.article = db.get_tracked_article_by_pmid(self.pmid)
        except Exception:
            self.article = None
        if self.article is None:
            return toga.Box(style=Pack(direction=COLUMN, margin=12), children=[
                back, toga.Label("This article is no longer tracked."),
            ])

        a = self.article
        authors = ", ".join(a.get("authors") or []) or "Unknown"
        url = a.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{a['pmid']}/"
        self.url = url
        self.notes_input = toga.MultilineTextInput(value=a.get("notes") or "", placeholder="Your notes",
                                                   style=Pack(height=100))
        children = [
            back,
            toga.Label(a.get("title") or f"PMID {a['pmid']}", style=Pack(font_size=15, font_weight="bold")),
            toga.Label(f"PMID {a['pmid']}"),
            toga.Label("Authors", style=HEADING_STYLE), toga.Label(authors),
            toga.Label("Journal", style=HEADING_STYLE), toga.Label(a.get("journal") or "Unknown"),
            toga.Label("Published", style=HEADING_STYLE), toga.Label(a.get("pub_date") or "Unknown"),
        ]
        if a.get("peptide_name"):
            children += [toga.Label("Peptide", style=HEADING_STYLE), toga.Label(a["peptide_name"])]
        children += [
            toga.Label("Abstract", style=HEADING_STYLE),
            toga.MultilineTextInput(value=a.get("abstract") or "No abstract available.", readonly=True,
                                    style=Pack(height=220)),
            toga.Label("Link", style=HEADING_STYLE), toga.Label(url),
            toga.Button("Open in browser", on_press=self._open_url),
            toga.Label("Notes", style=HEADING_STYLE), self.notes_input,
            toga.Button("Save notes", on_press=self._save_notes),
            self.status,
            toga.Button("Delete article", on_press=self._delete),
        ]
        return toga.Box(style=Pack(direction=COLUMN, margin=12), children=[
            toga.ScrollContainer(
                content=toga.Box(style=Pack(direction=COLUMN), children=children),
                horizontal=False, style=Pack(flex=1),
            ),
        ])

    def _open_url(self, widget):
        try:
            opened = webbrowser.open(self.url)
        except Exception:
            opened = False
        self.status.text = f"Opened {self.url}" if opened else f"Couldn't open a browser. Link: {self.url}"

    def _save_notes(self, widget):
        a = self.article
        try:
            saved = db.save_tracked_article(
                pmid=a["pmid"], title=a["title"], authors=a.get("authors") or [],
                abstract=a.get("abstract") or "", journal=a.get("journal") or "",
                pub_date=a.get("pub_date") or "", url=a.get("url") or "",
                notes=self.notes_input.value or "", peptide_name=a.get("peptide_name") or "",
            )
        except Exception as e:
            self.status.text = f"Couldn't save notes: {e}"
            return
        if saved:
            self.article = saved
        self.status.text = "Notes saved."

    async def _delete(self, widget):
        if await self.nav.window.confirm_dialog("Delete article", "Remove this article from your tracked list?"):
            try:
                db.delete_tracked_article(self.article["id"])
            except Exception as e:
                self.status.text = f"Couldn't delete: {e}"
                return
            self.nav.pop()
