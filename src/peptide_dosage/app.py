import os

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from . import db
from .android_support import BackHandler
from .nav import NavigationController, TabBar
from .screens.calculator import CalculatorScreen
from .screens.patients import PatientsScreen
from .screens.reference import ReferenceScreen
from .screens.more import MoreScreen


class PeptideDosageApp(toga.App):
    def startup(self):
        # The data folder must exist before the database is created in it.
        os.makedirs(self.paths.data, exist_ok=True)
        db.set_db_path(self.paths.data / "peptides.db")
        db.init_db()

        # Phone-shaped default size for desktop windows (width, height); the
        # layout is built for narrow screens. Android/iOS ignore this and
        # always fill the screen.
        self.main_window = toga.MainWindow(title=self.formal_name, size=(420, 680))

        root = toga.Box(style=Pack(direction=COLUMN, flex=1))
        destinations = {
            "Calculator": NavigationController(CalculatorScreen, window=self.main_window),
            "Patients": NavigationController(PatientsScreen, window=self.main_window),
            "Reference": NavigationController(ReferenceScreen, window=self.main_window),
            "More": NavigationController(MoreScreen, window=self.main_window),
        }
        self.destinations = destinations
        self.tab_bar = TabBar(root, destinations)

        # Android's system Back pops the active tab's stack (a no-op elsewhere).
        self.back_handler = BackHandler(
            self, can_go_back=self._can_go_back, go_back=self._go_back
        )
        for controller in destinations.values():
            controller.on_stack_change = self.back_handler.sync
        self.tab_bar.on_switch = self.back_handler.sync

        self.tab_bar.switch_to("Calculator")

        self.main_window.content = root
        self.main_window.show()

    def _can_go_back(self) -> bool:
        controller = self.tab_bar.active_controller
        return controller is not None and controller.can_pop

    def _go_back(self):
        controller = self.tab_bar.active_controller
        if controller is not None:
            controller.pop()


def main():
    # WARNING: do not change this app_id (nor the bundle, formal_name, or
    # author in pyproject.toml). Depending on the platform, Toga derives the
    # per-user data folder from some of these, and that folder holds the
    # SQLite database with every user's protocols and dose logs; changing
    # them could silently orphan existing data.
    return PeptideDosageApp("Peptide Dosage", "org.example.peptidedosage")


if __name__ == "__main__":
    main().main_loop()
