from datetime import datetime, timedelta

import pytest

from peptide_dosage import calc


def test_concentration_mg_ml():
    assert calc.concentration_mg_ml(5.0, 2.0) == 2.5
    assert calc.concentration_mg_ml(5.0, 0.0) == 0.0


def test_dose_to_mg():
    assert calc.dose_to_mg(250.0, "mcg") == 0.25
    assert calc.dose_to_mg(2.5, "mg") == 2.5


def test_draw_volume_ml():
    assert calc.draw_volume_ml(0.25, 2.5) == 0.1
    assert calc.draw_volume_ml(0.25, 0.0) == 0.0


def test_syringe_units():
    assert calc.syringe_units(0.1) == 10.0


def test_doses_per_vial():
    assert calc.doses_per_vial(5.0, 0.25) == 20.0
    assert calc.doses_per_vial(5.0, 0.0) == 0.0


def test_bpc157_known_good_numbers():
    # BPC-157: 5mg vial, 2mL water, 250mcg dose -> 2.5 mg/mL, 0.1 mL draw,
    # 10.0 Units, 20.0 doses/vial
    conc = calc.concentration_mg_ml(5.0, 2.0)
    dose_mg = calc.dose_to_mg(250.0, "mcg")
    volume = calc.draw_volume_ml(dose_mg, conc)
    units = calc.syringe_units(volume)
    per_vial = calc.doses_per_vial(5.0, dose_mg)

    assert conc == 2.5
    assert volume == 0.1
    assert units == 10.0
    assert per_vial == 20.0


def test_parse_weekly_frequency_daily_variants():
    assert calc.parse_weekly_frequency("daily") == 7.0
    assert calc.parse_weekly_frequency("daily (at bedtime)") == 7.0
    assert calc.parse_weekly_frequency("nightly (before bed)") == 7.0


def test_parse_weekly_frequency_weekly():
    assert calc.parse_weekly_frequency("weekly") == 1.0


def test_parse_weekly_frequency_nx_weekly():
    assert calc.parse_weekly_frequency("3x weekly") == 3.0
    assert calc.parse_weekly_frequency("2-3x weekly") == 2.5
    assert calc.parse_weekly_frequency("twice weekly") == 2.0
    assert calc.parse_weekly_frequency("2x weekly") == 2.0


def test_parse_weekly_frequency_multi_daily_and_intervals():
    assert calc.parse_weekly_frequency("twice daily") == 14.0
    assert calc.parse_weekly_frequency("daily (intranasal, 1-3x/day)") == 14.0
    assert calc.parse_weekly_frequency("daily (intranasal, split AM/PM)") == 14.0
    # "morning or split AM/PM" is an optional alternative: the base is once daily.
    assert calc.parse_weekly_frequency("daily (SubQ injection, morning or split AM/PM)") == 7.0
    assert calc.parse_weekly_frequency("daily (SubQ injection, morning)") == 7.0
    assert calc.parse_weekly_frequency("every other day") == 3.5
    assert calc.parse_weekly_frequency("every 2 weeks") == 0.5


@pytest.mark.parametrize(
    "freq, expected",
    [
        ("daily (1-3x, pre-meal)", 14.0),
        ("daily (1-3x)", 14.0),
        ("every 2 days", 3.5),
        ("every 3 days", 7.0 / 3.0),
        ("every 10 days", 0.7),
        ("every day", 7.0),
        ("every 12 hours", 14.0),
        ("every 3 weeks", 1.0 / 3.0),
        ("5 days on / 2 days off", 5.0),
        ("3 days on, 1 day off", 3.0 * 7.0 / 4.0),
        ("5 days a week", 5.0),
        ("once a day", 7.0),
        ("once daily", 7.0),
        ("once a week", 1.0),
        ("twice a week", 2.0),
        ("twice daily", 14.0),
        ("three times daily", 21.0),
        ("3 times a day", 21.0),
        ("2x/day", 14.0),
        ("1-3 times daily", 14.0),
        ("daily to 2x daily", 10.5),
        ("weekly (or twice weekly)", 1.0),
        ("2 daily", 14.0),
        ("2/day", 14.0),
        ("3 a day", 21.0),
        ("3 per day", 21.0),
        ("3 per week", 3.0),
        ("4 weekly", 4.0),
        ("3x daily, 5 days a week", 15.0),
        ("3x weekly, max 12 weeks", 3.0),
        ("daily (max 10 days)", 7.0),
        ("3x weekly, then stop", 3.0),
        ("daily, strengthening phase", 7.0),
        ("max 1x/24hr", None),
        ("as needed (PRN), 45 min before activity, max 1x/24hr", None),
        ("as directed (intranasal), up to 4x daily", None),
    ],
)
def test_parse_weekly_frequency_edge_phrasings(freq, expected):
    result = calc.parse_weekly_frequency(freq)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


