import hashlib
import secrets
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DB

from app.core.config import get_settings
from app.core.errors import AppError, missing
from app.core.security import digest
from app.db import SessionLocal, get_db, now
from app.models import (
    ConsentEvent,
    EntryAnalysis,
    Job,
    Journal,
    RateLimit,
    Session,
    User,
    WeeklyReview,
)

COOKIE = "emotion_session"


def consent_provider_key():
    settings = get_settings()
    if settings.ai_provider in {"fake", "disabled"}:
        return settings.ai_provider
    signature = hashlib.sha256(
        (
            settings.ai_base_url + "|" + settings.ai_model + "|" + settings.ai_policy_description
        ).encode()
    ).hexdigest()[:24]
    return settings.ai_provider + ":" + signature


def current_ai_consent(db, user):
    if not user.ai_enabled:
        return False
    event = db.scalar(
        select(ConsentEvent)
        .where(ConsentEvent.user_id == user.id)
        .order_by(ConsentEvent.occurred_at.desc(), ConsentEvent.id.desc())
        .limit(1)
    )
    return bool(
        event
        and event.action == "granted"
        and event.policy_version == "v1"
        and event.provider_key == consent_provider_key()
    )


def find_session(request: Request, db: DB):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    return db.scalar(
        select(Session).where(Session.token_hash == digest(token), Session.expires_at > now())
    )


def require_session(request: Request, db: DB = Depends(get_db)):
    session = find_session(request, db)
    if not session:
        raise AppError(401, "AUTH_REQUIRED", "请先登录")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        token = request.headers.get("x-csrf-token", "")
        if (
            not secrets.compare_digest(token, session.csrf_token)
            or request.headers.get("origin") not in get_settings().origins
        ):
            raise AppError(403, "CSRF_INVALID", "会话校验失败，请刷新页面")
    return session


def current_user(
    request: Request, session: Session = Depends(require_session), db: DB = Depends(get_db)
):
    if not session.user_id:
        raise AppError(401, "AUTH_REQUIRED", "请先登录")
    statement = select(User).where(User.id == session.user_id, User.status == "active")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        statement = statement.with_for_update()
    user = db.scalar(statement.execution_options(populate_existing=True))
    if not user:
        raise AppError(401, "SESSION_EXPIRED", "登录已失效")
    return user


def new_session(db, response: Response, old=None, user_id=None):
    if old:
        db.delete(old)
    raw = secrets.token_urlsafe(32)
    session = Session(
        token_hash=digest(raw),
        csrf_token=secrets.token_urlsafe(32),
        user_id=user_id,
        expires_at=now() + timedelta(seconds=get_settings().session_ttl_seconds),
    )
    db.add(session)
    db.flush()
    response.set_cookie(
        COOKIE,
        raw,
        max_age=get_settings().session_ttl_seconds,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )
    return session


def owned(db, model, resource_id: UUID, user_id):
    item = db.scalar(select(model).where(model.id == resource_id, model.user_id == user_id))
    if not item:
        missing()
    return item


def clean_jobs(db, user_id, kind, resource_id=None):
    filters = [Job.user_id == user_id, Job.kind == kind]
    if resource_id:
        filters.append(Job.resource_id == resource_id)
    db.execute(delete(Job).where(*filters, Job.status.in_(["succeeded", "failed", "cancelled"])))
    jobs = db.scalars(select(Job).where(*filters, Job.status.in_(["queued", "running"]))).all()
    for job in jobs:
        job.status, job.result_id, job.lease_token = "cancelled", None, None


def invalidate(db, user, journal_id=None, all_analyses=False):
    user.data_version += 1
    clean_jobs(db, user.id, "weekly_review")
    db.execute(delete(WeeklyReview).where(WeeklyReview.user_id == user.id))
    if journal_id or all_analyses:
        clean_jobs(db, user.id, "entry_analysis", journal_id)
        query = delete(EntryAnalysis).where(EntryAnalysis.user_id == user.id)
        if journal_id:
            query = query.where(EntryAnalysis.journal_id == journal_id)
        db.execute(query)


def date_range(user, start: date | None, end: date | None):
    if (start is None) != (end is None):
        raise AppError(422, "VALIDATION_ERROR", "起止日期必须同时提供")
    if start is None:
        end = now().astimezone(ZoneInfo(user.timezone)).date()
        start = end - timedelta(days=6)
    if not 0 <= (end - start).days <= 30:
        raise AppError(422, "VALIDATION_ERROR", "日期范围必须为 1～31 天")
    return start, end


def utc_bounds(user, start, end):
    zone = ZoneInfo(user.timezone)
    return datetime.combine(start, time.min, zone).astimezone(timezone.utc), datetime.combine(
        end + timedelta(days=1), time.min, zone
    ).astimezone(timezone.utc)


def ranged_journals(db, user, start, end):
    lo, hi = utc_bounds(user, start, end)
    return db.scalars(
        select(Journal)
        .where(Journal.user_id == user.id, Journal.occurred_at >= lo, Journal.occurred_at < hi)
        .order_by(Journal.occurred_at, Journal.id)
    ).all()


def hit_limit(key: str, seconds: int, limit: int, consume=True):
    moment = now()
    epoch = int(moment.timestamp()) // seconds * seconds
    start = datetime.fromtimestamp(epoch, timezone.utc)
    bucket = digest(key, "rate")
    with SessionLocal.begin() as db:
        if consume:
            statement = insert(RateLimit).values(
                bucket_key=bucket,
                window_start=start,
                count=1,
                expires_at=start + timedelta(seconds=seconds),
            )
            count = db.scalar(
                statement.on_conflict_do_update(
                    index_elements=["bucket_key", "window_start"],
                    set_={"count": RateLimit.count + 1},
                ).returning(RateLimit.count)
            )
        else:
            count = (
                db.scalar(
                    select(RateLimit.count).where(
                        RateLimit.bucket_key == bucket, RateLimit.window_start == start
                    )
                )
                or 0
            )
    if count > limit or (not consume and count >= limit):
        raise AppError(429, "RATE_LIMITED", "请求较多，请稍后重试")
