from conftest import signup
from sqlalchemy import select
from test_workflows import BASE, consent, enqueue, journal

from app.core.config import get_settings
from app.db import SessionLocal
from app.jobs import runner
from app.models import ConsentEvent


def test_service_change_requires_new_consent_and_clears_old_analysis(client):
    signup(client)
    consent(client)
    entry, _ = journal(client)
    enqueue(client, entry)
    runner.run_once()
    settings = get_settings()
    original = settings.ai_provider
    try:
        settings.ai_provider = "disabled"
        assert (
            client.post(
                BASE + f"/journals/{entry['id']}/analysis-jobs", json={"journal_version": 1}
            ).status_code
            == 403
        )
        response = client.put(
            BASE + "/me/consents/ai", json={"enabled": True, "policy_version": "v1"}
        )
        assert response.status_code == 200
        assert client.get(BASE + f"/journals/{entry['id']}/analysis").status_code == 404
        with SessionLocal() as db:
            assert len(db.scalars(select(ConsentEvent)).all()) == 2
    finally:
        settings.ai_provider = original


def test_queued_job_does_not_send_to_changed_service(client):
    signup(client)
    consent(client)
    entry, _ = journal(client)
    identifier = enqueue(client, entry)
    settings = get_settings()
    original = settings.ai_provider
    try:
        settings.ai_provider = "disabled"
        runner.run_once()
        assert client.get(BASE + f"/jobs/{identifier}").json()["status"] == "cancelled"
    finally:
        settings.ai_provider = original