CATALOG_FREQUENCIES = {
    "daily": 7.0,
    "daily (before bed)": 7.0,
    "daily (at bedtime)": 7.0,
    "nightly (before bed)": 7.0,
    "daily (SubQ injection, morning or split AM/PM)": 7.0,
    "daily (SubQ injection, morning)": 7.0,
    "daily (short course)": 7.0,
    "daily (post-workout)": 7.0,
    "daily (topical)": 7.0,
    "daily (1-3x, pre-meal)": 14.0,
    "daily (1-3x)": 14.0,
    "daily to 2x daily": 10.5,
    "daily (loading), then 2-3x weekly (maintenance)": 2.5,
    "weekly": 1.0,
    "weekly (or twice weekly)": 1.0,
    "twice weekly": 2.0,
    "2x weekly": 2.0,
    "2x weekly (loading)": 2.0,
    "3x weekly": 3.0,
    "3x weekly (short course)": 3.0,
    "2-3x weekly": 2.5,
    "1-2x weekly": 1.5,
    "as needed (PRN), 45 min before activity, max 1x/24hr": None,
    "as directed (intranasal), up to 4x daily": None,
}


def test_parse_weekly_frequency_all_catalog_strings():
    from peptide_dosage import db

    seen = {p["freq"] for p in db.DEFAULT_PEPTIDES}
    # Every catalog frequency must be covered here so new ones get reviewed.
    assert seen <= set(CATALOG_FREQUENCIES), seen - set(CATALOG_FREQUENCIES)
    for freq in seen:
        assert calc.parse_weekly_frequency(freq) == CATALOG_FREQUENCIES[freq], freq


def test_parse_weekly_frequency_unrecognized():
    assert calc.parse_weekly_frequency("as needed (PRN)") is None
    assert calc.parse_weekly_frequency("") is None
    assert calc.parse_weekly_frequency(None) is None


def test_format_vial_duration():
    # 20 doses at daily (7/wk) -> ~20 days
    assert "days" in calc.format_vial_duration(20.0, 7.0)
    # 2.5 doses at weekly (1/wk) -> ~2.5 wks
    assert "2.5 wks" in calc.format_vial_duration(2.5, 1.0)
    # No frequency -> returns doses count
    assert calc.format_vial_duration(10.0, None) == "10.0 doses"
    assert calc.format_vial_duration(0.0, 1.0) == "0 doses"


def test_syringe_draw_status():
    draw, status = calc.syringe_draw_status(80.0)
    assert draw == "80.0 Units"
    assert "✓ Normal draw" in status

    draw_over, status_over = calc.syringe_draw_status(160.0)
    assert "⚠️" in draw_over
    assert "Exceeds 100U" in status_over
    assert "1x 100U + 1x 60.0U" in status_over

    draw_zero, status_zero = calc.syringe_draw_status(0.0)
    assert draw_zero == "0.0 Units"


def test_adherence_percent_normal():
    # 1x/week expected, logged 2 doses over 14 days -> 100% (exactly on pace)
    assert calc.adherence_percent(2, 1.0, 14.0) == 100.0


def test_adherence_percent_partial():
    # 7x/week expected (daily), logged 3 doses over 7 days -> ~43%
    result = calc.adherence_percent(3, 7.0, 7.0)
    assert round(result, 1) == 42.9


def test_adherence_percent_capped_at_100():
    assert calc.adherence_percent(100, 1.0, 7.0) == 100.0


