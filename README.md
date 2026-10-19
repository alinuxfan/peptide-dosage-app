# Peptide Dosage (Toga port)

A cross-platform GUI port of [peptide-dosage-tui](https://github.com/alinuxfan/peptide-dosage-tui), built with **Python** and **[Toga](https://toga.readthedocs.io/)** (BeeWare) so the same reconstitution-dosing, patient-protocol, and literature-tracking tool runs on Android, iPhone, macOS, Windows, and Linux instead of just the terminal.

Research/educational tool — not medical advice.

## Status

Early prototype. The Calculator, Patients (protocol list + detail, dose logging, titration schedule generator), Reference (peptide list + detail + PubMed literature tracking), and profile/export screens all work end-to-end. Not yet packaged or released for any platform.

## Architecture

`calc.py`, `db.py`, and `ncbi.py` are carried over from the TUI unchanged (pure logic, no UI dependency) — see that repo for the data model and formulas. Everything under `src/peptide_dosage/screens/`, `dialogs/`, `nav.py`, and `widgets/` is new: a hand-rolled bottom-tab-bar + push/pop navigation stack (Toga has no built-in mobile nav widget), since a phone-sized screen needed a different information architecture than the TUI's six tabs.

## Development

```bash
pip install briefcase
briefcase dev        # install deps + run
pytest tests/        # logic tests ported from the TUI
```

## License

MIT — see [LICENSE](LICENSE).
