import json
import os
import uuid

from cryptography.fernet import Fernet
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db import now
from app.models import CareSession, ConsentEvent, Journal, User
from app.services.common import invalidate


def ledger_event(action, user_id, resource_id=None, db=None):
    settings = get_settings()
    root = settings.privacy_ledger_root
    root.mkdir(parents=True, exist_ok=True)
    event = {
        "id": str(uuid.uuid4()),
        "action": action,
        "user_id": str(user_id),
        "resource_id": str(resource_id) if resource_id else None,
        "occurred_at": now().isoformat(),
    }
    target = root / f"{event['id']}.event"
    temp = target.with_suffix(".tmp")
    encrypted = Fernet(settings.privacy_ledger_key.encode()).encrypt(json.dumps(event).encode())
    with open(temp, "xb") as stream:
        stream.write(encrypted)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, target)
    if db is not None:
        db.info.setdefault("privacy_events", []).append(target)
    return target


def mark_completed(path):
    # Completion is recorded only after commit. Keeping events allows restore replay.
    if path.exists():
        os.replace(path, path.with_suffix(".done"))


def apply_event(db, event):
    from datetime import datetime

    user = db.scalar(select(User).where(User.id == uuid.UUID(event["user_id"])).with_for_update())
    if not user:
        return
    if event["action"] == "delete_account":
        db.execute(delete(CareSession).where(CareSession.user_id == user.id))
        db.delete(user)
    elif event["action"] == "delete_journal":
        identifier = uuid.UUID(event["resource_id"])
        entry = db.scalar(
            select(Journal).where(Journal.id == identifier, Journal.user_id == user.id)
        )
        if entry:
            for care in db.scalars(
                select(CareSession).where(
                    CareSession.user_id == user.id, CareSession.journal_id == identifier
                )
            ):
                care.journal_id = None
            db.flush()
            invalidate(db, user, identifier)
            db.delete(entry)
    elif event["action"] == "revoke_ai":
        later_grant = db.scalar(
            select(ConsentEvent).where(
                ConsentEvent.user_id == user.id,
                ConsentEvent.action == "granted",
                ConsentEvent.occurred_at > datetime.fromisoformat(event["occurred_at"]),
            )
        )
        if not later_grant:
            user.ai_enabled = False
            user.consent_version += 1
            invalidate(db, user, all_analyses=True)


def replay_ledger(include_completed=False):
    from app.db import SessionLocal

    settings = get_settings()
    root = settings.privacy_ledger_root
    paths = list(root.glob("*.event"))
    if include_completed:
        paths += list(root.glob("*.done"))
    events = [
        (p, json.loads(Fernet(settings.privacy_ledger_key.encode()).decrypt(p.read_bytes())))
        for p in paths
    ]
    for path, event in sorted(events, key=lambda pair: pair[1]["occurred_at"]):
        with SessionLocal.begin() as db:
            apply_event(db, event)
        mark_completed(path)