def test_adherence_percent_unmeasurable():
    assert calc.adherence_percent(5, None, 30.0) is None
    assert calc.adherence_percent(0, 7.0, 0.5) is None


def test_next_dose_due_at_anchors_on_last_taken():
    last_taken = datetime(2026, 1, 1, 8, 0, 0)
    # weekly (1x/week) -> 7 day interval
    due = calc.next_dose_due_at(1.0, last_taken, None)
    assert due == last_taken + timedelta(days=7)


def test_next_dose_due_at_falls_back_when_never_logged():
    created = datetime(2026, 1, 1, 8, 0, 0)
    # daily (7x/week) -> 1 day interval
    due = calc.next_dose_due_at(7.0, None, created)
    assert due == created + timedelta(days=1)


def test_next_dose_due_at_unmeasurable():
    assert calc.next_dose_due_at(None, datetime(2026, 1, 1), datetime(2026, 1, 1)) is None
    assert calc.next_dose_due_at(1.0, None, None) is None


def test_format_due_label_overdue():
    now = datetime(2026, 1, 10)
    assert calc.format_due_label(now - timedelta(days=3), now) == "Overdue 3d"
    assert calc.format_due_label(now - timedelta(hours=2), now) == "Overdue (today)"


def test_format_due_label_upcoming():
    now = datetime(2026, 1, 10)
    assert calc.format_due_label(now + timedelta(hours=5), now) == "Due today"
    assert calc.format_due_label(now + timedelta(days=4), now) == "Due in 4d"


def test_format_due_label_unmeasurable():
    assert calc.format_due_label(None, datetime(2026, 1, 10)) == "N/A"


def test_generate_titration_schedule_increasing_ramp():
    schedule = calc.generate_titration_schedule(250.0, 1000.0, 250.0, 2.0, "mcg")
    assert schedule == [
        ("Week 1-2", 250.0, "mcg"),
        ("Week 3-4", 500.0, "mcg"),
        ("Week 5-6", 750.0, "mcg"),
        ("Week 7+ (Maintenance)", 1000.0, "mcg"),
    ]


def test_generate_titration_schedule_decreasing_ramp():
    schedule = calc.generate_titration_schedule(1000.0, 250.0, 250.0, 2.0, "mcg")
    assert schedule == [
        ("Week 1-2", 1000.0, "mcg"),
        ("Week 3-4", 750.0, "mcg"),
        ("Week 5-6", 500.0, "mcg"),
        ("Week 7+ (Maintenance)", 250.0, "mcg"),
    ]


def test_generate_titration_schedule_start_equals_target():
    assert calc.generate_titration_schedule(500.0, 500.0, 100.0, 2.0, "mcg") == [
        ("Maintenance Dose", 500.0, "mcg")
    ]


def test_generate_titration_schedule_invalid_inputs():
    with pytest.raises(ValueError):
        calc.generate_titration_schedule(0.0, 500.0, 100.0, 2.0, "mcg")
    with pytest.raises(ValueError):
        calc.generate_titration_schedule(250.0, 500.0, 100.0, 0.0, "mcg")
    with pytest.raises(ValueError):
        calc.generate_titration_schedule(250.0, 500.0, 0.0, 2.0, "mcg")


def test_generate_titration_schedule_max_steps_cap():
    schedule = calc.generate_titration_schedule(1.0, 1000.0, 0.01, 1.0, "mg", max_steps=5)
    assert len(schedule) == 6
    assert schedule[-1] == ("Week 6+ (Maintenance)", 1000.0, "mg")


def test_generate_titration_schedule_half_week_steps():
    schedule = calc.generate_titration_schedule(1.0, 3.0, 1.0, 0.5, "mg")
    assert schedule == [
        ("Week 1-1.5", 1.0, "mg"),
        ("Week 1.5-2", 2.0, "mg"),
        ("Week 2+ (Maintenance)", 3.0, "mg"),
    ]
    # No "Week 1-0" / "Week 2-1" style inverted labels, and the durations read back correctly.
    assert calc.schedule_phase_durations(schedule, 6.0) == [(0.5, 1.0, "mg"), (0.5, 2.0, "mg"), (5.0, 3.0, "mg")]


