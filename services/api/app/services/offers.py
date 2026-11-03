"""AI offer advisor: suggests founding and referral terms, validated by the same rules as a real offer.

The model proposes numbers and explains them. Every number is checked with `offer_problems`,
and all projections are computed here with the server's money helpers, never by the model.
"""

import json
import re

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Product, Profile
from app.money import format_usd, offer_problems, quote_founding, quote_referral
from app.presenters import latest_verification
from app.providers import ai
from app.schemas import OfferProjection, OfferReasons, OfferSuggestion, ProductFacts
from app.services.campaigns import DEFAULT_OFFER, PRICE_FIELDS
from app.services.common import campaign_for_product

_PRICE_RE = re.compile(r"\$\s?(\d{1,5}(?:\.\d{2})?)")
_AMOUNT_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?")


class _Idea(BaseModel):
    founding_price_cents: int = Field(ge=100, le=1_000_000)
    founding_spots_cap: int = Field(ge=10, le=1000)
    referral_list_price_cents: int = Field(ge=100, le=1_000_000)
    referral_discount_bps: int = Field(ge=0, le=5000)
    commission_bps: int = Field(ge=0, le=5000)
    founding_price_reason: str = Field(max_length=240)
    spots_reason: str = Field(max_length=240)
    list_price_reason: str = Field(max_length=240)
    discount_reason: str = Field(max_length=240)
    commission_reason: str = Field(max_length=240)


def _charm(cents: int) -> int:
    """Round to a whole-dollar price ending in 9 ($89, $149), never below $1."""
    dollars = max(1, round(cents / 100))
    if dollars >= 10:
        dollars = dollars - dollars % 10 + 9
    return dollars * 100


def _guess_list_price(product: Product | ProductFacts, notes: str | None, hint: int | None) -> int:
    if hint:
        return hint
    for text in (notes or "", product.description, product.access_terms):
        m = _PRICE_RE.search(text)
        if m:
            cents = round(float(m.group(1)) * 100)
            if 100 <= cents <= 1_000_000:
                return cents
    return DEFAULT_OFFER["referral_list_price_cents"]


def _avg_monthly_revenue(db: Session, product_id: str) -> int | None:
    v = latest_verification(db, product_id)
    if v is None or not v.months:
        return None
    values = [m if isinstance(m, int) else m.get("amount_cents", 0) for m in v.months]
    return round(sum(values) / len(values)) if values else None


def projection(offer: dict[str, int], fee_bps: int) -> OfferProjection:
    f = quote_founding(offer["founding_price_cents"], fee_bps)
    r = quote_referral(offer["referral_list_price_cents"], offer["referral_discount_bps"],
                       offer["commission_bps"], fee_bps)
    spots = offer["founding_spots_cap"]
    founding_keep = f.amount_cents - f.platform_fee_cents
    referral_keep = r.amount_cents - r.commission_cents - r.platform_fee_cents
    return OfferProjection(
        founding_keep_cents=founding_keep,
        all_spots_keep_cents=founding_keep * spots,
        friend_pays_cents=r.amount_cents,
        backer_earns_cents=r.commission_cents,
        referral_keep_cents=referral_keep,
        one_friend_each_keep_cents=(founding_keep + referral_keep) * spots,
        one_friend_each_backers_cents=r.commission_cents * spots,
    )


