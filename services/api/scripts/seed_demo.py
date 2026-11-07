# ruff: noqa: E501  (demo stories are long Markdown paragraphs)
"""Seed demo data through the real API flows (PayPal mock mode, template AI).

    uv run python scripts/seed_demo.py --owner-email you@example.com
    uv run python scripts/seed_demo.py --owner-email you@example.com --reset
    uv run python scripts/seed_demo.py --backdate

The owner must have signed in once so their profile exists. They get three products
(one published campaign with sales and a paid payout, one draft, one without a campaign)
and backings in two other builders' campaigns. Everyone else is a `demo_*` profile.
--reset wipes all BackIt app data (keeping real profiles) before seeding.
Seeding runs in about a minute, so its timestamps are then spread over the past ten weeks
(order preserved) to give dashboards some history. --backdate re-applies that to existing data.
"""

import argparse
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

os.environ["PAYPAL_MODE"] = "mock"
os.environ["OPENROUTER_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import bindparam, select, text

from app import webhooks_out
from app.auth import get_key_source
from app.config import get_settings
from app.db import SessionLocal, engine
from app.main import app
from app.models import Profile
from app.workers import run as worker

KEY = Ed25519PrivateKey.generate()
OFFER = {
    "founding_price_cents": 6000,
    "founding_spots_cap": 50,
    "referral_list_price_cents": 1200,
    "referral_discount_bps": 2000,
    "commission_bps": 2500,
}
# Ledgerly demo: a friend pays $76.80 for 8 months, a bit less than the $99 lifetime founding spot.
LEDGERLY_OFFER = {**OFFER, "founding_price_cents": 9900, "referral_months": 8}
VERIFIED_MONTHS = [180000, 150000, 130000]
FIRST_NAMES = ["Ava", "Noah", "Mira", "Kai", "Lena", "Omar", "Zoe", "Ravi", "Iris", "Theo",
               "Nina", "Arjun", "Ella", "Sami", "Priya", "Jonas", "Maya", "Leo", "Tara", "Ben"]
LAST_NAMES = ["Shah", "Park", "Okafor", "Silva", "Novak", "Hughes", "Iyer", "Berg", "Costa", "Reyes"]


class _Key:
    def __init__(self, key: Any) -> None:
        self.key = key


class _KeySource:
    def get_signing_key_from_jwt(self, token: str) -> _Key:
        return _Key(KEY.public_key())


LEDGERLY_STORY = """## Why I built Ledgerly

Every April I lost a full weekend to receipts. Stripe payouts in one tab, PayPal in another, a bank export that never matched either, and a spreadsheet held together with hope. I'm a solo founder, so there was no finance team to hand it to. I just wanted my books to be **done**.

Ledgerly started as a script that pulled my Stripe and PayPal transactions into one place and sorted them. A few founder friends asked for a copy. Today it runs the books for 40 paying founders.

## What it does

- **Connects to Stripe and PayPal** and imports every charge, refund, fee and payout automatically.
- **Sorts each transaction** into the categories your accountant expects, and learns from your corrections.
- **Matches payouts to bank deposits** so you can see exactly where money is sitting.
- **Exports a clean ledger** at tax time, as CSV or a PDF your accountant can read in five minutes.

## Who it's for

Solo founders and tiny teams selling software or digital products who don't want to learn accounting software built for 50-person companies. If you have ever typed "stripe fees tax deductible" into a search bar at midnight, it's for you.

## What you get as a founding backer

- **Lifetime access to Ledgerly Pro**, including every future update, for a one-time price.
- A permanent, numbered **founding backer badge**.
- A personal **referral link**. Friends who buy through it get a discount, and you earn a reward once their refund window closes.

## What your backing unlocks

Bank sync works today for the US and UK. Founding backers fund **bank sync for five more countries**: Canada, Australia, Germany, France and the Netherlands. I'll post progress on each one here as it ships.

> Full refund within 30 days, no questions asked. If Ledgerly doesn't save you time, you shouldn't pay for it."""

SHIPNOTE_STORY = """## Why Shipnote

Release notes are the last thing anyone writes and the first thing users skip. Shipnote reads your merged pull requests and drafts notes people actually want to read.

## What you get

- **Lifetime access to the Team plan** for up to 10 seats.
- A founding backer badge and your own referral link."""

TALLYBOOK_STORY = """## How Tallybook started

Tallybook started as a spreadsheet I shared with a few friends who were tired of chasing clients for money. It had one tab for invoices, one for reminders, and a lot of copy and paste. When more people asked for it than I could help by email, I turned it into a real app.

## What it does

- **Send invoices in minutes** from a template that looks good on every screen.
- **Chase automatically.** Polite reminders go out before and after the due date, so you don't have to write awkward emails.
- **Reconcile in one click** when a payment lands, so you always know who still owes you.

## Who it's for

Indie hackers, freelancers and small studios who send a handful of invoices a month and want them paid on time without a full accounting suite.

## Founding backers get

- **Lifetime access to Tallybook Pro** for a one-time price.
- A permanent, numbered founding backer badge.
- A referral link that gives friends a discount and earns you a reward for each one who buys.

## What your backing unlocks

Recurring invoices and multi-currency support are next on the roadmap. Founding backers fund both, and get them the day they ship."""

SHIPLOG_STORY = """## Changelogs people actually read

Most changelogs live on a page nobody visits. Shiplog puts a beautiful changelog **inside your product**, right where your users already are, so every release becomes a reason to come back.

## What it does

- **An embedded widget** that shows what's new without sending users to another site.
- **Release posts with images and tags**, written in Markdown.
- **Read tracking**, so you know which updates landed and which didn't.

## Founding backers get

- **Lifetime access to Shiplog Growth.**
- A founding backer badge and a referral link that earns you a reward for every friend who buys.

## What your backing unlocks

Founding backers fund in-app announcements and email digests, so users who missed an update still hear about it."""


def _fake_send(url: str, secret: str, key_version: int, event_id: str,
               payload: dict[str, Any]) -> webhooks_out.AttemptResult:
    return webhooks_out.AttemptResult(True, 200, None, "ok")


class Seeder:
    def __init__(self, client: TestClient) -> None:
        self.c = client

    def user(self, sub: str, email: str, name: str) -> dict[str, str]:
        settings = get_settings()
        now = int(time.time())
        token = jwt.encode({"sub": sub, "email": email, "name": name, "iss": settings.auth_issuer,
                            "aud": settings.jwt_audience, "iat": now, "exp": now + 3600},
                           KEY, algorithm="EdDSA")
        return {"Authorization": f"Bearer {token}"}

    def call(self, method: str, path: str, h: dict[str, str], body: Any = None) -> Any:
        r = self.c.request(method, f"/v1{path}", headers=h, json=body)
        if r.status_code >= 400:
            raise SystemExit(f"{method} {path} -> {r.status_code}: {r.text}")
        return r.json()

    def product(self, h: dict[str, str], **fields: Any) -> dict[str, Any]:
        return self.call("POST", "/products", h, fields)

    def campaign(self, h: dict[str, str], product: dict[str, Any], slug: str, headline: str,
                 summary: str, story: str, publish: bool = True,
                 offer: dict[str, int] = OFFER) -> dict[str, Any]:
        pid = product["id"]
        if publish:
            self.call("POST", f"/products/{pid}/paypal/onboarding", h)
            self.call("POST", f"/products/{pid}/verification/demo", h, {"months": VERIFIED_MONTHS})
        cmp = self.call("POST", "/campaigns", h, {"product_id": pid, "slug": slug, "headline": headline,
                                                  "summary": summary, "story": story, **offer})
        return self.call("POST", f"/campaigns/{cmp['id']}/publish", h) if publish else cmp

    def buy(self, campaign_id: str, h: dict[str, str], code: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"kind": "referral" if code else "founding"}
        if code:
            body["referral_code"] = code
        order = self.call("POST", f"/campaigns/{campaign_id}/orders", h, body)
        return self.call("POST", f"/orders/{order['id']}/capture", h)

    def backer(self, n: int) -> dict[str, str]:
        first = FIRST_NAMES[n % len(FIRST_NAMES)]
        h = self.user(f"demo_backer_{n:02d}", f"{first.lower()}.{n}@demo.backit.club",
                      f"{first} {LAST_NAMES[n % len(LAST_NAMES)]}")
        self.call("PATCH", "/me", h, {"payout_email": f"{first.lower()}.{n}@personal.example.com"})
        return h

    def pay_out(self, h: dict[str, str], product_id: str) -> None:
        self.call("POST", f"/products/{product_id}/dev/release-holds", h)
        preview = self.call("POST", f"/products/{product_id}/payout-previews", h)
        if preview["total_cents"] > 0:
            self.call("POST", f"/payout-previews/{preview['id']}/approve", h,
                      {"digest": preview["digest"], "funding_confirmed": True})
            worker.run_once()


def reset() -> None:
    with engine.begin() as conn:
        tables = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'app' "
            "AND tablename NOT IN ('alembic_version', 'profiles')"
        )).scalars().all()
        conn.execute(text("TRUNCATE " + ", ".join(f"app.{t}" for t in tables) + " CASCADE"))
        conn.execute(text(r"DELETE FROM app.profiles WHERE id LIKE 'demo\_%'"))


