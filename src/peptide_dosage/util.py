def num(value, default: float = 0.0) -> float:
    """toga.NumberInput.value is a decimal.Decimal (or None), but calc.py's
    math and SQLite's parameter binding both expect float."""
    return float(value) if value is not None else default
