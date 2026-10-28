import csv
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from peptide_dosage import db


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_peptides.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()
    return db


def test_init_db_seeds_default_profiles(fresh_db):
    profiles = fresh_db.get_profiles()
    names = {p["name"] for p in profiles}
    assert {"Default User"} <= names


def test_init_db_seeds_peptides_and_fixes_tesamorelin(fresh_db):
    names = {p["name"] for p in fresh_db.get_peptides()}
    assert "Tesamorelin" in names
    assert "Tesemorelin" not in names


def test_tesemorelin_migration_updates_existing_user_protocol(fresh_db):
    profiles = fresh_db.get_profiles()
    pid = profiles[0]["id"]

    conn = fresh_db.get_connection()
    conn.execute(
        "INSERT INTO user_protocols (profile_id, peptide_name, vial_mg, water_ml, target_dose, dose_unit) "
        "VALUES (?, 'Tesemorelin', 2.0, 2.0, 2.0, 'mg')",
        (pid,),
    )
    conn.commit()
    conn.close()

    fresh_db.init_db()  # re-run migration

    protocols = fresh_db.get_user_protocols(pid)
    assert protocols[0]["peptide_name"] == "Tesamorelin"


def test_selank_semax_migration_updates_existing_user_protocol(fresh_db):
    profiles = fresh_db.get_profiles()
    pid = profiles[0]["id"]

    conn = fresh_db.get_connection()
    conn.execute(
        "INSERT INTO user_protocols (profile_id, peptide_name, vial_mg, water_ml, target_dose, dose_unit, frequency, notes) "
        "VALUES (?, 'Selank', 11.0, 5.0, 250.0, 'mcg', 'daily (intranasal, split AM/PM)', 'intranasal spray notes')",
        (pid,),
    )
    conn.execute(
        "INSERT INTO user_protocols (profile_id, peptide_name, vial_mg, water_ml, target_dose, dose_unit, frequency, notes) "
        "VALUES (?, 'Semax', 11.0, 5.0, 300.0, 'mcg', 'daily (intranasal, 1-3x/day)', 'intranasal spray notes')",
        (pid,),
    )
    conn.execute("PRAGMA user_version = 0")  # simulate a DB from before the migration
    conn.commit()
    conn.close()

    fresh_db.init_db()  # re-run migration

    protocols = {p["peptide_name"]: p for p in fresh_db.get_user_protocols(pid)}
    assert "SubQ" in protocols["Selank"]["frequency"]
    assert "subcutaneous" in protocols["Selank"]["notes"].lower()
    assert "SubQ" in protocols["Semax"]["frequency"]
    assert "subcutaneous" in protocols["Semax"]["notes"].lower()


def test_add_profile_and_duplicate_rejected(fresh_db):
    new_id = fresh_db.add_profile("Charlie")
    assert new_id is not None
    assert fresh_db.add_profile("Charlie") is None


def test_delete_profile(fresh_db):
    new_id = fresh_db.add_profile("Charlie")
    assert fresh_db.delete_profile(new_id) is True
    names = {p["name"] for p in fresh_db.get_profiles()}
    assert "Charlie" not in names


def test_delete_profile_refuses_last_profile(fresh_db):
    profiles = fresh_db.get_profiles()
    for p in profiles[:-1]:
        assert fresh_db.delete_profile(p["id"]) is True

    last = fresh_db.get_profiles()
    assert len(last) == 1
    assert fresh_db.delete_profile(last[0]["id"]) is False
    assert len(fresh_db.get_profiles()) == 1


def test_delete_profile_cascades_protocols_and_dose_log(fresh_db):
    pid = fresh_db.add_profile("Charlie")
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "notes", [], []
    )
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]
    fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg")

    fresh_db.delete_profile(pid)

    conn = fresh_db.get_connection()
    remaining_protocols = conn.execute(
        "SELECT COUNT(*) as c FROM user_protocols WHERE profile_id = ?", (pid,)
    ).fetchone()["c"]
    remaining_logs = conn.execute(
        "SELECT COUNT(*) as c FROM dose_log WHERE profile_id = ?", (pid,)
    ).fetchone()["c"]
    conn.close()
    assert remaining_protocols == 0
    assert remaining_logs == 0


