from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DB

from app import schemas as s
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import DUMMY_HASH, hasher, verify_password
from app.db import get_db, now
from app.models import (
    CareSession,
    ConsentEvent,
    EntryAnalysis,
    Factor,
    Journal,
    User,
    WeeklyReview,
)
from app.services.common import (
    COOKIE,
    consent_provider_key,
    current_ai_consent,
    current_user,
    find_session,
    hit_limit,
    invalidate,
    new_session,
    require_session,
)
from app.services.privacy import ledger_event

router = APIRouter()


@router.get("/auth/session", response_model=s.SessionOut)
def session_info(request: Request, response: Response, db: DB = Depends(get_db)):
    session = find_session(request, db)
    if not session:
        session = new_session(db, response)
    user = db.get(User, session.user_id) if session.user_id else None
    return {"user": user, "csrf_token": session.csrf_token}


@router.post("/auth/register", response_model=s.SessionOut, status_code=201)
def register(
    data: s.Register,
    response: Response,
    request: Request,
    session=Depends(require_session),
    db: DB = Depends(get_db),
):
    hit_limit("register:" + request.client.host, 3600, 20)
    user = User(
        email=str(data.email).lower(),
        password_hash=hasher.hash(data.password),
        nickname=(data.nickname or "").strip() or None,
        terms_version=data.terms_version,
        privacy_version=data.privacy_version,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "ACCOUNT_EXISTS", "该邮箱无法注册，请尝试登录") from None
    session = new_session(db, response, session, user.id)
    return {"user": user, "csrf_token": session.csrf_token}


@router.post("/auth/login", response_model=s.SessionOut)
def login(
    data: s.Login,
    request: Request,
    response: Response,
    session=Depends(require_session),
    db: DB = Depends(get_db),
):
    key = "login:" + request.client.host
    hit_limit(key, 900, 10, consume=False)
    user = db.scalar(
        select(User).where(User.email == str(data.email).lower(), User.status == "active")
    )
    valid = verify_password(user.password_hash if user else DUMMY_HASH, data.password)
    if not user or not valid:
        hit_limit(key, 900, 10)
        raise AppError(401, "AUTH_REQUIRED", "邮箱或密码不正确")
    session = new_session(db, response, session, user.id)
    return {"user": user, "csrf_token": session.csrf_token}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: DB = Depends(get_db)):
    session = find_session(request, db)
    if session:
        require_session(request, db)
        db.delete(session)
    response.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=s.UserOut)
def me(user=Depends(current_user)):
    return user


@router.patch("/me", response_model=s.UserOut)
def update_me(data: s.ProfilePatch, user=Depends(current_user), db: DB = Depends(get_db)):
    if "nickname" in data.model_fields_set:
        user.nickname = (data.nickname or "").strip() or None
    if data.timezone and data.timezone != user.timezone:
        user.timezone = data.timezone
        invalidate(db, user)
    return user


@router.get("/me/consents", response_model=s.ConsentHistory)
def consents(user=Depends(current_user), db: DB = Depends(get_db)):
    events = db.scalars(
        select(ConsentEvent)
        .where(ConsentEvent.user_id == user.id)
        .order_by(ConsentEvent.occurred_at)
    ).all()
    return {
        "ai_enabled": user.ai_enabled,
        "consent_version": user.consent_version,
        "events": [
            {
                "action": e.action,
                "policy_version": e.policy_version,
                "provider_key": e.provider_key,
                "purpose": e.purpose,
                "occurred_at": e.occurred_at,
            }
            for e in events
        ],
    }


@router.put("/me/consents/ai", response_model=s.ConsentOut)
def consent(data: s.ConsentIn, user=Depends(current_user), db: DB = Depends(get_db)):
    replacing = data.enabled and user.ai_enabled and not current_ai_consent(db, user)
    if data.enabled != user.ai_enabled or (data.enabled and not current_ai_consent(db, user)):
        if not data.enabled:
            ledger_event("revoke_ai", user.id, db=db)
        user.ai_enabled = data.enabled
        user.consent_version += 1
        db.add(
            ConsentEvent(
                user_id=user.id,
                action="granted" if data.enabled else "revoked",
                policy_version=data.policy_version,
                provider_key=consent_provider_key(),
            )
        )
        invalidate(db, user, all_analyses=not data.enabled or replacing)
    return {"ai_enabled": user.ai_enabled, "consent_version": user.consent_version}


@router.get("/me/export")
def export(user=Depends(current_user), db: DB = Depends(get_db)):
    # Serialize against a stable user-locked snapshot: all relevant mutations acquire this lock.
    db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        db.scalar(select(func.count()).select_from(Journal).where(Journal.user_id == user.id))
        > 10000
    ):
        raise AppError(422, "EXPORT_LIMIT_EXCEEDED", "记录超过首版导出上限，请联系部署维护者")
    entries = db.scalars(select(Journal).where(Journal.user_id == user.id)).all()
    analyses = db.scalars(select(EntryAnalysis).where(EntryAnalysis.user_id == user.id)).all()
    analysis_data = []
    for a in analyses:
        analysis_data.append(
            {
                **{
                    k: getattr(a, k)
                    for k in (
                        "id",
                        "journal_id",
                        "journal_version",
                        "summary",
                        "reflection_question",
                        "created_at",
                    )
                },
                "factors": [
                    s.FactorOut.model_validate(f).model_dump(mode="json")
                    for f in db.scalars(select(Factor).where(Factor.analysis_id == a.id))
                ],
            }
        )
    payload = {
        "schema_version": "v1",
        "exported_at": now(),
        "user": s.UserOut.model_validate(user),
        "consents": consents(user, db),
        "journals": [s.JournalOut.model_validate(e) for e in entries],
        "analyses": analysis_data,
        "care_sessions": [
            s.CareOut.model_validate(c)
            for c in db.scalars(select(CareSession).where(CareSession.user_id == user.id))
        ],
        "reviews": [
            s.ReviewOut.model_validate(r)
            for r in db.scalars(select(WeeklyReview).where(WeeklyReview.user_id == user.id))
        ],
    }
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse

    return JSONResponse(
        jsonable_encoder(payload),
        headers={"Content-Disposition": 'attachment; filename="emotion-diary-export.json"'},
    )


@router.delete("/me", status_code=204)
def delete_account(
    data: s.DeleteAccount, response: Response, user=Depends(current_user), db: DB = Depends(get_db)
):
    if not verify_password(user.password_hash, data.password):
        raise AppError(401, "AUTH_REQUIRED", "密码不正确")
    ledger_event("delete_account", user.id, db=db)
    db.execute(delete(CareSession).where(CareSession.user_id == user.id))
    db.delete(user)
    response.delete_cookie(COOKIE, path="/")


@router.get("/metadata", response_model=s.MetadataOut)
def metadata():
    settings = get_settings()
    return {
        "emotions": [{"code": code, "label": label} for code, label in s.EMOTIONS.items()],
        "event_tags": [{"code": code, "label": label} for code, label in s.TAGS.items()],
        "scores": ["很不好", "不太好", "一般", "还不错", "很好"],
        "terms_version": "v1",
        "privacy_version": "v1",
        "ai_policy_version": "v1",
        "ai_available": settings.ai_enabled and settings.ai_provider != "disabled",
        "ai_mode": settings.ai_provider,
        "ai_description": settings.ai_policy_description,
    }
