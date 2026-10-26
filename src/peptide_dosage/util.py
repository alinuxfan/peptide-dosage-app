"""Small pure helpers shared by the UI layer.

Nothing here imports toga, so everything is unit-testable on any platform.

Timestamps: the database stores dose times as naive UTC strings
("%Y-%m-%d %H:%M:%S"), but people think and type in local time. The helpers
below convert between the two. Each takes an optional `tz` (a tzinfo) that
defaults to the system's local timezone; tests pass a fixed-offset timezone so
they don't depend on the machine they run on.
"""

from datetime import datetime, timezone, tzinfo

from . import calc

DB_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
INPUT_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"


def num(value, default: float = 0.0) -> float:
    """toga.NumberInput.value is a decimal.Decimal (or None), but calc.py's
    math and SQLite's parameter binding both expect float."""
    return float(value) if value is not None else default


def utc_now_naive() -> datetime:
    """Current UTC time as a naive datetime (the frame the DB uses)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_db_timestamp(utc_str: str) -> datetime | None:
    try:
        return datetime.strptime((utc_str or "").strip(), DB_TIMESTAMP_FORMAT)
    except ValueError:
        return None


def _utc_naive_to_local_naive(utc_dt: datetime, tz: tzinfo | None = None) -> datetime:
    """Naive UTC -> naive wall-clock time in `tz` (system local when None)."""
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz).replace(tzinfo=None)


def local_now_naive(tz: tzinfo | None = None, now_utc: datetime | None = None) -> datetime:
    """Current wall-clock time in `tz` as a naive datetime."""
    return _utc_naive_to_local_naive(now_utc or utc_now_naive(), tz)


def local_input_to_utc(text: str, tz: tzinfo | None = None, now_utc: datetime | None = None) -> str | None:
    """Convert a user-typed LOCAL dose time into a naive-UTC DB string.

    Blank (or "now") returns None, meaning "use the current time". Raises
    ValueError for malformed input or a time in the future (judged in local
    time, per calc.parse_dose_timestamp).
    """
    parsed_local = calc.parse_dose_timestamp(text, local_now_naive(tz, now_utc))
    if parsed_local is None:
        return None
    local_dt = datetime.strptime(parsed_local, DB_TIMESTAMP_FORMAT)
    try:
        # Attach the zone (astimezone(None) on a naive value assumes system local).
        aware = local_dt.replace(tzinfo=tz) if tz is not None else local_dt.astimezone()
        return aware.astimezone(timezone.utc).strftime(DB_TIMESTAMP_FORMAT)
    except (OSError, OverflowError):
        # e.g. pre-1970 dates on Windows, or year 0001 at a UTC offset
        raise ValueError("That date is out of range.") from None


def utc_to_local_input(utc_str: str, tz: tzinfo | None = None) -> str:
    """Naive-UTC DB string -> "YYYY-MM-DD HH:MM" local, for pre-filling the
    log-dose field. Unparseable input is returned unchanged."""
    utc_dt = _parse_db_timestamp(utc_str)
    if utc_dt is None:
        return utc_str or ""
    return _utc_naive_to_local_naive(utc_dt, tz).strftime(INPUT_TIMESTAMP_FORMAT)


def utc_to_local_display(utc_str: str, tz: tzinfo | None = None, now_utc: datetime | None = None) -> str:
    """Naive-UTC DB string -> short local label, e.g. "Oct 26, 14:30".

    The year is appended when it isn't the current local year. Unparseable
    input is returned unchanged.
    """
    utc_dt = _parse_db_timestamp(utc_str)
    if utc_dt is None:
        return utc_str or ""
    local = _utc_naive_to_local_naive(utc_dt, tz)
    label = f"{local:%b} {local.day}"
    if local.year != local_now_naive(tz, now_utc).year:
        label += f" {local.year}"
    return f"{label}, {local:%H:%M}"
