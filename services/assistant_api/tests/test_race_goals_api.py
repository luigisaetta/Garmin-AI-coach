"""
Author: L. Saetta
Date Modified: 2026-07-16
License: MIT
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from services.assistant_api.api.main import (
    create_app,
    get_current_user,
    get_race_goal_service,
)
from services.assistant_api.goals.race_goals import RaceGoalService
from services.assistant_api.identity.users import UserRepository
from services.assistant_api.tests.database import build_test_database


def _client(tmp_path, *, username: str = "alice") -> TestClient:
    database = build_test_database(tmp_path, f"{username}.db")
    user = UserRepository(database).ensure_user(username=username)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_race_goal_service] = lambda: RaceGoalService(database)
    return TestClient(app)


def _payload() -> dict[str, object]:
    return {
        "title": "Coastal 70.3",
        "event_date": (date.today() + timedelta(days=60)).isoformat(),
        "sport": "multisport",
        "distance_meters": None,
        "multisport_format": "half_iron_distance",
        "priority": "A",
        "goal_type": "completion",
        "target_duration_seconds": None,
        "notes": "",
        "status": "upcoming",
        "segments": [
            {"sport": "swimming", "distance_meters": 1900},
            {"sport": "cycling", "distance_meters": 90000},
            {"sport": "running", "distance_meters": 21100},
        ],
    }


def test_goal_endpoints_create_list_get_update_and_select_active(tmp_path) -> None:
    """Verify the authenticated athlete can manage one multisport race goal."""
    client = _client(tmp_path)

    created = client.post("/training/goals", json=_payload())

    assert created.status_code == 201
    body = created.json()
    assert body["sport"] == "multisport"
    assert [segment["sport"] for segment in body["segments"]] == [
        "swimming",
        "cycling",
        "running",
    ]

    listed = client.get("/training/goals?status=upcoming")
    active = client.get("/training/goals/active")
    fetched = client.get(f"/training/goals/{body['id']}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert active.json()["id"] == body["id"]
    assert fetched.json()["title"] == "Coastal 70.3"

    updated_payload = _payload() | {
        "title": "Updated Coastal 70.3",
        "status": "completed",
    }
    updated = client.patch(f"/training/goals/{body['id']}", json=updated_payload)
    history = client.get("/training/goals?status=history")
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated Coastal 70.3"
    assert history.json()[0]["status"] == "completed"


def test_goal_endpoint_restores_a_historical_goal_to_upcoming(tmp_path) -> None:
    """Verify an athlete can recover a goal marked final by mistake."""
    client = _client(tmp_path)
    created = client.post("/training/goals", json=_payload())
    goal_id = created.json()["id"]

    completed = client.patch(
        f"/training/goals/{goal_id}",
        json=_payload() | {"status": "completed"},
    )
    restored = client.patch(
        f"/training/goals/{goal_id}",
        json=_payload() | {"status": "upcoming"},
    )

    assert completed.status_code == 200
    assert restored.status_code == 200
    assert restored.json()["status"] == "upcoming"
    assert [
        goal["id"] for goal in client.get("/training/goals?status=upcoming").json()
    ] == [goal_id]
    assert client.get("/training/goals?status=history").json() == []


def test_goal_endpoint_rejects_invalid_multisport_payload(tmp_path) -> None:
    """Verify multisport validation is exposed as a safe HTTP error."""
    client = _client(tmp_path)
    payload = _payload() | {
        "segments": [{"sport": "swimming", "distance_meters": 1900}]
    }

    response = client.post("/training/goals", json=payload)

    assert response.status_code == 422
    assert "at least two" in response.json()["detail"]


def test_goal_endpoint_does_not_expose_another_users_goal(tmp_path) -> None:
    """Verify a goal id cannot be read through another current-user context."""
    database = build_test_database(tmp_path, "shared.db")
    users = UserRepository(database)
    alice = users.ensure_user(username="alice")
    bob = users.ensure_user(username="bob")
    service = RaceGoalService(database)
    app = create_app()
    app.dependency_overrides[get_race_goal_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: alice
    client = TestClient(app)
    created = client.post("/training/goals", json=_payload())

    app.dependency_overrides[get_current_user] = lambda: bob
    response = client.get(f"/training/goals/{created.json()['id']}")

    assert response.status_code == 404