def test_generate_titration_schedule_one_and_a_half_week_steps_do_not_overlap():
    schedule = calc.generate_titration_schedule(1.0, 4.0, 1.0, 1.5, "mg")
    assert [label for label, _, _ in schedule] == [
        "Week 1-2.5", "Week 2.5-4", "Week 4-5.5", "Week 5.5+ (Maintenance)",
    ]
    durations = calc.schedule_phase_durations(schedule, 12.0)
    assert [w for w, _, _ in durations] == [1.5, 1.5, 1.5, 7.5]


def test_generate_titration_schedule_single_week_steps():
    schedule = calc.generate_titration_schedule(1.0, 3.0, 1.0, 1.0, "mg")
    assert [label for label, _, _ in schedule] == ["Week 1", "Week 2", "Week 3+ (Maintenance)"]
    # A bare "Week N" mid-schedule lasts until the next phase starts.
    assert calc.schedule_phase_durations(schedule, 6.0) == [(1.0, 1.0, "mg"), (1.0, 2.0, "mg"), (4.0, 3.0, "mg")]


def test_generate_titration_schedule_rejects_tiny_steps():
    with pytest.raises(ValueError):
        calc.generate_titration_schedule(1.0, 3.0, 1.0, 0.00001, "mg")


def test_generate_titration_schedule_third_week_steps_sum_to_whole_weeks():
    schedule = calc.generate_titration_schedule(1.0, 2.0, 0.5, 1 / 3, "mg")
    durations = calc.schedule_phase_durations(schedule, 3.0)
    assert sum(w for w, _, _ in durations) == pytest.approx(3.0)
    assert durations[0][0] + durations[1][0] == pytest.approx(0.67)


def test_is_bounded_course():
    assert calc.is_bounded_course("Days 1-10 (Course 1)")
    assert calc.is_bounded_course("Week 1-4 (Course)")
    assert not calc.is_bounded_course("Week 5+ (Maintenance Course)")
    assert not calc.is_bounded_course("Week 1-4 (Titration)")
    assert not calc.is_bounded_course("Maintenance Dose")


def test_generate_titration_schedule_float_increment_reaches_target():
    schedule = calc.generate_titration_schedule(0.1, 0.4, 0.1, 1.0, "mg")
    assert [dose for _, dose, _ in schedule] == [0.1, 0.2, 0.3, 0.4]
    assert schedule[-1][0].endswith("(Maintenance)")


def test_split_vial_aliquots_even_split():
    result = calc.split_vial_aliquots(10.0, 2.0, 4)
    assert result == {"aliquot_mg": 2.5, "aliquot_ml": 0.5, "concentration_mg_ml": 5.0}


def test_split_vial_aliquots_invalid_inputs():
    with pytest.raises(ValueError):
        calc.split_vial_aliquots(10.0, 2.0, 0)
    with pytest.raises(ValueError):
        calc.split_vial_aliquots(0.0, 2.0, 2)


def test_bud_expiry_and_labels():
    recon = datetime(2026, 9, 1, 12, 0, 0)
    expiry = calc.bud_expiry_at(recon)
    assert expiry == recon + timedelta(days=calc.DEFAULT_BUD_DAYS)
    assert calc.bud_expiry_at(None) is None

    assert calc.format_bud_label(None, recon) == "Not reconstituted"
    assert "Fresh" in calc.format_bud_label(expiry, recon)
    assert "Expires in" in calc.format_bud_label(expiry, expiry - timedelta(days=3))
    assert "Expires today" in calc.format_bud_label(expiry, expiry - timedelta(hours=6))
    assert "Expired" in calc.format_bud_label(expiry, expiry + timedelta(days=4))


def test_bud_exceeded_by_duration():
    # 30 daily doses lasts 30 days -> outlives a 28-day BUD
    assert calc.bud_exceeded_by_duration(30.0, 7.0) is True
    # 10 daily doses lasts 10 days -> fine
    assert calc.bud_exceeded_by_duration(10.0, 7.0) is False
    # unparseable frequency can't be judged
    assert calc.bud_exceeded_by_duration(30.0, None) is False


