"""Tests for explicit domain state machines in peptide_dosage.states."""

from datetime import datetime, timedelta
import pytest

from peptide_dosage import states


def test_bud_state_unreconstituted():
    now = datetime(2026, 9, 1, 12, 0, 0)
    info = states.evaluate_bud_state(None, now)
    assert info.state == states.BudState.UNRECONSTITUTED
    assert info.label == "Not reconstituted"
    assert info.is_reconstituted is False
    assert info.is_warning is True
    assert info.pill_bg_color == states.COLOR_WARN


def test_bud_state_fresh():
    now = datetime(2026, 9, 1, 12, 0, 0)
    expiry = now + timedelta(days=20)
    info = states.evaluate_bud_state(expiry, now)
    assert info.state == states.BudState.FRESH
    assert "✓ Fresh (20d left)" in info.label
    assert info.is_expired is False
    assert info.pill_bg_color == states.COLOR_OK


def test_bud_state_expiring_soon():
    now = datetime(2026, 9, 1, 12, 0, 0)
    expiry = now + timedelta(days=3)
    info = states.evaluate_bud_state(expiry, now)
    assert info.state == states.BudState.EXPIRING_SOON
    assert "⚠️ Expires in 3d" in info.label
    assert info.is_warning is True
    assert info.pill_bg_color == states.COLOR_WARN


def test_bud_state_expires_today():
    now = datetime(2026, 9, 1, 12, 0, 0)
    expiry = now + timedelta(hours=6)
    info = states.evaluate_bud_state(expiry, now)
    assert info.state == states.BudState.EXPIRES_TODAY
    assert info.label == "⚠️ Expires today"
    assert info.is_warning is True


def test_bud_state_expired_today():
    now = datetime(2026, 9, 1, 12, 0, 0)
    expiry = now - timedelta(hours=6)
    info = states.evaluate_bud_state(expiry, now)
    assert info.state == states.BudState.EXPIRED_TODAY
    assert info.label == "❌ Expired today"
    assert info.is_expired is True
    assert info.pill_bg_color == states.COLOR_ERROR


def test_bud_state_expired_past():
    now = datetime(2026, 9, 1, 12, 0, 0)
    expiry = now - timedelta(days=4)
    info = states.evaluate_bud_state(expiry, now)
    assert info.state == states.BudState.EXPIRED
    assert info.label == "❌ Expired 4d ago"
    assert info.is_expired is True
    assert info.pill_bg_color == states.COLOR_ERROR


def test_bud_state_duration_risk_flag():
    now = datetime(2026, 9, 1, 12, 0, 0)
    expiry = now + timedelta(days=28)
    # 30 doses at 7/wk = 30 days > 28 days
    info = states.evaluate_bud_state(expiry, now, total_doses=30.0, weekly_expected=7.0)
    assert info.bud_exceeded_by_duration is True

    # 10 doses at 7/wk = 10 days <= 28 days
    info_ok = states.evaluate_bud_state(expiry, now, total_doses=10.0, weekly_expected=7.0)
    assert info_ok.bud_exceeded_by_duration is False


def test_vial_inventory_states():
    # No data
    info = states.evaluate_doses_remaining(0.0, 0.0)
    assert info.state == states.VialInventoryState.NO_DATA
    assert info.label == "N/A"

    # Empty
    info = states.evaluate_doses_remaining(0.0, 10.0)
    assert info.state == states.VialInventoryState.EMPTY
    assert info.label == "❌ Empty - reorder"
    assert info.is_empty is True
    assert info.is_low is True
    assert info.pill_bg_color == states.COLOR_ERROR

    # Low / Reorder
    info = states.evaluate_doses_remaining(1.5, 10.0)
    assert info.state == states.VialInventoryState.LOW_REORDER
    assert info.label == "⚠️ 1.5 left - reorder"
    assert info.is_empty is False
    assert info.is_low is True
    assert info.pill_bg_color == states.COLOR_WARN

    # Plentiful
    info = states.evaluate_doses_remaining(7.0, 10.0)
    assert info.state == states.VialInventoryState.PLENTIFUL
    assert info.label == "7.0 / 10.0 left"
    assert info.is_empty is False
    assert info.is_low is False
    assert info.pill_bg_color == states.COLOR_OK


