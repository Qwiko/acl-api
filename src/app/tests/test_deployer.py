# from fastapi import status
# from fastapi.testclient import TestClient
# from pytest_mock import MockerFixture
# from sqlalchemy.orm import Session

# from tests.conftest import fake, override_dependency

# from app.tests.helpers import generators, mocks


# def test_post_deployer(db: Session, client: TestClient) -> None:
#     target = generators.create_target(db)
#     response = client.post(
#         "/api/v1/deployers",
#         json={
#             "name": fake.name(),
#             "target": target.id,
#         },
#     )
#     assert response.status_code == status.HTTP_201_CREATED

#     response = client.post(
#         "/api/v1/deployers",
#         json={
#             "name": "NAMETHATISDUPLICATE",
#             "target": target.id,
#         },
#     )
#     assert response.status_code == status.HTTP_201_CREATED

#     response = client.post(
#         "/api/v1/deployers",
#         json={
#             "name": "NAMETHATISDUPLICATE",
#             "target": target.id,
#         },
#     )
#     assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

#     # Test with a non-existent target
#     response = client.post(
#         "/api/v1/deployers",
#         json={
#             "name": "NAMETHATISDUPLICATE",
#             "target": 999999999,
#         },
#     )
#     assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# def test_get_deployer(db: Session, client: TestClient) -> None:
#     target = generators.create_target(db)
#     deployer = generators.create_deployer(db, target=target)

#     response = client.get(f"/api/v1/deployers/{deployer.id}")
#     assert response.status_code == status.HTTP_200_OK

#     response_data = response.json()

#     assert response_data["id"] == deployer.id
#     assert response_data["name"] == deployer.name


# def test_get_multiple_deployers(db: Session, client: TestClient) -> None:
#     target = generators.create_target(db)
#     for _ in range(5):
#         generators.create_deployer(db, target=target)

#     response = client.get("/api/v1/deployers")
#     assert response.status_code == status.HTTP_200_OK

#     response_data = response.json()["items"]
#     assert len(response_data) >= 5
#     assert response.json()["total"] >= 5


# def test_get_deployers_with_filters(db: Session, client: TestClient) -> None:
#     # Test filtering by id
#     target = generators.create_target(db)
#     deployer = generators.create_deployer(db, target=target)
#     response = client.get(f"/api/v1/deployers?id={deployer.id}")
#     assert response.status_code == status.HTTP_200_OK
#     assert len(response.json()["items"]) == 1
#     assert response.json()["total"] == 1
#     assert response.json()["items"][0]["id"] == deployer.id

#     # Test filtering by name
#     response = client.get(f"/api/v1/deployers?name={deployer.name}")
#     assert response.status_code == status.HTTP_200_OK
#     assert len(response.json()["items"]) == 1
#     assert response.json()["total"] == 1
#     assert response.json()["items"][0]["name"] == deployer.name

#     # Test filterring by id__in
#     deployer_1 = generators.create_deployer(db, target=target)
#     deployer_2 = generators.create_deployer(db, target=target)
#     response = client.get(
#         f"/api/v1/deployers?id__in={deployer_1.id},{deployer_2.id}",
#     )
#     assert response.status_code == status.HTTP_200_OK
#     assert len(response.json()["items"]) == 2
#     assert response.json()["total"] == 2
#     assert response.json()["items"][0]["id"] == deployer_1.id
#     assert response.json()["items"][1]["id"] == deployer_2.id


# def test_update_deployer(db: Session, client: TestClient) -> None:
#     target = generators.create_target(db)
#     deployer = generators.create_deployer(db, target=target)

#     update_target = generators.create_target(db)
#     new_name = fake.name()

#     # Test updating a deployer
#     response = client.put(f"/api/v1/deployers/{deployer.id}", json={"name": new_name, "target": update_target.id})
#     assert response.status_code == status.HTTP_200_OK

#     # Test updating a deployer with a duplicate name
#     deployer2 = generators.create_deployer(db, target=update_target)
#     response = client.put(f"/api/v1/deployers/{deployer2.id}", json={"name": new_name, "target": update_target.id})
#     assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

#     # Test updating a non-existent deployer
#     response = client.put(
#         "/api/v1/deployers/99999999",
#         json={"name": new_name, "target": update_target.id},
#     )
#     assert response.status_code == status.HTTP_404_NOT_FOUND

#     # Test updating a deployer with a target that does not exist
#     response = client.put(f"/api/v1/deployers/{deployer.id}", json={"name": new_name, "target": 99999999})
#     assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

#     # Test updating a deployer with an empty name
#     response = client.put(f"/api/v1/deployers/{deployer.id}", json={"name": "", "target": update_target.id})
#     assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# def test_delete_deployer(db: Session, client: TestClient) -> None:
#     target = generators.create_target(db)
#     deployer = generators.create_deployer(db, target=target)

#     # Test deleting a deployer
#     response = client.delete(f"/api/v1/deployers/{deployer.id}")
#     assert response.status_code == status.HTTP_200_OK

#     # Test deleting a non-existent deployer
#     response = client.delete("/api/v1/deployers/999999999")
#     assert response.status_code == status.HTTP_404_NOT_FOUND
