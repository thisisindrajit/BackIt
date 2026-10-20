"""Background worker: `python -m app.workers.run --once` or `--loop --interval 5`.

Each pass:
1. expires stale order reservations,
2. releases matured commission holds (held -> payable),
3. processes verified PayPal webhook events from the inbox,
4. runs due outbox jobs (payout execution / reconciliation),
5. delivers due builder webhooks.

Rows are claimed with SELECT ... FOR UPDATE SKIP LOCKED plus a lease, so several workers can
run safely. Failures back off exponentially with jitter until max attempts, then go `dead`.
"""

import argparse
import logging
import random
import time
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.ids import utcnow
from app.models import OutboxJob, ProviderEvent, WebhookDelivery
from app.providers.paypal import PayPalProvider, get_paypal
from app.services.checkout import expire_stale_orders
from app.services.deliveries import claim_due
from app.services.payouts import RetryLater, execute_batch
from app.services.provider_events import process_event
from app.services.refunds import release_matured_holds
from app.webhooks_out import attempt_delivery

log = logging.getLogger("backit.worker")

LEASE_SECONDS = 120
EVENT_MAX_ATTEMPTS = 8


def _backoff(attempts: int, base: int = 15) -> timedelta:
    seconds = min(base * (2 ** max(attempts - 1, 0)), 3600)
    return timedelta(seconds=seconds * random.uniform(0.8, 1.2))


def _claim_jobs(db: Session, limit: int = 10) -> list[str]:
    now = utcnow()
    ids = list(db.scalars(
        select(OutboxJob.id)
        .where(OutboxJob.state.in_(("pending", "running")), OutboxJob.next_attempt_at <= now,
               or_(OutboxJob.lease_until.is_(None), OutboxJob.lease_until < now))
        .order_by(OutboxJob.next_attempt_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all())
    if ids:
        db.execute(update(OutboxJob).where(OutboxJob.id.in_(ids)).values(
            state="running", lease_until=now + timedelta(seconds=LEASE_SECONDS)))
    db.commit()
    return ids


def run_job(db: Session, job_id: str, paypal: PayPalProvider) -> None:
    job = db.get(OutboxJob, job_id)
    if job is None:
        return
    job.attempts += 1
    db.commit()
    try:
        if job.kind == "execute_payout":
            execute_batch(db, job.payload["batch_id"], paypal)
        else:
            raise ValueError(f"unknown job kind {job.kind}")
    except RetryLater as exc:
        db.rollback()
        job = db.get(OutboxJob, job_id, populate_existing=True)
        assert job is not None
        # Waiting on the provider is not a failure; it does not consume the attempt budget.
        job.attempts = max(job.attempts - 1, 0)
        job.state = "pending"
        job.lease_until = None
        job.last_error = str(exc)
        job.next_attempt_at = utcnow() + timedelta(seconds=exc.delay_seconds)
        db.commit()
        return
    except Exception as exc:
        log.exception("job %s failed", job_id)
        db.rollback()
        job = db.get(OutboxJob, job_id, populate_existing=True)
        assert job is not None
        job.last_error = f"{type(exc).__name__}: {exc}"[:1000]
        job.lease_until = None
        if job.attempts >= job.max_attempts:
            job.state = "dead"
        else:
            job.state = "pending"
            job.next_attempt_at = utcnow() + _backoff(job.attempts)
        db.commit()
        return
    job = db.get(OutboxJob, job_id, populate_existing=True)
    assert job is not None
    job.state = "done"
    job.lease_until = None
    job.last_error = None
    db.commit()


def _claim_events(db: Session, limit: int = 20) -> list[str]:
    now = utcnow()
    ids = list(db.scalars(
        select(ProviderEvent.id)
        .where(ProviderEvent.state.in_(("received", "failed")),
               or_(ProviderEvent.lease_until.is_(None), ProviderEvent.lease_until < now))
        .order_by(ProviderEvent.received_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all())
    if ids:
        db.execute(update(ProviderEvent).where(ProviderEvent.id.in_(ids)).values(
            lease_until=now + timedelta(seconds=LEASE_SECONDS)))
    db.commit()
    return ids


def run_event(db: Session, event_id: str, paypal: PayPalProvider) -> None:
    event = db.get(ProviderEvent, event_id)
    if event is None:
        return
    event.attempts += 1
    db.commit()
    try:
        state = process_event(db, event, paypal)
    except Exception as exc:
        log.exception("provider event %s failed", event_id)
        db.rollback()
        event = db.get(ProviderEvent, event_id, populate_existing=True)
        assert event is not None
        event.last_error = f"{type(exc).__name__}: {exc}"[:1000]
        event.state = "dead" if event.attempts >= EVENT_MAX_ATTEMPTS else "failed"
        event.lease_until = utcnow() + _backoff(event.attempts)
        db.commit()
        return
    event = db.get(ProviderEvent, event_id, populate_existing=True)
    assert event is not None
    event.state = state
    event.processed_at = utcnow()
    event.lease_until = None
    event.last_error = None
    db.commit()


def run_once(paypal: PayPalProvider | None = None) -> dict[str, int]:
    paypal = paypal or get_paypal()
    stats = {"expired": 0, "released": 0, "events": 0, "jobs": 0, "deliveries": 0}
    with SessionLocal() as db:
        stats["expired"] = expire_stale_orders(db, paypal)
        stats["released"] = release_matured_holds(db)
        db.commit()
        for event_id in _claim_events(db):
            run_event(db, event_id, paypal)
            stats["events"] += 1
        for job_id in _claim_jobs(db):
            run_job(db, job_id, paypal)
            stats["jobs"] += 1
        for delivery_id in claim_due(db):
            delivery = db.get(WebhookDelivery, delivery_id)
            if delivery is not None:
                attempt_delivery(db, delivery)
                db.commit()
                stats["deliveries"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="BackIt background worker")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run a single pass and exit")
    mode.add_argument("--loop", action="store_true", help="run passes forever")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between passes")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.once:
        log.info("pass: %s", run_once())
        return
    while True:
        try:
            stats = run_once()
            if any(stats.values()):
                log.info("pass: %s", stats)
        except Exception:
            log.exception("worker pass failed")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
