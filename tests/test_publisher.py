from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from tests.conftest import fake, override_dependency

from .helpers import generators, mocks


def test_post_publisher(db: Session, client: TestClient) -> None:
    target = generators.create_target(db)
    response = client.post(
        "/api/v1/publishers",
        json={
            "name": fake.name(),
            "target": target.id,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/v1/publishers",
        json={
            "name": "NAMETHATISDUPLICATE",
            "target": target.id,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/v1/publishers",
        json={
            "name": "NAMETHATISDUPLICATE",
            "target": target.id,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test with a non-existent target
    response = client.post(
        "/api/v1/publishers",
        json={
            "name": "NAMETHATISDUPLICATE",
            "target": 999999999,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_publisher(db: Session, client: TestClient) -> None:
    target = generators.create_target(db)
    publisher = generators.create_publisher(db, target=target)

    response = client.get(f"/api/v1/publishers/{publisher.id}")
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()

    assert response_data["id"] == publisher.id
    assert response_data["name"] == publisher.name


def test_get_multiple_publishers(db: Session, client: TestClient) -> None:
    target = generators.create_target(db)
    for _ in range(5):
        generators.create_publisher(db, target=target)

    response = client.get("/api/v1/publishers")
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()["items"]
    assert len(response_data) >= 5
    assert response.json()["total"] >= 5


def test_get_publishers_with_filters(db: Session, client: TestClient) -> None:
    # Test filtering by id
    target = generators.create_target(db)
    publisher = generators.create_publisher(db, target=target)
    response = client.get(f"/api/v1/publishers?id={publisher.id}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == publisher.id

    # Test filtering by name
    response = client.get(f"/api/v1/publishers?name={publisher.name}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == publisher.name

    # Test filterring by id__in
    publisher_1 = generators.create_publisher(db, target=target)
    publisher_2 = generators.create_publisher(db, target=target)
    response = client.get(
        f"/api/v1/publishers?id__in={publisher_1.id},{publisher_2.id}",
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 2
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["id"] == publisher_1.id
    assert response.json()["items"][1]["id"] == publisher_2.id


def test_update_publisher(db: Session, client: TestClient) -> None:
    target = generators.create_target(db)
    publisher = generators.create_publisher(db, target=target)

    update_target = generators.create_target(db)
    new_name = fake.name()

    # Test updating a publisher
    response = client.put(f"/api/v1/publishers/{publisher.id}", json={"name": new_name, "target": update_target.id})
    assert response.status_code == status.HTTP_200_OK

    # Test updating a publisher with a duplicate name
    publisher2 = generators.create_publisher(db, target=update_target)
    response = client.put(f"/api/v1/publishers/{publisher2.id}", json={"name": new_name, "target": update_target.id})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test updating a non-existent publisher
    response = client.put(
        "/api/v1/publishers/99999999",
        json={"name": new_name, "target": update_target.id},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

    # Test updating a publisher with a target that does not exist
    response = client.put(f"/api/v1/publishers/{publisher.id}", json={"name": new_name, "target": 99999999})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test updating a publisher with an empty name
    response = client.put(f"/api/v1/publishers/{publisher.id}", json={"name": "", "target": update_target.id})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_delete_publisher(db: Session, client: TestClient) -> None:
    target = generators.create_target(db)
    publisher = generators.create_publisher(db, target=target)

    # Test deleting a publisher
    response = client.delete(f"/api/v1/publishers/{publisher.id}")
    assert response.status_code == status.HTTP_200_OK

    # Test deleting a non-existent publisher
    response = client.delete("/api/v1/publishers/999999999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
