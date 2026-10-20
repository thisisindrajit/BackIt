from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.ids import new_id, utcnow
from app.models import LedgerEntry, RiskFlag

RULE_EXPLANATIONS = {
    "self_referral_email": (
        "The PayPal payer email on this referred purchase matches the referrer's own email. "
        "The commission is blocked until the builder reviews it."
    ),
    "self_referral_payer": (
        "The PayPal payer account on this referred purchase is the same payer account the "
        "referrer used for their own purchase. The commission is blocked pending review."
    ),
    "payout_email_matches_buyer": (
        "The referrer's payout email matches the buyer's email or PayPal payer email, which "
        "suggests the referrer may be paying themselves. The commission is blocked pending review."
    ),
    "capture_amount_mismatch": (
        "PayPal reported a captured amount, currency or payee that differs from the server quote. "
        "Access was not granted; reconcile the capture manually."
    ),
    "late_capture_oversold": (
        "A payment was captured after all founding spots were taken. No badge was issued; "
        "refund or reconcile this order manually."
    ),
    "duplicate_founding_capture": (
        "A second founding payment was captured for a buyer who already holds a founding badge. "
        "Refund the duplicate payment."
    ),
    "refund_after_payout": (
        "This order was refunded after its commission was submitted or paid. PayPal payouts "
        "cannot be pulled back automatically; recover the amount manually."
    ),
    "duplicate_capture_id": (
        "PayPal reported a different capture for an order that is already completed. Check for "
        "a double charge."
    ),
}


def append_ledger(
    db: Session,
    *,
    campaign_id: str,
    entry_type: str,
    amount_cents: int,
    source_key: str,
    public_ref: str,
    order_id: str | None = None,
    backing_id: str | None = None,
    commission_id: str | None = None,
    payout_item_id: str | None = None,
    occurred_at: datetime | None = None,
) -> bool:
    """Append-only, idempotent by source_key. Returns True when a row was inserted."""
    stmt = (
        insert(LedgerEntry)
        .values(
            id=new_id("le"),
            campaign_id=campaign_id,
            entry_type=entry_type,
            amount_cents=amount_cents,
            currency="USD",
            source_key=source_key,
            public_ref=public_ref,
            order_id=order_id,
            backing_id=backing_id,
            commission_id=commission_id,
            payout_item_id=payout_item_id,
            occurred_at=occurred_at or utcnow(),
        )
        .on_conflict_do_nothing(index_elements=["source_key"])
    )
    result = db.execute(stmt)
    return bool(result.rowcount)


def raise_flag(
    db: Session,
    *,
    product_id: str,
    rule: str,
    subject_key: str,
    severity: str,
    evidence: dict[str, Any],
    campaign_id: str | None = None,
    order_id: str | None = None,
    backing_id: str | None = None,
    commission_id: str | None = None,
) -> None:
    stmt = (
        insert(RiskFlag)
        .values(
            id=new_id("rf"),
            product_id=product_id,
            campaign_id=campaign_id,
            order_id=order_id,
            backing_id=backing_id,
            commission_id=commission_id,
            rule=rule,
            subject_key=subject_key,
            severity=severity,
            status="open",
            evidence=evidence,
            explanation=RULE_EXPLANATIONS.get(rule),
        )
        .on_conflict_do_nothing(index_elements=["rule", "subject_key"])
    )
    db.execute(stmt)
