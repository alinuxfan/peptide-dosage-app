import math
import re
from datetime import datetime, timedelta

# Pure dosing-math and adherence-heuristic functions shared by main.py (live UI)
# and db.py (file export), so the formula only lives in one place.


def concentration_mg_ml(vial_mg: float, water_ml: float) -> float:
    if water_ml <= 0:
        return 0.0
    return vial_mg / water_ml


def dose_to_mg(dose: float, unit: str) -> float:
    return dose / 1000.0 if unit == "mcg" else dose


def draw_volume_ml(dose_mg: float, conc_mg_ml: float) -> float:
    if conc_mg_ml <= 0:
        return 0.0
    return dose_mg / conc_mg_ml


def syringe_units(volume_ml: float) -> float:
    return volume_ml * 100.0


def doses_per_vial(vial_mg: float, dose_mg: float) -> float:
    if dose_mg <= 0:
        return 0.0
    return vial_mg / dose_mg


_RANGE_X_WEEKLY_RE = re.compile(r"(\d+)\s*-\s*(\d+)\s*x", re.IGNORECASE)
_X_WEEKLY_RE = re.compile(r"(\d+)\s*x", re.IGNORECASE)


def parse_weekly_frequency(freq: str) -> float | None:
    """Best-effort parse of a free-text frequency string into expected doses/week.

    Frequency strings are free text (e.g. "daily (at bedtime)", "3x weekly"),
    so this is a heuristic, not an exact parser -- unrecognized phrasing
    returns None rather than guessing.
    """
    if not freq:
        return None
    text = freq.strip().lower()

    # Per-day range: e.g. '1-3x/day', '1-3x daily', '1-3 times daily'
    day_range = re.search(r"(\d+)\s*-\s*(\d+)\s*(?:x|times)?\s*(?:/|\s*per\s*|\s*a\s*)?(?:day|daily)", text)
    if day_range:
        low, high = int(day_range.group(1)), int(day_range.group(2))
        return ((low + high) / 2.0) * 7.0

    # Per-day exact: e.g. '2x/day', '2x daily', '3 times a day'
    day_exact = re.search(r"(\d+)\s*(?:x|times)?\s*(?:/|\s*per\s*|\s*a\s*)?(?:day|daily)", text)
    if day_exact and not re.search(r"(?:every\s+other\s+day|\beod\b)", text):
        return float(day_exact.group(1)) * 7.0

    if "twice daily" in text or "2x daily" in text or "split am/pm" in text or re.search(r"\bbid\b", text):
        return 14.0
    if "three times daily" in text or "thrice daily" in text or re.search(r"\btid\b", text):
        return 21.0

    if "every other day" in text or re.search(r"\beod\b", text) or re.search(r"\bqod\b", text):
        return 3.5

    if "every other week" in text or "every 2 weeks" in text or re.search(r"\bq2w\b", text):
        return 0.5

    # Check range first so '2-3x weekly' is not matched as '3x weekly'
    range_match = _RANGE_X_WEEKLY_RE.search(text)
    if range_match:
        low, high = int(range_match.group(1)), int(range_match.group(2))
        return (low + high) / 2.0

    if re.search(r"\b(?:twice|2x|2 times)\s*weekly\b", text) or text == "twice weekly":
        return 2.0
    if re.search(r"\b(?:three times|thrice|3x|3 times)\s*weekly\b", text):
        return 3.0
    if re.search(r"\b(?:four times|4x|4 times)\s*weekly\b", text):
        return 4.0

    x_match = _X_WEEKLY_RE.search(text)
    if x_match:
        return float(x_match.group(1))

    if "daily" in text or "nightly" in text:
        return 7.0

    if "weekly" in text:
        return 1.0

    return None


def adherence_percent(logged_count: int, weekly_expected: float | None, days_elapsed: float) -> float | None:
    """Percentage of expected doses actually logged, capped at 100.

    Returns None when adherence can't be meaningfully measured: the
    frequency couldn't be parsed, or the protocol is too new (<1 day old).
    """
    if weekly_expected is None or weekly_expected <= 0:
        return None
    if days_elapsed < 1:
        return None

    expected_count = weekly_expected * (days_elapsed / 7.0)
    if expected_count <= 0:
        return None

    return min(100.0, (logged_count / expected_count) * 100.0)


