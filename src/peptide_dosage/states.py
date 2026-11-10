"""Explicit Domain State Machines for the Peptide Dosage App.

Elevates:
- Developer Experience (DX): Strongly-typed enums and immutable dataclasses
  replace fragmented boolean conditions, regex heuristics, and stringly-typed
  status checks.
- Agent Experience (AX): Deterministic, fully-introspectable states and
  transitions allow AI agents to observe, reason about, and modify domain states
  without error-prone text/emoji parsing.
- User Experience (UX): Unified status badges, colors, and consistent safety
  cues across all screens and widgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import enum
import math

# Standard color palette matching the app's visual theme
COLOR_OK = "#2e7d32"        # Forest green
COLOR_WARN = "#f9a825"      # Amber / warning
COLOR_WARN_TEXT = "#2a2100" # Dark text for amber badges
COLOR_DUE = "#e65100"       # Deep orange for due soon
COLOR_ERROR = "#c62828"     # Ruby red for expired / overdue / danger
COLOR_MUTED = "#b8c4ce"     # Soft slate for neutral info
COLOR_LIGHT_TEXT = "#e8f5e9"
COLOR_ERROR_TEXT = "#ffebee"


# ============================================================================
# 1. Vial Lifecycle & Beyond-Use-Date (BUD) State Machine
# ============================================================================

class BudState(enum.Enum):
    """Lifecycle state of a reconstituted peptide vial."""
    UNRECONSTITUTED = "unreconstituted"
    FRESH = "fresh"
    EXPIRING_SOON = "expiring_soon"
    EXPIRES_TODAY = "expires_today"
    EXPIRED_TODAY = "expired_today"
    EXPIRED = "expired"


@dataclass(frozen=True)
class BudStatusInfo:
    state: BudState
    label: str
    days_remaining: float | None
    is_reconstituted: bool
    is_expired: bool
    is_warning: bool
    pill_bg_color: str
    pill_text_color: str
    bud_exceeded_by_duration: bool = False


def evaluate_bud_state(
    expiry_at: datetime | None,
    now: datetime,
    total_doses: float = 0.0,
    weekly_expected: float | None = None,
    bud_days: float = 28.0,
) -> BudStatusInfo:
    """Evaluate the current BUD lifecycle state from an expiry datetime."""
    exceeded_by_duration = False
    if weekly_expected and weekly_expected > 0 and total_doses > 0 and bud_days > 0:
        usable_days = total_doses / (weekly_expected / 7.0)
        exceeded_by_duration = usable_days > bud_days

    if expiry_at is None:
        return BudStatusInfo(
            state=BudState.UNRECONSTITUTED,
            label="Not reconstituted",
            days_remaining=None,
            is_reconstituted=False,
            is_expired=False,
            is_warning=True,
            pill_bg_color=COLOR_WARN,
            pill_text_color=COLOR_WARN_TEXT,
            bud_exceeded_by_duration=exceeded_by_duration,
        )

    delta_days = (expiry_at - now).total_seconds() / 86400.0

    if delta_days < 0:
        expired_days = abs(delta_days)
        label = "❌ Expired today" if expired_days < 1 else f"❌ Expired {expired_days:.0f}d ago"
        state = BudState.EXPIRED_TODAY if expired_days < 1 else BudState.EXPIRED
        return BudStatusInfo(
            state=state,
            label=label,
            days_remaining=delta_days,
            is_reconstituted=True,
            is_expired=True,
            is_warning=True,
            pill_bg_color=COLOR_ERROR,
            pill_text_color=COLOR_ERROR_TEXT,
            bud_exceeded_by_duration=exceeded_by_duration,
        )

    if delta_days < 1:
        return BudStatusInfo(
            state=BudState.EXPIRES_TODAY,
            label="⚠️ Expires today",
            days_remaining=delta_days,
            is_reconstituted=True,
            is_expired=False,
            is_warning=True,
            pill_bg_color=COLOR_WARN,
            pill_text_color=COLOR_WARN_TEXT,
            bud_exceeded_by_duration=exceeded_by_duration,
        )

    if delta_days <= 5:
        return BudStatusInfo(
            state=BudState.EXPIRING_SOON,
            label=f"⚠️ Expires in {delta_days:.0f}d",
            days_remaining=delta_days,
            is_reconstituted=True,
            is_expired=False,
            is_warning=True,
            pill_bg_color=COLOR_WARN,
            pill_text_color=COLOR_WARN_TEXT,
            bud_exceeded_by_duration=exceeded_by_duration,
        )

    return BudStatusInfo(
        state=BudState.FRESH,
        label=f"✓ Fresh ({delta_days:.0f}d left)",
        days_remaining=delta_days,
        is_reconstituted=True,
        is_expired=False,
        is_warning=False,
        pill_bg_color=COLOR_OK,
        pill_text_color=COLOR_LIGHT_TEXT,
        bud_exceeded_by_duration=exceeded_by_duration,
    )


# ============================================================================
# 2. Vial Doses Inventory & Reorder State Machine
# ============================================================================

class VialInventoryState(enum.Enum):
    """Inventory supply status for remaining doses in current vial."""
    NO_DATA = "no_data"
    EMPTY = "empty"
    LOW_REORDER = "low_reorder"
    PLENTIFUL = "plentiful"


@dataclass(frozen=True)
class VialInventoryInfo:
    state: VialInventoryState
    label: str
    remaining: float
    total: float
    is_empty: bool
    is_low: bool
    pill_bg_color: str
    pill_text_color: str


def evaluate_doses_remaining(remaining: float, total: float) -> VialInventoryInfo:
    """Evaluate inventory level and reorder urgency for a vial."""
    if total <= 0:
        return VialInventoryInfo(
            state=VialInventoryState.NO_DATA,
            label="N/A",
            remaining=0.0,
            total=0.0,
            is_empty=True,
            is_low=False,
            pill_bg_color=COLOR_MUTED,
            pill_text_color=COLOR_LIGHT_TEXT,
        )
    if remaining <= 0:
        return VialInventoryInfo(
            state=VialInventoryState.EMPTY,
            label="❌ Empty - reorder",
            remaining=0.0,
            total=total,
            is_empty=True,
            is_low=True,
            pill_bg_color=COLOR_ERROR,
            pill_text_color=COLOR_ERROR_TEXT,
        )
    if remaining <= 2:
        return VialInventoryInfo(
            state=VialInventoryState.LOW_REORDER,
            label=f"⚠️ {remaining:.1f} left - reorder",
            remaining=remaining,
            total=total,
            is_empty=False,
            is_low=True,
            pill_bg_color=COLOR_WARN,
            pill_text_color=COLOR_WARN_TEXT,
        )
    return VialInventoryInfo(
        state=VialInventoryState.PLENTIFUL,
        label=f"{remaining:.1f} / {total:.1f} left",
        remaining=remaining,
        total=total,
        is_empty=False,
        is_low=False,
        pill_bg_color=COLOR_OK,
        pill_text_color=COLOR_LIGHT_TEXT,
    )


# ============================================================================
# 3. Dose Due & Schedule State Machine
# ============================================================================

class DoseDueState(enum.Enum):
    """Due status for the next scheduled dose."""
    UPCOMING = "upcoming"
    DUE_TODAY = "due_today"
    OVERDUE_TODAY = "overdue_today"
    OVERDUE = "overdue"
    UNSCHEDULED = "unscheduled"


@dataclass(frozen=True)
class DoseDueInfo:
    state: DoseDueState
    label: str
    due_at: datetime | None
    days_diff: float | None
    is_overdue: bool
    is_due_today: bool
    pill_bg_color: str
    pill_text_color: str


def evaluate_dose_due(due_at: datetime | None, now: datetime) -> DoseDueInfo:
    """Evaluate due status relative to wall clock time."""
    if due_at is None:
        return DoseDueInfo(
            state=DoseDueState.UNSCHEDULED,
            label="N/A",
            due_at=None,
            days_diff=None,
            is_overdue=False,
            is_due_today=False,
            pill_bg_color=COLOR_MUTED,
            pill_text_color=COLOR_LIGHT_TEXT,
        )

    delta_days = (due_at - now).total_seconds() / 86400.0

    if delta_days < 0:
        overdue_days = abs(delta_days)
        label = "Overdue (today)" if overdue_days < 1 else f"Overdue {overdue_days:.0f}d"
        state = DoseDueState.OVERDUE_TODAY if overdue_days < 1 else DoseDueState.OVERDUE
        return DoseDueInfo(
            state=state,
            label=label,
            due_at=due_at,
            days_diff=delta_days,
            is_overdue=True,
            is_due_today=False,
            pill_bg_color=COLOR_ERROR,
            pill_text_color=COLOR_ERROR_TEXT,
        )

    label = "Due today" if delta_days < 1 else f"Due in {delta_days:.0f}d"
    state = DoseDueState.DUE_TODAY if delta_days < 1 else DoseDueState.UPCOMING
    pill_color = COLOR_WARN if delta_days < 1 else COLOR_OK
    pill_text = COLOR_WARN_TEXT if delta_days < 1 else COLOR_LIGHT_TEXT

    return DoseDueInfo(
        state=state,
        label=label,
        due_at=due_at,
        days_diff=delta_days,
        is_overdue=False,
        is_due_today=(delta_days < 1),
        pill_bg_color=pill_color,
        pill_text_color=pill_text,
    )


# ============================================================================
# 4. Protocol Dose Adherence State Machine
# ============================================================================

class AdherenceState(enum.Enum):
    """Adherence measurement status."""
    MEASURABLE = "measurable"
    TOO_NEW = "too_new"
    UNRECOGNIZED_FREQUENCY = "unrecognized_frequency"
    NO_SCHEDULE = "no_schedule"


@dataclass(frozen=True)
class AdherenceStatusInfo:
    state: AdherenceState
    label: str
    percentage: float | None
    is_measurable: bool


def evaluate_adherence_label(
    adherence_pct: float | None,
    weekly_expected: float | None,
    days_elapsed: float,
) -> AdherenceStatusInfo:
    """Evaluate adherence status from computed percentage or unmeasurable conditions."""
    if adherence_pct is not None:
        return AdherenceStatusInfo(
            state=AdherenceState.MEASURABLE,
            label=f"{adherence_pct:.0f}%",
            percentage=adherence_pct,
            is_measurable=True,
        )
    if weekly_expected is None or weekly_expected <= 0:
        return AdherenceStatusInfo(
            state=AdherenceState.UNRECOGNIZED_FREQUENCY,
            label="Freq. not recognized",
            percentage=None,
            is_measurable=False,
        )
    if days_elapsed < 1.0:
        return AdherenceStatusInfo(
            state=AdherenceState.TOO_NEW,
            label="Too new",
            percentage=None,
            is_measurable=False,
        )
    return AdherenceStatusInfo(
        state=AdherenceState.NO_SCHEDULE,
        label="N/A",
        percentage=None,
        is_measurable=False,
    )


# ============================================================================
# 5. Syringe Draw & Volumetric Safety State Machine
# ============================================================================

class SyringeDrawState(enum.Enum):
    """Draw safety and capacity status for insulin syringes."""
    EMPTY = "empty"
    NORMAL = "normal"
    EXCEEDS_CAPACITY_UPGRADE_AVAILABLE = "exceeds_capacity_upgrade_available"
    EXCEEDS_CAPACITY_MULTI_DRAW = "exceeds_capacity_multi_draw"
    INVALID = "invalid"


@dataclass(frozen=True)
class SyringeDrawInfo:
    state: SyringeDrawState
    units: float
    capacity: float
    draw_label: str
    status_label: str
    is_over_capacity: bool
    upgrade_suggested: bool
    full_syringes: int
    remainder_units: float
    color_hex: str


def evaluate_syringe_draw(units: float, max_capacity: float = 100.0) -> SyringeDrawInfo:
    """Evaluate syringe draw status, multi-draw splits, and capacity recommendations."""
    if units <= 0:
        return SyringeDrawInfo(
            state=SyringeDrawState.EMPTY,
            units=0.0,
            capacity=max_capacity,
            draw_label="0.0 Units",
            status_label="—",
            is_over_capacity=False,
            upgrade_suggested=False,
            full_syringes=0,
            remainder_units=0.0,
            color_hex=COLOR_OK,
        )
    if max_capacity <= 0:
        return SyringeDrawInfo(
            state=SyringeDrawState.INVALID,
            units=units,
            capacity=max_capacity,
            draw_label=f"{units:.1f} Units",
            status_label="—",
            is_over_capacity=False,
            upgrade_suggested=False,
            full_syringes=0,
            remainder_units=0.0,
            color_hex=COLOR_OK,
        )

    cap = f"{max_capacity:g}U"
    if units <= max_capacity:
        return SyringeDrawInfo(
            state=SyringeDrawState.NORMAL,
            units=units,
            capacity=max_capacity,
            draw_label=f"{units:.1f} Units",
            status_label=f"✓ Normal draw ({units:.1f}U / {cap})",
            is_over_capacity=False,
            upgrade_suggested=False,
            full_syringes=1 if units == max_capacity else 0,
            remainder_units=units,
            color_hex=COLOR_OK,
        )

    rounded = round(units, 6)  # avoid float noise just below an exact multiple
    draws = int(rounded // max_capacity)
    remainder = rounded % max_capacity
    if remainder > 0.05:
        draw_desc = f"{draws}x {cap} + 1x {remainder:.1f}U"
        rem_val = round(remainder, 1)
    else:
        draw_desc = f"{draws}x {cap}"
        rem_val = 0.0

    can_upgrade = (units <= 100.0 and max_capacity < 100.0)
    state = (
        SyringeDrawState.EXCEEDS_CAPACITY_UPGRADE_AVAILABLE
        if can_upgrade
        else SyringeDrawState.EXCEEDS_CAPACITY_MULTI_DRAW
    )

    return SyringeDrawInfo(
        state=state,
        units=units,
        capacity=max_capacity,
        draw_label=f"⚠️ {units:.1f} Units",
        status_label=f"⚠️ Exceeds {cap} ({draw_desc})",
        is_over_capacity=True,
        upgrade_suggested=can_upgrade,
        full_syringes=draws,
        remainder_units=rem_val,
        color_hex=COLOR_ERROR,
    )


# ============================================================================
# 6. Calculator Input & Validation State Machine
# ============================================================================

MAX_VIAL_MG = 10_000.0
MAX_WATER_ML = 1_000.0
MAX_DOSE_MG = 10_000.0


class CalcInputState(enum.Enum):
    """Input evaluation state for reconstitution calculator."""
    VALID = "valid"
    BLANK_INPUT = "blank_input"
    NON_FINITE = "non_finite"
    NON_POSITIVE = "non_positive"
    EXCEEDS_MAX_VIAL = "exceeds_max_vial"
    EXCEEDS_MAX_WATER = "exceeds_max_water"
    EXCEEDS_MAX_DOSE = "exceeds_max_dose"


@dataclass(frozen=True)
class CalcValidationInfo:
    state: CalcInputState
    is_valid: bool
    is_blank: bool
    error_message: str | None


def evaluate_calc_inputs(
    vial_mg: float,
    water_ml: float,
    dose: float,
    unit: str,
) -> CalcValidationInfo:
    """Evaluate calculator inputs and identify specific error states."""
    for label, val in (("Vial size", vial_mg), ("BAC water", water_ml), ("Dose", dose)):
        if not math.isfinite(val):
            return CalcValidationInfo(
                state=CalcInputState.NON_FINITE,
                is_valid=False,
                is_blank=False,
                error_message=f"{label} must be a real number.",
            )
        if val <= 0:
            return CalcValidationInfo(
                state=CalcInputState.NON_POSITIVE,
                is_valid=False,
                is_blank=False,
                error_message="Enter positive numbers...",
            )

    if vial_mg > MAX_VIAL_MG:
        return CalcValidationInfo(
            state=CalcInputState.EXCEEDS_MAX_VIAL,
            is_valid=False,
            is_blank=False,
            error_message=f"Vial size must be {MAX_VIAL_MG:,.0f} mg or less.",
        )
    if water_ml > MAX_WATER_ML:
        return CalcValidationInfo(
            state=CalcInputState.EXCEEDS_MAX_WATER,
            is_valid=False,
            is_blank=False,
            error_message=f"BAC water must be {MAX_WATER_ML:,.0f} mL or less.",
        )

    dose_mg = dose if unit == "mg" else (dose / 1000.0 if unit == "mcg" else dose)
    if dose_mg > MAX_DOSE_MG:
        return CalcValidationInfo(
            state=CalcInputState.EXCEEDS_MAX_DOSE,
            is_valid=False,
            is_blank=False,
            error_message=f"Dose must be {MAX_DOSE_MG:,.0f} mg or less.",
        )

    return CalcValidationInfo(
        state=CalcInputState.VALID,
        is_valid=True,
        is_blank=False,
        error_message=None,
    )


# ============================================================================
# 7. Titration Schedule & Phase Progression State Machine
# ============================================================================

class TitrationPhaseState(enum.Enum):
    """Progression state of a protocol titration ramp."""
    FIXED_DOSE = "fixed_dose"
    ACTIVE_RAMP = "active_ramp"
    MAINTENANCE = "maintenance"
    COURSE_COMPLETED = "course_completed"


@dataclass(frozen=True)
class TitrationPhaseInfo:
    state: TitrationPhaseState
    active_phase_label: str
    dose: float
    unit: str
    dose_mg: float
    phase_index: int
    total_phases: int
    is_maintenance: bool
    is_completed: bool


# ============================================================================
# 8. Literature Async Fetch & Tracking State Machine
# ============================================================================

class LiteratureTrackingState(enum.Enum):
    """State of an article being tracked from NCBI PubMed."""
    IDLE = "idle"
    FETCHING = "fetching"
    TRACKED = "tracked"
    FAILED = "failed"


@dataclass(frozen=True)
class LiteratureTrackingInfo:
    state: LiteratureTrackingState
    display_text: str
    button_label: str
    button_enabled: bool
    is_in_flight: bool
    error: str | None = None


# ============================================================================
# 9. Navigation Stack State Machine
# ============================================================================

class NavStackState(enum.Enum):
    """State of a navigation controller stack."""
    EMPTY = "empty"
    ROOT = "root"
    PUSHED = "pushed"
