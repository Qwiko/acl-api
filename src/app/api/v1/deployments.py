from typing import Annotated, Any

from fastapi import APIRouter, Depends, Security
from fastapi.exceptions import RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...core.cruds import deployment_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...core.security import User, get_current_user
from ...filters.deployment import DeploymentFilter
from ...models import Deployment
from ...schemas.deployment import DeploymentRead, DeploymentReadBrief

router = APIRouter(tags=["deployments"])


# publishers_jobs
@router.get("/deployments", response_model=Page[DeploymentReadBrief])
async def read_deployments(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["deployments:read"])],
    deployment_filter: DeploymentFilter = FilterDepends(DeploymentFilter),
) -> Any:
    query = select(Deployment)
    query = deployment_filter.filter(query)
    query = deployment_filter.sort(query)

    return await paginate(db, query)


@router.get("/deployments/{id}", response_model=DeploymentRead)
async def read_deployment(
    id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["deployments:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    deployment = await deployment_crud.get(db, id, load_relations=True)

    if deployment is None:
        raise NotFoundException("Deployment not found")

    return deployment


@router.delete("/deployments/{id}")
async def erase_deployment(
    id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["deployments:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    publisher = await deployment_crud.get(db, id)

    if publisher is None:
        raise NotFoundException("Deployment not found")

    await deployment_crud.delete(db, publisher.id)
    return {"message": "Deployment deleted"}
