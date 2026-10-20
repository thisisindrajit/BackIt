from fastapi import APIRouter, status
from sqlalchemy import select

from app.deps import CurrentUserDep, DBDep, IdempotencyKeyHeader
from app.models import PayoutBatch
from app.presenters import batch_out, preview_out
from app.schemas import ApproveIn, PayoutBatchOut, PayoutPreviewOut, ReleasedOut
from app.services import payouts
from app.services.common import owned_product
from app.services.idempotency import run_idempotent

router = APIRouter(tags=["payouts"])


@router.post("/products/{product_id}/payout-previews", status_code=status.HTTP_201_CREATED)
def create_payout_preview(product_id: str, user: CurrentUserDep, db: DBDep) -> PayoutPreviewOut:
    product = owned_product(db, product_id, user, lock=True)
    return preview_out(payouts.create_preview(db, user, product))


@router.get("/payout-previews/{preview_id}")
def get_payout_preview(preview_id: str, user: CurrentUserDep, db: DBDep) -> PayoutPreviewOut:
    preview, product = payouts.owned_preview(db, user, preview_id)
    return preview_out(payouts.refresh_preview(db, preview, product))


@router.post("/payout-previews/{preview_id}/approve", status_code=status.HTTP_201_CREATED)
def approve_payout_preview(
    preview_id: str,
    body: ApproveIn,
    user: CurrentUserDep,
    db: DBDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> PayoutBatchOut:
    def action() -> tuple[int, PayoutBatchOut]:
        batch = payouts.approve(db, user, preview_id, body)
        return 201, batch_out(db, batch)

    return run_idempotent(  # type: ignore[return-value]
        db, user_id=user.id, scope=f"approve:{preview_id}", key=idempotency_key,
        body=body.model_dump(), action=action,
    )


@router.get("/payout-batches/{batch_id}")
def get_payout_batch(batch_id: str, user: CurrentUserDep, db: DBDep) -> PayoutBatchOut:
    return batch_out(db, payouts.visible_batch(db, user, batch_id))


@router.get("/products/{product_id}/payout-batches")
def list_payout_batches(product_id: str, user: CurrentUserDep, db: DBDep) -> list[PayoutBatchOut]:
    product = owned_product(db, product_id, user)
    batches = db.scalars(
        select(PayoutBatch).where(PayoutBatch.product_id == product.id)
        .order_by(PayoutBatch.approved_at.desc())
    ).all()
    return [batch_out(db, b) for b in batches]


@router.post("/products/{product_id}/dev/release-holds")
def dev_release_holds(product_id: str, user: CurrentUserDep, db: DBDep) -> ReleasedOut:
    product = owned_product(db, product_id, user, lock=True)
    return ReleasedOut(released=payouts.dev_release_holds(db, user, product))
