from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Security
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.cruds import dynamic_policy_crud
from app.core.db.database import async_get_db
from app.core.exceptions.http_exceptions import NotFoundException
from app.core.security import User, get_current_user
from app.filters.dynamic_policy import DynamicPolicyFilter
from app.models import DynamicPolicy
from app.schemas.dynamic_policy import (
    DynamicPolicyCreate,
    DynamicPolicyCreated,
    DynamicPolicyRead,
    DynamicPolicyReadBrief,
    DynamicPolicyUpdate,
)

router = APIRouter(tags=["dynamic_policies"])


@router.get("/dynamic_policies", response_model=Page[DynamicPolicyReadBrief])
async def read_dynamic_policies(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["dynamic_policies:read"])],
    dynamic_policy_filter: DynamicPolicyFilter = FilterDepends(DynamicPolicyFilter),
) -> Any:
    query = select(DynamicPolicy)
    query = dynamic_policy_filter.filter(query)
    query = dynamic_policy_filter.sort(query)
    return await paginate(db, query)


@router.post("/dynamic_policies", response_model=DynamicPolicyCreated, status_code=201)
async def write_policy(
    request: Request,
    values: DynamicPolicyCreate,
    current_user: Annotated[User, Security(get_current_user, scopes=["dynamic_policies:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await dynamic_policy_crud.create(db, values, extra_data={"edited": True})
    return policy


@router.get("/dynamic_policies/{dynamic_policy_id}", response_model=DynamicPolicyRead)
async def read_policy(
    request: Request,
    dynamic_policy_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["dynamic_policies:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await dynamic_policy_crud.get(db, dynamic_policy_id, load_relations=True)
    return policy


@router.put("/dynamic_policies/{dynamic_policy_id}", response_model=DynamicPolicyCreated)
async def put_policy(
    request: Request,
    dynamic_policy_id: int,
    values: DynamicPolicyUpdate,
    current_user: Annotated[User, Security(get_current_user, scopes=["dynamic_policies:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await dynamic_policy_crud.update(db, dynamic_policy_id, values, extra_data={"edited": True})
    return policy


@router.delete("/dynamic_policies/{dynamic_policy_id}")
async def erase_policy(
    request: Request,
    dynamic_policy_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["dynamic_policies:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    # Check if the dynamic_policy exists
    dynamic_policy = await dynamic_policy_crud.get(db, dynamic_policy_id)
    if not dynamic_policy:
        return NotFoundException(f"Dynamic policy with id {dynamic_policy_id} not found")

    # Delete the dynamic_policy
    dynamic_policy = await dynamic_policy_crud.delete(db, dynamic_policy_id)
    return {"message": "Dynamic policy deleted"}
