import argparse

from sqlalchemy import delete, update

from app.db import SessionLocal
from app.models import Job, Session
from app.services.privacy import replay_ledger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--after-restore",
        action="store_true",
        help="Run offline after an authorized backup restoration",
    )
    args = parser.parse_args()
    replay_ledger(include_completed=args.after_restore)
    if args.after_restore:
        with SessionLocal.begin() as db:
            db.execute(delete(Session))
            db.execute(
                update(Job)
                .where(Job.status.in_(["queued", "running"]))
                .values(status="cancelled", lease_token=None)
            )
    print("Privacy ledger replay completed.")


if __name__ == "__main__":
    main()
