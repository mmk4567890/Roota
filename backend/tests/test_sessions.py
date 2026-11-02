from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_session_returns_session_with_empty_observations(client: TestClient) -> None:
    response = client.post(
        "/sessions",
        json={
            "equipment_name": "CNC Mill A1",
            "fault_description": "Spindle fails to reach set RPM",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["equipment_name"] == "CNC Mill A1"
    assert body["fault_description"] == "Spindle fails to reach set RPM"
    assert body["observations"] == []
    assert body["id"]
    assert body["created_at"]
    assert body["updated_at"]
    assert body["created_at"] == body["updated_at"]


def test_get_session_returns_created_session(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={
            "equipment_name": "Pump P-12",
            "fault_description": "Intermittent pressure drop",
        },
    ).json()

    response = client.get(f"/sessions/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_add_observation_appends_to_session_history(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={
            "equipment_name": "Conveyor B",
            "fault_description": "Belt slips under load",
        },
    ).json()
    session_id = created["id"]

    first = client.post(
        f"/sessions/{session_id}/observations",
        json={
            "question": "Is belt tension within spec?",
            "answer": "No, tension is below minimum",
        },
    )
    assert first.status_code == 201
    first_body = first.json()
    assert len(first_body["observations"]) == 1
    assert first_body["observations"][0]["question"] == "Is belt tension within spec?"
    assert first_body["observations"][0]["answer"] == "No, tension is below minimum"
    assert first_body["updated_at"] >= first_body["created_at"]

    second = client.post(
        f"/sessions/{session_id}/observations",
        json={
            "question": "Were tensioners adjusted?",
            "answer": "Yes, adjusted to midpoint",
        },
    )
    assert second.status_code == 201
    second_body = second.json()
    assert len(second_body["observations"]) == 2
    assert second_body["observations"][1]["question"] == "Were tensioners adjusted?"

    fetched = client.get(f"/sessions/{session_id}")
    assert fetched.status_code == 200
    assert len(fetched.json()["observations"]) == 2


def test_create_session_rejects_invalid_inputs(client: TestClient) -> None:
    missing_field = client.post(
        "/sessions",
        json={"equipment_name": "Lathe 3"},
    )
    assert missing_field.status_code == 422

    blank_fields = client.post(
        "/sessions",
        json={"equipment_name": "   ", "fault_description": ""},
    )
    assert blank_fields.status_code == 422


def test_add_observation_rejects_invalid_inputs(client: TestClient) -> None:
    session_id = client.post(
        "/sessions",
        json={
            "equipment_name": "Press 7",
            "fault_description": "Hydraulic leak",
        },
    ).json()["id"]

    response = client.post(
        f"/sessions/{session_id}/observations",
        json={"question": " ", "answer": ""},
    )
    assert response.status_code == 422


def test_get_nonexistent_session_returns_404(client: TestClient) -> None:
    response = client.get(f"/sessions/{uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_add_observation_to_nonexistent_session_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/sessions/{uuid4()}/observations",
        json={
            "question": "Any error codes?",
            "answer": "E42",
        },
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