def test_add_update_get_by_id_delete_user_protocol(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "notes", [("Week 1", 250.0, "mcg")], []
    )
    protocol = fresh_db.get_user_protocols(pid)[0]
    fetched = fresh_db.get_user_protocol_by_id(protocol["id"])
    assert fetched["peptide_name"] == "BPC-157"
    assert fetched["schedule"] == [["Week 1", 250.0, "mcg"]]

    # Update by re-adding same peptide name -> upsert, not duplicate row
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 500.0, "mcg", "daily", "notes", [], []
    )
    protocols = fresh_db.get_user_protocols(pid)
    assert len(protocols) == 1
    assert protocols[0]["target_dose"] == 500.0

    fresh_db.delete_user_protocol(protocol["id"])
    assert fresh_db.get_user_protocols(pid) == []


def test_update_protocol_schedule_updates_schedule_and_target_dose(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "Selank", 11.0, 5.0, 250.0, "mcg", "daily", "notes", [("Week 1-2", 250.0, "mcg")], []
    )
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]

    new_schedule = [
        ("Week 1-2", 250.0, "mcg"),
        ("Week 3-4", 500.0, "mcg"),
        ("Week 5+ (Maintenance)", 750.0, "mcg"),
    ]
    fresh_db.update_protocol_schedule(protocol_id, new_schedule, 750.0, "mcg")

    fetched = fresh_db.get_user_protocol_by_id(protocol_id)
    assert fetched["schedule"] == [list(step) for step in new_schedule]
    assert fetched["target_dose"] == 750.0
    assert fetched["dose_unit"] == "mcg"


def test_dose_log_add_list_delete(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.log_dose(pid, None, "BPC-157", 250.0, "mcg", notes="left thigh")
    log = fresh_db.get_dose_log(pid)
    assert len(log) == 1
    assert log[0]["notes"] == "left thigh"

    fresh_db.delete_dose_log_entry(log[0]["id"])
    assert fresh_db.get_dose_log(pid) == []


def test_get_protocol_adherence_measurable(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "notes", [], []
    )
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]

    # Backdate created_at 7 days so adherence math has a window to measure against
    conn = fresh_db.get_connection()
    week_ago = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE user_protocols SET created_at = ? WHERE id = ?", (week_ago, protocol_id))
    conn.commit()
    conn.close()

    for _ in range(3):
        fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg")

    adherence = fresh_db.get_protocol_adherence(pid)
    entry = next(a for a in adherence if a["protocol_id"] == protocol_id)
    assert entry["logged_count"] == 3
    # daily -> 7 expected over 7 days, 3 logged -> ~42.9%
    assert round(entry["adherence_pct"], 1) == 42.9


def test_get_protocol_adherence_unmeasurable_for_unparseable_frequency(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "PT-141", 10.0, 2.0, 1.0, "mg", "as needed (PRN)", "notes", [], []
    )
    adherence = fresh_db.get_protocol_adherence(pid)
    entry = next(a for a in adherence if a["peptide_name"] == "PT-141")
    assert entry["adherence_pct"] is None
    assert entry["next_due_at"] is None


