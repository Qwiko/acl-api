from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...core.cruds import dynamic_policy_crud
from ...core.db.database import async_get_db
from ...filters.dynamic_policy import DynamicPolicyFilter
from ...models import DynamicPolicy
from ...schemas.dynamic_policy import (
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
    dynamic_policy_filter: DynamicPolicyFilter = FilterDepends(DynamicPolicyFilter),
) -> Any:
    query = select(DynamicPolicy)
    query = dynamic_policy_filter.filter(query)
    query = dynamic_policy_filter.sort(query)
    return await paginate(db, query)


@router.post("/dynamic_policies", response_model=DynamicPolicyCreated, status_code=201)
async def write_policy(
    request: Request, values: DynamicPolicyCreate, db: Annotated[AsyncSession, Depends(async_get_db)]
) -> Any:
    # extra_data={"targets":[], "terms": []}
    policy = await dynamic_policy_crud.create(db, values)
    return policy


@router.get("/dynamic_policies/{id}", response_model=DynamicPolicyRead)
async def read_policy(request: Request, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> Any:
    policy = await dynamic_policy_crud.get(db, id, load_relations=True)
    return policy


@router.put("/dynamic_policies/{id}", response_model=DynamicPolicyCreated)
# # @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_policy(
    request: Request,
    id: int,
    values: DynamicPolicyUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await dynamic_policy_crud.update(db, id, values)
    return policy


@router.delete("/dynamic_policies/{id}")
# # @cache("{username}_post_cache", resource_id_name="id", to_invalidate_extra={"{username}_posts": "{username}"})
async def erase_policy(
    request: Request,
    id: int,
    # current_user: Annotated[DynamicPolicyRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await dynamic_policy_crud.delete(db, id)
    return {"message": "Dynamic policy deleted"}