def test_dose_due_states():
    now = datetime(2026, 9, 1, 12, 0, 0)

    # Unscheduled
    info = states.evaluate_dose_due(None, now)
    assert info.state == states.DoseDueState.UNSCHEDULED
    assert info.label == "N/A"

    # Upcoming
    info = states.evaluate_dose_due(now + timedelta(days=3), now)
    assert info.state == states.DoseDueState.UPCOMING
    assert info.label == "Due in 3d"
    assert info.is_overdue is False

    # Due today
    info = states.evaluate_dose_due(now + timedelta(hours=6), now)
    assert info.state == states.DoseDueState.DUE_TODAY
    assert info.label == "Due today"
    assert info.is_due_today is True

    # Overdue today
    info = states.evaluate_dose_due(now - timedelta(hours=6), now)
    assert info.state == states.DoseDueState.OVERDUE_TODAY
    assert info.label == "Overdue (today)"
    assert info.is_overdue is True

    # Overdue days
    info = states.evaluate_dose_due(now - timedelta(days=4), now)
    assert info.state == states.DoseDueState.OVERDUE
    assert info.label == "Overdue 4d"
    assert info.is_overdue is True


def test_adherence_states():
    # Measurable
    info = states.evaluate_adherence_label(85.0, 7.0, 14.0)
    assert info.state == states.AdherenceState.MEASURABLE
    assert info.label == "85%"
    assert info.percentage == 85.0
    assert info.is_measurable is True

    # Unrecognized frequency
    info = states.evaluate_adherence_label(None, None, 14.0)
    assert info.state == states.AdherenceState.UNRECOGNIZED_FREQUENCY
    assert info.label == "Freq. not recognized"
    assert info.is_measurable is False

    # Too new
    info = states.evaluate_adherence_label(None, 7.0, 0.5)
    assert info.state == states.AdherenceState.TOO_NEW
    assert info.label == "Too new"
    assert info.is_measurable is False

    # No schedule / other N/A
    info = states.evaluate_adherence_label(None, 7.0, 14.0)
    assert info.state == states.AdherenceState.NO_SCHEDULE
    assert info.label == "N/A"
    assert info.is_measurable is False


def test_syringe_draw_states():
    # Empty
    empty = states.evaluate_syringe_draw(0.0, 100.0)
    assert empty.state == states.SyringeDrawState.EMPTY
    assert empty.draw_label == "0.0 Units"
    assert empty.status_label == "—"

    # Normal
    normal = states.evaluate_syringe_draw(40.0, 50.0)
    assert normal.state == states.SyringeDrawState.NORMAL
    assert normal.draw_label == "40.0 Units"
    assert normal.status_label == "✓ Normal draw (40.0U / 50U)"
    assert normal.is_over_capacity is False

    # Exceeds capacity with upgrade available (40U on 30U syringe, fits in 100U)
    upgrade = states.evaluate_syringe_draw(40.0, 30.0)
    assert upgrade.state == states.SyringeDrawState.EXCEEDS_CAPACITY_UPGRADE_AVAILABLE
    assert upgrade.is_over_capacity is True
    assert upgrade.upgrade_suggested is True
    assert "⚠️ Exceeds 30U (1x 30U + 1x 10.0U)" == upgrade.status_label

    # Exceeds capacity multi-draw (>100U on 100U syringe)
    multi = states.evaluate_syringe_draw(160.0, 100.0)
    assert multi.state == states.SyringeDrawState.EXCEEDS_CAPACITY_MULTI_DRAW
    assert multi.is_over_capacity is True
    assert multi.upgrade_suggested is False
    assert "⚠️ Exceeds 100U (1x 100U + 1x 60.0U)" == multi.status_label


def test_calc_validation_states():
    # Valid
    val = states.evaluate_calc_inputs(5.0, 2.0, 250.0, "mcg")
    assert val.state == states.CalcInputState.VALID
    assert val.is_valid is True
    assert val.error_message is None

    # Non-positive
    val_neg = states.evaluate_calc_inputs(-1.0, 2.0, 250.0, "mcg")
    assert val_neg.state == states.CalcInputState.NON_POSITIVE
    assert val_neg.is_valid is False
    assert "Enter positive" in val_neg.error_message

    # Non-finite
    val_inf = states.evaluate_calc_inputs(float("inf"), 2.0, 250.0, "mcg")
    assert val_inf.state == states.CalcInputState.NON_FINITE
    assert "real number" in val_inf.error_message

    # Exceeds bounds
    val_vial = states.evaluate_calc_inputs(1e6, 2.0, 250.0, "mcg")
    assert val_vial.state == states.CalcInputState.EXCEEDS_MAX_VIAL
    assert "Vial size" in val_vial.error_message
