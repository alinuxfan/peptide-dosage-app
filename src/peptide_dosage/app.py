import os

import toga
from toga.style import Pack
from toga.style.pack import COLUMN

from . import db
from .nav import NavigationController, TabBar
from .screens.calculator import CalculatorScreen
from .screens.patients import PatientsScreen
from .screens.reference import ReferenceScreen
from .screens.more import MoreScreen


class PeptideDosageApp(toga.App):
    def startup(self):
        db.set_db_path(self.paths.data / "peptides.db")
        os.makedirs(self.paths.data, exist_ok=True)
        db.init_db()

        self.main_window = toga.MainWindow(title=self.formal_name)

        root = toga.Box(style=Pack(direction=COLUMN, flex=1))
        destinations = {
            "Calculator": NavigationController(CalculatorScreen, window=self.main_window),
            "Patients": NavigationController(PatientsScreen, window=self.main_window),
            "Reference": NavigationController(ReferenceScreen, window=self.main_window),
            "More": NavigationController(MoreScreen, window=self.main_window),
        }
        self.destinations = destinations
        self.tab_bar = TabBar(root, destinations)
        self.tab_bar.switch_to("Calculator")

        self.main_window.content = root
        self.main_window.show()


def main():
    return PeptideDosageApp("Peptide Dosage", "org.example.peptidedosage")


if __name__ == "__main__":
    main().main_loop()