def test_adherence_label_distinguishes_unmeasurable_cases():
    assert calc.adherence_label(87.5, 7.0, 10.0) == "88%"
    assert calc.adherence_label(None, None, 10.0) == "Freq. not recognized"
    assert calc.adherence_label(None, 7.0, 0.2) == "Too new"
    assert calc.adherence_label(None, 7.0, 10.0) == "N/A"


def test_doses_remaining_and_formatting():
    assert calc.doses_remaining(10.0, 3) == 7.0
    assert calc.doses_remaining(2.0, 5) == 0.0  # floored, never negative
    assert "left" in calc.format_doses_remaining(7.0, 10.0)
    assert "reorder" in calc.format_doses_remaining(1.5, 10.0)
    assert "Empty" in calc.format_doses_remaining(0.0, 10.0)
    assert calc.format_doses_remaining(0.0, 0.0) == "N/A"


def test_parse_dose_timestamp():
    now = datetime(2026, 9, 17, 12, 0, 0)
    assert calc.parse_dose_timestamp("", now) is None
    assert calc.parse_dose_timestamp("now", now) is None
    assert calc.parse_dose_timestamp("2026-09-15", now) == "2026-09-15 00:00:00"
    assert calc.parse_dose_timestamp("2026-09-15 08:30", now) == "2026-09-15 08:30:00"
    assert calc.parse_dose_timestamp("2026-09-15 08:30:15", now) == "2026-09-15 08:30:15"

    with pytest.raises(ValueError):
        calc.parse_dose_timestamp("garbage", now)
    with pytest.raises(ValueError):
        calc.parse_dose_timestamp("2099-01-01", now)


def test_safe_filename_part_flattens_path_separators():
    # The bug: profile "Adam/Bob" produced "patient_adam/bob_...txt", a path
    # into a directory that doesn't exist -> FileNotFoundError.
    assert calc.safe_filename_part("Adam/Bob") == "adam_bob"
    assert calc.safe_filename_part("Custom / Other") == "custom_other"
    assert calc.safe_filename_part("CJC-1295 / Ipamorelin Blend") == "cjc-1295_ipamorelin_blend"
    assert calc.safe_filename_part("Default User") == "default_user"


def test_safe_filename_part_blocks_traversal_and_empty_names():
    for hostile in ("../escape", "../../etc/passwd", "..", "...", "/", ""):
        result = calc.safe_filename_part(hostile)
        assert "/" not in result
        assert not result.startswith(".")
        assert result  # never empty -- falls back rather than yielding a bare extension
    assert calc.safe_filename_part("", fallback="anon") == "anon"


def test_validate_reconstitution_inputs_accepts_realistic_values():
    assert calc.validate_reconstitution_inputs(5.0, 2.0, 250.0, "mcg") is None
    assert calc.validate_reconstitution_inputs(500.0, 10.0, 50.0, "mg") is None


def test_validate_reconstitution_inputs_rejects_out_of_range():
    assert "Enter positive" in calc.validate_reconstitution_inputs(0.0, 2.0, 250.0, "mcg")
    assert "Enter positive" in calc.validate_reconstitution_inputs(5.0, 2.0, -1.0, "mcg")
    assert "Vial size" in calc.validate_reconstitution_inputs(1e99, 2.0, 250.0, "mcg")
    assert "BAC water" in calc.validate_reconstitution_inputs(5.0, 5000.0, 250.0, "mcg")
    assert "Dose" in calc.validate_reconstitution_inputs(5.0, 2.0, 99999.0, "mg")


def test_validate_reconstitution_inputs_rejects_nan_and_inf():
    assert "real number" in calc.validate_reconstitution_inputs(float("nan"), 2.0, 250.0, "mcg")
    assert "real number" in calc.validate_reconstitution_inputs(float("inf"), 2.0, 250.0, "mcg")


def test_convert_dose_between_units():
    assert calc.convert_dose(1.0, "mg", "mcg") == 1000.0
    assert calc.convert_dose(250.0, "mcg", "mg") == 0.25
    assert calc.convert_dose(5.0, "mg", "mg") == 5.0
    assert calc.convert_dose(5.0, "iu", "mg") == 5.0  # unknown units pass through