HISTORY_DAYS = 70
DEMO_SLUGS = ("ledgerly", "shipnote", "tallybook", "shiplog")


def spread_history(start: datetime, end: datetime) -> None:
    """Map every app timestamp in [start, end] onto the past ten weeks, keeping their order."""
    now = datetime.now(UTC)
    new_start, new_end = now - timedelta(days=HISTORY_DAYS), now - timedelta(days=1)
    scale = (new_end - new_start).total_seconds() / max((end - start).total_seconds(), 1)
    params = {"t0": start.timestamp(), "a": new_start.timestamp(), "k": scale, "s": start, "e": end}
    with engine.begin() as conn:
        cols = conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'app' AND data_type LIKE 'timestamp%'"
        )).all()
        for table, col in cols:
            conn.execute(text(
                f'UPDATE app."{table}" SET "{col}" = '  # noqa: S608 (names from information_schema)
                f'to_timestamp(:a + (extract(epoch FROM "{col}") - :t0) * :k) '
                f'WHERE "{col}" BETWEEN :s AND :e'
            ), params)


def demo_window() -> tuple[datetime, datetime] | None:
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT min(p.created_at), max(o.created_at) FROM app.products p "
            "JOIN app.campaigns c ON c.product_id = p.id "
            "LEFT JOIN app.orders o ON o.campaign_id = c.id WHERE c.slug IN :slugs"
        ).bindparams(bindparam("slugs", expanding=True)), {"slugs": list(DEMO_SLUGS)}).first()
    if not row or row[0] is None:
        return None
    return row[0] - timedelta(minutes=2), row[1] + timedelta(minutes=2)


