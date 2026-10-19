"""Patients tab — merges the TUI's patient-tab + schedule-tab + dose-log-tab.

Root screen: card list of protocols for the active profile, each showing
BUD/doses-left at a glance (same data calc.format_bud_label /
calc.format_doses_remaining produce for the TUI's table columns), with a
status pill colored by urgency. Tapping a card pushes ProtocolDetailScreen
(schedule + dose log + BUD status + actions for that one protocol).
"""

from datetime import datetime, timedelta, timezone

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from .. import calc, db
from ..nav import Screen
from .protocol_detail import ProtocolDetailScreen

CARD_STYLE = Pack(direction=COLUMN, background_color="#1f2d3a", margin=(0, 12, 10, 12), gap=4)
TITLE_STYLE = Pack(font_size=15, font_weight="bold", color="#e8eef3")
PILL_OK = Pack(background_color="#2e7d32", color="#e8f5e9", font_size=11, margin=(2, 0))
PILL_WARN = Pack(background_color="#f9a825", color="#2a2100", font_size=11, margin=(2, 0))
PILL_OVERDUE = Pack(background_color="#c62828", color="#ffebee", font_size=11, margin=(2, 0))


def _pill_style(bud_expiry_at, now):
    if bud_expiry_at is None:
        return PILL_WARN
    if bud_expiry_at <= now:
        return PILL_OVERDUE
    if bud_expiry_at <= now + timedelta(days=5):
        return PILL_WARN
    return PILL_OK


class PatientsScreen(Screen):
    def build(self) -> toga.Box:
        self.profile_select = toga.Selection(on_change=self._on_profile_change)
        self.card_list = toga.Box(style=Pack(direction=COLUMN, flex=1))
        return toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[self.profile_select, self.card_list],
        )

    def on_shown(self):
        profiles = db.get_profiles()
        self._profiles_by_name = {p["name"]: p["id"] for p in profiles}
        current = self.profile_select.value
        self.profile_select.items = [p["name"] for p in profiles]
        if profiles:
            self.profile_select.value = current if current in self._profiles_by_name else profiles[0]["name"]
        self._refresh_cards()

    def _on_profile_change(self, widget):
        self._refresh_cards()

    def _refresh_cards(self):
        self.card_list.clear()
        name = self.profile_select.value
        if name is None:
            return
        profile_id = self._profiles_by_name[name]
        protocols = db.get_user_protocols(profile_id)
        adherence_by_id = {a["protocol_id"]: a for a in db.get_protocol_adherence(profile_id)}
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for protocol in protocols:
            self.card_list.add(self._make_card(protocol, adherence_by_id.get(protocol["id"]), now))

    def _make_card(self, protocol, adherence, now) -> toga.Box:
        title = toga.Label(
            f"{protocol['peptide_name']} — {protocol['target_dose']}{protocol['dose_unit']}",
            style=TITLE_STYLE,
        )
        badges = toga.Box(style=Pack(direction=ROW, gap=8))
        if adherence:
            badges.add(toga.Label(
                calc.format_bud_label(adherence["bud_expiry_at"], now),
                style=_pill_style(adherence["bud_expiry_at"], now),
            ))
            badges.add(toga.Label(
                calc.format_doses_remaining(adherence["doses_remaining"], adherence["doses_total"]),
                style=Pack(font_size=11, color="#b8c4ce"),
            ))
        return toga.Box(
            style=CARD_STYLE,
            children=[
                title, badges,
                toga.Button("Details", on_press=self._make_open_detail(protocol["id"]), style=Pack(margin_top=6)),
            ],
        )

    def _make_open_detail(self, protocol_id):
        def handler(widget):
            self.nav.push(lambda nav: ProtocolDetailScreen(nav, protocol_id, on_deleted=self._refresh_cards))
        return handler
