"""Payout previews, approval and execution. All amounts are computed here, never by AI."""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError, forbidden, not_found
from app.ids import new_id, utcnow
from app.models import (
    Backing,
    Commission,
    OutboxJob,
    PayoutAllocation,
    PayoutBatch,
    PayoutItem,
    PayoutPreview,
    Product,
    Profile,
    Refund,
    RiskFlag,
)
from app.money import format_usd
from app.providers import ai
from app.providers.paypal import PayoutBatchResult, PayoutItemRequest, PayPalProvider, ProviderError
from app.schemas import ApproveIn
from app.security import mask_email, public_ref, sha256_hex
from app.services.common import audit, campaign_for_product, conflict, owned_product
from app.services.ledger import append_ledger
from app.services.refunds import release_matured_holds


class RetryLater(Exception):
    def __init__(self, message: str, delay_seconds: int = 60) -> None:
        super().__init__(message)
        self.delay_seconds = delay_seconds


@dataclass
class Eligibility:
    items: list[dict[str, Any]] = field(default_factory=list)
    exclusions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_cents(self) -> int:
        return sum(i["amount_cents"] for i in self.items)

    def digest(self, product_id: str) -> str:
        canonical = {
            "product_id": product_id,
            "currency": "USD",
            "items": sorted(
                (
                    {
                        "backing_id": i["backing_id"],
                        "receiver": i["receiver"],
                        "amount_cents": i["amount_cents"],
                        "commission_ids": sorted(i["commission_ids"]),
                    }
                    for i in self.items
                ),
                key=lambda x: x["backing_id"],
            ),
        }
        return sha256_hex(json.dumps(canonical, sort_keys=True, separators=(",", ":")))


def compute_eligibility(db: Session, product: Product) -> Eligibility:
    settings = get_settings()
    result = Eligibility()
    campaign = campaign_for_product(db, product.id)
    if campaign is None:
        return result
    release_matured_holds(db, campaign.id)
    commissions = db.scalars(
        select(Commission)
        .where(Commission.campaign_id == campaign.id,
               Commission.state.in_(("held", "payable", "blocked")))
        .order_by(Commission.created_at, Commission.id)
    ).all()
    active_alloc = set(db.scalars(
        select(PayoutAllocation.commission_id).where(PayoutAllocation.active.is_(True))
    ).all())
    pending_refund_orders = set(db.scalars(
        select(Refund.order_id).where(Refund.state.in_(("requested", "pending")))
    ).all())
    groups: dict[str, list[Commission]] = defaultdict(list)
    for c in commissions:
        if c.id not in active_alloc:
            groups[c.backing_id].append(c)

    for backing_id in sorted(groups):
        group = groups[backing_id]
        backing = db.get(Backing, backing_id)
        profile = db.get(Profile, backing.user_id) if backing else None
        name = profile.display_name if profile else "Backer"
        open_flags = db.scalar(
            select(func.count(RiskFlag.id)).where(RiskFlag.backing_id == backing_id,
                                                  RiskFlag.status == "open")
        )

        def exclude(reason: str, cs: list[Commission], *, _b: str = backing_id, _n: str = name) -> None:
            if cs:
                result.exclusions.append({
                    "backing_id": _b, "backer_name": _n,
                    "amount_cents": sum(c.amount_cents for c in cs), "reason": reason,
                })

        refund_pending = [c for c in group if c.order_id in pending_refund_orders]
        rest = [c for c in group if c.order_id not in pending_refund_orders]
        exclude("refund_pending", refund_pending)
        exclude("in_hold", [c for c in rest if c.state == "held"])
        exclude("risk_review", [c for c in rest if c.state == "blocked"])
        eligible = [c for c in rest if c.state == "payable"]
        if not eligible:
            continue
        amount = sum(c.amount_cents for c in eligible)
        if open_flags:
            exclude("risk_review", eligible)
        elif profile is None or not profile.payout_email or not profile.payout_email_verified:
            exclude("no_payout_email", eligible)
        elif amount < settings.payout_minimum_cents:
            exclude("below_minimum", eligible)
        else:
            result.items.append({
                "backing_id": backing_id,
                "backer_name": name,
                "receiver": profile.payout_email.strip().lower(),
                "payout_email_masked": mask_email(profile.payout_email),
                "amount_cents": amount,
                "commission_ids": [c.id for c in eligible],
            })
    return result