def seed(owner: Profile) -> None:
    app.dependency_overrides[get_key_source] = _KeySource
    webhooks_out.send = _fake_send  # type: ignore[assignment]
    with TestClient(app) as client:
        s = Seeder(client)
        me = s.user(owner.id, owner.email, owner.display_name)
        if not owner.payout_email:
            s.call("PATCH", "/me", me, {"payout_email": owner.email})

        # The owner's own products: one live campaign, one draft, one without a campaign.
        ledgerly = s.product(
            me, name="Ledgerly", url="https://ledgerly.example.com",
            description="Bookkeeping for solo founders. Connects to Stripe and PayPal, sorts every "
                        "transaction, and hands your accountant a clean ledger at tax time.",
            access_terms="Lifetime access to Ledgerly Pro, including every future update.",
            refund_terms="Full refund within 30 days, no questions asked.",
            webhook_url="https://ledgerly.example.com/webhooks/backit")
        lc = s.campaign(
            me, ledgerly, "ledgerly", "Back Ledgerly and never dread tax season again",
            "Founding backers get lifetime Pro for a one-time price and earn a reward for every "
            "friend who buys.",
            LEDGERLY_STORY, offer=LEDGERLY_OFFER)
        codes = [s.buy(lc["id"], s.backer(n))["backing"]["referral_code"] for n in range(1, 13)]
        # Early referrals clear the hold and get paid out; later ones stay on hold.
        for n, code in zip(range(13, 17), [codes[0], codes[0], codes[2], codes[4]], strict=True):
            s.buy(lc["id"], s.backer(n), code)
        s.pay_out(me, ledgerly["id"])
        for n, code in zip(range(17, 21), [codes[0], codes[1], codes[2], codes[6]], strict=True):
            s.buy(lc["id"], s.backer(n), code)
        refunded = s.buy(lc["id"], s.backer(21), codes[3])
        s.call("POST", f"/orders/{refunded['id']}/refund", me)

        shipnote = s.product(
            me, name="Shipnote", url="https://shipnote.example.com",
            description="Release notes that write themselves from your merged pull requests.",
            access_terms="Lifetime access to the Team plan for up to 10 seats.",
            refund_terms="Full refund within 30 days.")
        s.campaign(me, shipnote, "shipnote", "Back Shipnote: release notes people actually read",
                   "Founding backers lock in the Team plan for life.",
                   SHIPNOTE_STORY, publish=False)

        s.product(me, name="Pagecraft", url="https://pagecraft.example.com",
                  description="A landing page builder for indie apps, with built-in waitlists.",
                  access_terms="Lifetime access to Pagecraft Plus.")

        # Campaigns the owner backs: founding backer #7 of Tallybook, referred customer of Shiplog.
        maya = s.user("demo_builder_maya", "maya@tallybook.example.com", "Maya Lin")
        tally = s.product(
            maya, name="Tallybook", url="https://tallybook.example.com",
            description="Invoicing for indie hackers: send, chase and reconcile invoices in minutes.",
            access_terms="Lifetime access to Tallybook Pro.",
            refund_terms="Full refund within 30 days.",
            webhook_url="https://tallybook.example.com/webhooks/backit")
        tc = s.campaign(maya, tally, "tallybook", "Invoicing for indie hackers",
                        "Get paid faster with invoices that chase themselves.",
                        TALLYBOOK_STORY)
        for n in range(31, 37):
            s.buy(tc["id"], s.backer(n))
        my_code = s.buy(tc["id"], me)["backing"]["referral_code"]
        for n in range(37, 40):
            s.buy(tc["id"], s.backer(n), my_code)
        s.pay_out(maya, tally["id"])
        for n in range(40, 42):
            s.buy(tc["id"], s.backer(n), my_code)

        leo = s.user("demo_builder_leo", "leo@shiplog.example.com", "Leo Brandt")
        shiplog = s.product(
            leo, name="Shiplog", url="https://shiplog.example.com",
            description="Changelogs your users read, embedded right inside your app.",
            access_terms="Lifetime access to Shiplog Growth.",
            webhook_url="https://shiplog.example.com/webhooks/backit")
        sc = s.campaign(leo, shiplog, "shiplog", "Changelogs your users read",
                        "Turn every release into a reason for users to come back.",
                        SHIPLOG_STORY)
        friend_code = s.buy(sc["id"], s.backer(51))["backing"]["referral_code"]
        for n in range(52, 55):
            s.buy(sc["id"], s.backer(n))
        s.buy(sc["id"], me, friend_code)
        worker.run_once()
    app.dependency_overrides.clear()


