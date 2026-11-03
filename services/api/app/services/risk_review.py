"""AI-assisted risk review of the backers in a payout preview.

Signals and the minimum risk level are computed by rules. The model may raise the level,
recommend a hold and explain the pattern, but it can never rate a backer safer than the
rules do, and it never moves money: the builder decides.
"""

import json
import re
from collections import Counter
from datetime import timedelta
from itertools import pairwise
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ids import utcnow
from app.models import Backing, Order, Profile, RiskFlag
from app.providers import ai

Level = Literal["low", "medium", "high"]
_RANK = {"low": 0, "medium": 1, "high": 2}
NEW_ACCOUNT_MINUTES = 60
BURST_SALES_24H = 5
FAST_GAP_MINUTES = 2
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


class _Assessment(BaseModel):
    backing_id: str
    level: Level
    recommendation: Literal["pay", "hold"]
    summary: str = Field(max_length=320)


class _Review(BaseModel):
    assessments: list[_Assessment]


def backer_signals(db: Session, backing_id: str) -> dict[str, Any]:
    """Facts about one backer's referred sales. Pure counts and durations, no judgement."""
    backing = db.get(Backing, backing_id)
    rows = db.execute(
        select(Order, Profile.created_at)
        .join(Profile, Profile.id == Order.buyer_id)
        .where(Order.referrer_backing_id == backing_id, Order.state.in_(("completed", "refunded")))
        .order_by(Order.completed_at)
    ).all()
    orders = [o for o, _ in rows]
    times = [o.completed_at for o in orders if o.completed_at]
    gaps = [(b - a).total_seconds() / 60 for a, b in pairwise(times)]
    payer_counts = Counter(o.payer_id for o in orders if o.payer_id)
    window = timedelta(minutes=NEW_ACCOUNT_MINUTES)
    new_accounts = sum(
        1 for o, joined in rows
        if o.completed_at and joined and timedelta(0) <= o.completed_at - joined <= window
    )
    since = utcnow() - timedelta(hours=24)
    first_sale_minutes = (
        round((times[0] - backing.created_at).total_seconds() / 60)
        if times and backing is not None else None
    )
    return {
        "referred_sales": len(orders),
        "refunded_sales": sum(1 for o in orders if o.state == "refunded"),
        "unique_buyers": len({o.buyer_id for o in orders}),
        "repeat_payer_accounts": sum(1 for n in payer_counts.values() if n > 1),
        "sales_last_24h": sum(1 for t in times if t >= since),
        "fastest_gap_minutes": round(min(gaps), 1) if gaps else None,
        "buyers_with_new_accounts": new_accounts,
        "first_sale_minutes_after_backing": first_sale_minutes,
        "open_flags": db.scalar(
            select(func.count(RiskFlag.id)).where(RiskFlag.backing_id == backing_id, RiskFlag.status == "open")
        ) or 0,
    }


def rule_assessment(s: dict[str, Any]) -> tuple[Level, list[str]]:
    """Deterministic floor: the level the AI may raise but never lower, plus the reasons."""
    level: Level = "low"
    reasons: list[str] = []

    def bump(to: Level, reason: str) -> None:
        nonlocal level
        reasons.append(reason)
        if _RANK[to] > _RANK[level]:
            level = to

    sales = s["referred_sales"]
    if s["open_flags"]:
        bump("high", f"{s['open_flags']} open risk flag(s) on this backer")
    if sales >= 2 and s["refunded_sales"] * 2 >= sales:
        bump("high", f"{s['refunded_sales']} of {sales} referred sales were refunded")
    elif s["refunded_sales"]:
        bump("low", f"{s['refunded_sales']} referred sale(s) refunded")
    if s["repeat_payer_accounts"]:
        bump("medium", "the same PayPal payer account bought more than once")
    if s["sales_last_24h"] >= BURST_SALES_24H:
        bump("medium", f"{s['sales_last_24h']} sales in the last 24 hours")
    if sales >= 3 and s["fastest_gap_minutes"] is not None and s["fastest_gap_minutes"] < FAST_GAP_MINUTES:
        bump("medium", f"two sales {s['fastest_gap_minutes']} minutes apart")
    if sales >= 3 and s["buyers_with_new_accounts"] * 5 >= sales * 4:
        bump("medium", f"{s['buyers_with_new_accounts']} of {sales} buyers signed up minutes before buying")
    if s["first_sale_minutes_after_backing"] is not None and s["first_sale_minutes_after_backing"] < 5:
        bump("low", "first referred sale came within 5 minutes of backing")
    return level, reasons


