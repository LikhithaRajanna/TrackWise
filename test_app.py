
import os

os.environ["TRACKWISE_DATABASE"] = "trackwise_test.db"

from app import app


def test_home_endpoint():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200


def test_health_endpoint():
    client = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200

    data = response.get_json()

    assert data["application"] == "TrackWise API"
    assert data["database"] == "connected"
    assert data["status"] == "healthy"


def test_duplicate_event_detection():
    client = app.test_client()

    import uuid

    unique_id = str(uuid.uuid4())

    event_data = {
        "user_id": "pytest_duplicate_" + unique_id,
        "event_name": "product_viewed",
        "product_id": "PYTEST_DUPLICATE_PRODUCT"
    }

    first_response = client.post("/api/events", json=event_data)
    second_response = client.post("/api/events", json=event_data)

    assert first_response.status_code == 201
    assert second_response.status_code == 200

    first_data = first_response.get_json()
    second_data = second_response.get_json()

    assert first_data["status"] == "accepted"
    assert second_data["status"] == "duplicate"
    assert first_data["event_id"] == second_data["event_id"]


def test_missing_product_id_is_rejected():
    client = app.test_client()

    response = client.post(
        "/api/events",
        json={
            "user_id": "pytest_user_002",
            "event_name": "product_viewed"
        }
    )

    assert response.status_code == 400

    data = response.get_json()

    assert "product_id" in data["error"]



def test_valid_event_submission():
    import uuid

    client = app.test_client()
    unique_id = str(uuid.uuid4())

    response = client.post(
        "/api/events",
        json={
            "user_id": "pytest_user_" + unique_id,
            "event_name": "product_viewed",
            "product_id": "PYTEST_PRODUCT_001"
        }
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["status"] == "accepted"
    assert data["event"]["event_name"] == "product_viewed"



def test_filter_events_by_user_id():
    import uuid

    client = app.test_client()
    unique_id = "pytest_filter_" + str(uuid.uuid4())

    # Create an event for this test user first.
    create_response = client.post(
        "/api/events",
        json={
            "user_id": unique_id,
            "event_name": "product_viewed",
            "product_id": "FILTER_TEST_PRODUCT"
        }
    )

    assert create_response.status_code == 201

    # Filter events using the same user ID.
    response = client.get(
        "/api/events",
        query_string={"user_id": unique_id}
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data["count"] >= 1

    for event in data["events"]:
        assert event["user_id"] == unique_id



def test_attempt_history_endpoint():
    client = app.test_client()

    response = client.get("/api/attempts")

    assert response.status_code == 200

    data = response.get_json()

    assert "attempts" in data
    assert "count" in data
    assert isinstance(data["attempts"], list)


def test_monitoring_endpoint():
    client = app.test_client()

    response = client.get("/api/monitoring")

    assert response.status_code == 200

    data = response.get_json()

    assert "total_attempts" in data
    assert "accepted" in data
    assert "duplicates" in data
    assert "rejected" in data
    assert "acceptance_rate_percent" in data

    assert (
        data["total_attempts"]
        == data["accepted"]
        + data["duplicates"]
        + data["rejected"]
        + data["errors"]
    )

def test_same_client_event_id_is_detected_as_duplicate():
    import uuid

    client = app.test_client()
    unique_id = str(uuid.uuid4())

    event_data = {
        "user_id": "pytest_retry_" + unique_id,
        "event_name": "product_viewed",
        "product_id": "RETRY_TEST_PRODUCT",
        "client_event_id": "event-" + unique_id
    }

    first_response = client.post("/api/events", json=event_data)
    second_response = client.post("/api/events", json=event_data)

    assert first_response.status_code == 201
    assert second_response.status_code == 200

    first_data = first_response.get_json()
    second_data = second_response.get_json()

    assert first_data["status"] == "accepted"
    assert second_data["status"] == "duplicate"
    assert first_data["event_id"] == second_data["event_id"]


def test_different_client_event_ids_allow_repeated_views():
    import uuid

    client = app.test_client()
    unique_id = str(uuid.uuid4())

    base_event = {
        "user_id": "pytest_repeat_" + unique_id,
        "event_name": "product_viewed",
        "product_id": "REPEATED_VIEW_PRODUCT"
    }

    first_event = {
        **base_event,
        "client_event_id": "view-1-" + unique_id
    }

    second_event = {
        **base_event,
        "client_event_id": "view-2-" + unique_id
    }

    first_response = client.post("/api/events", json=first_event)
    second_response = client.post("/api/events", json=second_event)

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_data = first_response.get_json()
    second_data = second_response.get_json()

    assert first_data["status"] == "accepted"
    assert second_data["status"] == "accepted"
    assert first_data["event_id"] != second_data["event_id"]
    
def test_save_event_retries_when_database_is_locked(monkeypatch):
    import sqlite3
    import app as app_module

    calls = {"count": 0}

    def fake_save_event(
        user_id,
        event_name,
        product_id,
        client_event_id
    ):
        calls["count"] += 1

        if calls["count"] == 1:
            raise sqlite3.OperationalError("database is locked")

        return {
            "event_id": 123,
            "duplicate": False
        }

    monkeypatch.setattr(
        app_module,
        "save_event",
        fake_save_event
    )

    result = app_module.save_event_with_retry(
        "retry_test_user",
        "product_viewed",
        "retry_test_product",
        "retry-test-event"
    )

    assert calls["count"] == 2
    assert result["event_id"] == 123
    assert result["duplicate"] is False

    
def test_save_event_does_not_retry_other_database_errors(monkeypatch):
    import sqlite3
    import app as app_module

    calls = {"count": 0}

    def fake_save_event(
        user_id,
        event_name,
        product_id,
        client_event_id
    ):
        calls["count"] += 1
        raise sqlite3.OperationalError("no such table: events")

    monkeypatch.setattr(
        app_module,
        "save_event",
        fake_save_event
    )

    try:
        app_module.save_event_with_retry(
            "retry_test_user",
            "product_viewed",
            "retry_test_product",
            "retry-test-event"
        )
        assert False, "Expected sqlite3.OperationalError"
    except sqlite3.OperationalError as error:
        assert "no such table" in str(error)

    assert calls["count"] == 1


