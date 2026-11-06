import pytest

from app.money import (
    apply_bps,
    decimal_string_to_cents,
    format_usd,
    offer_problems,
    quote_founding,
    quote_referral,
    round_half_up_div,
)


def test_contract_example() -> None:
    q = quote_referral(10000, 1, 2000, 2500, 800)
    assert q.discount_cents == 2000
    assert q.amount_cents == 8000
    assert q.platform_fee_cents == 640
    assert q.commission_cents == 2000


@pytest.mark.parametrize(
    ("num", "den", "expected"),
    [(5, 10, 1), (4, 10, 0), (15, 10, 2), (25, 10, 3), (14999, 10000, 1), (15000, 10000, 2), (0, 7, 0)],
)
def test_round_half_up(num: int, den: int, expected: int) -> None:
    assert round_half_up_div(num, den) == expected


def test_apply_bps_half_up_edges() -> None:
    assert apply_bps(125, 2000) == 25  # exact
    assert apply_bps(1, 5000) == 1  # 0.5 -> 1
    assert apply_bps(3, 5000) == 2  # 1.5 -> 2
    assert apply_bps(999, 800) == 80  # 79.92 -> 80
    assert apply_bps(1006, 2500) == 252  # 251.5 -> 252


def test_founding_quote_has_no_commission() -> None:
    q = quote_founding(4900, 800)
    assert (q.amount_cents, q.platform_fee_cents, q.commission_cents, q.discount_cents) == (4900, 392, 0, 0)


def test_offer_problems_validates_ranges() -> None:
    assert offer_problems(4900, 10000, 1, 2000, 2500, 800) == []
    assert offer_problems(4900, 99, 1, 2000, 2500, 800)  # price below minimum
    assert offer_problems(4900, 10000, 1, 5001, 2500, 800)  # discount above 50%
    assert offer_problems(4900, 10000, 1, 2000, 6000, 800)  # commission above 50%
    assert offer_problems(4900, 1200, 0, 2000, 2500, 800)  # no prepaid months
    assert offer_problems(4900, 1200, 37, 2000, 2500, 800)  # more than 3 years
    assert offer_problems(4900, 100_000, 12, 2000, 2500, 800)  # $12,000 prepaid is above the cap


def test_referral_quote_prepays_months_of_the_monthly_price() -> None:
    q = quote_referral(1200, 12, 2000, 2500, 800)
    assert (q.list_price_cents, q.discount_cents, q.amount_cents) == (14400, 2880, 11520)
    assert (q.commission_cents, q.platform_fee_cents) == (2880, 922)


def test_formatting_roundtrip() -> None:
    assert format_usd(123456) == "$1,234.56"
    assert decimal_string_to_cents("80.00") == 8000
    assert decimal_string_to_cents("0.5") == 50
