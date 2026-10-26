from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from app import schemas as s
from app.core.errors import AppError, conflict
from app.core.security import fingerprint
from app.db import get_db
from app.models import CareSession, Journal
from app.services.common import current_user, date_range, invalidate, owned, utc_bounds
from app.services.privacy import ledger_event

router = APIRouter()


@router.post("/journals", response_model=s.JournalOut, status_code=201)
def create(
    data: s.JournalCreate, response: Response, user=Depends(current_user), db: DB = Depends(get_db)
):
    payload = data.model_dump(mode="json")
    mark = fingerprint(payload)
    existing = db.scalar(
        select(Journal).where(
            Journal.user_id == user.id, Journal.client_request_id == data.client_request_id
        )
    )
    if existing:
        if existing.request_fingerprint != mark:
            conflict("REQUEST_ID_REUSED", "同一请求标识不能提交不同内容")
        response.status_code = 200
        return existing
    item = Journal(
        **{**payload, "client_request_id": data.client_request_id, "occurred_at": data.occurred_at},
        user_id=user.id,
        request_fingerprint=mark,
    )
    db.add(item)
    invalidate(db, user)
    db.flush()
    return item


@router.get("/journals", response_model=s.Page[s.JournalSummary])
def listing(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: date | None = None,
    end_date: date | None = None,
    emotion_code: str | None = None,
    tag_code: str | None = None,
    tag_label: str | None = None,
    user=Depends(current_user),
    db: DB = Depends(get_db),
):
    filters = [Journal.user_id == user.id]
    if start_date or end_date:
        start, end = date_range(user, start_date, end_date)
        lo, hi = utc_bounds(user, start, end)
        filters.extend([Journal.occurred_at >= lo, Journal.occurred_at < hi])
    if emotion_code:
        if emotion_code not in s.EMOTIONS and emotion_code != "custom":
            raise AppError(422, "VALIDATION_ERROR", "无效情绪")
        filters.append(Journal.emotions.contains([{"code": emotion_code}]))
    if tag_code:
        if tag_code not in s.TAGS and tag_code != "custom":
            raise AppError(422, "VALIDATION_ERROR", "无效标签")
        if tag_code == "custom" and not tag_label:
            raise AppError(422, "VALIDATION_ERROR", "自定义标签需提供名称")
        filters.append(
            Journal.event_tags.contains(
                [{"code": tag_code, **({"label": tag_label} if tag_label else {})}]
            )
        )
    total = db.scalar(select(func.count()).select_from(Journal).where(*filters))
    rows = db.scalars(
        select(Journal)
        .where(*filters)
        .order_by(Journal.occurred_at.desc(), Journal.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                **{
                    k: getattr(j, k)
                    for k in (
                        "id",
                        "mood_score",
                        "emotions",
                        "event_tags",
                        "occurred_at",
                        "version",
                    )
                },
                "body_preview": j.body[:80],
            }
            for j in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/journals/{identifier}", response_model=s.JournalOut)
def detail(identifier: UUID, user=Depends(current_user), db: DB = Depends(get_db)):
    return owned(db, Journal, identifier, user.id)


@router.patch("/journals/{identifier}", response_model=s.JournalOut)
def edit(
    identifier: UUID, data: s.JournalPatch, user=Depends(current_user), db: DB = Depends(get_db)
):
    item = owned(db, Journal, identifier, user.id)
    if item.version != data.version:
        conflict()
    merged = {k: getattr(item, k) for k in s.JournalFields.model_fields}
    merged.update(data.model_dump(exclude_unset=True, exclude={"version"}))
    try:
        checked = s.JournalFields.model_validate(merged)
    except ValidationError:
        raise AppError(422, "VALIDATION_ERROR", "请检查记录内容或时间") from None
    for key, value in checked.model_dump().items():
        setattr(item, key, value)
    item.version += 1
    invalidate(db, user, item.id)
    db.flush()
    return item


@router.delete("/journals/{identifier}", status_code=204)
def remove(
    identifier: UUID,
    version: int = Query(..., ge=1),
    user=Depends(current_user),
    db: DB = Depends(get_db),
):
    item = owned(db, Journal, identifier, user.id)
    if item.version != version:
        conflict()
    ledger_event("delete_journal", user.id, item.id, db=db)
    for care in db.scalars(
        select(CareSession).where(CareSession.user_id == user.id, CareSession.journal_id == item.id)
    ):
        care.journal_id = None
    db.flush()
    invalidate(db, user, item.id)
    db.delete(item)
