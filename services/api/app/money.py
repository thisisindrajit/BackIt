"""Pure money arithmetic. All amounts are integer cents; rates are basis points."""

from dataclasses import dataclass
from typing import Literal

BPS_DENOMINATOR = 10_000
MIN_PRICE_CENTS = 100
MAX_PRICE_CENTS = 1_000_000
MAX_DISCOUNT_BPS = 5000
MAX_COMMISSION_BPS = 5000


def round_half_up_div(numerator: int, denominator: int) -> int:
    """Integer division rounding halves away from zero, without floats."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if numerator < 0:
        return -round_half_up_div(-numerator, denominator)
    return (2 * numerator + denominator) // (2 * denominator)


def apply_bps(amount_cents: int, bps: int) -> int:
    if amount_cents < 0 or bps < 0:
        raise ValueError("amount and bps must be non-negative")
    return round_half_up_div(amount_cents * bps, BPS_DENOMINATOR)


@dataclass(frozen=True)
class Quote:
    kind: Literal["founding", "referral"]
    list_price_cents: int
    discount_cents: int
    amount_cents: int
    platform_fee_cents: int
    commission_cents: int
    discount_bps: int
    commission_bps: int
    platform_fee_bps: int

    @property
    def seller_proceeds_before_provider_fees_cents(self) -> int:
        return self.amount_cents - self.platform_fee_cents


def quote_founding(price_cents: int, platform_fee_bps: int) -> Quote:
    return Quote(
        kind="founding",
        list_price_cents=price_cents,
        discount_cents=0,
        amount_cents=price_cents,
        platform_fee_cents=apply_bps(price_cents, platform_fee_bps),
        commission_cents=0,
        discount_bps=0,
        commission_bps=0,
        platform_fee_bps=platform_fee_bps,
    )


def quote_referral(
    list_price_cents: int, discount_bps: int, commission_bps: int, platform_fee_bps: int
) -> Quote:
    discount = apply_bps(list_price_cents, discount_bps)
    amount = list_price_cents - discount
    return Quote(
        kind="referral",
        list_price_cents=list_price_cents,
        discount_cents=discount,
        amount_cents=amount,
        platform_fee_cents=apply_bps(amount, platform_fee_bps),
        commission_cents=apply_bps(amount, commission_bps),
        discount_bps=discount_bps,
        commission_bps=commission_bps,
        platform_fee_bps=platform_fee_bps,
    )


def offer_problems(
    founding_price_cents: int,
    referral_list_price_cents: int,
    referral_discount_bps: int,
    commission_bps: int,
    platform_fee_bps: int,
) -> list[str]:
    problems: list[str] = []
    for name, value in (
        ("founding_price_cents", founding_price_cents),
        ("referral_list_price_cents", referral_list_price_cents),
    ):
        if not MIN_PRICE_CENTS <= value <= MAX_PRICE_CENTS:
            problems.append(f"{name} must be between {MIN_PRICE_CENTS} and {MAX_PRICE_CENTS}")
    if not 0 <= referral_discount_bps <= MAX_DISCOUNT_BPS:
        problems.append("referral_discount_bps must be between 0 and 5000")
    if not 0 <= commission_bps <= MAX_COMMISSION_BPS:
        problems.append("commission_bps must be between 0 and 5000")
    if problems:
        return problems
    referral = quote_referral(
        referral_list_price_cents, referral_discount_bps, commission_bps, platform_fee_bps
    )
    if referral.commission_cents + referral.platform_fee_cents >= referral.amount_cents:
        problems.append("commission plus platform fee must be below the discounted referral price")
    founding = quote_founding(founding_price_cents, platform_fee_bps)
    if founding.platform_fee_cents >= founding.amount_cents:
        problems.append("platform fee must be below the founding price")
    return problems


def format_usd(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100:,}.{cents % 100:02d}"


def cents_to_decimal_string(cents: int) -> str:
    if cents < 0:
        raise ValueError("negative amount")
    return f"{cents // 100}.{cents % 100:02d}"


def decimal_string_to_cents(value: str) -> int:
    whole, _, frac = value.strip().partition(".")
    frac = (frac + "00")[:2]
    if not whole.isdigit() or not frac.isdigit():
        raise ValueError(f"invalid amount {value!r}")
    return int(whole) * 100 + int(frac)
