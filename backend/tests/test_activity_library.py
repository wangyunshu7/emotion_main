import json
from collections import Counter

from conftest import signup

from app.cli.import_content import load_content
from app.core.config import ROOT
from app.db import now
from app.schemas import ActivityImport


def test_bundled_activities_publish_idempotently_and_are_visible(client):
    path = ROOT / "content"
    records = []
    for file in sorted((path / "activities").glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        records.extend(
            ActivityImport.model_validate(item)
            for item in (data if isinstance(data, list) else [data])
        )
    assert len(records) == len({r.slug for r in records}) == 25
    assert Counter(r.type for r in records) == {
        "writing": 5, "daily_care": 5, "mindfulness": 5, "movement": 5, "music": 5
    }
    for item in records:
        assert item.status == "published"
        assert item.review_due_at > now()
        assert item.reviewed_at <= now()
        assert "非人工或专业审核" in item.reviewer
        assert item.audio_asset_key is None
        assert len(item.steps) >= 4
        assert [step.order for step in item.steps] == list(range(1, len(item.steps) + 1))
        assert all("开发草稿" not in step.text for step in item.steps)

    load_content(path, validate_only=True)
    load_content(path)
    load_content(path)
    signup(client)
    response = client.get("/api/v1/activities?page_size=100")
    assert response.status_code == 200
    assert response.json()["total"] == 25
    assert len(response.json()["items"]) == 25
    for kind in ("writing", "daily_care", "mindfulness", "movement", "music"):
        assert client.get(f"/api/v1/activities?type={kind}").json()["total"] == 5
    assert client.get("/api/v1/activities?scene=outdoor&type=movement").json()["total"] == 5

    recommendation = client.post(
        "/api/v1/care/recommendations",
        json={"available_minutes": 5, "scene": "home", "excluded_types": []},
    )
    assert recommendation.status_code == 200
    assert recommendation.json()["items"]
    identifier = response.json()["items"][0]["id"]
    assert len(client.get(f"/api/v1/activities/{identifier}").json()["steps"]) >= 4