def test_parse_phase_week_range():
    assert calc.parse_phase_week_range("Week 1-4") == (1.0, 4.0)
    assert calc.parse_phase_week_range("Week 13-16 (Titration)") == (13.0, 16.0)
    assert calc.parse_phase_week_range("Week 17+ (Maintenance)") == (17.0, None)
    assert calc.parse_phase_week_range("Week 9") == (9.0, None)
    assert calc.parse_phase_week_range("Maintenance Dose") is None
    assert calc.parse_phase_week_range("") is None


def test_parse_phase_week_range_days_and_fractions():
    # Days are converted to weeks: 10 days = 10/7 weeks (end - start + 1).
    start, end = calc.parse_phase_week_range("Days 1-10 (Course)")
    assert start == 1.0
    assert end - start + 1 == pytest.approx(10.0 / 7.0)
    # Fractional ranges are half-open: "Week 1-1.5" lasts half a week.
    start, end = calc.parse_phase_week_range("Week 1-1.5")
    assert end - start + 1 == pytest.approx(0.5)
    assert calc.parse_phase_week_range("Week 5.5+ (Maintenance)") == (5.5, None)


def test_schedule_phase_durations_days_phases():
    schedule = [("Days 1-10 (Course 1)", 100.0, "mcg"), ("Days 1-10 (Course 2, next cycle)", 200.0, "mcg")]
    result = calc.schedule_phase_durations(schedule, 26.0)
    assert result == [(pytest.approx(10 / 7), 100.0, "mcg"), (pytest.approx(10 / 7), 200.0, "mcg")]


def test_project_inventory_bounded_course_not_extended():
    schedule = [("Days 1-10 (Course)", 5.0, "mg")]
    for months in (1, 3, 6):
        proj = calc.project_inventory(schedule, 5.0, "mg", 7.0, months)
        assert proj["total_doses"] == pytest.approx(10.0)
        assert proj["total_mg"] == pytest.approx(50.0)
        assert proj["bounded"] is True
    # Horizon shorter than the course just truncates it.
    short = calc.project_inventory([("Days 1-20 (Extended Course)", 10.0, "mg")], 10.0, "mg", 7.0, 0.1)
    assert short["bounded"] is False
    assert short["total_doses"] == pytest.approx(0.1 * calc.WEEKS_PER_MONTH * 7.0)


def test_project_inventory_catalog_course_peptides_are_bounded():
    from peptide_dosage import db

    for name in ("Epithalon", "Pinealon", "Thymalin", "Cartalax", "FOXO4-DRI"):
        pep = next(p for p in db.DEFAULT_PEPTIDES if p["name"] == name)
        weekly = calc.parse_weekly_frequency(pep["freq"])
        proj = calc.project_inventory(pep["schedule"], pep["dose"], pep["unit"], weekly, 6)
        assert proj["bounded"] is True, name
        assert proj["course_weeks"] < 6, name


def test_schedule_phase_durations_dated_phases():
    schedule = [("Week 1-4", 0.25, "mg"), ("Week 5-8", 0.50, "mg")]
    # Exactly spans both 4-week phases.
    assert calc.schedule_phase_durations(schedule, 8.0) == [(4.0, 0.25, "mg"), (4.0, 0.50, "mg")]
    # Truncated mid-second-phase.
    assert calc.schedule_phase_durations(schedule, 6.0) == [(4.0, 0.25, "mg"), (2.0, 0.50, "mg")]
    # Shorter than even the first phase.
    assert calc.schedule_phase_durations(schedule, 2.0) == [(2.0, 0.25, "mg")]


def test_schedule_phase_durations_open_ended_last_phase():
    schedule = [("Week 1-4 (Titration)", 0.25, "mg"), ("Week 5+ (Maintenance)", 1.0, "mg")]
    result = calc.schedule_phase_durations(schedule, 12.0)
    assert result == [(4.0, 0.25, "mg"), (8.0, 1.0, "mg")]


def test_schedule_phase_durations_unparseable_label_fills_or_defaults():
    # A single-step "Maintenance Dose" (no week number at all) fills the horizon.
    assert calc.schedule_phase_durations([("Maintenance Dose", 2.4, "mg")], 10.0) == [(10.0, 2.4, "mg")]
    # An unparseable *non-last* phase defaults to a single week.
    schedule = [("Loading Phase", 1.0, "mg"), ("Week 2-5", 2.0, "mg")]
    assert calc.schedule_phase_durations(schedule, 10.0) == [(1.0, 1.0, "mg"), (4.0, 2.0, "mg")]


