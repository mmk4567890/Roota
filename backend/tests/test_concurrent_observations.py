from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi.testclient import TestClient


def test_concurrent_observation_writes_are_all_persisted(client: TestClient) -> None:
    created = client.post(
        "/sessions",
        json={
            "equipment_name": "Compressor C-9",
            "fault_description": "Unusual vibration at startup",
        },
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    write_count = 40

    def post_observation(index: int) -> int:
        response = client.post(
            f"/sessions/{session_id}/observations",
            json={
                "question": f"Check #{index}",
                "answer": f"Result #{index}",
            },
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(post_observation, i) for i in range(write_count)]
        status_codes = [future.result() for future in as_completed(futures)]

    assert status_codes.count(201) == write_count

    fetched = client.get(f"/sessions/{session_id}")
    assert fetched.status_code == 200
    observations = fetched.json()["observations"]
    assert len(observations) == write_count
