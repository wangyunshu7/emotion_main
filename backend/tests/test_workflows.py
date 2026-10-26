import uuid
from datetime import timedelta
from threading import Event, Thread

import pytest
from conftest import signup
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ai.provider import ProviderError
from app.core.config import get_settings
from app.db import SessionLocal, now
from app.jobs import runner
from app.main import app
from app.models import Activity, EntryAnalysis, Job, Journal
from app.schemas import ModelAnalysis

BASE = "/api/v1"


def journal(client, **changes):
    data = {
        "client_request_id": str(uuid.uuid4()),
        "mood_score": 2,
        "emotions": [{"code": "sad", "label": "低落"}],
        "body": "今天汇报被打断，担心自己表现不好。",
        "event_tags": [{"code": "work", "label": "工作"}],
        "occurred_at": now().isoformat(),
        **changes,
    }
    response = client.post(BASE + "/journals", json=data)
    assert response.status_code in (200, 201), response.text
    return response.json(), data


def consent(client):
    response = client.put(BASE + "/me/consents/ai", json={"enabled": True, "policy_version": "v1"})
    assert response.status_code == 200, response.text


def enqueue(client, item):
    response = client.post(
        BASE + f"/journals/{item['id']}/analysis-jobs", json={"journal_version": item["version"]}
    )
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def activity(status="published", expired=False):
    with SessionLocal.begin() as db:
        row = Activity(
            slug=str(uuid.uuid4()),
            title="Test text activity",
            type="writing",
            duration_minutes=3,
            scenes=["home"],
            steps=[{"order": 1, "text": "Test step"}],
            suitability_note="Test fixture",
            source_name="Test",
            license_note="Test",
            reviewer="test",
            reviewed_at=now() - timedelta(days=2),
            review_due_at=now() + timedelta(days=-1 if expired else 30),
            status=status,
        )
        db.add(row)
        db.flush()
        return str(row.id)


def test_auth_cookie_csrf_and_logout(client):
    anonymous_cookie = client.cookies.get("emotion_session")
    signup(client)
    assert anonymous_cookie != client.cookies.get("emotion_session")
    assert client.get(BASE + "/me").status_code == 200
    assert (
        client.patch(
            BASE + "/me", json={"nickname": "x"}, headers={"X-CSRF-Token": "bad"}
        ).status_code
        == 403
    )
    assert (
        client.put(
            BASE + "/me/consents/ai",
            json={"enabled": True, "policy_version": "v1"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    old = client.cookies.get("emotion_session")
    assert client.post(BASE + "/auth/logout").status_code == 204
    client.cookies.set("emotion_session", old)
    assert client.get(BASE + "/me").status_code == 401


def test_registration_adult_and_password_bounds(client):
    payload = {
        "email": "a@example.com",
        "password": "short",
        "adult_confirmed": False,
        "terms_version": "v1",
        "privacy_version": "v1",
    }
    response = client.post(BASE + "/auth/register", json=payload)
    assert response.status_code == 422
    assert "short" not in response.text


def test_journal_idempotency_and_optimistic_lock(client):
    signup(client)
    item, data = journal(client, body="")
    assert client.post(BASE + "/journals", json=data).json()["id"] == item["id"]
    assert client.post(BASE + "/journals", json={**data, "body": "different"}).status_code == 409
    changed = client.patch(BASE + f"/journals/{item['id']}", json={"version": 1, "body": "new"})
    assert changed.status_code == 200 and changed.json()["version"] == 2
    assert (
        client.patch(
            BASE + f"/journals/{item['id']}", json={"version": 1, "body": "stale"}
        ).status_code
        == 409
    )
    assert client.delete(BASE + f"/journals/{item['id']}?version=1").status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Journal)) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"mood_score": True},
        {"mood_score": 6},
        {"emotions": []},
        {"occurred_at": "2026-01-01T12:00:00"},
        {"body": "x" * 10001},
        {"user_id": str(uuid.uuid4())},
        {"occurred_at": (now() + timedelta(days=1)).isoformat()},
    ],
)
def test_journal_invalid_input(client, change):
    signup(client)
    data = {
        "client_request_id": str(uuid.uuid4()),
        "mood_score": 3,
        "emotions": [{"code": "calm", "label": "平静"}],
        "occurred_at": now().isoformat(),
        **change,
    }
    assert client.post(BASE + "/journals", json=data).status_code == 422


