import logging
import threading
import time
import uuid
from datetime import date, timedelta

from sqlalchemy import delete, select, update

from app.ai.budget import reserve, settle
from app.ai.provider import ProviderError, generate, needs_support
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import fingerprint
from app.db import SessionLocal, now
from app.models import (
    EntryAnalysis,
    Factor,
    Job,
    Journal,
    RateLimit,
    Session,
    Usage,
    User,
    WeeklyReview,
)
from app.services.common import current_ai_consent, hit_limit, ranged_journals
from app.services.privacy import replay_ledger
from app.services.statistics import insights

log = logging.getLogger("emotion.worker")


def claim():
    settings = get_settings()
    with SessionLocal.begin() as db:
        expired = db.scalars(
            select(Job)
            .where(Job.status == "running", Job.lease_until < now())
            .with_for_update(skip_locked=True)
        ).all()
        for job in expired:
            job.status = "queued" if job.attempt < job.max_attempts else "failed"
            job.error_code, job.lease_token = "WORKER_LOST", None
        db.flush()
        job = db.scalar(
            select(Job)
            .where(Job.status == "queued", Job.available_at <= now())
            .order_by(Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        job.status, job.lease_token = "running", uuid.uuid4()
        job.lease_until = now() + timedelta(seconds=settings.job_lease_seconds)
        job.attempt += 1
        db.flush()
        return job


def heartbeat(job, stop):
    settings = get_settings()
    while not stop.wait(settings.job_heartbeat_seconds):
        with SessionLocal.begin() as db:
            db.execute(
                update(Job)
                .where(
                    Job.id == job.id, Job.status == "running", Job.lease_token == job.lease_token
                )
                .values(lease_until=now() + timedelta(seconds=settings.job_lease_seconds))
            )


def valid_user(db, job, lock=False):
    statement = select(User).where(User.id == job.user_id, User.status == "active")
    if lock:
        statement = statement.with_for_update()
    user = db.scalar(statement)
    if not user or user.consent_version != job.input_meta["consent_version"]:
        return None
    if job.kind == "entry_analysis":
        entry = db.scalar(
            select(Journal).where(Journal.id == job.resource_id, Journal.user_id == user.id)
        )
        if (
            not current_ai_consent(db, user)
            or not entry
            or entry.version != job.input_meta["journal_version"]
        ):
            return None
    elif (
        user.data_version != job.input_meta["data_version"]
        or user.timezone != job.input_meta["timezone"]
    ):
        return None
    return user


def prepare(job):
    with SessionLocal() as db:
        user = valid_user(db, job)
        if not user:
            raise ProviderError("INPUT_STALE")
        if job.kind == "entry_analysis":
            entry = db.get(Journal, job.resource_id)
            if needs_support(entry.body):
                raise ProviderError("SAFETY_REDIRECT")
            return {
                "schema_version": "entry_analysis.v1",
                "locale": "zh-CN",
                "entry": {
                    "mood_score": entry.mood_score,
                    "emotions": [x["label"] for x in entry.emotions],
                    "event_tags": [x["label"] for x in entry.event_tags],
                    "body": entry.body,
                },
            }, None
        start, end = (
            date.fromisoformat(job.input_meta["start_date"]),
            date.fromisoformat(job.input_meta["end_date"]),
        )
        stats = insights(db, user, start, end)
        entries = ranged_journals(db, user, start, end)
        ai_status = "insufficient" if stats["recorded_days"] < 3 else "disabled"
        if (
            stats["recorded_days"] >= 3
            and current_ai_consent(db, user)
            and get_settings().ai_enabled
            and get_settings().ai_provider != "disabled"
        ):
            ai_status = "pending"
        selected = (
            entries
            if len(entries) <= 30
            else [entries[round(i * (len(entries) - 1) / 29)] for i in range(30)]
        )
        identifiers = [e.id for e in selected]
        factors = db.scalars(
            select(Factor)
            .join(EntryAnalysis, Factor.analysis_id == EntryAnalysis.id)
            .where(
                EntryAnalysis.user_id == user.id,
                EntryAnalysis.journal_id.in_(identifiers),
                Factor.review_status.in_(["matches", "partial"]),
            )
        ).all()
        payload = {
            "statistics": stats,
            "sampled": len(entries) > 30 or any(len(e.body) > 800 for e in selected),
            "total_entries": len(entries),
            "selected_entries": len(selected),
            "entries": [
                {"journal_id": str(e.id), "body": e.body[:800], "mood_score": e.mood_score}
                for e in selected
            ],
            "confirmed_factors": [f.user_text or f.hypothesis for f in factors],
        }
        if any(needs_support(e.body) for e in entries):
            ai_status = "safety_blocked"
        return payload, {"statistics": stats, "ai_status": ai_status}


def validate_observations(result, payload):
    references = {e["journal_id"]: e["body"] for e in payload["entries"]}
    allowed_stats = {"entry_count", "recorded_days", "mean_score"}
    observations = []
    for observation in result.observations:
        okay = True
        for evidence in observation.evidence:
            if evidence.journal_id:
                okay &= bool(
                    evidence.quote
                    and evidence.quote in references.get(str(evidence.journal_id), "")
                )
            elif evidence.stat_path:
                okay &= evidence.stat_path in allowed_stats
            else:
                okay = False
        if okay:
            observations.append(observation.model_dump(mode="json"))
    return observations


def save_result(job, payload, result, review_info):
    with SessionLocal.begin() as db:
        user = valid_user(db, job, lock=True)
        row = db.scalar(select(Job).where(Job.id == job.id).with_for_update())
        if not row or row.status != "running" or row.lease_token != job.lease_token:
            return
        if not user:
            row.status, row.lease_token = "cancelled", None
            return
        if job.kind == "entry_analysis":
            entry = db.get(Journal, job.resource_id)
            analysis = EntryAnalysis(
                user_id=user.id,
                journal_id=entry.id,
                journal_version=entry.version,
                consent_version=user.consent_version,
                summary=result.summary,
                reflection_question=result.reflection_question,
                provider_key=get_settings().ai_provider,
                model_key=get_settings().ai_model or "fake",
            )
            db.add(analysis)
            db.flush()
            for f in result.factors:
                if f.evidence_quote in entry.body:
                    db.add(Factor(analysis_id=analysis.id, **f.model_dump()))
            row.result_id = analysis.id
        else:
            narrative = result.narrative if result else None
            if narrative and payload.get("sampled"):
                narrative = "本回顾仅参考部分记录或正文片段。" + narrative
            review = WeeklyReview(
                user_id=user.id,
                start_date=date.fromisoformat(job.input_meta["start_date"]),
                end_date=date.fromisoformat(job.input_meta["end_date"]),
                timezone=user.timezone,
                source_data_version=user.data_version,
                consent_version=user.consent_version,
                input_fingerprint=fingerprint(job.input_meta),
                statistics=review_info["statistics"],
                insight_eligible=review_info["statistics"]["recorded_days"] >= 3,
                narrative=narrative,
                observations=validate_observations(result, payload) if result else [],
                ai_status=review_info["ai_status"],
            )
            db.add(review)
            db.flush()
            row.result_id = review.id
        row.status, row.error_code, row.lease_token = "succeeded", None, None


def fail(job, error):
    with SessionLocal.begin() as db:
        row = db.scalar(select(Job).where(Job.id == job.id).with_for_update())
        if not row or row.status != "running" or row.lease_token != job.lease_token:
            return
        row.error_code, row.lease_token = error.code, None
        if error.code in {"INPUT_STALE", "AI_CONSENT_REQUIRED"}:
            row.status = "cancelled"
        elif error.retryable and row.attempt < row.max_attempts:
            row.status, row.available_at = "queued", now() + timedelta(seconds=5)
        else:
            row.status = "failed"


def run_once():
    job = claim()
    if not job:
        return False
    stop = threading.Event()
    thread = threading.Thread(target=heartbeat, args=(job, stop), daemon=True)
    thread.start()
    reservation = None
    try:
        payload, review_info = prepare(job)
        result = None
        call_model = job.kind == "entry_analysis" or review_info["ai_status"] == "pending"
        if call_model:
            try:
                if job.kind == "weekly_review":
                    hit_limit(f"ai-hour:{job.user_id}", 3600, get_settings().ai_user_hourly_limit)
                    hit_limit(f"ai-day:{job.user_id}", 86400, get_settings().ai_user_daily_limit)
                reservation = reserve(job, payload)
                result, usage = generate(job.kind, payload)
                settle(reservation, usage)
                reservation = None
                if review_info:
                    review_info["ai_status"] = "succeeded"
            except (ProviderError, AppError) as exc:
                if job.kind == "entry_analysis":
                    raise
                review_info["ai_status"] = (
                    "safety_blocked" if exc.code == "SAFETY_REDIRECT" else "failed"
                )
        save_result(job, payload, result, review_info)
    except ProviderError as exc:
        fail(job, exc)
    except Exception as exc:
        log.error("job=%s exception_type=%s", job.id, type(exc).__name__)
        fail(job, ProviderError("WORKER_ERROR"))
    finally:
        try:
            settle(reservation)
        finally:
            stop.set()
            thread.join(timeout=2)
    return True


def maintenance():
    replay_ledger()
    with SessionLocal.begin() as db:
        db.execute(delete(Session).where(Session.expires_at < now()))
        db.execute(delete(RateLimit).where(RateLimit.expires_at < now()))
        db.execute(
            delete(Usage).where(
                Usage.created_at < now() - timedelta(days=30), Usage.status != "reserved"
            )
        )
        db.execute(
            delete(Job).where(
                Job.status.in_(["succeeded", "failed", "cancelled"]),
                Job.updated_at < now() - timedelta(days=7),
            )
        )


def main():
    logging.basicConfig(level=get_settings().log_level)
    heartbeat_path = get_settings().privacy_ledger_root.parent / "worker-heartbeat"
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    last_maintenance = 0
    while True:
        try:
            heartbeat_path.write_text(now().isoformat(), encoding="utf-8")
            if time.monotonic() - last_maintenance > 60:
                maintenance()
                last_maintenance = time.monotonic()
            if not run_once():
                time.sleep(1)
        except KeyboardInterrupt:
            return
        except Exception as exc:
            log.error("worker loop exception_type=%s", type(exc).__name__)
            time.sleep(2)


if __name__ == "__main__":
    main()
