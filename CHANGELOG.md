# Changelog

## Unreleased

Bug fixes
- Dosing math, database, and PubMed (NCBI) handling fixes.
- Protocol creation fixes.
- Scrolling fixes on long screens.
- "Log dose now" and the log-dose form use the current titration phase's dose instead of always the target dose.
- The vial-split screen now takes the calculator's syringe size into account (warns when a dose overflows it).

Features
- Dose log editing.
- Calculator presets.
- Literature tracker improvements.
- Profile management.
- Android: the system Back gesture/button now steps back through screens (Android 13+; best-effort).
- Android: exports open the share sheet, so the file can be saved to Drive, emailed, etc.
- Phone-shaped default window size on desktop.

Packaging and CI
- New "Build check" workflow: every PR runs `briefcase create` + `build` for Linux, Windows, macOS, and Android.
- Tests now run on Ubuntu, Windows, and macOS.
- Android: explicit INTERNET permission and the Material theme/dependency Toga 0.5 expects.
- README documents supported platforms (iOS is intentionally unsupported), install steps, and CI.

## 0.1.0

Initial prototype: Calculator, Patients (protocol list/detail, dose logging,
titration schedule generator), Reference (peptide list/detail, PubMed
literature tracking), and profile/export screens, ported from
[peptide-dosage-tui](https://github.com/alinuxfan/peptide-dosage-tui) to
Toga for cross-platform (Linux/Windows/macOS/Android) distribution.