def test_stats_weighted_average_missing_and_multiselect(client):
    signup(client)
    for score, when in [
        (1, "2026-01-01T02:00:00Z"),
        (5, "2026-01-01T03:00:00Z"),
        (2, "2026-01-02T02:00:00Z"),
    ]:
        journal(
            client,
            mood_score=score,
            occurred_at=when,
            emotions=[{"code": "sad", "label": "低落"}, {"code": "anxious", "label": "紧张"}],
        )
    r = client.get(BASE + "/insights?start_date=2026-01-01&end_date=2026-01-03").json()
    assert r["mean_score"] == 2.7
    assert [d["mean_score"] for d in r["days"]] == [3.0, 2.0, None]
    assert r["recorded_days"] == 2 and r["entry_count"] == 3
    assert sum(x["ratio"] for x in r["emotion_distribution"]) == 2


def test_timezone_boundaries(client):
    signup(client)
    journal(client, occurred_at="2026-01-01T20:00:00Z")
    r = client.get(BASE + "/insights?start_date=2026-01-02&end_date=2026-01-02").json()
    assert r["entry_count"] == 1
    assert client.patch(BASE + "/me", json={"timezone": "America/New_York"}).status_code == 200
    assert (
        client.get(BASE + "/insights?start_date=2026-01-02&end_date=2026-01-02").json()[
            "entry_count"
        ]
        == 0
    )


def test_filter_and_date_validation(client):
    signup(client)
    journal(client)
    assert client.get(BASE + "/journals?tag_code=work").json()["total"] == 1
    assert client.get(BASE + "/journals?emotion_code=happy").json()["total"] == 0
    assert client.get(BASE + "/journals?tag_code=custom").status_code == 422
    assert client.get(BASE + "/insights?start_date=2026-01-01").status_code == 422


def test_owner_isolation_all_resources(client):
    signup(client)
    item, _ = journal(client)
    consent(client)
    job_id = enqueue(client, item)
    with TestClient(app) as b:
        b.headers["Origin"] = "http://localhost:5173"
        b.headers["X-CSRF-Token"] = b.get(BASE + "/auth/session").json()["csrf_token"]
        signup(b, "bob@example.com")
        for path in [
            f"/journals/{item['id']}",
            f"/journals/{item['id']}/analysis",
            f"/jobs/{job_id}",
        ]:
            assert b.get(BASE + path).status_code == 404
        assert (
            b.patch(
                BASE + f"/journals/{item['id']}", json={"version": 1, "body": "hacked"}
            ).status_code
            == 404
        )
        assert b.get(BASE + "/journals").json()["total"] == 0


