import json
from decimal import Decimal

from sqlalchemy import select, text

from app.ai.provider import ProviderError
from app.core.config import get_settings
from app.db import SessionLocal, now
from app.models import DailyCost, Usage, User
from app.services.common import current_ai_consent


def reserve(job, payload):
    settings = get_settings()
    if settings.ai_provider == "fake":
        return None
    day = now().date()
    # UTF-8 byte count is a deliberately conservative token ceiling for the serialized input.
    max_input = len(json.dumps(payload, ensure_ascii=False).encode()) + 4096
    amount = (
        Decimal(max_input) * Decimal(settings.ai_input_price_per_million)
        + Decimal(2048) * Decimal(settings.ai_output_price_per_million)
    ) / Decimal(1000000)
    with SessionLocal.begin() as db:
        user = db.scalar(
            select(User).where(
                User.id == job.user_id,
                User.ai_enabled.is_(True),
                User.consent_version == job.input_meta["consent_version"],
            )
        )
        if not user or not current_ai_consent(db, user):
            raise ProviderError("AI_CONSENT_REQUIRED")
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": day.toordinal()})
        total = db.get(DailyCost, day)
        if not total:
            total = DailyCost(budget_date=day, amount=Decimal(0))
            db.add(total)
        if total.amount + amount > Decimal(settings.ai_global_daily_budget):
            raise ProviderError("RATE_LIMITED")
        total.amount += amount
        item = Usage(
            user_id=job.user_id,
            job_id=job.id,
            attempt=job.attempt,
            budget_date=day,
            currency=settings.ai_price_currency,
            reserved_amount=amount,
            status="reserved",
        )
        db.add(item)
        db.flush()
        return item.id


def settle(identifier, usage=None):
    if not identifier:
        return
    settings = get_settings()
    with SessionLocal.begin() as db:
        item = db.get(Usage, identifier)
        if not item or item.status != "reserved":
            return
        cost = item.reserved_amount
        if usage and all(
            type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")
        ):
            cost = (
                Decimal(usage["input_tokens"]) * Decimal(settings.ai_input_price_per_million)
                + Decimal(usage["output_tokens"]) * Decimal(settings.ai_output_price_per_million)
            ) / Decimal(1000000)
            item.input_tokens, item.output_tokens = usage["input_tokens"], usage["output_tokens"]
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": item.budget_date.toordinal()}
        )
        total = db.get(DailyCost, item.budget_date)
        total.amount += cost - item.reserved_amount
        item.settled_amount, item.status = cost, "settled"