DEMO_STORIES = {"ledgerly": LEDGERLY_STORY, "shipnote": SHIPNOTE_STORY,
                "tallybook": TALLYBOOK_STORY, "shiplog": SHIPLOG_STORY}


def refresh_stories() -> None:
    """Rewrite demo campaign stories in place, through the normal update service."""
    from app.models import Campaign, Product
    from app.schemas import CampaignUpdate
    from app.services import campaigns as campaign_service

    with SessionLocal() as db:
        for slug, story in DEMO_STORIES.items():
            campaign = db.scalar(select(Campaign).where(Campaign.slug == slug).with_for_update())
            if campaign is None or campaign.story == story:
                continue
            product = db.get(Product, campaign.product_id)
            owner = db.get(Profile, product.owner_id) if product else None
            if owner is None:
                continue
            campaign_service.update_campaign(db, owner, campaign, CampaignUpdate(story=story))
            print(f"Refreshed the {slug} story.")
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed BackIt demo data.")
    parser.add_argument("--owner-email", help="email of a profile that has signed in once")
    parser.add_argument("--reset", action="store_true", help="wipe BackIt app data before seeding")
    parser.add_argument("--backdate", action="store_true",
                        help="only spread existing demo data over the past ten weeks")
    parser.add_argument("--refresh-stories", action="store_true",
                        help="only rewrite demo campaign stories with the current Markdown copy")
    args = parser.parse_args()

    if get_settings().environment != "development":
        raise SystemExit("Refusing to seed outside ENVIRONMENT=development.")
    if args.refresh_stories:
        refresh_stories()
        return
    if args.backdate:
        window = demo_window()
        if window is None:
            raise SystemExit("No demo data to backdate.")
        if window[1] - window[0] > timedelta(hours=2):
            raise SystemExit("Demo data already spans more than two hours; it looks backdated already.")
        spread_history(*window)
        print("Spread demo history over the past ten weeks.")
        return
    if not args.owner_email:
        parser.error("--owner-email is required unless --backdate is set")
    if args.reset:
        reset()
    with SessionLocal() as db:
        owner = db.scalars(select(Profile).where(Profile.email == args.owner_email)).first()
        if owner is None:
            raise SystemExit(f"No profile for {args.owner_email}. Sign in to the web app once first.")
        if db.execute(text("SELECT 1 FROM app.campaigns WHERE slug = 'ledgerly'")).first():
            raise SystemExit("Demo data already exists. Re-run with --reset to start over.")
    started = datetime.now(UTC) - timedelta(seconds=5)
    seed(owner)
    spread_history(started, datetime.now(UTC) + timedelta(seconds=5))
    print(f"Seeded demo data for {owner.display_name} <{owner.email}>.")


if __name__ == "__main__":
    main()
