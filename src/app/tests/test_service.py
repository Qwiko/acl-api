from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.helpers import generators
from faker import Faker

fake = Faker()


def test_post_service(client: TestClient) -> None:
    response = client.post(
        "/api/v1/services",
        json={
            "name": fake.name(),
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/v1/services",
        json={
            "name": "NAMETHATISDUPLICATE",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/v1/services",
        json={
            "name": "NAMETHATISDUPLICATE",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_service(db: Session, client: TestClient) -> None:
    service = generators.create_service(db)

    response = client.get(f"/api/v1/services/{service.id}")
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()

    assert response_data["id"] == service.id
    assert response_data["name"] == service.name


def test_get_multiple_services(db: Session, client: TestClient) -> None:
    for _ in range(5):
        generators.create_service(db)

    response = client.get("/api/v1/services")
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()["items"]
    assert len(response_data) >= 5
    assert response.json()["total"] >= 5


def test_get_services_with_filters(db: Session, client: TestClient) -> None:
    # Test filtering by id
    service = generators.create_service(db)
    response = client.get(f"/api/v1/services?id={service.id}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == service.id

    # Test filtering by name
    response = client.get(f"/api/v1/services?name={service.name}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == service.name

    # Test filterring by id__in
    service_1 = generators.create_service(db)
    service_2 = generators.create_service(db)
    response = client.get(
        f"/api/v1/services?id__in={service_1.id},{service_2.id}",
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 2
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["id"] == service_1.id
    assert response.json()["items"][1]["id"] == service_2.id


def test_update_service(db: Session, client: TestClient) -> None:
    service = generators.create_service(db)
    new_name = fake.name()

    # Test updating a service
    response = client.put(f"/api/v1/services/{service.id}", json={"name": new_name})
    assert response.status_code == status.HTTP_200_OK

    # Test updating a non-existent service
    response = client.put(
        "/api/v1/services/99999999",
        json={"name": new_name},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

    # Test updating a service with a duplicate name
    service2 = generators.create_service(db)
    response = client.put(f"/api/v1/services/{service2.id}", json={"name": new_name})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test updating a service with no name
    response = client.put(f"/api/v1/services/{service.id}", json={"name": ""})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_delete_service(db: Session, client: TestClient) -> None:
    service = generators.create_service(db)

    # Test deleting a service
    response = client.delete(f"/api/v1/services/{service.id}")
    assert response.status_code == status.HTTP_200_OK

    # Test deleting a non-existent service
    response = client.delete("/api/v1/services/999999999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
