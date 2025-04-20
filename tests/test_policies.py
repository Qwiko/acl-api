from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from tests.conftest import fake, override_dependency

from .helpers import generators, mocks


def test_post_policy(client: TestClient) -> None:
    response = client.post(
        "/api/v1/policies",
        json={
            "name": fake.name(),
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/v1/policies",
        json={
            "name": "NAMETHATISDUPLICATE",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        "/api/v1/policies",
        json={
            "name": "NAMETHATISDUPLICATE",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_policy_term_position(client: TestClient) -> None:
    policy = client.post(
        "/api/v1/policies",
        json={
            "name": fake.name(),
        },
    )
    assert policy.status_code == status.HTTP_201_CREATED

    policy = policy.json()

    policy_term1 = client.post(
        f"/api/v1/policies/{policy.get('id')}/terms",
        json={"name": fake.name(), "enabled": True, "action": "accept", "position": 1},
    )
    assert policy_term1.status_code == status.HTTP_201_CREATED

    assert policy_term1.json()["position"] == 1

    policy_term2 = client.post(
        f"/api/v1/policies/{policy.get('id')}/terms",
        json={"name": fake.name(), "enabled": True, "action": "accept", "position": 1},
    )
    assert policy_term2.status_code == status.HTTP_201_CREATED

    for i in range(10):
        # Update policy_term2 to be position 1
        policy_term2 = client.put(
            f"/api/v1/policies/{policy.get('id')}/terms/{policy_term2.json().get('id')}",
            json={"name": fake.name(), "enabled": True, "action": "accept", "position": 1},
        )
        assert policy_term2.status_code == status.HTTP_200_OK
        assert policy_term2.json()["position"] == 1

        # Get policy_term1 and verify its position to 2
        policy_term1 = client.get(
            f"/api/v1/policies/{policy.get('id')}/terms/{policy_term1.json().get('id')}",
        )
        assert policy_term1.status_code == status.HTTP_200_OK
        assert policy_term1.json()["position"] == 2

        # Update policy_term1 to be position 1
        policy_term1 = client.put(
            f"/api/v1/policies/{policy.get('id')}/terms/{policy_term1.json().get('id')}",
            json={"name": fake.name(), "enabled": True, "action": "accept", "position": 1},
        )
        assert policy_term1.status_code == status.HTTP_200_OK
        assert policy_term1.json()["position"] == 1

        # Get policy_term2 and verify its position to 2
        policy_term2 = client.get(
            f"/api/v1/policies/{policy.get('id')}/terms/{policy_term2.json().get('id')}",
        )
        assert policy_term2.status_code == status.HTTP_200_OK
        assert policy_term2.json()["position"] == 2


# def test_get_policy(db: Session, client: TestClient) -> None:
#     policy = generators.create_policy(db)

#     response = client.get(f"/api/v1/policies/{policy.id}")
#     assert response.status_code == status.HTTP_200_OK

#     response_data = response.json()

#     assert response_data["id"] == policy.id
#     assert response_data["name"] == policy.name


# def test_get_multiple_policies(db: Session, client: TestClient) -> None:
#     for _ in range(5):
#         generators.create_policy(db)

#     response = client.get("/api/v1/policies")
#     assert response.status_code == status.HTTP_200_OK

#     response_data = response.json()["items"]
#     assert len(response_data) >= 5
#     assert response.json()["total"] >= 5


# def test_get_policies_with_filters(db: Session, client: TestClient) -> None:
#     # Test filtering by id
#     policy = generators.create_policy(db)
#     response = client.get(f"/api/v1/policies?id={policy.id}")
#     assert response.status_code == status.HTTP_200_OK
#     assert len(response.json()["items"]) == 1
#     assert response.json()["total"] == 1
#     assert response.json()["items"][0]["id"] == policy.id

#     # Test filtering by name
#     response = client.get(f"/api/v1/policies?name={policy.name}")
#     assert response.status_code == status.HTTP_200_OK
#     assert len(response.json()["items"]) == 1
#     assert response.json()["total"] == 1
#     assert response.json()["items"][0]["name"] == policy.name

#     # Test filterring by id__in
#     policy_1 = generators.create_policy(db)
#     policy_2 = generators.create_policy(db)
#     response = client.get(
#         f"/api/v1/policies?id__in={policy_1.id},{policy_2.id}",
#     )
#     assert response.status_code == status.HTTP_200_OK
#     assert len(response.json()["items"]) == 2
#     assert response.json()["total"] == 2
#     assert response.json()["items"][0]["id"] == policy_1.id
#     assert response.json()["items"][1]["id"] == policy_2.id


# def test_update_policy(db: Session, client: TestClient) -> None:
#     policy = generators.create_policy(db)
#     new_name = fake.name()

#     # Test updating a policy
#     response = client.put(f"/api/v1/policies/{policy.id}", json={"name": new_name, "generator": "cisco"})
#     assert response.status_code == status.HTTP_200_OK

#     # Test updating a non-existent policy
#     response = client.put(
#         "/api/v1/policies/99999999",
#         json={"name": new_name, "generator": "cisco"},
#     )
#     assert response.status_code == status.HTTP_404_NOT_FOUND


# def test_delete_policy(db: Session, client: TestClient) -> None:
#     policy = generators.create_policy(db)

#     # Test deleting a policy
#     response = client.delete(f"/api/v1/policies/{policy.id}")
#     assert response.status_code == status.HTTP_200_OK

#     # Test deleting a non-existent policy
#     response = client.delete("/api/v1/policies/999999999")
#     assert response.status_code == status.HTTP_404_NOT_FOUND
