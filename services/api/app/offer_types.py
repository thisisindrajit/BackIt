"""What a backer gets for their money. The price is separate; this is the reward."""

OFFER_TYPES = ("lifetime", "access_period", "discount", "voucher", "custom")

# (min, max) for offer_value, or None when the type takes no value.
_VALUE_RANGE: dict[str, tuple[int, int] | None] = {
    "lifetime": None,
    "access_period": (1, 120),  # months
    "discount": (1, 100),  # percent off
    "voucher": (100, 1_000_000),  # credit in cents
    "custom": None,
}


def offer_value_problem(offer_type: str, value: int | None) -> str | None:
    rng = _VALUE_RANGE.get(offer_type)
    if offer_type not in _VALUE_RANGE:
        return "Unknown offer type"
    if rng is None:
        return None if value is None else "This offer type doesn’t take a value"
    if value is None:
        return {
            "access_period": "Set how many months of access backers get",
            "discount": "Set the discount percentage",
            "voucher": "Set the voucher amount",
        }[offer_type]
    lo, hi = rng
    if not lo <= value <= hi:
        return {
            "access_period": "Access must be between 1 and 120 months",
            "discount": "Discount must be between 1% and 100%",
            "voucher": "Voucher must be between $1 and $10,000",
        }[offer_type]
    return None


def _months(n: int) -> str:
    if n % 12 == 0:
        years = n // 12
        return f"{years} year" if years == 1 else f"{years} years"
    return f"{n} month" if n == 1 else f"{n} months"


def offer_label(offer_type: str, value: int | None) -> str:
    if offer_type == "access_period" and value:
        return f"{_months(value)} of access"
    if offer_type == "discount" and value:
        return f"{value}% off for life"
    if offer_type == "voucher" and value:
        return f"${value / 100:,.2f}".replace(".00", "") + " voucher"
    if offer_type == "custom":
        return "Founding offer"
    return "Lifetime deal"