def test_get_protocol_adherence_next_due_anchors_on_last_dose(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "weekly", "notes", [], []
    )
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]

    conn = fresh_db.get_connection()
    two_days_ago = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg")
    conn.execute("UPDATE dose_log SET taken_at = ? WHERE protocol_id = ?", (two_days_ago, protocol_id))
    conn.commit()
    conn.close()

    adherence = fresh_db.get_protocol_adherence(pid)
    entry = next(a for a in adherence if a["protocol_id"] == protocol_id)
    # weekly -> 7 day interval, last dose was 2 days ago -> ~5 days until next due
    assert entry["next_due_at"] is not None
    days_until = (entry["next_due_at"] - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() / 86400.0
    assert 4.9 < days_until < 5.1


def test_get_protocol_adherence_next_due_falls_back_to_created_at_when_never_logged(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "notes", [], []
    )
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]

    adherence = fresh_db.get_protocol_adherence(pid)
    entry = next(a for a in adherence if a["protocol_id"] == protocol_id)
    assert entry["next_due_at"] is not None
    # never logged -> anchored on created_at (just now) + 1 day (daily)
    days_until = (entry["next_due_at"] - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() / 86400.0
    assert 0.9 < days_until < 1.1


def test_export_dose_log_csv(fresh_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.log_dose(pid, None, "BPC-157", 250.0, "mcg", notes="left thigh")
    fresh_db.log_dose(pid, None, "Ipamorelin / CJC-1295", 300.0, "mcg")

    filename = fresh_db.export_dose_log_csv(pid)
    assert filename is not None

    import csv
    with open(tmp_path / filename, newline="") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["ID", "Peptide", "Dose Amount", "Dose Unit", "Taken At", "Notes"]
    assert len(rows) == 3  # header + 2 entries
    peptides = {row[1] for row in rows[1:]}
    assert peptides == {"BPC-157", "Ipamorelin / CJC-1295"}
    notes_by_peptide = {row[1]: row[5] for row in rows[1:]}
    assert notes_by_peptide["BPC-157"] == "left thigh"
    assert notes_by_peptide["Ipamorelin / CJC-1295"] == ""


def test_export_dose_log_csv_unknown_profile(fresh_db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert fresh_db.export_dose_log_csv(99999) is None


def test_log_dose_backdating_and_editing(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "notes", [], []
    )
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]

    fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg", "backdated",
                      taken_at="2026-01-05 08:30:00")
    fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg", "now")

    log = fresh_db.get_dose_log(pid)
    assert "2026-01-05 08:30:00" in [entry["taken_at"] for entry in log]

    backdated = next(e for e in log if e["notes"] == "backdated")
    fresh_db.update_dose_log_entry(backdated["id"], 500.0, "mcg", "2026-02-02 09:00:00", "corrected")

    updated = fresh_db.get_dose_log_entry_by_id(backdated["id"])
    assert updated["dose_amount"] == 500.0
    assert updated["taken_at"] == "2026-02-02 09:00:00"
    assert updated["notes"] == "corrected"


def test_reconstitution_starts_bud_and_resets_vial_inventory(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    # 5mg vial at 250mcg per dose -> 20 doses per vial
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "notes", [], []
    )
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]

    before = fresh_db.get_protocol_adherence(pid)[0]
    assert before["reconstituted_at"] is None
    assert before["bud_expiry_at"] is None
    assert before["doses_total"] == 20.0
    assert before["doses_remaining"] == 20.0

    fresh_db.set_protocol_reconstituted(protocol_id, when="2026-01-01 08:00:00")
    fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg", taken_at="2026-01-01 09:00:00")
    fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg", taken_at="2026-01-02 09:00:00")

    after = fresh_db.get_protocol_adherence(pid)[0]
    assert after["reconstituted_at"] is not None
    assert after["bud_expiry_at"] is not None
    assert after["doses_used"] == 2
    assert after["doses_remaining"] == 18.0

    # Opening a new vial resets the inventory count; prior doses came from the old one
    fresh_db.set_protocol_reconstituted(protocol_id, when="2026-02-01 08:00:00")
    fresh_vial = fresh_db.get_protocol_adherence(pid)[0]
    assert fresh_vial["doses_used"] == 0
    assert fresh_vial["doses_remaining"] == 20.0
    assert fresh_vial["logged_count"] == 2  # dose history itself is untouched


def test_doses_before_reconstitution_dont_count_against_current_vial(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "notes", [], []
    )
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]

    fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg", taken_at="2020-01-01 10:00:00")
    fresh_db.set_protocol_reconstituted(protocol_id)
    fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg")

    entry = fresh_db.get_protocol_adherence(pid)[0]
    assert entry["logged_count"] == 2      # full history preserved
    assert entry["doses_used"] == 1        # but only one drawn from this vial


def test_adherence_label_reports_why_it_is_unmeasurable(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "n", [], []
    )
    fresh_db.add_or_update_user_protocol(
        pid, "PT-141", 10.0, 2.0, 1.0, "mg", "as needed (PRN)", "n", [], []
    )
    labels = {e["peptide_name"]: e["adherence_label"] for e in fresh_db.get_protocol_adherence(pid)}
    assert labels["BPC-157"] == "Too new"                  # brand-new protocol
    assert labels["PT-141"] == "Freq. not recognized"      # unparseable frequency


