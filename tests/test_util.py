"""Tests for the pure helpers in util.py (timezone handling).

Fixed-offset timezones are used so results don't depend on the host machine
or on tzdata being installed (Windows CI).
"""

from datetime import datetime, timedelta, timezone

import pytest

from peptide_dosage import util

UTC_PLUS_13 = timezone(timedelta(hours=13))   # Auckland (summer)
UTC_MINUS_7 = timezone(timedelta(hours=-7))   # Los Angeles (summer)
NOW_UTC = datetime(2025, 10, 26, 12, 0, 0)    # 2025-10-27 01:00 in +13, 05:00 in -7


def test_num():
    assert util.num(None) == 0.0
    assert util.num(None, 3.0) == 3.0
    assert util.num(2) == 2.0


def test_utc_now_naive_is_naive_utc():
    now = util.utc_now_naive()
    assert now.tzinfo is None
    assert abs(now - datetime.now(timezone.utc).replace(tzinfo=None)) < timedelta(seconds=5)


def test_blank_means_now():
    assert util.local_input_to_utc("", UTC_PLUS_13, NOW_UTC) is None
    assert util.local_input_to_utc("  now ", UTC_MINUS_7, NOW_UTC) is None


def test_east_of_utc_today_is_not_future():
    # Local time is 2025-10-27 01:00; typing a few hours earlier today must work.
    assert util.local_input_to_utc("2025-10-27 00:30", UTC_PLUS_13, NOW_UTC) == "2025-10-26 11:30:00"


def test_east_of_utc_future_rejected():
    with pytest.raises(ValueError):
        util.local_input_to_utc("2025-10-27 03:00", UTC_PLUS_13, NOW_UTC)


def test_west_of_utc_converted_to_utc():
    assert util.local_input_to_utc("2025-10-26 04:00", UTC_MINUS_7, NOW_UTC) == "2025-10-26 11:00:00"
    # 05:30 local is 12:30 UTC, i.e. after "now" -> future.
    with pytest.raises(ValueError):
        util.local_input_to_utc("2025-10-26 05:30", UTC_MINUS_7, NOW_UTC)


def test_date_only_is_local_midnight():
    assert util.local_input_to_utc("2025-10-20", UTC_MINUS_7, NOW_UTC) == "2025-10-20 07:00:00"


def test_bad_format_raises():
    with pytest.raises(ValueError):
        util.local_input_to_utc("tomorrow-ish", UTC_PLUS_13, NOW_UTC)


def test_system_local_roundtrip():
    # No tz given -> system local; converting out and back must be lossless.
    utc = "2025-03-02 10:15:00"
    local = util.utc_to_local_input(utc)
    assert util.local_input_to_utc(local, now_utc=datetime(2026, 1, 1)) == "2025-03-02 10:15:00"


def test_utc_to_local_display():
    assert util.utc_to_local_display("2025-10-26 01:30:00", UTC_MINUS_7, NOW_UTC) == "Oct 25, 18:30"
    assert util.utc_to_local_display("2025-10-26 11:30:00", UTC_PLUS_13, NOW_UTC) == "Oct 27, 00:30"


def test_display_includes_year_when_not_current():
    assert util.utc_to_local_display("2024-01-05 09:00:00", timezone.utc, NOW_UTC) == "Jan 5 2024, 09:00"


def test_display_and_input_pass_through_garbage():
    assert util.utc_to_local_display("not a date") == "not a date"
    assert util.utc_to_local_input("not a date") == "not a date"
    assert util.utc_to_local_display(None) == ""


def test_utc_to_local_input():
    assert util.utc_to_local_input("2025-10-26 11:30:45", UTC_PLUS_13) == "2025-10-27 00:30"


def test_zoneinfo_dst_if_available():
    zoneinfo = pytest.importorskip("zoneinfo")
    try:
        la = zoneinfo.ZoneInfo("America/Los_Angeles")
    except zoneinfo.ZoneInfoNotFoundError:
        pytest.skip("tzdata not installed")
    now = datetime(2025, 12, 1, 20, 0, 0)
    # December: PST (UTC-8)
    assert util.local_input_to_utc("2025-12-01 10:00", la, now) == "2025-12-01 18:00:00"
    # July: PDT (UTC-7)
    assert util.local_input_to_utc("2025-07-01 10:00", la, now) == "2025-07-01 17:00:00"


def test_out_of_range_date_is_value_error_not_oserror():
    with pytest.raises(ValueError):
        util.local_input_to_utc("0001-01-01", UTC_PLUS_13, NOW_UTC)
    with pytest.raises(ValueError):
        util.local_input_to_utc("0001-01-01", None, NOW_UTC)