def _fallback_summary(name: str, sales: int, reasons: list[str]) -> str:
    noun = "sale" if sales == 1 else "sales"
    if not reasons:
        return f"{name}'s {sales} referred {noun} look normal: different buyers, no refunds, steady timing."
    return f"{name}: " + "; ".join(reasons) + "."


def review(db: Session, actor_id: str, items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    """Assess each payout item. Returns (assessments, source) or ([], None) when nothing to review."""
    if not items:
        return [], None
    facts: list[dict[str, Any]] = []
    floors: dict[str, tuple[Level, list[str]]] = {}
    for item in items:
        signals = backer_signals(db, item["backing_id"])
        floors[item["backing_id"]] = rule_assessment(signals)
        facts.append({
            "backing_id": item["backing_id"],
            "backer": item["backer_name"].split()[0] if item["backer_name"].strip() else "Backer",
            "rule_level": floors[item["backing_id"]][0],
            "rule_reasons": floors[item["backing_id"]][1],
            **signals,
        })

    allowed_numbers = {str(v) for f in facts for v in f.values() if isinstance(v, int | float)}
    allowed_numbers |= {str(int(v)) for f in facts for v in f.values() if isinstance(v, float)}
    allowed_numbers |= {str(n) for n in (24, BURST_SALES_24H, FAST_GAP_MINUTES, NEW_ACCOUNT_MINUTES, 5)}

    def check(out: _Review) -> None:
        ids = [a.backing_id for a in out.assessments]
        if sorted(ids) != sorted(floors):
            raise ValueError("assessments must cover each backer exactly once")
        for a in out.assessments:
            floor = floors[a.backing_id][0]
            if _RANK[a.level] < _RANK[floor]:
                raise ValueError("assessment is below the rule level")
            if a.level == "high" and a.recommendation != "hold":
                raise ValueError("high risk must recommend hold")
            for n in _NUMBER_RE.findall(a.summary):
                if n not in allowed_numbers:
                    raise ValueError(f"summary mentions unknown number {n}")

    def fallback() -> _Review:
        return _Review(assessments=[
            _Assessment(
                backing_id=f["backing_id"],
                level=floors[f["backing_id"]][0],
                recommendation="hold" if floors[f["backing_id"]][0] == "high" else "pay",
                summary=_fallback_summary(f["backer"], f["referred_sales"], floors[f["backing_id"]][1])[:320],
            )
            for f in facts
        ])

    out, source, _ = ai.generate(
        db,
        purpose="payout_risk_review",
        prompt_version="payout_risk_review.v1",
        actor_id=actor_id,
        system=(
            "You are a referral-fraud analyst for BackIt, where backers earn commission when friends buy "
            "through their link. Before the builder sends PayPal payouts, assess each backer from the facts. "
            "Look for patterns that suggest self-referral or fake buyers: bursts of sales, sales minutes apart, "
            "buyers whose accounts were created right before buying, repeat payer accounts, high refund rates. "
            "A few normal sales spread over days from different buyers is low risk. "
            "Rules: return one assessment per backing_id. Never choose a level below rule_level. "
            "High risk must recommend hold. Medium may recommend pay or hold; explain why. "
            "summary: at most 2 short sentences to the builder, plain words, first name only. "
            "Only use numbers that appear in the facts, never mention money amounts, "
            "never accuse; describe the pattern."
        ),
        user=json.dumps({"backers": facts}),
        schema=_Review,
        fallback=fallback,
        post_validate=check,
    )
    return [
        {**a.model_dump(), "signals": floors[a.backing_id][1]} for a in out.assessments
    ], source