def next_dose_due_at(
    weekly_expected: float | None,
    last_taken_at: datetime | None,
    fallback_at: datetime | None,
) -> datetime | None:
    """When the next dose is due, given an expected weekly dose count.

    Anchors off the most recently logged dose if there is one, otherwise
    off `fallback_at` (typically the protocol's created_at) so a
    never-logged protocol still reports a due date instead of nothing.
    Returns None when frequency couldn't be parsed into a weekly count.
    """
    if weekly_expected is None or weekly_expected <= 0:
        return None
    anchor = last_taken_at or fallback_at
    if anchor is None:
        return None

    interval_days = 7.0 / weekly_expected
    return anchor + timedelta(days=interval_days)


def format_due_label(next_due_at: datetime | None, now: datetime) -> str:
    """Human-readable label for a next_dose_due_at value relative to `now`."""
    if next_due_at is None:
        return "N/A"

    delta_days = (next_due_at - now).total_seconds() / 86400.0
    if delta_days < 0:
        overdue_days = abs(delta_days)
        return "Overdue (today)" if overdue_days < 1 else f"Overdue {overdue_days:.0f}d"

    return "Due today" if delta_days < 1 else f"Due in {delta_days:.0f}d"


def format_vial_duration(doses_per_vial: float, weekly_expected: float | None, freq_text: str = "") -> str:
    """Format an estimated time duration a vial will last based on doses and frequency."""
    if doses_per_vial <= 0:
        return "0 doses"
    if weekly_expected is None or weekly_expected <= 0:
        return f"{doses_per_vial:.1f} doses"

    total_days = doses_per_vial / (weekly_expected / 7.0)
    total_weeks = doses_per_vial / weekly_expected

    if total_days <= 14:
        return f"~{total_days:.1f} days"
    elif total_weeks <= 8:
        return f"~{total_weeks:.1f} wks (~{total_days:.0f} days)"
    else:
        months = total_days / 30.4375
        return f"~{months:.1f} mos ({total_weeks:.1f} wks)"


