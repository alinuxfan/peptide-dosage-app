"""More tab — profile management + exports. Doesn't need a thumb-reachable
bottom-nav slot, so it absorbs the TUI's less-frequent actions."""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import db
from ..nav import Screen
from ..dialogs.add_profile import AddProfileScreen


class MoreScreen(Screen):
    def build(self) -> toga.Box:
        self.profile_select = toga.Selection()
        self.status = toga.Label("")
        return toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Label("Profiles & Exports"),
                self.profile_select,
                toga.Button("Add profile", on_press=self._add_profile),
                toga.Button("Export reference sheet (.txt)", on_press=self._export_reference),
                toga.Button("Export dose log (.csv)", on_press=self._export_dose_log),
                self.status,
            ],
        )

    def on_shown(self):
        profiles = db.get_profiles()
        self._profiles_by_name = {p["name"]: p["id"] for p in profiles}
        current = self.profile_select.value
        self.profile_select.items = [p["name"] for p in profiles]
        if profiles:
            self.profile_select.value = current if current in self._profiles_by_name else profiles[0]["name"]

    def _add_profile(self, widget):
        self.nav.push(lambda nav: AddProfileScreen(nav, on_added=self.on_shown))

    def _selected_profile_id(self):
        name = self.profile_select.value
        return self._profiles_by_name.get(name) if name else None

    async def _export_reference(self, widget):
        await self._export(db.export_person_reference_sheet)

    async def _export_dose_log(self, widget):
        await self._export(db.export_dose_log_csv)

    async def _export(self, export_fn):
        profile_id = self._selected_profile_id()
        if profile_id is None:
            self.status.text = "Add a profile first."
            return
        dest_dir = await self.nav.window.select_folder_dialog("Choose export folder")
        if dest_dir is None:
            return
        filename = export_fn(profile_id, dest_dir=str(dest_dir))
        self.status.text = f"Saved {filename}" if filename else "Export failed."
