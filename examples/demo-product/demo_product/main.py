"""Demo builder product: receives signed BackIt webhooks and manages entitlements."""

import hashlib
import hmac
import html
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

TOLERANCE_SECONDS = 300
MAX_BODY_BYTES = 64 * 1024


def _secret() -> str:
    secret = os.environ.get("BACKIT_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="BACKIT_WEBHOOK_SECRET is not configured")
    return secret


def _backit_api() -> str:
    return os.environ.get("BACKIT_API_URL", "http://localhost:8001").rstrip("/")


def _product_id() -> str:
    product_id = os.environ.get("BACKIT_PRODUCT_ID", "")
    if not product_id:
        raise HTTPException(status_code=503, detail="BACKIT_PRODUCT_ID is not configured")
    return product_id


def _app_name() -> str:
    return os.environ.get("APP_NAME", "Ledgerly")


def _campaign_url() -> str:
    return os.environ.get("CAMPAIGN_URL", "https://www.backit.club/explore")


def mask_email(value: str | None) -> str | None:
    """These lists are public on the hosted test app, so emails are only hinted at."""
    if not value or "@" not in value:
        return value
    name, domain = value.split("@", 1)
    return f"{name[:1]}***@{domain}"


INDEX_HTML = (Path(__file__).parent / "static" / "index.html").read_text()


def _db_path() -> Path:
    return Path(os.environ.get("DEMO_DB_PATH", Path(__file__).resolve().parents[1] / "demo.sqlite3"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS entitlements (
    order_id TEXT PRIMARY KEY,
    buyer_email TEXT,
    plan_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
    granted_at TEXT NOT NULL,
    revoked_at TEXT,
    claimed_by TEXT
);
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    order_id TEXT,
    outcome TEXT NOT NULL,
    received_at TEXT NOT NULL
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(entitlements)")}
        if "claimed_by" not in columns:  # databases created before claim codes
            conn.execute("ALTER TABLE entitlements ADD COLUMN claimed_by TEXT")


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def expected_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = f"{timestamp}.".encode() + raw_body
    return "v1=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify(secret: str, timestamp: str | None, signature: str | None, raw_body: bytes,
           now: float | None = None) -> bool:
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs((time.time() if now is None else now) - ts) > TOLERANCE_SECONDS:
        return False
    # The header may carry several comma-separated signatures during key rotation.
    expected = expected_signature(secret, timestamp, raw_body)
    return any(hmac.compare_digest(expected, s.strip()) for s in signature.split(","))


@asynccontextmanager
async def lifespan(_: FastAPI):  # type: ignore[no-untyped-def]
    init_db()
    yield


app = FastAPI(title="BackIt demo product", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class WebhookAck(BaseModel):
    received: bool
    duplicate: bool = False
    outcome: str


class Entitlement(BaseModel):
    order_id: str
    buyer_email: str | None
    plan_id: str | None
    status: str
    granted_at: str
    revoked_at: str | None
    claimed_by: str | None = None


class ClaimIn(BaseModel):
    code: str
    user_ref: str


class ClaimOut(BaseModel):
    status: str
    order_id: str
    plan_id: str
    user_ref: str
    badge_number: int | None = None


def redeem_with_backit(code: str, user_ref: str) -> dict[str, Any]:
    """Server-to-server call; the webhook secret never reaches the browser."""
    body = json.dumps({"product_id": _product_id(), "code": code, "user_ref": user_ref}).encode()
    req = urllib.request.Request(  # noqa: S310 - URL comes from operator config
        f"{_backit_api()}/v1/claims/redeem", data=body, method="POST",
        headers={"Authorization": f"Bearer {_secret()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:  # noqa: S310
            return json.loads(res.read())
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read())["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = "BackIt rejected the code"
        raise HTTPException(status_code=exc.code, detail=message) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail="Can't reach BackIt") from exc


class ProcessedEvent(BaseModel):
    event_id: str
    event_type: str
    order_id: str | None
    outcome: str
    received_at: str


def _apply(conn: sqlite3.Connection, event_type: str, data: dict[str, Any]) -> str:
    order_id = data.get("order_id")
    if event_type == "ping":
        return "pong"
    if event_type == "purchase.completed" and order_id:
        conn.execute(
            """INSERT INTO entitlements (order_id, buyer_email, plan_id, status, granted_at)
               VALUES (?, ?, ?, 'active', ?)
               ON CONFLICT(order_id) DO NOTHING""",
            (order_id, data.get("buyer_email"), data.get("plan_id"), now_iso()),
        )
        return "granted"
    if event_type == "refund.issued" and order_id:
        cur = conn.execute(
            "UPDATE entitlements SET status = 'revoked', revoked_at = ? WHERE order_id = ? AND status = 'active'",
            (now_iso(), order_id),
        )
        return "revoked" if cur.rowcount else "no_entitlement"
    return "ignored"


@app.post("/webhooks/backit")
async def backit_webhook(
    request: Request,
    timestamp: Annotated[str | None, Header(alias="BackIt-Timestamp")] = None,
    signature: Annotated[str | None, Header(alias="BackIt-Signature")] = None,
    header_event_id: Annotated[str | None, Header(alias="BackIt-Event-Id")] = None,
) -> WebhookAck:
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    if not verify(_secret(), timestamp, signature, raw):
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        event = json.loads(raw)
        event_id = str(event["id"])
        event_type = str(event["type"])
        data = event.get("data") or {}
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed event") from exc
    if header_event_id and header_event_id != event_id:
        raise HTTPException(status_code=400, detail="Event id mismatch")

    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        seen = conn.execute("SELECT outcome FROM events WHERE event_id = ?", (event_id,)).fetchone()
        if seen:
            return WebhookAck(received=True, duplicate=True, outcome=seen["outcome"])
        outcome = _apply(conn, event_type, data)
        conn.execute(
            "INSERT INTO events (event_id, event_type, order_id, outcome, received_at) VALUES (?, ?, ?, ?, ?)",
            (event_id, event_type, data.get("order_id"), outcome, now_iso()),
        )
    return WebhookAck(received=True, outcome=outcome)


@app.post("/claims")
def claim(body: ClaimIn) -> ClaimOut:
    result = redeem_with_backit(body.code, body.user_ref)
    with connect() as conn:
        conn.execute(
            """INSERT INTO entitlements (order_id, buyer_email, plan_id, status, granted_at, claimed_by)
               VALUES (?, ?, ?, 'active', ?, ?)
               ON CONFLICT(order_id) DO UPDATE SET claimed_by = excluded.claimed_by""",
            (result["order_id"], result.get("buyer_email"), result["plan_id"], now_iso(), result["user_ref"]),
        )
    return ClaimOut(status=result["status"], order_id=result["order_id"], plan_id=result["plan_id"],
                    user_ref=result["user_ref"], badge_number=result.get("badge_number"))


@app.get("/entitlements")
def list_entitlements() -> list[Entitlement]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM entitlements ORDER BY granted_at DESC").fetchall()
    return [
        Entitlement(**{**dict(r), "buyer_email": mask_email(r["buyer_email"]),
                       "claimed_by": mask_email(r["claimed_by"])})
        for r in rows
    ]


@app.get("/events")
def list_events(limit: int = 50) -> list[ProcessedEvent]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY received_at DESC LIMIT ?", (max(1, min(limit, 200)),)
        ).fetchall()
    return [ProcessedEvent(**dict(r)) for r in rows]


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return INDEX_HTML.replace("__APP_NAME__", html.escape(_app_name())).replace(
        "__CAMPAIGN_URL__", html.escape(_campaign_url(), quote=True)
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "backit-demo-product", "webhook": "/webhooks/backit"}