def syringe_draw_status(units: float, max_capacity: float = 100.0) -> tuple[str, str]:
    """Return a short draw string and safety status for a U-100 syringe draw.

    Returns (draw_label, safety_status).
    e.g. ("80.0 Units", "✓ Normal draw (80.0U / 100U)")
    or ("⚠️ 160.0 Units", "⚠️ Exceeds 100U (requires 2 draws: 100U + 60.0U)")
    """
    if units <= 0:
        return "0.0 Units", "—"
    if units <= max_capacity:
        return f"{units:.1f} Units", f"✓ Normal draw ({units:.1f}U / 100U)"

    draws = int(units // max_capacity)
    remainder = units % max_capacity
    if remainder > 0.05:
        draw_desc = f"{draws}x 100U + 1x {remainder:.1f}U"
    else:
        draw_desc = f"{draws}x 100U"
    return f"⚠️ {units:.1f} Units", f"⚠️ Exceeds 100U ({draw_desc})"


def generate_titration_schedule(
    start_dose: float,
    target_dose: float,
    step_increment: float,
    weeks_per_step: float,
    unit: str,
    max_steps: int = 26,
) -> list[tuple[str, float, str]]:
    """Build a linear titration ramp from start_dose to target_dose.

    Returns (phase_label, dose, unit) tuples, the same shape already used by
    DEFAULT_PEPTIDES["schedule"] / user_protocols.schedule_json, so callers
    can drop the result straight into existing rendering/export code.

    Steps up (or down, if target_dose < start_dose) by step_increment every
    weeks_per_step weeks, then appends a final maintenance step pinned at
    target_dose. max_steps caps runaway schedules from a too-small increment.
    """
    if start_dose <= 0 or target_dose <= 0:
        raise ValueError("Start and target dose must be greater than 0.")
    if weeks_per_step <= 0:
        raise ValueError("Weeks per step must be greater than 0.")

    if start_dose == target_dose:
        return [("Maintenance Dose", round(target_dose, 2), unit)]

    if step_increment <= 0:
        raise ValueError("Step increment must be greater than 0.")

    direction = 1 if target_dose > start_dose else -1
    dose = start_dose
    week_start = 1
    schedule: list[tuple[str, float, str]] = []

    for _ in range(max_steps):
        week_end = week_start + weeks_per_step - 1
        label = f"Week {week_start:.0f}-{week_end:.0f}"
        next_dose = dose + step_increment * direction

        reached_target = (
            (direction == 1 and next_dose >= target_dose)
            or (direction == -1 and next_dose <= target_dose)
        )
        if reached_target:
            schedule.append((label, round(dose, 2), unit))
            schedule.append((f"Week {week_end + 1:.0f}+ (Maintenance)", round(target_dose, 2), unit))
            return schedule

        schedule.append((label, round(dose, 2), unit))
        dose = next_dose
        week_start = week_end + 1

    # Safety cap reached without converging -- pin the final step at target anyway.
    schedule.append((f"Week {week_start:.0f}+ (Maintenance)", round(target_dose, 2), unit))
    return schedule


def split_vial_aliquots(vial_mg: float, water_ml: float, num_splits: int) -> dict:
    """Divide one reconstituted vial evenly into `num_splits` storage aliquots.

    Splitting a homogeneous reconstituted solution doesn't change
    concentration or per-dose draw volume -- it only divides the total mg
    and volume across containers.
    """
    if num_splits < 1:
        raise ValueError("Number of aliquots must be at least 1.")
    if vial_mg <= 0 or water_ml <= 0:
        raise ValueError("Vial mg and water mL must be greater than 0.")

    return {
        "aliquot_mg": vial_mg / num_splits,
        "aliquot_ml": water_ml / num_splits,
        "concentration_mg_ml": concentration_mg_ml(vial_mg, water_ml),
    }



# Reconstituted peptide in bacteriostatic water is generally considered stable
# for ~28 days refrigerated; past that the solution is beyond-use regardless of
# how many doses are left in the vial.
DEFAULT_BUD_DAYS = 28


def bud_expiry_at(reconstituted_at: datetime | None, bud_days: float = DEFAULT_BUD_DAYS) -> datetime | None:
    """Beyond-use date for a reconstituted vial, or None if not yet reconstituted."""
    if reconstituted_at is None or bud_days <= 0:
        return None
    return reconstituted_at + timedelta(days=bud_days)


def format_bud_label(expiry_at: datetime | None, now: datetime) -> str:
    """Human-readable beyond-use-date status for a reconstituted vial."""
    if expiry_at is None:
        return "Not reconstituted"

    delta_days = (expiry_at - now).total_seconds() / 86400.0
    if delta_days < 0:
        expired_days = abs(delta_days)
        return "❌ Expired today" if expired_days < 1 else f"❌ Expired {expired_days:.0f}d ago"
    if delta_days < 1:
        return "⚠️ Expires today"
    if delta_days <= 5:
        return f"⚠️ Expires in {delta_days:.0f}d"
    return f"✓ Fresh ({delta_days:.0f}d left)"


def bud_exceeded_by_duration(
    doses_per_vial: float,
    weekly_expected: float | None,
    bud_days: float = DEFAULT_BUD_DAYS,
) -> bool:
    """True when a vial holds more doses than can be used before it expires.

    Flags the misleading case where "est. vial duration" spans months but the
    reconstituted solution is only good for bud_days.
    """
    if weekly_expected is None or weekly_expected <= 0 or doses_per_vial <= 0 or bud_days <= 0:
        return False
    usable_days = doses_per_vial / (weekly_expected / 7.0)
    return usable_days > bud_days


def adherence_label(
    adherence_pct: float | None,
    weekly_expected: float | None,
    days_elapsed: float,
) -> str:
    """Distinguish *why* adherence is unmeasurable instead of showing a bare N/A.

    A brand-new protocol and an unparseable frequency both yield
    adherence_pct=None but mean very different things to the user.
    """
    if adherence_pct is not None:
        return f"{adherence_pct:.0f}%"
    if weekly_expected is None or weekly_expected <= 0:
        return "Freq. not recognized"
    if days_elapsed < 1:
        return "Too new"
    return "N/A"


def doses_remaining(doses_per_vial: float, doses_used: int) -> float:
    """Doses left in the current vial, floored at 0."""
    return max(0.0, doses_per_vial - doses_used)


def format_doses_remaining(remaining: float, total: float) -> str:
    """Inventory label for a vial, warning as it runs low."""
    if total <= 0:
        return "N/A"
    if remaining <= 0:
        return "❌ Empty - reorder"
    if remaining <= 2:
        return f"⚠️ {remaining:.1f} left - reorder"
    return f"{remaining:.1f} / {total:.1f} left"


# dose_log timestamps are naive UTC strings (SQLite CURRENT_TIMESTAMP), so
# user-entered dose dates are interpreted in the same frame.
DOSE_TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def parse_dose_timestamp(text: str, now: datetime) -> str | None:
    """Parse a user-entered dose date/time into a dose_log timestamp string.

    Accepts "YYYY-MM-DD HH:MM[:SS]" or "YYYY-MM-DD" (midnight). Blank or "now"
    returns None, meaning "use the current time". Raises ValueError on anything
    else, or on a date in the future (you can't have taken a dose yet).
    """
    cleaned = (text or "").strip()
    if not cleaned or cleaned.lower() == "now":
        return None

    for fmt in DOSE_TIMESTAMP_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError("Use format YYYY-MM-DD or YYYY-MM-DD HH:MM (or blank for now).")

    if parsed > now + timedelta(minutes=5):
        raise ValueError("Dose date can't be in the future.")

    return parsed.strftime("%Y-%m-%d %H:%M:%S")


# Profile names are user-entered and several catalog peptides contain "/"
# (e.g. "CJC-1295 / Ipamorelin Blend", "Custom / Other"), so any name used to
# build an export filename must be flattened first -- an unsanitised "/" turns
# the filename into a path into a directory that doesn't exist.
_UNSAFE_FILENAME_CHARS_RE = re.compile(r"[^a-z0-9._-]+")


def safe_filename_part(name: str, fallback: str = "unnamed") -> str:
    """Flatten an arbitrary name into a single safe filename component.

    Lowercases, collapses runs of unsafe characters (path separators, spaces,
    ':', '*', '+', etc.) into single underscores, and strips leading dots so the
    result can never traverse directories or produce a hidden file.
    """
    cleaned = _UNSAFE_FILENAME_CHARS_RE.sub("_", (name or "").strip().lower())
    cleaned = cleaned.strip("._-")
    return cleaned or fallback


# Sane upper bounds for reconstitution inputs. The seed catalog tops out at a
# 500 mg vial, 10 mL of water and a 50 mg dose, so these leave ample headroom
# while still rejecting values that produce meaningless output (e.g. a 1e99 mg
# vial rendering a 40-digit concentration that overflows the layout).
MAX_VIAL_MG = 10_000.0
MAX_WATER_ML = 1_000.0
MAX_DOSE_MG = 10_000.0


def validate_reconstitution_inputs(
    vial_mg: float,
    water_ml: float,
    dose: float,
    unit: str,
) -> str | None:
    """Return a human-readable problem with the calculator inputs, else None."""
    for label, value in (("Vial size", vial_mg), ("BAC water", water_ml), ("Dose", dose)):
        if not math.isfinite(value):
            return f"{label} must be a real number."
        if value <= 0:
            return "Enter positive numbers..."

    if vial_mg > MAX_VIAL_MG:
        return f"Vial size must be {MAX_VIAL_MG:,.0f} mg or less."
    if water_ml > MAX_WATER_ML:
        return f"BAC water must be {MAX_WATER_ML:,.0f} mL or less."
    if dose_to_mg(dose, unit) > MAX_DOSE_MG:
        return f"Dose must be {MAX_DOSE_MG:,.0f} mg or less."

    return None


def convert_dose(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a dose between mcg and mg (identity for matching/unknown units)."""
    if from_unit == to_unit:
        return value
    if from_unit == "mcg" and to_unit == "mg":
        return value / 1000.0
    if from_unit == "mg" and to_unit == "mcg":
        return value * 1000.0
    return value