def test_tracked_literature_peptide_association_and_filter(fresh_db):
    fresh_db.save_tracked_article("111", "A", ["Author A"], "abs A", peptide_name="Semax")
    fresh_db.save_tracked_article("222", "B", ["Author B"], "abs B", peptide_name="Selank")
    fresh_db.save_tracked_article("333", "C", ["Author C"], "abs C")

    assert len(fresh_db.get_tracked_literature()) == 3
    semax = fresh_db.get_tracked_literature("Semax")
    assert [a["pmid"] for a in semax] == ["111"]

    # Re-saving without a peptide must not wipe an existing association
    fresh_db.save_tracked_article("111", "A v2", ["Author A"], "abs A2")
    assert fresh_db.get_tracked_article_by_pmid("111")["peptide_name"] == "Semax"


def test_deleting_protocol_nulls_dose_log_reference_but_keeps_history(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "n", [], []
    )
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]
    fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg", "kept")

    fresh_db.delete_user_protocol(protocol_id)

    log = fresh_db.get_dose_log(pid)
    assert len(log) == 1                      # history survives the protocol
    assert log[0]["peptide_name"] == "BPC-157"
    assert log[0]["notes"] == "kept"
    assert log[0]["protocol_id"] is None      # but no longer dangles


# ---------------------------------------------------------------------------
# Robustness fixes
# ---------------------------------------------------------------------------

def _utc_str(delta=timedelta(0)):
    return (datetime.now(timezone.utc).replace(tzinfo=None) + delta).strftime("%Y-%m-%d %H:%M:%S")