def suggest_offer(db: Session, user: Profile, product: Product | ProductFacts, notes: str | None,
                  list_price_hint: int | None) -> OfferSuggestion:
    fee_bps = get_settings().platform_fee_bps
    saved = isinstance(product, Product)
    existing = campaign_for_product(db, product.id) if saved else None
    current = {f: getattr(existing, f) for f in PRICE_FIELDS} if existing else None
    if list_price_hint is None and current:
        list_price_hint = current["referral_list_price_cents"]
    list_price = _guess_list_price(product, notes, list_price_hint)
    mrr = _avg_monthly_revenue(db, product.id) if saved else None

    def valid(o: dict[str, int]) -> bool:
        return not offer_problems(o["founding_price_cents"], o["referral_list_price_cents"],
                                  o["referral_discount_bps"], o["commission_bps"], fee_bps)

    def fallback() -> _Idea:
        offer = {
            "founding_price_cents": _charm(round(list_price * 0.6)),
            "founding_spots_cap": 100,
            "referral_list_price_cents": list_price,
            "referral_discount_bps": 2000,
            "commission_bps": 2500,
        }
        if offer["founding_price_cents"] >= list_price or not valid(offer):
            offer = dict(DEFAULT_OFFER)
        return _Idea(
            **offer,
            founding_price_reason="About 40% off the regular price: a clear reward for backing early.",
            spots_reason="100 spots is scarce enough to feel founding, and enough to fund real progress.",
            list_price_reason="Your regular price, so referred buyers see an honest discount.",
            discount_reason="20% off is a strong enough nudge for friends without undercutting the product.",
            commission_reason="25% of what the friend pays makes sharing worth it for backers.",
        )

    def check(o: _Idea) -> None:
        offer = o.model_dump(include=set(PRICE_FIELDS))
        if not valid(offer):
            raise ValueError("suggested offer fails validation")
        if o.founding_price_cents >= o.referral_list_price_cents:
            raise ValueError("founding price must be below the list price")
        p = projection(offer, fee_bps)
        allowed = {format_usd(v) for v in (*offer.values(), *p.model_dump().values(), list_price)}
        allowed |= {a.replace(".00", "") for a in allowed}
        text = " ".join((o.founding_price_reason, o.spots_reason, o.list_price_reason,
                         o.discount_reason, o.commission_reason))
        for amount in _AMOUNT_RE.findall(text):
            if amount not in allowed:
                raise ValueError(f"reason mentions unknown amount {amount}")

    facts = {
        "product": product.name,
        "description": product.description,
        "what_buyers_get": product.access_terms,
        "builder_notes": (notes or "")[:3000],
        "regular_price_hint": format_usd(list_price),
        "average_monthly_revenue": format_usd(mrr) if mrr is not None else "unknown",
        "current_offer": current,
        "platform_fee_percent": fee_bps / 100,
        "limits": "prices $1 to $10,000 in cents; spots 10 to 1000; discount and commission 0 to 5000 bps; "
                  "commission + platform fee must stay below the discounted price",
    }
    out, source, _ = ai.generate(
        db,
        purpose="offer_advice",
        prompt_version="offer_advice.v1",
        actor_id=user.id,
        system=(
            "You are a pricing advisor for indie software builders running a founding-backer campaign on BackIt. "
            "Founding backers pay once for lifetime access and a numbered badge; each gets a referral link. "
            "Friends buying through it pay the list price minus a discount, and the backer earns a commission "
            "on what the friend pays. Suggest terms that reward early backers, give friends a real reason to buy, "
            "make sharing worthwhile, and still leave the builder most of each sale. "
            "Use the regular price hint as the list price unless the notes clearly state another price. "
            "The founding price must be below the list price. All prices are integer cents, percentages are "
            "basis points (2000 = 20%). Each reason is one short sentence in plain words for the builder; "
            "only mention dollar amounts that are part of your suggestion."
        ),
        user=json.dumps(facts, default=str),
        schema=_Idea,
        fallback=fallback,
        post_validate=check,
    )
    offer = out.model_dump(include=set(PRICE_FIELDS))
    return OfferSuggestion(
        **offer,
        reasons=OfferReasons(
            founding_price=out.founding_price_reason,
            spots=out.spots_reason,
            list_price=out.list_price_reason,
            discount=out.discount_reason,
            commission=out.commission_reason,
        ),
        projection=projection(offer, fee_bps),
        platform_fee_bps=fee_bps,
        source=source,
    )
