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