def _funding(db: Session, product: Product, required: int) -> dict[str, Any]:
    budget = get_settings().sandbox_payout_budget_cents
    committed = db.scalar(
        select(func.coalesce(func.sum(PayoutBatch.total_cents), 0)).where(
            PayoutBatch.product_id == product.id, PayoutBatch.status != "failed"
        )
    ) or 0
    remaining = budget - int(committed)
    # Sandbox sender balance is not visible via API, so sufficiency is unknown (None) unless
    # the request exceeds this tenant's bounded sandbox budget.
    return {
        "source": "sandbox_sender",
        "available_cents": None,
        "required_cents": required,
        "sufficient": False if required > remaining else None,
    }


class _Explanation(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


REASON_LABELS = {
    "in_hold": "still inside the {hold}-day hold",
    "below_minimum": "below the {minimum} payout minimum",
    "no_payout_email": "missing a verified payout email",
    "risk_review": "under risk review",
    "refund_pending": "waiting on a pending refund",
}


def _template_explanation(elig: Eligibility) -> str:
    settings = get_settings()
    parts: list[str] = []
    if elig.items:
        parts.append(
            f"This preview pays {len(elig.items)} backer{'s' if len(elig.items) != 1 else ''} "
            f"a total of {format_usd(elig.total_cents)} in referral commissions whose hold has ended."
        )
    else:
        parts.append("No commissions are eligible for payout right now.")
    by_reason: dict[str, list[int]] = defaultdict(list)
    for e in elig.exclusions:
        by_reason[e["reason"]].append(e["amount_cents"])
    for reason, amounts in by_reason.items():
        label = REASON_LABELS[reason].format(hold=settings.hold_days,
                                             minimum=format_usd(settings.payout_minimum_cents))
        parts.append(f"Excluded: {len(amounts)} amount{'s' if len(amounts) != 1 else ''} "
                     f"totalling {format_usd(sum(amounts))} {label}.")
    parts.append(
        "Payouts are sent from a separately pre-funded PayPal sandbox sender account, not from "
        "checkout proceeds. Nothing is sent until you approve this exact preview."
    )
    return " ".join(parts)


_AMOUNT_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?")


def _explain(db: Session, user: Profile, elig: Eligibility) -> tuple[str, str, str]:
    template = _template_explanation(elig)
    allowed = {format_usd(elig.total_cents)}
    allowed |= {format_usd(i["amount_cents"]) for i in elig.items}
    allowed |= {format_usd(e["amount_cents"]) for e in elig.exclusions}
    allowed.add(format_usd(get_settings().payout_minimum_cents))
    allowed_plain = {a.replace(".00", "") for a in allowed} | allowed

    def check(out: _Explanation) -> None:
        for amount in _AMOUNT_RE.findall(out.text):
            if amount not in allowed_plain:
                raise ValueError(f"explanation mentions unknown amount {amount}")

    facts = {
        "items": [{"backer": i["backer_name"], "amount": format_usd(i["amount_cents"])}
                  for i in elig.items],
        "exclusions": [{"backer": e["backer_name"], "amount": format_usd(e["amount_cents"]),
                        "reason": e["reason"]} for e in elig.exclusions],
        "total": format_usd(elig.total_cents),
        "hold_days": get_settings().hold_days,
        "funding": "separately pre-funded PayPal sandbox sender account",
    }
    out, source, run_id = ai.generate(
        db,
        purpose="payout_explanation",
        prompt_version="payout_explanation.v1",
        actor_id=user.id,
        system=(
            "You explain a payout preview to a software builder in plain language (<=120 words). "
            "Use only the amounts given verbatim; never compute, round or invent numbers. "
            "Mention exclusions and that the builder must approve before anything is sent."
        ),
        user=json.dumps(facts),
        schema=_Explanation,
        fallback=lambda: _Explanation(text=template),
        post_validate=check,
    )
    return out.text, source, run_id


def create_preview(db: Session, user: Profile, product: Product) -> PayoutPreview:
    now = utcnow()
    db.execute(
        update(PayoutPreview)
        .where(PayoutPreview.product_id == product.id, PayoutPreview.status == "open")
        .values(status="stale")
    )
    elig = compute_eligibility(db, product)
    text, source, run_id = _explain(db, user, elig)
    preview = PayoutPreview(
        id=new_id("pp"),
        product_id=product.id,
        created_by=user.id,
        status="open",
        digest=elig.digest(product.id),
        total_cents=elig.total_cents,
        currency="USD",
        items=elig.items,
        exclusions=elig.exclusions,
        funding=_funding(db, product, elig.total_cents),
        explanation_text=text,
        explanation_source=source,
        ai_run_id=run_id,
        created_at=now,
        expires_at=now + timedelta(minutes=get_settings().payout_preview_ttl_minutes),
    )
    db.add(preview)
    audit(db, actor_id=user.id, action="payout.preview_created", target_type="payout_preview",
          target_id=preview.id, details={"total_cents": preview.total_cents, "digest": preview.digest})
    db.commit()
    return preview


def refresh_preview(db: Session, preview: PayoutPreview, product: Product) -> PayoutPreview:
    if preview.status != "open":
        return preview
    if preview.expires_at <= utcnow():
        preview.status = "expired"
    elif compute_eligibility(db, product).digest(product.id) != preview.digest:
        preview.status = "stale"
    db.commit()
    return preview


def owned_preview(db: Session, user: Profile, preview_id: str, *, lock: bool = False) -> tuple[PayoutPreview, Product]:
    preview = db.get(PayoutPreview, preview_id)
    if preview is None:
        raise not_found("Payout preview")
    product = owned_product(db, preview.product_id, user, lock=lock)
    if lock:
        preview = db.scalars(
            select(PayoutPreview).where(PayoutPreview.id == preview_id).with_for_update()
        ).one()
    return preview, product


def approve(db: Session, user: Profile, preview_id: str, body: ApproveIn) -> PayoutBatch:
    # Lock the product first: serialises approvals per tenant.
    preview, product = owned_preview(db, user, preview_id, lock=True)
    if preview.status == "approved":
        raise conflict("preview_already_approved", "This preview was already approved")
    if preview.status != "open" or body.digest != preview.digest:
        raise conflict("stale_preview", "This preview is no longer current; create a new one",
                       {"reason": "digest_mismatch" if preview.status == "open" else preview.status})
    if preview.expires_at <= utcnow():
        preview.status = "expired"
        db.commit()
        raise conflict("stale_preview", "This preview expired; create a new one", {"reason": "expired"})
    elig = compute_eligibility(db, product)
    if elig.digest(product.id) != preview.digest:
        preview.status = "stale"
        db.commit()
        raise conflict("stale_preview", "Eligible commissions changed since this preview was created",
                       {"reason": "changed"})
    if elig.total_cents <= 0:
        raise conflict("nothing_to_pay", "There are no eligible commissions in this preview")
    funding = _funding(db, product, elig.total_cents)
    if funding["sufficient"] is False:
        raise conflict("insufficient_funding", "The sandbox payout budget is insufficient",
                       {"funding": funding})
    if funding["sufficient"] is None and not body.funding_confirmed:
        raise conflict("funding_confirmation_required",
                       "Confirm that the sandbox sender account is funded before approving")

    now = utcnow()
    batch_id = new_id("pb")
    batch = PayoutBatch(
        id=batch_id,
        product_id=product.id,
        preview_id=preview.id,
        preview_digest=preview.digest,
        status="queued",
        provider="paypal_sandbox" if get_settings().paypal_mode == "sandbox" else "mock",
        sender_batch_id=f"backit_{batch_id}",
        total_cents=elig.total_cents,
        currency="USD",
        funding_confirmed=body.funding_confirmed,
        approved_by=user.id,
        approved_at=now,
    )
    db.add(batch)
    db.flush()
    for item in elig.items:
        item_id = new_id("pi")
        db.add(PayoutItem(
            id=item_id, batch_id=batch.id, backing_id=item["backing_id"],
            receiver=item["receiver"], amount_cents=item["amount_cents"], status="queued",
            sender_item_id=f"backit_{item_id}",
        ))
        db.flush()
        commissions = db.scalars(
            select(Commission).where(Commission.id.in_(item["commission_ids"])).with_for_update()
        ).all()
        for c in commissions:
            if c.state != "payable":
                db.rollback()
                raise conflict("stale_preview", "A commission changed during approval",
                               {"reason": "changed"})
            c.state = "reserved"
            db.add(PayoutAllocation(id=new_id("pa"), payout_item_id=item_id, commission_id=c.id,
                                    amount_cents=c.amount_cents, active=True))
    preview.status = "approved"
    db.add(OutboxJob(id=new_id("job"), kind="execute_payout", payload={"batch_id": batch.id},
                     dedupe_key=f"execute_payout:{batch.id}", state="pending",
                     max_attempts=get_settings().job_max_attempts, next_attempt_at=now))
    audit(db, actor_id=user.id, action="payout.approved", target_type="payout_batch",
          target_id=batch.id, details={
              "preview_id": preview.id, "digest": preview.digest, "total_cents": batch.total_cents,
              "funding_confirmed": body.funding_confirmed,
              "funding_confirmation": "sandbox sender funding confirmed by builder (sandbox only)"
              if body.funding_confirmed else None,
          })
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("preview_already_approved", "This preview was already approved") from exc
    return batch


def visible_batch(db: Session, user: Profile, batch_id: str) -> PayoutBatch:
    batch = db.get(PayoutBatch, batch_id)
    if batch is None:
        raise not_found("Payout batch")
    product = db.get(Product, batch.product_id)
    if product is None or product.owner_id != user.id:
        raise forbidden()
    return batch


# ---------------- execution (worker) ----------------


def _release_item(db: Session, item: PayoutItem, status: str, error: str | None) -> None:
    item.status = status
    item.error = error
    allocs = db.scalars(
        select(PayoutAllocation).where(PayoutAllocation.payout_item_id == item.id,
                                       PayoutAllocation.active.is_(True))
    ).all()
    for alloc in allocs:
        alloc.active = False
        c = db.get(Commission, alloc.commission_id)
        if c is None:
            continue
        if c.blocked_reason == "refunded_after_payout":
            c.state = "reversed"
            c.reversed_at = utcnow()
        elif c.state in ("reserved", "submitted"):
            c.state = "payable"


def _item_commissions(db: Session, item: PayoutItem) -> list[Commission]:
    ids = db.scalars(
        select(PayoutAllocation.commission_id).where(PayoutAllocation.payout_item_id == item.id,
                                                     PayoutAllocation.active.is_(True))
    ).all()
    if not ids:
        return []
    return list(db.scalars(select(Commission).where(Commission.id.in_(ids)).with_for_update()).all())


def _revalidate(db: Session, item: PayoutItem) -> str | None:
    commissions = _item_commissions(db, item)
    if not commissions:
        return "no_active_allocations"
    if any(c.state != "reserved" for c in commissions):
        return "commission_changed"
    if sum(c.amount_cents for c in commissions) != item.amount_cents:
        return "amount_changed"
    backing = db.get(Backing, item.backing_id)
    profile = db.get(Profile, backing.user_id) if backing else None
    if (profile is None or not profile.payout_email_verified
            or (profile.payout_email or "").strip().lower() != item.receiver):
        return "destination_changed"
    flags = db.scalar(select(func.count(RiskFlag.id)).where(
        RiskFlag.backing_id == item.backing_id, RiskFlag.status == "open"))
    if flags:
        return "risk_review"
    return None


def _summarize(db: Session, batch: PayoutBatch) -> None:
    items = db.scalars(select(PayoutItem).where(PayoutItem.batch_id == batch.id)).all()
    statuses = [i.status for i in items]
    paid = [i for i in items if i.status == "success"]
    if any(s in ("queued", "submitted", "pending") for s in statuses):
        batch.status = "processing"
    elif statuses and all(s == "success" for s in statuses):
        batch.status = "success"
    elif paid or any(s == "unclaimed" for s in statuses):
        batch.status = "partial"
    else:
        batch.status = "failed"
    counts = defaultdict(int)
    for s in statuses:
        counts[s] += 1
    detail = ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
    batch.summary = (
        f"{len(paid)} of {len(items)} payout item{'s' if len(items) != 1 else ''} confirmed paid "
        f"({format_usd(sum(i.amount_cents for i in paid))}). Item status: {detail}."
        + (" Provider: mock (no money moved)." if batch.provider == "mock" else
           " Provider: PayPal sandbox.")
    )


_SUCCESS = {"SUCCESS"}
_FAILED = {"FAILED", "BLOCKED", "DENIED"}
_RETURNED = {"RETURNED", "REFUNDED", "REVERSED"}
_UNCLAIMED = {"UNCLAIMED"}


def apply_item_results(db: Session, batch: PayoutBatch, result: PayoutBatchResult) -> None:
    items = {i.sender_item_id: i for i in db.scalars(
        select(PayoutItem).where(PayoutItem.batch_id == batch.id).with_for_update()).all()}
    now = utcnow()
    for r in result.items:
        item = items.get(r.sender_item_id)
        if item is None or item.status in ("success", "failed", "returned"):
            continue
        item.provider_item_id = r.provider_item_id or item.provider_item_id
        item.provider_status = r.transaction_status
        status = r.transaction_status.upper()
        if status in _SUCCESS:
            item.status = "success"
            for c in _item_commissions(db, item):
                c.state = "paid"
                c.paid_at = now
            append_ledger(db, campaign_id=_campaign_id(db, batch), entry_type="payout_paid",
                          amount_cents=item.amount_cents, source_key=f"payout_item:{item.id}:paid",
                          public_ref=public_ref("backing", item.backing_id),
                          backing_id=item.backing_id, payout_item_id=item.id, occurred_at=now)
        elif status in _FAILED:
            _release_item(db, item, "failed", r.error or status)
        elif status in _RETURNED:
            _release_item(db, item, "returned", r.error or status)
        elif status in _UNCLAIMED:
            item.status = "unclaimed"
        else:
            item.status = "pending"
    _summarize(db, batch)


def _campaign_id(db: Session, batch: PayoutBatch) -> str:
    campaign = campaign_for_product(db, batch.product_id)
    assert campaign is not None
    return campaign.id


def execute_batch(db: Session, batch_id: str, paypal: PayPalProvider) -> None:
    """Advance a payout batch. Raises RetryLater when it should be checked again."""
    batch = db.scalars(select(PayoutBatch).where(PayoutBatch.id == batch_id).with_for_update()).first()
    if batch is None:
        return
    if batch.status == "queued":
        items = db.scalars(select(PayoutItem).where(PayoutItem.batch_id == batch.id,
                                                    PayoutItem.status == "queued")).all()
        valid: list[PayoutItem] = []
        for item in items:
            reason = _revalidate(db, item)
            if reason:
                _release_item(db, item, "failed", f"invalidated_before_dispatch: {reason}")
            else:
                valid.append(item)
        if not valid:
            batch.status = "failed"
            batch.summary = "No items remained valid at dispatch time; nothing was sent."
            db.commit()
            return
        for item in valid:
            item.status = "submitted"
            for c in _item_commissions(db, item):
                c.state = "submitted"
        batch.status = "submitted"
        batch.submitted_at = utcnow()
        db.commit()  # sender_batch_id / sender_item_ids are persisted before the provider call.
        batch = db.scalars(select(PayoutBatch).where(PayoutBatch.id == batch_id).with_for_update()).one()

    if batch.status == "submitted" and not batch.provider_batch_id:
        items = db.scalars(select(PayoutItem).where(PayoutItem.batch_id == batch.id,
                                                    PayoutItem.status == "submitted")).all()
        requests = [PayoutItemRequest(sender_item_id=i.sender_item_id, receiver=i.receiver,
                                      amount_cents=i.amount_cents,
                                      note="BackIt referral commission (sandbox)") for i in items]
        try:
            result = paypal.create_payout(sender_batch_id=batch.sender_batch_id, items=requests,
                                          subject="You received a BackIt commission")
        except ProviderError as exc:
            batch.last_error = str(exc)[:500]
            if exc.uncertain or exc.issue in ("DUPLICATE_REQUEST_ID", "SENDER_BATCH_ID_ALREADY_USED"):
                db.commit()
                raise RetryLater(f"payout outcome uncertain: {exc}", 120) from exc
            for item in items:
                _release_item(db, item, "failed", exc.issue or "provider_rejected")
            batch.status = "failed"
            _summarize(db, batch)
            db.commit()
            return
        batch.provider_batch_id = result.provider_batch_id
        batch.status = "processing"
        batch.last_error = None
        if result.items:
            apply_item_results(db, batch, result)
        db.commit()
        if batch.status == "processing":
            raise RetryLater("awaiting provider item results", 30)
        return

    if batch.status in ("processing", "partial") and batch.provider_batch_id:
        sender_ids = list(db.scalars(select(PayoutItem.sender_item_id).where(
            PayoutItem.batch_id == batch.id)).all())
        try:
            result = paypal.get_payout_batch(batch.provider_batch_id, sender_ids)
        except ProviderError as exc:
            batch.last_error = str(exc)[:500]
            db.commit()
            raise RetryLater(f"reconcile failed: {exc}", 120) from exc
        apply_item_results(db, batch, result)
        db.commit()
        if batch.status == "processing":
            raise RetryLater("awaiting provider item results", 60)
        return
    db.commit()


def dev_release_holds(db: Session, user: Profile, product: Product) -> int:
    if not get_settings().is_development:
        raise AppError(404, "not_found", "Not available")
    campaign = campaign_for_product(db, product.id)
    if campaign is None:
        return 0
    now = utcnow()
    db.execute(update(Commission).where(Commission.campaign_id == campaign.id,
                                        Commission.state == "held").values(release_at=now))
    released = release_matured_holds(db, campaign.id)
    audit(db, actor_id=user.id, action="dev.release_holds", target_type="product",
          target_id=product.id, details={"released": released, "environment": "development"})
    db.commit()
    return released
