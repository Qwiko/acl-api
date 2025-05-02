from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from tests.conftest import fake, override_dependency

from .helpers import generators, mocks


def test_post_network(client: TestClient) -> None:
    response = client.post(
        "/api/v1/networks",
        json={
            "name": fake.name(),
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/v1/networks",
        json={
            "name": "NAMETHATISDUPLICATE",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/v1/networks",
        json={
            "name": "NAMETHATISDUPLICATE",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_network(db: Session, client: TestClient) -> None:
    network = generators.create_network(db)

    response = client.get(f"/api/v1/networks/{network.id}")
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()

    assert response_data["id"] == network.id
    assert response_data["name"] == network.name


def test_get_multiple_networks(db: Session, client: TestClient) -> None:
    for _ in range(5):
        generators.create_network(db)

    response = client.get("/api/v1/networks")
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()["items"]
    assert len(response_data) >= 5
    assert response.json()["total"] >= 5


def test_get_networks_with_filters(db: Session, client: TestClient) -> None:
    # Test filtering by id
    network = generators.create_network(db)
    response = client.get(f"/api/v1/networks?id={network.id}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == network.id

    # Test filtering by name
    response = client.get(f"/api/v1/networks?name={network.name}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == network.name

    # Test filterring by id__in
    network_1 = generators.create_network(db)
    network_2 = generators.create_network(db)
    response = client.get(
        f"/api/v1/networks?id__in={network_1.id},{network_2.id}",
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 2
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["id"] == network_1.id
    assert response.json()["items"][1]["id"] == network_2.id


def test_update_network(db: Session, client: TestClient) -> None:
    network = generators.create_network(db)
    new_name = fake.name()

    # Test updating a network
    response = client.put(f"/api/v1/networks/{network.id}", json={"name": new_name})
    assert response.status_code == status.HTTP_200_OK

    # Test updating a non-existent network
    response = client.put(
        "/api/v1/networks/99999999",
        json={"name": new_name},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

    # Test updating a network with a duplicate name
    network2 = generators.create_network(db)
    response = client.put(f"/api/v1/networks/{network2.id}", json={"name": new_name})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test updating a network with no name
    response = client.put(f"/api/v1/networks/{network.id}", json={"name": ""})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_delete_network(db: Session, client: TestClient) -> None:
    network = generators.create_network(db)

    # Test deleting a network
    response = client.delete(f"/api/v1/networks/{network.id}")
    assert response.status_code == status.HTTP_200_OK

    # Test deleting a non-existent network
    response = client.delete("/api/v1/networks/999999999")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_post_network_address(db: Session, client: TestClient) -> None:
    nested_network_1 = generators.create_network(db)
    nested_network_2 = generators.create_network(db)
    network = generators.create_network(db)

    # Test creating a address with adress
    response = client.post(
        f"/api/v1/networks/{network.id}/addresses",
        json={
            "address": fake.ipv4(),
            "comment": fake.sentence(),
            "nested_network_id": None,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    # Test creating an address with a nested network
    response = client.post(
        f"/api/v1/networks/{network.id}/addresses",
        json={
            "nested_network_id": nested_network_1.id,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    # Test adding nested_network_2
    response = client.post(
        f"/api/v1/networks/{network.id}/addresses",
        json={
            "nested_network_id": nested_network_2.id,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    # Test deleting the nested network
    response = client.delete(
        f"/api/v1/networks/{nested_network_1.id}",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Test creating an address with a non-existent nested network
    response = client.post(
        f"/api/v1/networks/{network.id}/addresses",
        json={
            "nested_network_id": 99999999,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test creating an address with address and nested_network_id
    response = client.post(
        f"/api/v1/networks/{network.id}/addresses",
        json={
            "address": fake.ipv4(),
            "comment": fake.sentence(),
            "nested_network_id": 99999999,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test creating an address with a non-existent network
    response = client.post(
        f"/api/v1/networks/{99999999}/addresses",
        json={
            "nested_network_id": 99999999,
        },
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
