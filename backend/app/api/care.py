from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from app import schemas as s
from app.core.errors import AppError, conflict, missing
from app.core.security import fingerprint
from app.db import get_db, now
from app.models import Activity, CareSession, Journal, SupportResource
from app.services.common import current_user, invalidate, owned

router = APIRouter()


def available():
    return (Activity.status == "published", Activity.review_due_at > now())


def activity_out(item):
    return s.ActivityOut.model_validate(item).model_dump(mode="json")


def find_activity(db, identifier):
    item = db.scalar(select(Activity).where(Activity.id == identifier, *available()))
    if not item:
        missing()
    return item


@router.get("/activities", response_model=s.Page[s.ActivitySummary])
def activities(
    type: s.ActivityType | None = None,
    scene: s.Scene | None = None,
    max_minutes: int | None = Query(None, ge=1, le=60),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(current_user),
    db: DB = Depends(get_db),
):
    filters = list(available())
    if type:
        filters.append(Activity.type == type)
    if scene and scene != "any":
        filters.append(Activity.scenes.contains([scene]) | Activity.scenes.contains(["any"]))
    if max_minutes:
        filters.append(Activity.duration_minutes <= max_minutes)
    return {
        "items": db.scalars(
            select(Activity)
            .where(*filters)
            .order_by(Activity.duration_minutes, Activity.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all(),
        "total": db.scalar(select(func.count()).select_from(Activity).where(*filters)),
        "page": page,
        "page_size": page_size,
    }


@router.get("/activities/{identifier}", response_model=s.ActivityOut)
def activity(identifier: UUID, user=Depends(current_user), db: DB = Depends(get_db)):
    return activity_out(find_activity(db, identifier))


@router.post("/care/recommendations", response_model=s.RecommendationOut)
def recommend(data: s.RecommendationIn, user=Depends(current_user), db: DB = Depends(get_db)):
    if data.journal_id:
        owned(db, Journal, data.journal_id, user.id)
    rows = db.scalars(
        select(Activity).where(
            *available(),
            Activity.duration_minutes <= data.available_minutes,
            Activity.type.not_in(data.excluded_types),
        )
    ).all()
    rows = [a for a in rows if data.scene == "any" or data.scene in a.scenes or "any" in a.scenes]
    recent = set(
        db.scalars(
            select(CareSession.activity_id)
            .where(CareSession.user_id == user.id)
            .order_by(CareSession.started_at.desc())
            .limit(5)
        )
    )
    rows.sort(key=lambda a: (a.id in recent, a.duration_minutes, str(a.id)))
    return {
        "items": [
            {
                "activity": a,
                "reason": f"符合本次时间与场景条件，约 {a.duration_minutes} 分钟可完成。",
            }
            for a in rows[:3]
        ],
        "empty_reason": None if rows else "暂时没有符合条件的已审核活动，可以调整时长或场景。",
    }


@router.post("/care/sessions", response_model=s.CareOut, status_code=201)
def create_session(
    data: s.CareCreate, response: Response, user=Depends(current_user), db: DB = Depends(get_db)
):
    mark = fingerprint(data.model_dump(mode="json"))
    existing = db.scalar(
        select(CareSession).where(
            CareSession.user_id == user.id, CareSession.client_request_id == data.client_request_id
        )
    )
    if existing:
        if existing.request_fingerprint != mark:
            conflict("REQUEST_ID_REUSED", "同一请求标识不能提交不同内容")
        response.status_code = 200
        return existing
    activity = find_activity(db, data.activity_id)
    if data.journal_id:
        owned(db, Journal, data.journal_id, user.id)
    row = CareSession(
        **data.model_dump(),
        user_id=user.id,
        request_fingerprint=mark,
        activity_snapshot=activity_out(activity),
    )
    db.add(row)
    db.flush()
    return row


@router.get("/care/sessions", response_model=s.Page[s.CareOut])
def sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    user=Depends(current_user),
    db: DB = Depends(get_db),
):
    filters = [CareSession.user_id == user.id]
    if status:
        if status not in {"running", "paused", "completed", "stopped"}:
            raise AppError(422, "VALIDATION_ERROR", "无效活动状态")
        filters.append(CareSession.status == status)
    return {
        "items": db.scalars(
            select(CareSession)
            .where(*filters)
            .order_by(CareSession.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all(),
        "total": db.scalar(select(func.count()).select_from(CareSession).where(*filters)),
        "page": page,
        "page_size": page_size,
    }


@router.get("/care/sessions/{identifier}", response_model=s.CareOut)
def session_detail(identifier: UUID, user=Depends(current_user), db: DB = Depends(get_db)):
    return owned(db, CareSession, identifier, user.id)


@router.patch("/care/sessions/{identifier}/state", response_model=s.CareOut)
def state(
    identifier: UUID, data: s.CareState, user=Depends(current_user), db: DB = Depends(get_db)
):
    row = owned(db, CareSession, identifier, user.id)
    if row.version != data.version:
        conflict()
    allowed = {"running": {"paused", "completed", "stopped"}, "paused": {"running", "stopped"}}
    if data.status not in allowed.get(row.status, set()):
        conflict("INVALID_TRANSITION", "当前活动状态不能执行此操作")
    wall = (now() - row.started_at).total_seconds()
    since = (now() - row.updated_at).total_seconds() if row.status == "running" else 0
    if data.elapsed_seconds < row.elapsed_seconds or data.elapsed_seconds > min(
        wall + 5, row.elapsed_seconds + since + 5
    ):
        raise AppError(422, "VALIDATION_ERROR", "活动时长不符合实际经过时间")
    if row.status == "paused" and data.elapsed_seconds != row.elapsed_seconds:
        raise AppError(422, "VALIDATION_ERROR", "暂停期间不能累计活动时长")
    row.status, row.elapsed_seconds = data.status, data.elapsed_seconds
    row.version += 1
    row.updated_at = now()
    if data.status in {"completed", "stopped"}:
        row.ended_at = now()
        invalidate(db, user)
    db.flush()
    return row


@router.put("/care/sessions/{identifier}/feedback", response_model=s.CareOut)
def feedback(
    identifier: UUID, data: s.Feedback, user=Depends(current_user), db: DB = Depends(get_db)
):
    row = owned(db, CareSession, identifier, user.id)
    if row.version != data.version:
        conflict()
    if row.status not in {"completed", "stopped"}:
        conflict("INVALID_TRANSITION", "活动结束后可以填写反馈")
    for k, v in data.model_dump(exclude_unset=True, exclude={"version"}).items():
        setattr(row, k, v)
    row.version += 1
    invalidate(db, user)
    db.flush()
    return row


@router.get("/support-resources", response_model=s.SupportList)
def support(region: str = Query("CN", max_length=16), db: DB = Depends(get_db)):
    rows = db.scalars(
        select(SupportResource).where(
            SupportResource.region_code == region,
            SupportResource.status == "published",
            SupportResource.review_due_at > now(),
        )
    ).all()
    return {
        "items": [
            {
                k: getattr(r, k)
                for k in (
                    "id",
                    "title",
                    "description",
                    "contact_text",
                    "url",
                    "source_url",
                    "verified_at",
                )
            }
            for r in rows
        ],
        "generic_support_text": "如果你此刻需要支持，可以联系可信任的人，或寻求当地专业与紧急支持。这里不提供实时监护。",
    }
