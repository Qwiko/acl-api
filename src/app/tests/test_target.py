from faker import Faker
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.tests.helpers import generators

fake = Faker()


def test_post_target(client: TestClient) -> None:
    response = client.post(
        "/api/v1/targets",
        json={
            "name": fake.name(),
            "generator": "cisco_ios",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/v1/targets",
        json={
            "name": "NAMETHATISDUPLICATE",
            "generator": "cisco_ios",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/v1/targets",
        json={
            "name": "NAMETHATISDUPLICATE",
            "generator": "cisco_ios",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_target(db: Session, client: TestClient) -> None:
    target = generators.create_target(db)

    response = client.get(f"/api/v1/targets/{target.id}")
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()

    assert response_data["id"] == target.id
    assert response_data["name"] == target.name


def test_get_multiple_targets(db: Session, client: TestClient) -> None:
    for _ in range(5):
        generators.create_target(db)

    response = client.get("/api/v1/targets")
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()["items"]
    assert len(response_data) >= 5
    assert response.json()["total"] >= 5


def test_get_targets_with_filters(db: Session, client: TestClient) -> None:
    # Test filtering by id
    target = generators.create_target(db)
    response = client.get(f"/api/v1/targets?id={target.id}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == target.id

    # Test filtering by name
    response = client.get(f"/api/v1/targets?name={target.name}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == target.name

    # Test filterring by id__in
    target_1 = generators.create_target(db)
    target_2 = generators.create_target(db)
    response = client.get(
        f"/api/v1/targets?id__in={target_1.id},{target_2.id}",
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 2
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["id"] == target_1.id
    assert response.json()["items"][1]["id"] == target_2.id


def test_update_target(db: Session, client: TestClient) -> None:
    target = generators.create_target(db)
    new_name = fake.name()

    # Test updating a target
    response = client.put(f"/api/v1/targets/{target.id}", json={"name": new_name, "generator": "cisco_ios"})
    assert response.status_code == status.HTTP_200_OK

    # Test updating a non-existent target
    response = client.put(
        "/api/v1/targets/99999999",
        json={"name": new_name, "generator": "cisco_ios"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_target(db: Session, client: TestClient) -> None:
    target = generators.create_target(db)

    # Test deleting a target
    response = client.delete(f"/api/v1/targets/{target.id}")
    assert response.status_code == status.HTTP_200_OK

    # Test deleting a non-existent target
    response = client.delete("/api/v1/targets/999999999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
