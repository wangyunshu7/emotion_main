from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from app import schemas as s
from app.core.config import get_settings
from app.core.errors import AppError, conflict
from app.core.security import fingerprint
from app.db import get_db
from app.models import EntryAnalysis, Factor, Job, Journal, WeeklyReview
from app.services.common import (
    current_ai_consent,
    current_user,
    date_range,
    hit_limit,
    invalidate,
    owned,
)
from app.services.statistics import insights

router = APIRouter()


def job_view(job):
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "attempt": job.attempt,
        "error_code": job.error_code,
        "result": {
            "type": "analysis" if job.kind == "entry_analysis" else "weekly_review",
            "id": job.result_id,
        }
        if job.status == "succeeded" and job.result_id
        else None,
    }


def enqueue(db, user, kind, meta, resource_id=None):
    key = fingerprint({"kind": kind, "meta": meta, "resource_id": resource_id})
    existing = db.scalar(
        select(Job).where(
            Job.user_id == user.id,
            Job.kind == kind,
            Job.dedupe_key == key,
            Job.status.in_(["queued", "running"]),
        )
    )
    if existing:
        return {"job_id": existing.id, "status": existing.status}
    if kind == "entry_analysis":
        settings = get_settings()
        hit_limit(f"ai-hour:{user.id}", 3600, settings.ai_user_hourly_limit)
        hit_limit(f"ai-day:{user.id}", 86400, settings.ai_user_daily_limit)
    job = Job(
        user_id=user.id,
        kind=kind,
        input_meta=meta,
        resource_id=resource_id,
        dedupe_key=key,
        max_attempts=get_settings().ai_max_attempts,
    )
    db.add(job)
    db.flush()
    return {"job_id": job.id, "status": job.status}


@router.post(
    "/journals/{identifier}/analysis-jobs",
    response_model=s.JobReceipt | s.ReusedAnalysis,
    status_code=202,
)
def analyze(
    identifier: UUID,
    data: s.AnalysisRequest,
    response: Response,
    user=Depends(current_user),
    db: DB = Depends(get_db),
):
    entry = owned(db, Journal, identifier, user.id)
    if entry.version != data.journal_version:
        conflict()
    if not current_ai_consent(db, user):
        raise AppError(
            403,
            "AI_CONSENT_REQUIRED",
            "请先阅读并授权 AI 处理；服务变更后需在设置中撤回旧授权并重新授权",
        )
    existing = db.scalar(
        select(EntryAnalysis).where(
            EntryAnalysis.user_id == user.id,
            EntryAnalysis.journal_id == identifier,
            EntryAnalysis.journal_version == entry.version,
            EntryAnalysis.consent_version == user.consent_version,
        )
    )
    if existing:
        response.status_code = 200
        return {"analysis_id": existing.id, "reused": True}
    if not entry.body.strip():
        raise AppError(
            422, "EMPTY_BODY_FOR_ANALYSIS", "只有情绪选择时无需 AI 整理，可以直接查看统计"
        )
    settings = get_settings()
    if not settings.ai_enabled or settings.ai_provider == "disabled":
        raise AppError(503, "AI_UNAVAILABLE", "当前部署未启用 AI；记录与关怀活动仍可使用")
    return enqueue(
        db,
        user,
        "entry_analysis",
        {"journal_version": entry.version, "consent_version": user.consent_version},
        identifier,
    )


@router.get("/jobs/{identifier}", response_model=s.JobOut)
def job(identifier: UUID, user=Depends(current_user), db: DB = Depends(get_db)):
    return job_view(owned(db, Job, identifier, user.id))


@router.post("/jobs/{identifier}/cancel", response_model=s.JobOut)
def cancel(identifier: UUID, user=Depends(current_user), db: DB = Depends(get_db)):
    row = owned(db, Job, identifier, user.id)
    if row.status in {"queued", "running"}:
        row.status, row.lease_token = "cancelled", None
    return job_view(row)


@router.get("/journals/{identifier}/analysis", response_model=s.AnalysisOut)
def analysis(identifier: UUID, user=Depends(current_user), db: DB = Depends(get_db)):
    owned(db, Journal, identifier, user.id)
    row = db.scalar(
        select(EntryAnalysis).where(
            EntryAnalysis.user_id == user.id, EntryAnalysis.journal_id == identifier
        )
    )
    if not row:
        from app.core.errors import missing

        missing()
    return {
        **{
            k: getattr(row, k)
            for k in (
                "id",
                "journal_id",
                "journal_version",
                "summary",
                "reflection_question",
                "created_at",
            )
        },
        "factors": db.scalars(select(Factor).where(Factor.analysis_id == row.id)).all(),
    }


@router.patch("/analyses/{identifier}/factors/{factor_id}", response_model=s.FactorOut)
def factor(
    identifier: UUID,
    factor_id: UUID,
    data: s.FactorPatch,
    user=Depends(current_user),
    db: DB = Depends(get_db),
):
    row = owned(db, EntryAnalysis, identifier, user.id)
    item = db.scalar(select(Factor).where(Factor.id == factor_id, Factor.analysis_id == row.id))
    if not item:
        from app.core.errors import missing

        missing()
    item.review_status, item.user_text = data.review_status, data.user_text
    invalidate(db, user)
    db.flush()
    return item


@router.get("/insights", response_model=s.InsightsOut)
def statistics(
    start_date: date | None = None,
    end_date: date | None = None,
    user=Depends(current_user),
    db: DB = Depends(get_db),
):
    start, end = date_range(user, start_date, end_date)
    return insights(db, user, start, end)


@router.post("/reviews", response_model=s.JobReceipt | s.ReusedReview, status_code=202)
def review(
    data: s.ReviewRequest, response: Response, user=Depends(current_user), db: DB = Depends(get_db)
):
    meta = {
        "start_date": data.start_date.isoformat(),
        "end_date": data.end_date.isoformat(),
        "timezone": user.timezone,
        "data_version": user.data_version,
        "consent_version": user.consent_version,
        "prompt_version": "review.v1",
    }
    mark = fingerprint(meta)
    existing = db.scalar(
        select(WeeklyReview).where(
            WeeklyReview.user_id == user.id, WeeklyReview.input_fingerprint == mark
        )
    )
    if existing:
        response.status_code = 200
        return {"review_id": existing.id, "reused": True}
    return enqueue(db, user, "weekly_review", meta)


@router.get("/reviews", response_model=s.Page[s.ReviewOut])
def reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(current_user),
    db: DB = Depends(get_db),
):
    query = select(WeeklyReview).where(WeeklyReview.user_id == user.id)
    return {
        "items": db.scalars(
            query.order_by(WeeklyReview.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all(),
        "total": db.scalar(
            select(func.count()).select_from(WeeklyReview).where(WeeklyReview.user_id == user.id)
        ),
        "page": page,
        "page_size": page_size,
    }


@router.get("/reviews/{identifier}", response_model=s.ReviewOut)
def review_detail(identifier: UUID, user=Depends(current_user), db: DB = Depends(get_db)):
    return owned(db, WeeklyReview, identifier, user.id)