def test_analysis_evidence_correction_and_invalidation(client):
    signup(client)
    item, _ = journal(client)
    assert (
        client.post(
            BASE + f"/journals/{item['id']}/analysis-jobs", json={"journal_version": 1}
        ).status_code
        == 403
    )
    consent(client)
    job_id = enqueue(client, item)
    assert enqueue(client, item) == job_id
    assert runner.run_once()
    job = client.get(BASE + f"/jobs/{job_id}").json()
    assert job["status"] == "succeeded"
    a = client.get(BASE + f"/journals/{item['id']}/analysis").json()
    assert a["factors"][0]["evidence_quote"] in item["body"]
    f = a["factors"][0]
    assert (
        client.patch(
            BASE + f"/analyses/{a['id']}/factors/{f['id']}",
            json={"review_status": "partial", "user_text": "我的理解"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            BASE + f"/journals/{item['id']}", json={"version": 1, "body": "updated"}
        ).status_code
        == 200
    )
    assert client.get(BASE + f"/journals/{item['id']}/analysis").status_code == 404
    assert client.get(BASE + f"/jobs/{job_id}").status_code == 404


@pytest.mark.parametrize("action", ["edit", "delete", "revoke", "account"])
def test_late_model_cannot_resurrect_data(client, monkeypatch, action):
    signup(client)
    consent(client)
    item, _ = journal(client)
    enqueue(client, item)
    entered, release = Event(), Event()

    def delayed(kind, payload):
        entered.set()
        assert release.wait(15)
        return ModelAnalysis(summary="test", factors=[], reflection_question=None), {}

    monkeypatch.setattr(runner, "generate", delayed)
    worker = Thread(target=runner.run_once)
    worker.start()
    assert entered.wait(10)
    try:
        if action == "edit":
            r = client.patch(
                BASE + f"/journals/{item['id']}", json={"version": 1, "body": "updated"}
            )
        elif action == "delete":
            r = client.delete(BASE + f"/journals/{item['id']}?version=1")
        elif action == "revoke":
            r = client.put(
                BASE + "/me/consents/ai", json={"enabled": False, "policy_version": "v1"}
            )
        else:
            r = client.request(
                "DELETE",
                BASE + "/me",
                json={"password": "private-password-123", "confirmation": "DELETE_MY_ACCOUNT"},
            )
        assert r.status_code in (200, 204), r.text
    finally:
        release.set()
        worker.join(10)
    assert not worker.is_alive()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(EntryAnalysis)) == 0


def test_bad_evidence_removed_and_cancelled_job(client, monkeypatch):
    signup(client)
    consent(client)
    item, _ = journal(client)
    monkeypatch.setattr(
        runner,
        "generate",
        lambda *_: (
            ModelAnalysis(
                summary="test",
                factors=[{"label": "x", "hypothesis": "x", "evidence_quote": "not in body"}],
                reflection_question=None,
            ),
            {},
        ),
    )
    enqueue(client, item)
    runner.run_once()
    assert client.get(BASE + f"/journals/{item['id']}/analysis").json()["factors"] == []


def test_worker_retry_and_lease_recovery(client, monkeypatch):
    signup(client)
    consent(client)
    item, _ = journal(client)
    identifier = enqueue(client, item)

    def fail(*_):
        raise ProviderError("PROVIDER_TEMPORARY", True)

    monkeypatch.setattr(runner, "generate", fail)
    runner.run_once()
    with SessionLocal.begin() as db:
        row = db.get(Job, uuid.UUID(identifier))
        assert row.status == "queued"
        row.available_at = now() - timedelta(seconds=1)
    old = runner.claim()
    with SessionLocal.begin() as db:
        row = db.get(Job, old.id)
        row.lease_until = now() - timedelta(seconds=1)
    assert runner.claim() is None
    assert client.get(BASE + f"/jobs/{identifier}").json()["status"] == "failed"


def test_weekly_stats_without_ai_and_mutation_invalidation(client):
    signup(client)
    journal(client, occurred_at="2026-01-01T02:00:00Z")
    request = {"start_date": "2026-01-01", "end_date": "2026-01-07"}
    receipt = client.post(BASE + "/reviews", json=request).json()
    runner.run_once()
    result = client.get(BASE + f"/jobs/{receipt['job_id']}").json()["result"]
    r = client.get(BASE + f"/reviews/{result['id']}").json()
    assert r["ai_status"] == "insufficient" and r["statistics"]["entry_count"] == 1
    assert client.post(BASE + "/reviews", json=request).json()["reused"]
    journal(client)
    assert client.get(BASE + f"/reviews/{result['id']}").status_code == 404


