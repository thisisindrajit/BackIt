"""Backers flag an offer they can't use. Open reports halt the product's reward payouts."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import forbidden, not_found
from app.ids import new_id, utcnow
from app.models import AccessReport, Backing, Campaign, Order, Product, Profile
from app.services.common import audit, conflict
from app.services.notifications import notify, send_emails_for


def _owned_backing(db: Session, user: Profile, backing_id: str) -> tuple[Backing, Campaign, Product]:
    backing = db.get(Backing, backing_id)
    if backing is None:
        raise not_found("Backing")
    if backing.user_id != user.id:
        raise forbidden()
    campaign = db.get(Campaign, backing.campaign_id)
    assert campaign is not None
    product = db.get(Product, campaign.product_id)
    assert product is not None
    return backing, campaign, product


def _open_report(db: Session, backing_id: str, *, lock: bool = False) -> AccessReport | None:
    stmt = select(AccessReport).where(AccessReport.backing_id == backing_id, AccessReport.status == "open")
    if lock:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def open_report(db: Session, user: Profile, backing_id: str, message: str) -> AccessReport:
    backing, campaign, product = _owned_backing(db, user, backing_id)
    order = db.get(Order, backing.order_id)
    if order is None or order.state != "completed":
        raise conflict("not_reportable", "Only a completed purchase can be reported")
    if _open_report(db, backing.id):
        raise conflict("report_open", "You already have an open report for this purchase")
    report = AccessReport(
        id=new_id("acr"), campaign_id=campaign.id, product_id=product.id, backing_id=backing.id,
        reporter_id=user.id, status="open", message=message.strip(),
    )
    db.add(report)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("report_open", "You already have an open report for this purchase") from exc
    owner = db.get(Profile, product.owner_id)
    key = f"access:{report.id}:opened"
    if owner is not None:
        notify(
            db, user=owner, kind="access_report", dedupe_key=key,
            title=f"A backer can't access {product.name}",
            body=(f"{user.display_name} reported: \u201c{report.message}\u201d\n"
                  "Reward payouts for this product are paused until it's sorted. "
                  "Reply from your Sales tab, or refund the purchase."),
            link=f"/app/products/{product.id}?tab=sales", campaign_id=campaign.id, order_id=order.id,
            email=True,
        )
    audit(db, actor_id=user.id, action="access_report.opened", target_type="access_report",
          target_id=report.id, details={"backing_id": backing.id})
    db.commit()
    send_emails_for(db, [key])
    return report


def resolve_report(db: Session, user: Profile, backing_id: str) -> AccessReport:
    backing, campaign, product = _owned_backing(db, user, backing_id)
    report = _open_report(db, backing.id, lock=True)
    if report is None:
        raise not_found("Open report")
    report.status = "resolved"
    report.resolved_at = utcnow()
    owner = db.get(Profile, product.owner_id)
    if owner is not None:
        notify(
            db, user=owner, kind="access_report", dedupe_key=f"access:{report.id}:resolved",
            title=f"Access report resolved for {product.name}",
            body=f"{user.display_name} confirmed they can access it now. Thanks for sorting it out.",
            link=f"/app/products/{product.id}?tab=sales", campaign_id=campaign.id,
        )
    audit(db, actor_id=user.id, action="access_report.resolved", target_type="access_report",
          target_id=report.id)
    db.commit()
    return report


def builder_reports(db: Session, product: Product) -> list[AccessReport]:
    return list(db.scalars(
        select(AccessReport).where(AccessReport.product_id == product.id)
        .order_by((AccessReport.status == "open").desc(), AccessReport.created_at.desc())
        .limit(100)
    ).all())


def reply(db: Session, user: Profile, report_id: str, note: str) -> AccessReport:
    report = db.scalars(select(AccessReport).where(AccessReport.id == report_id).with_for_update()).first()
    if report is None:
        raise not_found("Report")
    product = db.get(Product, report.product_id)
    if product is None or product.owner_id != user.id:
        raise forbidden()
    if report.status != "open":
        raise conflict("report_closed", "This report is already closed")
    now = utcnow()
    report.builder_note = note.strip()
    report.builder_replied_at = now
    reporter = db.get(Profile, report.reporter_id)
    key = f"access:{report.id}:reply:{int(now.timestamp())}"
    if reporter is not None:
        notify(
            db, user=reporter, kind="access_report_reply", dedupe_key=key,
            title=f"{product.name} replied to your report",
            body=(f"\u201c{report.builder_note}\u201d\n"
                  "If it works now, mark the report resolved under Backings."),
            link="/app/backings", campaign_id=report.campaign_id, email=True,
        )
    audit(db, actor_id=user.id, action="access_report.replied", target_type="access_report",
          target_id=report.id)
    db.commit()
    send_emails_for(db, [key])
    return report
