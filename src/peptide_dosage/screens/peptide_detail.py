"""Peptide detail — notes/schedule/sources for one master peptide, plus a
"Track" action per cited PMID feeding the same tracked_literature store the
TUI's Literature Tracker tab uses. Fetches run as async handlers (Toga
schedules `async def` handlers as tasks natively), replacing the TUI's
self.run_worker pattern."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import db, ncbi
from ..nav import Screen


class PeptideDetailScreen(Screen):
    def __init__(self, nav, peptide_name):
        super().__init__(nav)
        self.peptide_name = peptide_name

    def build(self) -> toga.Box:
        peptide = db.get_peptide_by_name(self.peptide_name)
        self.status = toga.Label("")
        children = [
            toga.Button("< Back", on_press=lambda w: self.nav.pop()),
            toga.Label(peptide["name"]),
            toga.Label(peptide.get("notes") or ""),
            self.status,
            toga.Label("Cited sources"),
        ]
        for source in peptide["sources"]:
            already = db.get_tracked_article_by_pmid(source["pmid"]) is not None
            children.append(toga.Box(style=Pack(direction=COLUMN, margin=(0, 0, 6, 0)), children=[
                toga.Label(f"{source['title']} (PMID {source['pmid']})"),
                toga.Button(
                    "Tracked" if already else "Track",
                    enabled=not already,
                    on_press=self._make_track(source["pmid"], peptide["name"]),
                ),
            ]))
        return toga.Box(style=Pack(direction=COLUMN, margin=12), children=children)

    def _make_track(self, pmid, peptide_name):
        async def handler(widget):
            widget.enabled = False
            self.status.text = f"Fetching PMID {pmid}..."
            try:
                article = await ncbi.fetch_pubmed_article(pmid)
            except (ValueError, RuntimeError) as e:
                self.status.text = f"Failed: {e}"
                widget.enabled = True
                return
            db.save_tracked_article(
                pmid=article["pmid"], title=article["title"], authors=article["authors"],
                abstract=article["abstract"], journal=article["journal"],
                pub_date=article["pub_date"], url=article["url"], peptide_name=peptide_name,
            )
            self.status.text = f"Tracked PMID {pmid}."
            widget.text = "Tracked"
        return handler