def test_review_eligible_unconsented_and_model_failure(client, monkeypatch):
    signup(client)
    for day in (1, 2, 3):
        journal(client, occurred_at=f"2026-01-0{day}T02:00:00Z")
    request = {"start_date": "2026-01-01", "end_date": "2026-01-07"}
    client.post(BASE + "/reviews", json=request)
    runner.run_once()
    assert client.get(BASE + "/reviews").json()["items"][0]["ai_status"] == "disabled"
    consent(client)

    def fail(*_):
        raise ProviderError("MODEL_SCHEMA_INVALID")

    monkeypatch.setattr(runner, "generate", fail)
    client.post(BASE + "/reviews", json=request)
    runner.run_once()
    assert client.get(BASE + "/reviews").json()["items"][0]["ai_status"] == "failed"


def test_recommendation_filters_and_care_state_feedback(client):
    signup(client)
    good = activity()
    activity("draft")
    activity(expired=True)
    r = client.post(
        BASE + "/care/recommendations",
        json={"available_minutes": 5, "scene": "home", "excluded_types": []},
    ).json()
    assert [x["activity"]["id"] for x in r["items"]] == [good]
    assert (
        client.post(
            BASE + "/care/recommendations", json={"available_minutes": 2, "scene": "home"}
        ).json()["items"]
        == []
    )
    payload = {"activity_id": good, "client_request_id": str(uuid.uuid4())}
    c = client.post(BASE + "/care/sessions", json=payload).json()
    assert client.post(BASE + "/care/sessions", json=payload).json()["id"] == c["id"]
    endpoint = BASE + f"/care/sessions/{c['id']}"
    assert (
        client.put(
            endpoint + "/feedback", json={"version": 1, "helpfulness": "helpful"}
        ).status_code
        == 409
    )
    assert (
        client.patch(
            endpoint + "/state",
            json={"version": 1, "status": "completed", "elapsed_seconds": 10000},
        ).status_code
        == 422
    )
    c = client.patch(
        endpoint + "/state", json={"version": 1, "status": "completed", "elapsed_seconds": 0}
    ).json()
    assert c["status"] == "completed"
    assert (
        client.patch(
            endpoint + "/state", json={"version": 2, "status": "running", "elapsed_seconds": 0}
        ).status_code
        == 409
    )
    assert (
        client.put(
            endpoint + "/feedback", json={"version": 2, "after_score": 4, "helpfulness": "helpful"}
        ).status_code
        == 200
    )


def test_delete_detaches_care_and_export_private_fields(client):
    signup(client)
    item, _ = journal(client)
    good = activity()
    c = client.post(
        BASE + "/care/sessions",
        json={
            "activity_id": good,
            "client_request_id": str(uuid.uuid4()),
            "journal_id": item["id"],
        },
    ).json()
    exported = client.get(BASE + "/me/export")
    assert exported.status_code == 200, exported.text
    assert (
        "password_hash" not in exported.text
        and "csrf_token" not in exported.text
        and "token_hash" not in exported.text
    )
    assert client.delete(BASE + f"/journals/{item['id']}?version=1").status_code == 204
    assert client.get(BASE + f"/care/sessions/{c['id']}").json()["journal_id"] is None


def test_support_never_fabricates_resources(client):
    assert client.get(BASE + "/support-resources?region=UNKNOWN").json()["items"] == []


def test_health_and_model_disabled_path(client):
    assert client.get("/health/ready").status_code == 200
    signup(client)
    consent(client)
    item, _ = journal(client)
    settings = get_settings()
    old = settings.ai_enabled
    try:
        settings.ai_enabled = False
        assert (
            client.post(
                BASE + f"/journals/{item['id']}/analysis-jobs", json={"journal_version": 1}
            ).status_code
            == 503
        )
        assert client.get(BASE + "/insights").status_code == 200
    finally:
        settings.ai_enabled = old


def test_replay_prevents_restored_deletion(client):
    from app.services.privacy import replay_ledger

    signup(client)
    item, _ = journal(client)
    assert client.delete(BASE + f"/journals/{item['id']}?version=1").status_code == 204
    replay_ledger()
    assert list(get_settings().privacy_ledger_root.glob("*.done"))
    replay_ledger(include_completed=True)
    assert client.get(BASE + "/journals").json()["total"] == 0