def _make_legacy_db(path):
    """Schema as shipped by the old TUI: no created_at / reconstituted_at /
    peptide_name columns, and no user_version."""
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE peptides (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, vial_mg REAL, water_ml REAL,
        dose REAL, unit TEXT, freq TEXT, notes TEXT, schedule_json TEXT, sources_json TEXT);
    CREATE TABLE user_protocols (
        id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, peptide_name TEXT NOT NULL,
        vial_mg REAL NOT NULL, water_ml REAL NOT NULL, target_dose REAL NOT NULL, dose_unit TEXT NOT NULL,
        frequency TEXT, notes TEXT, schedule_json TEXT, sources_json TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE);
    CREATE TABLE dose_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, protocol_id INTEGER,
        peptide_name TEXT NOT NULL, dose_amount REAL NOT NULL, dose_unit TEXT NOT NULL,
        taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, notes TEXT,
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE);
    CREATE TABLE tracked_literature (
        id INTEGER PRIMARY KEY AUTOINCREMENT, pmid TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
        authors_json TEXT, abstract TEXT, journal TEXT, pub_date TEXT, url TEXT, notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    INSERT INTO profiles (name) VALUES ('Legacy User');
    INSERT INTO user_protocols (profile_id, peptide_name, vial_mg, water_ml, target_dose, dose_unit,
                                frequency, notes, updated_at)
        VALUES (1, 'BPC-157', 5.0, 2.0, 250.0, 'mcg', 'daily', 'old', '2025-06-01 12:00:00');
    INSERT INTO user_protocols (profile_id, peptide_name, vial_mg, water_ml, target_dose, dose_unit,
                                frequency, notes)
        VALUES (1, 'Selank', 11.0, 5.0, 250.0, 'mcg', 'daily (intranasal)', 'intranasal spray');
    """)
    conn.commit()
    conn.close()


def test_init_db_upgrades_legacy_db_with_rows(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    _make_legacy_db(str(path))
    monkeypatch.setattr(db, "DB_PATH", str(path))

    db.init_db()  # used to raise OperationalError (non-constant default on ADD COLUMN)
    db.init_db()  # and stays idempotent

    protocols = {p["peptide_name"]: p for p in db.get_user_protocols(1)}
    assert set(protocols) == {"BPC-157", "Selank"}
    # created_at backfilled; BPC-157 had an explicit updated_at to copy
    assert protocols["BPC-157"]["created_at"] == "2025-06-01 12:00:00"
    assert protocols["Selank"]["created_at"]
    assert protocols["BPC-157"]["reconstituted_at"] is None
    # legacy intranasal Selank protocol was migrated once
    assert "SubQ" in protocols["Selank"]["frequency"]
    # new inserts get created_at on an upgraded table too
    db.add_or_update_user_protocol(1, "TB-500", 5.0, 2.0, 2.0, "mg", "weekly", "", [], [])
    new = next(p for p in db.get_user_protocols(1) if p["peptide_name"] == "TB-500")
    assert new["created_at"]
    assert db.get_protocol_adherence(1)  # adherence works on upgraded DB


def test_selank_semax_migration_is_one_shot(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    # User later writes their own intranasal note on a Selank protocol
    fresh_db.add_or_update_user_protocol(
        pid, "Selank", 11.0, 5.0, 250.0, "mcg", "daily (intranasal)", "my own intranasal notes", [], []
    )
    fresh_db.init_db()
    fresh_db.init_db()
    p = fresh_db.get_user_protocols(pid)[0]
    assert p["frequency"] == "daily (intranasal)"
    assert p["notes"] == "my own intranasal notes"


def test_init_db_sets_user_version(fresh_db):
    conn = fresh_db.get_connection()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    conn.close()


def test_connections_are_closed_even_on_exception(fresh_db, monkeypatch):
    opened = []
    real = fresh_db.get_connection

    def tracking():
        conn = real()
        opened.append(conn)
        return conn

    monkeypatch.setattr(fresh_db, "get_connection", tracking)
    with pytest.raises(sqlite3.OperationalError):
        with fresh_db._db() as conn:
            conn.execute("SELECT * FROM no_such_table")
    fresh_db.get_profiles()
    fresh_db.add_profile("Dup A")
    assert fresh_db.add_profile("Dup A") is None  # IntegrityError path
    assert opened
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


def test_updated_at_is_utc(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "n", [], [])
    p = fresh_db.get_user_protocols(pid)[0]
    for key in ("updated_at", "created_at"):
        delta = datetime.now(timezone.utc).replace(tzinfo=None) - datetime.strptime(p[key], "%Y-%m-%d %H:%M:%S")
        assert abs(delta.total_seconds()) < 5

    conn = fresh_db.get_connection()
    conn.execute("UPDATE user_protocols SET updated_at = '2000-01-01 00:00:00'")
    conn.commit()
    conn.close()
    fresh_db.update_protocol_schedule(p["id"], [("Week 1+", 250.0, "mcg")], 250.0, "mcg")
    updated = datetime.strptime(fresh_db.get_user_protocol_by_id(p["id"])["updated_at"], "%Y-%m-%d %H:%M:%S")
    assert abs((datetime.now(timezone.utc).replace(tzinfo=None) - updated).total_seconds()) < 5


def test_retracking_article_keeps_existing_notes(fresh_db):
    fresh_db.save_tracked_article("111", "A", ["x"], "abs", notes="my notes")
    fresh_db.save_tracked_article("111", "A v2", ["x"], "abs")  # notes defaults to ''
    assert fresh_db.get_tracked_article_by_pmid("111")["notes"] == "my notes"
    fresh_db.save_tracked_article("111", "A v3", ["x"], "abs", notes="newer")
    assert fresh_db.get_tracked_article_by_pmid("111")["notes"] == "newer"


def test_get_peptide_by_name_unknown_returns_none(fresh_db):
    assert fresh_db.get_peptide_by_name("No Such Peptide") is None
    assert fresh_db.get_peptide_by_name(None) is None
    assert fresh_db.get_peptide_by_name("BPC-157")["name"] == "BPC-157"


def test_export_reference_sheet_utf8_and_null_fields(fresh_db, tmp_path):
    pid = fresh_db.add_profile("Zoë")
    fresh_db.add_or_update_user_protocol(pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", None, None, [], [
        {"title": "α-synuclein and β-amyloid", "pmid": "42", "url": "https://x/42"}
    ])
    fresh_db.log_dose(pid, None, "BPC-157", 250.0, "mcg", notes="naïve — ok")
    out = tmp_path / "out"
    filename = fresh_db.export_person_reference_sheet(pid, str(out))
    text = (out / filename).read_text(encoding="utf-8")
    assert "α-synuclein and β-amyloid" in text
    assert "naïve — ok" in text
    assert "None" not in text
    assert "Clinical Notes:      -" in text
    assert "Prescribed Dose:     250.0 mcg\n" in text
    assert "UTC" in text


def test_export_creates_missing_dest_dir_and_never_overwrites(fresh_db, tmp_path):
    pid = fresh_db.get_profiles()[0]["id"]
    dest = tmp_path / "a" / "b"
    first = fresh_db.export_dose_log_csv(pid, str(dest))
    second = fresh_db.export_dose_log_csv(pid, str(dest))
    third = fresh_db.export_person_reference_sheet(pid, str(dest))
    fourth = fresh_db.export_person_reference_sheet(pid, str(dest))
    assert first != second and third != fourth
    assert (dest / first).exists() and (dest / second).exists()
    assert second.endswith("_2.csv") and fourth.endswith("_2.txt")


def test_export_filename_collision_between_profiles(fresh_db, tmp_path):
    a = fresh_db.add_profile("Ann/B")
    b = fresh_db.add_profile("Ann:B")  # flattens to the same safe name
    fresh_db.log_dose(a, None, "BPC-157", 1.0, "mg", notes="from A")
    fresh_db.log_dose(b, None, "BPC-157", 2.0, "mg", notes="from B")
    fa = fresh_db.export_dose_log_csv(a, str(tmp_path))
    fb = fresh_db.export_dose_log_csv(b, str(tmp_path))
    assert fa != fb
    with open(tmp_path / fa, newline="", encoding="utf-8") as f:
        assert list(csv.reader(f))[1][5] == "from A"
    with open(tmp_path / fb, newline="", encoding="utf-8") as f:
        assert list(csv.reader(f))[1][5] == "from B"


def test_export_csv_utf8_roundtrip(fresh_db, tmp_path):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.log_dose(pid, None, "BPC-157", 250.0, "mcg", notes="α/β, \"quoted\"\nline2")
    filename = fresh_db.export_dose_log_csv(pid, str(tmp_path))
    raw = (tmp_path / filename).read_bytes()
    assert "α/β".encode("utf-8") in raw
    assert b"\r\r\n" not in raw  # newline="" => no doubled carriage returns
    with open(tmp_path / filename, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[1][5] == "α/β, \"quoted\"\nline2"


def test_export_raises_oserror_when_dest_unusable(fresh_db, tmp_path):
    pid = fresh_db.get_profiles()[0]["id"]
    blocker = tmp_path / "file.txt"
    blocker.write_text("not a directory")
    with pytest.raises(OSError):
        fresh_db.export_dose_log_csv(pid, str(blocker / "sub"))
    with pytest.raises(OSError):
        fresh_db.export_person_reference_sheet(pid, str(blocker))


def test_vial_inventory_without_reconstitution_counts_since_protocol_start(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "n", [], [])
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]
    conn = fresh_db.get_connection()
    conn.execute("UPDATE user_protocols SET created_at = ?", (_utc_str(timedelta(days=-100)),))
    conn.commit()
    conn.close()
    # 30 doses long ago (before the protocol "started"), 2 recent
    for i in range(30):
        fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg", taken_at=_utc_str(timedelta(days=-200 + i)))
    for i in range(2):
        fresh_db.log_dose(pid, protocol_id, "BPC-157", 250.0, "mcg", taken_at=_utc_str(timedelta(days=-3 + i)))
    entry = fresh_db.get_protocol_adherence(pid)[0]
    assert entry["logged_count"] == 32
    assert entry["doses_used"] == 2
    assert entry["doses_remaining"] == 18.0


def test_vial_total_uses_current_titration_phase_dose(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    schedule = [
        ("Week 1-2", 250.0, "mcg"),
        ("Week 3-4", 500.0, "mcg"),
        ("Week 5+ (Maintenance)", 1000.0, "mcg"),
    ]
    # 5 mg vial: 20 doses at 250 mcg, 10 at 500, 5 at 1000
    fresh_db.add_or_update_user_protocol(pid, "BPC-157", 5.0, 2.0, 1000.0, "mcg", "daily", "n", schedule, [])
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]

    def total_after(days):
        conn = fresh_db.get_connection()
        conn.execute("UPDATE user_protocols SET created_at = ? WHERE id = ?",
                     (_utc_str(timedelta(days=-days)), protocol_id))
        conn.commit()
        conn.close()
        return fresh_db.get_protocol_adherence(pid)[0]["doses_total"]

    assert total_after(0) == 20.0     # week 1
    assert total_after(8) == 20.0     # still week 2
    assert total_after(15) == 10.0    # week 3
    assert total_after(30) == 5.0     # week 5+
    assert total_after(400) == 5.0    # long past the ramp -> final phase


def test_vial_total_falls_back_to_target_dose_without_usable_schedule(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "n", [("Maintenance Dose", 500.0, "mcg")], []
    )
    assert fresh_db.get_protocol_adherence(pid)[0]["doses_total"] == 20.0


def test_legacy_created_at_backfill_prefers_earliest_dose(tmp_path, monkeypatch):
    path = tmp_path / "legacy2.db"
    _make_legacy_db(str(path))
    conn = sqlite3.connect(str(path))
    conn.execute("UPDATE user_protocols SET updated_at = '2026-03-01 00:00:00' WHERE id = 1")
    conn.execute(
        "INSERT INTO dose_log (profile_id, protocol_id, peptide_name, dose_amount, dose_unit, taken_at) "
        "VALUES (1, 1, 'BPC-157', 250, 'mcg', '2026-01-10 08:00:00')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()
    assert db.get_user_protocol_by_id(1)["created_at"] == "2026-01-10 08:00:00"


def test_bare_week_labels_do_not_swallow_later_phases(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    schedule = [("Week 1", 250.0, "mcg"), ("Week 2", 500.0, "mcg"), ("Week 3+", 1000.0, "mcg")]
    fresh_db.add_or_update_user_protocol(pid, "BPC-157", 5.0, 2.0, 1000.0, "mcg", "daily", "n", schedule, [])
    protocol_id = fresh_db.get_user_protocols(pid)[0]["id"]

    def total_after(days):
        conn = fresh_db.get_connection()
        conn.execute("UPDATE user_protocols SET created_at = ? WHERE id = ?",
                     (_utc_str(timedelta(days=-days)), protocol_id))
        conn.commit()
        conn.close()
        return fresh_db.get_protocol_adherence(pid)[0]["doses_total"]

    assert total_after(0) == 20.0
    assert total_after(8) == 10.0
    assert total_after(20) == 5.0


def test_delete_profile_unknown_id_with_multiple_profiles(fresh_db):
    fresh_db.add_profile("Other")
    assert fresh_db.delete_profile(99999) is True  # nothing to delete, but not refused
    assert len(fresh_db.get_profiles()) == 2


def test_current_protocol_dose_follows_titration_phase(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    schedule = [
        ("Week 1-2", 250.0, "mcg"),
        ("Week 3-4", 500.0, "mcg"),
        ("Week 5+ (Maintenance)", 1000.0, "mcg"),
    ]
    fresh_db.add_or_update_user_protocol(pid, "BPC-157", 5.0, 2.0, 1000.0, "mcg", "daily", "n", schedule, [])
    protocol = fresh_db.get_user_protocols(pid)[0]
    created = datetime.strptime(protocol["created_at"], "%Y-%m-%d %H:%M:%S")

    def dose_after(days):
        return fresh_db.current_protocol_dose(protocol, now=created + timedelta(days=days))

    assert dose_after(0) == (250.0, "mcg")
    assert dose_after(15) == (500.0, "mcg")
    assert dose_after(40) == (1000.0, "mcg")


def test_current_protocol_dose_converts_to_protocol_unit(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(
        pid, "Tesamorelin", 5.0, 2.0, 2.0, "mg", "daily", "n", [("Week 1+", 500.0, "mcg")], []
    )
    protocol = fresh_db.get_user_protocols(pid)[0]
    assert fresh_db.current_protocol_dose(protocol) == (0.5, "mg")


def test_current_protocol_dose_without_schedule_is_target(fresh_db):
    pid = fresh_db.get_profiles()[0]["id"]
    fresh_db.add_or_update_user_protocol(pid, "BPC-157", 5.0, 2.0, 250.0, "mcg", "daily", "n", [], [])
    protocol = fresh_db.get_user_protocols(pid)[0]
    assert fresh_db.current_protocol_dose(protocol) == (250.0, "mcg")
