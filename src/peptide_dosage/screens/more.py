"""More tab — profile management, exports and an About section. Doesn't need
a thumb-reachable bottom-nav slot, so it absorbs the TUI's less-frequent
actions."""

import os
import sys
from importlib import metadata
from pathlib import Path

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from .. import db
from ..nav import Screen
from ..dialogs.add_profile import AddProfileScreen

REPO_URL = "https://github.com/alinuxfan/peptide-dosage-app"

SECTION_LABEL = Pack(font_weight="bold", font_size=13, margin=(16, 0, 4, 0))
BODY_STYLE = Pack(font_size=12, margin=(2, 0))
BUTTON_STYLE = Pack(margin=(4, 0))
STATUS_STYLE = Pack(font_size=12, margin=(4, 0))


def _is_android() -> bool:
    """True when running on the Android backend. Imports nothing
    platform-specific, so it is safe on every desktop backend."""
    try:
        if toga.platform.current_platform == "android":
            return True
    except Exception:
        pass
    return hasattr(sys, "getandroidapilevel") or sys.platform == "android"


def _app_version() -> str:
    try:
        return metadata.version("peptide-dosage")
    except Exception:
        pass
    try:
        return toga.App.app.version or "unknown"
    except Exception:
        return "unknown"


def _text(value):
    """Selection values may be plain strings or Item-like objects."""
    return getattr(value, "name", value) if value is not None else None


class MoreScreen(Screen):
    def build(self) -> toga.Box:
        self._profiles_by_name = {}
        # NavigationController re-runs build() whenever a child screen pops, so
        # remember the user's choice across rebuilds in an attribute that
        # survives (the Selection widget itself is recreated).
        self._wanted_profile = getattr(self, "_wanted_profile", None)
        self.profile_select = toga.Selection(on_change=self._remember_profile)
        self.profile_status = toga.Label("", style=STATUS_STYLE)
        self.export_status = toga.Label("", style=STATUS_STYLE)
        self.data_label = toga.Label("", style=BODY_STYLE)
        content = toga.Box(
            style=Pack(direction=COLUMN, margin=12),
            children=[
                toga.Label("Profiles", style=SECTION_LABEL),
                self.profile_select,
                toga.Button("Add profile", on_press=self._add_profile, style=BUTTON_STYLE),
                toga.Button("Delete selected profile", on_press=self._delete_profile, style=BUTTON_STYLE),
                self.profile_status,
                toga.Label("Export", style=SECTION_LABEL),
                toga.Label("Exports use the profile selected above.", style=BODY_STYLE),
                toga.Button("Export reference sheet (.txt)", on_press=self._export_reference, style=BUTTON_STYLE),
                toga.Button("Export dose log (.csv)", on_press=self._export_dose_log, style=BUTTON_STYLE),
                self.export_status,
                toga.Label("About", style=SECTION_LABEL),
                toga.Label(f"Peptide Dosage {_app_version()}", style=Pack(font_weight="bold", margin=(2, 0))),
                toga.Label("Research/educational tool - not medical advice.", style=BODY_STYLE),
                toga.Label("Data is stored locally on this device.", style=BODY_STYLE),
                self.data_label,
                toga.Label(f"Privacy: see PRIVACY.md at {REPO_URL}", style=BODY_STYLE),
            ],
        )
        # Tall content: scroll so nothing is clipped on small phone screens.
        return toga.Box(
            style=Pack(direction=COLUMN, flex=1),
            children=[toga.ScrollContainer(content=content, horizontal=False, style=Pack(flex=1))],
        )

    def on_shown(self):
        profiles = db.get_profiles()
        self._profiles_by_name = {p["name"]: p["id"] for p in profiles}
        wanted = self._wanted_profile or self._selected_profile_name()
        self.profile_select.items = [p["name"] for p in profiles]
        if profiles:
            self.profile_select.value = wanted if wanted in self._profiles_by_name else profiles[0]["name"]
            self._wanted_profile = self._selected_profile_name()
        data_dir = self._data_dir()
        self.data_label.text = f"Data location: {data_dir}" if data_dir else ""

    # --- profiles -----------------------------------------------------

    def _add_profile(self, widget):
        self.nav.push(lambda nav: AddProfileScreen(nav, on_added=self.on_shown))

    def _remember_profile(self, widget):
        name = _text(widget.value)
        if name in self._profiles_by_name:
            self._wanted_profile = name

    def _selected_profile_name(self):
        return _text(self.profile_select.value)

    def _selected_profile_id(self):
        name = self._selected_profile_name()
        return self._profiles_by_name.get(name) if name else None

    async def _delete_profile(self, widget):
        profile_id = self._selected_profile_id()
        name = self._selected_profile_name()
        if profile_id is None:
            self.profile_status.text = "Select a profile first."
            return
        if len(self._profiles_by_name) <= 1:
            self.profile_status.text = "Can't delete the last profile."
            return
        confirmed = await self.nav.window.confirm_dialog(
            "Delete profile",
            f"Delete '{name}'? Its protocols and dose history will also be "
            "permanently deleted. This can't be undone.",
        )
        if not confirmed:
            return
        try:
            deleted = db.delete_profile(profile_id)
        except Exception as e:
            self.profile_status.text = f"Couldn't delete profile: {e}"
            return
        self.profile_status.text = (
            f"Deleted profile '{name}'." if deleted else "Can't delete the last profile."
        )
        self.on_shown()

    # --- exports ------------------------------------------------------

    def _data_dir(self):
        try:
            return Path(self.nav.window.app.paths.data)
        except Exception:
            return None

    def _fallback_export_dir(self) -> Path:
        """App-private exports folder (always writable, incl. Android)."""
        data_dir = self._data_dir()
        if data_dir is None:
            raise OSError("Could not determine the app data folder.")
        dest = data_dir / "exports"
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    async def _export_reference(self, widget):
        await self._export(db.export_person_reference_sheet)

    async def _export_dose_log(self, widget):
        await self._export(db.export_dose_log_csv)

    async def _choose_dest_dir(self):
        """Returns (dest_dir, cancelled). On Android, or whenever the native
        folder picker is unavailable, falls back to the app's exports folder
        (Android's picker returns content URIs we can't write to directly)."""
        self._used_fallback = False
        if not _is_android():
            try:
                chosen = await self.nav.window.select_folder_dialog("Choose export folder")
            except Exception:  # NotImplementedError or backend-specific failures
                self._used_fallback = True
                return self._fallback_export_dir(), False
            if isinstance(chosen, (list, tuple)):
                chosen = chosen[0] if chosen else None
            if chosen is None:
                return None, True
            return Path(chosen), False
        self._used_fallback = True
        return self._fallback_export_dir(), False

    async def _export(self, export_fn):
        profile_id = self._selected_profile_id()
        if profile_id is None:
            self.export_status.text = "Add a profile first."
            return
        try:
            dest_dir, cancelled = await self._choose_dest_dir()
            if cancelled:
                return
            filename = export_fn(profile_id, dest_dir=str(dest_dir))
        except Exception as e:  # OSError (disk/permissions) and anything unexpected
            self.export_status.text = f"Export failed: {e}"
            return
        if not filename:
            self.export_status.text = "Export failed: profile not found."
            return
        saved = os.path.join(str(dest_dir), str(filename))
        if self._used_fallback:
            self.export_status.text = f"Saved to the app's exports folder: {saved}"
        else:
            self.export_status.text = f"Saved to {saved}"
