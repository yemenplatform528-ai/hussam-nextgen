from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

def money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def require_nonnegative(value: Decimal) -> Decimal:
    value = money(value)
    if value < 0:
        raise ValueError("money must be non-negative")
    return value
