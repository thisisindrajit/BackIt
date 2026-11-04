"""Create in-app notifications and send their emails (immediately, with worker retries)."""

import logging
import random
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.email import EmailNotConfigured, render, send_email
from app.ids import new_id, utcnow
from app.models import Backing, Campaign, Commission, Notification, Order, Product, Profile

log = logging.getLogger("backit.notifications")

LEASE_SECONDS = 60


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}".replace(".00", "")


def _short(display_name: str) -> str:
    parts = display_name.split()
    if not parts:
        return "Someone"
    return f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else parts[0]


def notify(
    db: Session,
    *,
    user: Profile,
    kind: str,
    dedupe_key: str,
    title: str,
    body: str,
    link: str | None = None,
    campaign_id: str | None = None,
    order_id: str | None = None,
    email: bool = False,
) -> None:
    """Insert once per `dedupe_key`; replays of the same event are ignored."""
    wants_email = email and bool(user.email)
    db.execute(
        insert(Notification)
        .values(
            id=new_id("ntf"),
            user_id=user.id,
            kind=kind,
            dedupe_key=dedupe_key,
            title=title,
            body=body,
            link=link,
            campaign_id=campaign_id,
            order_id=order_id,
            email_to=user.email if wants_email else None,
            email_state="pending" if wants_email else "none",
            email_attempts=0,
            email_next_attempt_at=utcnow() if wants_email else None,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )


def notify_sale(
    db: Session,
    *,
    order: Order,
    campaign: Campaign,
    product: Product,
    buyer: Profile,
    backing: Backing,
    commission: Commission | None,
) -> None:
    """Tell the builder about the sale, and the referring backer about their reward."""
    owner = db.get(Profile, product.owner_id)
    buyer_name = _short(buyer.display_name)
    builder_net = order.amount_cents - order.platform_fee_cents - order.commission_cents
    if owner is not None:
        if order.kind == "founding":
            title = f"Founding backer #{backing.badge_number} for {product.name}"
            what = f"{buyer_name} claimed founding spot #{backing.badge_number} and paid {_money(order.amount_cents)}."
        else:
            title = f"New referral sale for {product.name}"
            what = f"{buyer_name} bought through a backer's link and paid {_money(order.amount_cents)}."
        notify(
            db, user=owner, kind="sale", dedupe_key=f"sale:{order.id}:builder",
            title=title, body=f"{what}\nYou keep {_money(builder_net)} after fees and rewards.",
            link=f"/app/products/{product.id}?tab=sales", campaign_id=campaign.id, order_id=order.id,
            email=True,
        )

    if order.referrer_backing_id:
        referrer_backing = db.get(Backing, order.referrer_backing_id)
        referrer = db.get(Profile, referrer_backing.user_id) if referrer_backing else None
        if referrer is not None and (owner is None or referrer.id != owner.id):
            if commission is not None and commission.state == "held":
                reward = (f"You earned {_money(commission.amount_cents)}. It's held for "
                          f"{get_settings().hold_days} days in case of a refund, then paid to your PayPal.")
            elif commission is not None:
                reward = "This sale is under review, so its reward is on hold for now."
            else:
                reward = "This offer has no reward per sale, but thanks for spreading the word."
            notify(
                db, user=referrer, kind="referral_sale", dedupe_key=f"sale:{order.id}:referrer",
                title=f"Your link sold {product.name}",
                body=f"{buyer_name} bought {product.name} with your referral link.\n{reward}",
                link="/app/backings", campaign_id=campaign.id, order_id=order.id, email=True,
            )


def notify_campaign_live(db: Session, *, campaign: Campaign, product: Product, owner: Profile) -> None:
    notify(
        db, user=owner, kind="campaign_live", dedupe_key=f"live:{campaign.id}:{campaign.version}",
        title=f"{product.name} is live",
        body=f"Your campaign is open at backit.club/{campaign.slug}. Share it with the people who'd back it first.",
        link=f"/{campaign.slug}", campaign_id=campaign.id,
    )


def _claim(db: Session, ids: list[str] | None = None, limit: int = 20) -> list[str]:
    now = utcnow()
    query = (
        select(Notification.id)
        .where(
            Notification.email_state.in_(("pending", "failed")),
            Notification.email_next_attempt_at <= now,
            or_(Notification.email_lease_until.is_(None), Notification.email_lease_until < now),
        )
        .order_by(Notification.email_next_attempt_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    if ids is not None:
        if not ids:
            return []
        query = query.where(Notification.id.in_(ids))
    rows = list(db.scalars(query).all())
    if rows:
        db.execute(
            update(Notification)
            .where(Notification.id.in_(rows))
            .values(email_lease_until=now + timedelta(seconds=LEASE_SECONDS))
        )
    db.commit()
    return rows


def _send(db: Session, notification: Notification) -> None:
    settings = get_settings()
    now = utcnow()
    notification.email_attempts += 1
    notification.email_lease_until = None
    link = f"{settings.web_base_url.rstrip('/')}{notification.link}" if notification.link else None
    cta = {"sale": "See your sales", "referral_sale": "See your rewards"}.get(notification.kind, "Open BackIt")
    html, text = render(heading=notification.title, body=notification.body, cta_label=cta, cta_url=link)
    try:
        result = send_email(to=notification.email_to or "", subject=notification.title, html=html,
                            text=text, idempotency_key=notification.id)
    except EmailNotConfigured as exc:
        notification.email_state = "skipped"
        notification.email_last_error = str(exc)
        notification.email_next_attempt_at = None
        return
    if result.ok:
        notification.email_state = "sent"
        notification.email_sent_at = now
        notification.email_message_id = result.message_id
        notification.email_last_error = None
        notification.email_next_attempt_at = None
        return
    notification.email_last_error = result.error
    if not result.retryable or notification.email_attempts >= settings.email_max_attempts:
        notification.email_state = "dead"
        notification.email_next_attempt_at = None
        log.warning("email %s dead: %s", notification.id, result.error)
    else:
        notification.email_state = "failed"
        delay = 30 * 2 ** (notification.email_attempts - 1)
        notification.email_next_attempt_at = now + timedelta(seconds=delay + random.randint(0, 15))


def send_due_emails(db: Session, ids: list[str] | None = None) -> int:
    """Send claimed emails. Pass `ids` for a best-effort immediate send; the worker sweeps the rest."""
    claimed = _claim(db, ids)
    for notification_id in claimed:
        notification = db.get(Notification, notification_id, populate_existing=True)
        if notification is None:
            continue
        try:
            _send(db, notification)
        except Exception:
            log.exception("email %s crashed", notification_id)
            notification.email_state = "failed"
            notification.email_next_attempt_at = utcnow() + timedelta(minutes=5)
        db.commit()
    return len(claimed)


def send_order_emails(db: Session, order_id: str) -> None:
    ids = list(db.scalars(select(Notification.id).where(
        Notification.order_id == order_id, Notification.email_state == "pending")).all())
    send_due_emails(db, ids)
