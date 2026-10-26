import argparse
import secrets
from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import fingerprint, hasher
from app.db import SessionLocal, now
from app.models import Activity, Journal, User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", required=True)
    parser.add_argument("--email", default="demo@example.com")
    parser.add_argument("--password", help="Optional local demo password; generated when omitted")
    args = parser.parse_args()
    if get_settings().app_env not in {"development", "test"}:
        raise SystemExit("Demo seed is forbidden in production")
    password = args.password or secrets.token_urlsafe(16)
    with SessionLocal.begin() as db:
        if db.scalar(select(User).where(User.email == args.email)):
            raise SystemExit("Account exists; no changes made")
        user = User(
            email=args.email,
            password_hash=hasher.hash(password),
            nickname="心晴体验者",
            terms_version="v1",
            privacy_version="v1",
        )
        db.add(user)
        db.flush()
        import uuid

        for day, score in enumerate([3, 4, 2, 3, 5, 3, 4]):
            payload = {
                "mood_score": score,
                "emotions": [
                    {
                        "code": "calm" if score >= 3 else "tired",
                        "label": "平静" if score >= 3 else "疲惫",
                    }
                ],
                "event_tags": [{"code": "work", "label": "工作"}],
                "body": f"【虚构演示】第 {day + 1} 天，给自己留下一点记录。",
                "occurred_at": now() - timedelta(days=6 - day),
            }
            db.add(
                Journal(
                    **payload,
                    client_request_id=uuid.uuid4(),
                    user_id=user.id,
                    request_fingerprint=fingerprint(payload),
                )
            )
        # Explicit developer fixtures are clearly marked, never imported as production approval.
        for index, (title, kind, minutes) in enumerate(
            [
                ("给此刻写一句话", "writing", 2),
                ("留三分钟安静休息", "daily_care", 3),
                ("观察窗外的颜色", "mindfulness", 5),
            ]
        ):
            if not db.scalar(select(Activity).where(Activity.slug == f"demo-{index}")):
                db.add(
                    Activity(
                        slug=f"demo-{index}",
                        title="【开发演示】" + title,
                        type=kind,
                        duration_minutes=minutes,
                        scenes=["home", "office"],
                        steps=[
                            {
                                "order": 1,
                                "text": "这是一条开发联调样例，请按自己的舒适程度选择，可随时停止。",
                            },
                            {"order": 2, "text": "结束后可写下此刻感受，也可以跳过反馈。"},
                        ],
                        suitability_note="仅供本地开发演示，非正式审核内容。",
                        source_name="项目开发样例",
                        license_note="项目原创开发示例，无外部音频",
                        reviewer="development-fixture-only",
                        reviewed_at=now(),
                        review_due_at=now() + timedelta(days=30),
                        status="published",
                    )
                )
    print(f"Created local demo account: {args.email}")
    if not args.password:
        print(f"Generated demo password (store locally): {password}")


if __name__ == "__main__":
    main()
