from collections import Counter
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import CareSession
from app.services.common import ranged_journals, utc_bounds


def average(values):
    return (
        float((Decimal(sum(values)) / len(values)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        if values
        else None
    )


def insights(db, user, start, end):
    entries = ranged_journals(db, user, start, end)
    zone = ZoneInfo(user.timezone)
    groups = {}
    emotions, tags = Counter(), Counter()
    for item in entries:
        groups.setdefault(item.occurred_at.astimezone(zone).date(), []).append(item.mood_score)
        emotions.update({(t["code"], t["label"]) for t in item.emotions})
        tags.update({(t["code"], t["label"]) for t in item.event_tags})
    days = []
    day = start
    while day <= end:
        values = groups.get(day, [])
        days.append(
            {"date": day.isoformat(), "entry_count": len(values), "mean_score": average(values)}
        )
        day += timedelta(days=1)
    lo, hi = utc_bounds(user, start, end)
    care = db.scalars(
        select(CareSession).where(
            CareSession.user_id == user.id, CareSession.ended_at >= lo, CareSession.ended_at < hi
        )
    ).all()
    return {
        "timezone": user.timezone,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "entry_count": len(entries),
        "recorded_days": len(groups),
        "mean_score": average([j.mood_score for j in entries]),
        "days": days,
        "emotion_distribution": [
            {
                "code": code,
                "label": label,
                "entry_count": count,
                "ratio": round(count / len(entries), 4),
            }
            for (code, label), count in sorted(emotions.items())
        ],
        "tag_distribution": [
            {"code": code, "label": label, "entry_count": count}
            for (code, label), count in sorted(tags.items())
        ],
        "care_summary": {
            "completed_count": sum(c.status == "completed" for c in care),
            "feedback_count": sum(c.helpfulness is not None for c in care),
            "helpful_count": sum(c.helpfulness == "helpful" for c in care),
        },
    }
