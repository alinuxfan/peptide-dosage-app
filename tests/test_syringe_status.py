"""syringe_draw_status respects the syringe size (30/50/100 U)."""

import pytest

from peptide_dosage import calc


def test_default_capacity_unchanged():
    assert calc.syringe_draw_status(80.0) == ("80.0 Units", "✓ Normal draw (80.0U / 100U)")
    draw, status = calc.syringe_draw_status(160.0)
    assert draw == "⚠️ 160.0 Units"
    assert status == "⚠️ Exceeds 100U (1x 100U + 1x 60.0U)"


@pytest.mark.parametrize("cap", [30.0, 50.0, 100.0])
def test_within_capacity(cap):
    draw, status = calc.syringe_draw_status(cap, cap)
    assert draw == f"{cap:.1f} Units"
    assert f"/ {cap:g}U)" in status
    assert "Exceeds" not in status


def test_over_small_syringe():
    draw, status = calc.syringe_draw_status(40.0, 30.0)
    assert "⚠️" in draw
    assert status == "⚠️ Exceeds 30U (1x 30U + 1x 10.0U)"


def test_exact_multiple_has_no_remainder():
    _, status = calc.syringe_draw_status(100.0, 50.0)
    assert status == "⚠️ Exceeds 50U (2x 50U)"
    _, status = calc.syringe_draw_status(150.0, 50.0)
    assert status == "⚠️ Exceeds 50U (3x 50U)"


def test_zero_and_bad_capacity():
    assert calc.syringe_draw_status(0.0, 30.0) == ("0.0 Units", "—")
    assert calc.syringe_draw_status(10.0, 0.0) == ("10.0 Units", "—")


def test_float_noise_below_exact_multiple():
    _, status = calc.syringe_draw_status(59.99999999999999, 30.0)
    assert status == "⚠️ Exceeds 30U (2x 30U)"