def test_project_inventory_maintenance_only():
    # 250mcg daily (7x/week) for 1 month (~4.345 weeks) with no titration schedule.
    proj = calc.project_inventory(None, 250.0, "mcg", 7.0, 1)
    assert proj is not None
    expected_doses = 1 * calc.WEEKS_PER_MONTH * 7.0
    assert proj["total_doses"] == pytest.approx(expected_doses)
    assert proj["total_mg"] == pytest.approx(expected_doses * 0.25)


def test_project_inventory_titrates_then_holds_at_final_dose():
    # Semaglutide-style ramp, weekly dosing, projected 6 months out: the
    # schedule's dated phases (16 weeks) are used as-is, then the remainder
    # continues at the schedule's own last dose (2.40mg), not the catalog's
    # nominal starting dose.
    schedule = [
        ("Week 1-4 (Titration)", 0.25, "mg"),
        ("Week 5-8 (Titration)", 0.50, "mg"),
        ("Week 9-12 (Titration)", 1.00, "mg"),
        ("Week 13-16 (Titration)", 1.70, "mg"),
        ("Week 17+ (Maintenance)", 2.40, "mg"),
    ]
    proj = calc.project_inventory(schedule, 0.25, "mg", 1.0, 6)
    assert proj is not None
    horizon_weeks = 6 * calc.WEEKS_PER_MONTH
    maintenance_weeks = horizon_weeks - 16.0
    expected_mg = (0.25 * 4) + (0.50 * 4) + (1.00 * 4) + (1.70 * 4) + (2.40 * maintenance_weeks)
    assert proj["total_mg"] == pytest.approx(expected_mg)


def test_project_inventory_requires_parseable_frequency():
    assert calc.project_inventory([("Week 1-4", 1.0, "mg")], 1.0, "mg", None, 3) is None
    assert calc.project_inventory([("Week 1-4", 1.0, "mg")], 1.0, "mg", 0.0, 3) is None


def test_vials_needed():
    assert calc.vials_needed(10.0, 5.0) == 2
    assert calc.vials_needed(10.1, 5.0) == 3
    assert calc.vials_needed(0.0, 5.0) == 0
    assert calc.vials_needed(10.0, 0.0) == 0


def test_format_inventory_projection_includes_all_horizons_and_vial_counts():
    text = calc.format_inventory_projection(None, 250.0, "mcg", 7.0, 5.0)
    assert "1 mo" in text and "3 mo" in text and "6 mo" in text
    assert "vial" in text


def test_format_inventory_projection_uses_real_dose_unit():
    # 250 mcg daily: 1 mo ~= 7,609 mcg, shown as mcg (not mislabelled "mg").
    mcg_text = calc.format_inventory_projection(None, 250.0, "mcg", 7.0, 5.0)
    assert "mcg" in mcg_text and "1 mo: 7,609.4 mcg (2 vials)" in mcg_text
    assert " mg" not in mcg_text
    # Same dose entered in mg stays in mg.
    mg_text = calc.format_inventory_projection(None, 0.25, "mg", 7.0, 5.0)
    assert "1 mo: 7.6 mg (2 vials)" in mg_text
    # The schedule's own unit wins over the fallback.
    sched_text = calc.format_inventory_projection([("Week 1-4", 250.0, "mcg")], 0.25, "mg", 7.0, 5.0)
    assert "mcg" in sched_text


def test_format_inventory_projection_notes_bounded_course():
    text = calc.format_inventory_projection([("Days 1-10 (Course)", 5.0, "mg")], 5.0, "mg", 7.0, 50.0)
    assert "1 mo: 50.0 mg (1 vial)" in text and "6 mo: 50.0 mg (1 vial)" in text
    assert "course ends after ~1.4 wks" in text


def test_format_inventory_projection_unrecognized_frequency():
    text = calc.format_inventory_projection(None, 250.0, "mcg", None, 5.0)
    assert "not recognized" in text
