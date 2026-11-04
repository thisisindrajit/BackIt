from fastapi import APIRouter
from sqlalchemy import func, select, update

from app.deps import CurrentUserDep, DBDep
from app.ids import iso, utcnow
from app.models import Notification
from app.schemas import MarkNotificationsRead, NotificationList, NotificationOut

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


def _list(db: DBDep, user_id: str) -> NotificationList:
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(30)
    ).all()
    unread = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None))) or 0
    return NotificationList(
        items=[
            NotificationOut(id=n.id, kind=n.kind, title=n.title, body=n.body, link=n.link,  # type: ignore[arg-type]
                            read=n.read_at is not None, created_at=iso(n.created_at) or "")
            for n in rows
        ],
        unread_count=unread,
    )


@router.get("")
def list_notifications(user: CurrentUserDep, db: DBDep) -> NotificationList:
    return _list(db, user.id)


@router.post("/read")
def mark_read(body: MarkNotificationsRead, user: CurrentUserDep, db: DBDep) -> NotificationList:
    """Mark the given notifications read, or all of them when `ids` is omitted."""
    query = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if body.ids is not None:
        query = query.where(Notification.id.in_(body.ids))
    db.execute(query.values(read_at=utcnow()))
    db.commit()
    return _list(db, user.id)
