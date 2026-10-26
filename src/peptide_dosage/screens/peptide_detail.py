"""Peptide detail — dosing info/notes/schedule/sources for one master
peptide, plus a "Track" action per cited PMID feeding the same
tracked_literature store the TUI's Literature Tracker tab uses. Fetches run
as async handlers (Toga schedules `async def` handlers as tasks natively),
replacing the TUI's self.run_worker pattern."""

import webbrowser

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import db, ncbi
from ..nav import Screen

HEADING_STYLE = Pack(font_weight="bold", margin=(10, 0, 4, 0))


def _fmt(value) -> str:
    """Render a number without a trailing .0 (250.0 -> '250')."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def format_schedule_row(row) -> str:
    """Schedule rows are stored as [label, dose, unit] (JSON from a tuple)."""
    try:
        label, dose, unit = row
        return f"{label}: {_fmt(dose)} {unit}"
    except (TypeError, ValueError):
        return str(row)


def dosing_lines(peptide: dict) -> list[str]:
    """Human-readable summary of the catalog row's dosing defaults."""
    lines = []
    if peptide.get("dose") is not None:
        dose = f"{_fmt(peptide['dose'])} {peptide.get('unit') or ''}".strip()
        freq = f" ({peptide['freq']})" if peptide.get("freq") else ""
        lines.append(f"Typical dose: {dose}{freq}")
    elif peptide.get("freq"):
        lines.append(f"Frequency: {peptide['freq']}")
    if peptide.get("vial_mg") is not None:
        lines.append(f"Default vial: {_fmt(peptide['vial_mg'])} mg")
    if peptide.get("water_ml") is not None:
        lines.append(f"Default water: {_fmt(peptide['water_ml'])} mL")
    return lines


class PeptideDetailScreen(Screen):
    def __init__(self, nav, peptide_name, on_add_to_profile=None):
        super().__init__(nav)
        self.peptide_name = peptide_name
        # Optional hook (peptide_name) -> None; the app wires this to the
        # protocol form. When absent the "Add to profile" button is hidden.
        self.on_add_to_profile = on_add_to_profile

    def build(self) -> toga.Box:
        self.status = toga.Label("")
        back = toga.Button("< Back", on_press=lambda w: self.nav.pop())
        try:
            peptide = db.get_peptide_by_name(self.peptide_name)
        except Exception:
            peptide = None
        if peptide is None:
            return toga.Box(style=Pack(direction=COLUMN, margin=12), children=[
                back,
                toga.Label(f"Couldn't find \"{self.peptide_name}\" in the reference catalog."),
            ])

        children = [back, toga.Label(peptide["name"], style=Pack(font_size=16, font_weight="bold"))]

        if self.on_add_to_profile is not None:
            children.append(toga.Button("Add to profile", on_press=self._add_to_profile))

        info = dosing_lines(peptide)
        if info:
            children.append(toga.Label("Dosing", style=HEADING_STYLE))
            children.extend(toga.Label(line) for line in info)
        if peptide.get("notes"):
            children.append(toga.Label("Notes", style=HEADING_STYLE))
            children.append(toga.Label(peptide["notes"]))
        if peptide.get("schedule"):
            children.append(toga.Label("Titration schedule", style=HEADING_STYLE))
            children.extend(toga.Label(format_schedule_row(r)) for r in peptide["schedule"])

        children.append(toga.Label("Cited sources", style=HEADING_STYLE))
        children.append(self.status)
        sources = peptide.get("sources") or []
        if not sources:
            children.append(toga.Label("No cited sources."))
        for source in sources:
            children.append(self._build_source(source, peptide["name"]))

        return toga.Box(style=Pack(direction=COLUMN, margin=12), children=[
            toga.ScrollContainer(
                content=toga.Box(style=Pack(direction=COLUMN), children=children),
                horizontal=False, style=Pack(flex=1),
            ),
        ])

    def _build_source(self, source, peptide_name) -> toga.Box:
        pmid = str(source.get("pmid", "")).strip()
        url = source.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
        try:
            existing = db.get_tracked_article_by_pmid(pmid) if pmid else None
        except Exception:
            existing = None
        # Tracked earlier without a peptide link (e.g. via Track by PMID) still
        # offers "Track" so it can be linked to this peptide.
        already = bool(existing and existing.get("peptide_name"))
        track = toga.Button(
            "Tracked" if already else "Track",
            enabled=bool(pmid) and not already,
            on_press=self._make_track(pmid, peptide_name),
        )
        title = source.get("title") or "Untitled"
        children = [toga.Label(f"{title} (PMID {pmid})" if pmid else title)]
        if url:
            children.append(toga.Label(url))  # visible fallback where no browser can be opened
        children.append(track)
        if url:
            children.append(toga.Button("Open in browser", on_press=self._make_open_url(url)))
        return toga.Box(style=Pack(direction=COLUMN, margin=(0, 0, 8, 0)), children=children)

    def _add_to_profile(self, widget):
        try:
            self.on_add_to_profile(self.peptide_name)
        except Exception as e:
            self.status.text = f"Couldn't open the profile form: {e}"

    def _make_open_url(self, url):
        def handler(widget):
            try:
                opened = webbrowser.open(url)
            except Exception:
                opened = False
            self.status.text = f"Opened {url}" if opened else f"Couldn't open a browser. Link: {url}"
        return handler

    def _make_track(self, pmid, peptide_name):
        async def handler(widget):
            widget.enabled = False
            self.status.text = f"Fetching PMID {pmid}..."
            try:
                article = await ncbi.fetch_pubmed_article(pmid)
            except Exception as e:  # network, parse, bad PMID, anything: never leave "Fetching..." stuck
                self.status.text = f"Failed: {e}"
                widget.enabled = True
                return
            try:
                prior = db.get_tracked_article_by_pmid(pmid)  # keep any notes the user wrote
                db.save_tracked_article(
                    pmid=article["pmid"], title=article["title"], authors=article["authors"],
                    abstract=article["abstract"], journal=article["journal"],
                    pub_date=article["pub_date"], url=article["url"], peptide_name=peptide_name,
                    notes=(prior or {}).get("notes") or "",
                )
            except Exception as e:
                self.status.text = f"Couldn't save PMID {pmid}: {e}"
                widget.enabled = True
                return
            self.status.text = f"Tracked PMID {pmid}."
            widget.text = "Tracked"
        return handler
