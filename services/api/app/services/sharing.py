"""Share-draft generation for backers. AI writes copy; the disclosure is always appended by code."""

import json
import re

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Backing, Campaign, Product, Profile
from app.money import format_usd
from app.presenters import share_url
from app.providers import ai
from app.schemas import ShareDraft, ShareDraftIn, ShareDraftsOut

LIMITS = {"x": 280, "linkedin": 1200, "email": 2000}
_BANNED = re.compile(r"\b(invest(ment|or)?s?|roi|returns?|equity|shares? in|guaranteed)\b", re.I)


class _Drafts(BaseModel):
    drafts: list[str] = Field(min_length=1, max_length=3)


def disclosure(campaign: Campaign, *, short: bool) -> str:
    if short:
        return f"(I earn a {campaign.commission_bps / 100:g}% referral commission.)"
    return (
        f"Disclosure: I'm a backer and earn a {campaign.commission_bps / 100:g}% referral commission "
        "if you buy through my link. This is a product purchase, not an investment."
    )


def generate_share_drafts(db: Session, user: Profile, backing: Backing, campaign: Campaign,
                          product: Product, body: ShareDraftIn) -> ShareDraftsOut:
    url = share_url(campaign.slug, backing.referral_code)
    disc = disclosure(campaign, short=body.channel == "x")
    budget = LIMITS[body.channel] - len(url) - len(disc) - 4
    discount = f"{campaign.referral_discount_bps / 100:g}% off"

    def template() -> _Drafts:
        if body.channel == "x":
            texts = [
                f"I backed {product.name}: {campaign.headline}. Get {discount} with my link",
                f"Early supporter of {product.name}. If it fits your workflow, {discount} here",
            ]
        elif body.channel == "linkedin":
            texts = [
                f"I'm a founding supporter of {product.name}. {campaign.summary} "
                f"If it sounds useful, you can get {discount} through my link.",
            ]
        else:
            texts = [
                f"Subject: Thought you'd like {product.name}\n\nHi,\n\nI've been backing "
                f"{product.name}. {campaign.summary}\n\nYou get {discount} "
                f"(list price {format_usd(campaign.referral_list_price_cents)}) with my link.",
            ]
        return _Drafts(drafts=[t[:budget] for t in texts])

    def check(out: _Drafts) -> None:
        for text in out.drafts:
            if len(text) > budget:
                raise ValueError("draft too long")
            if _BANNED.search(text):
                raise ValueError("draft contains investment language")

    facts = {
        "channel": body.channel, "product": product.name, "headline": campaign.headline,
        "summary": campaign.summary, "discount": discount, "max_chars": budget,
        "backer_context": body.context or "",
    }
    out, source, _ = ai.generate(
        db, purpose="share_drafts", prompt_version="share_drafts.v1", actor_id=user.id,
        system=(
            "Write 2 short, honest share posts for a product the user personally backed. "
            "Do not include links or disclosures (they are appended automatically). "
            "Never describe it as an investment or promise returns. Respect max_chars."
        ),
        user=json.dumps(facts), schema=_Drafts, fallback=template, post_validate=check,
    )
    db.commit()
    drafts = [ShareDraft(channel=body.channel, text=f"{text.strip()} {url}\n\n{disc}")
              for text in out.drafts]
    return ShareDraftsOut(drafts=drafts, source=source)
