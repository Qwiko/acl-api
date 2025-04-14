from typing import Annotated, Any

from aerleon.lib.plugin_supervisor import BUILTIN_GENERATORS
from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination import paginate as dict_paginate
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...core.cruds import target_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...filters.target import TargetFilter, TargetGeneratorFilter
from ...models import Target
from ...schemas.target import TargetCreate, TargetRead, TargetUpdate
from .dynamic_policies import dynamic_policy_crud
from .policies import policy_crud

router = APIRouter(tags=["targets"])


class Generators(BaseModel):
    id: str
    name: str


# targets generators
@router.get("/target_generators", response_model=Page[Generators])
async def read_target_generators(
    tg_filter: TargetGeneratorFilter = FilterDepends(TargetGeneratorFilter),
) -> Any:
    id__in = tg_filter.id__in if tg_filter.id__in else [a[0] for a in BUILTIN_GENERATORS]

    generator_list = sorted(
        [
            {"id": val[0], "name": val[2]}
            for val in BUILTIN_GENERATORS
            if tg_filter.q.lower() in val[2].lower() and val[0] in id__in
        ],
        key=lambda x: x[tg_filter.order_by[0].strip("+").strip("-")],
    )
    if tg_filter.name:
        generator_list = [d for d in generator_list if d["name"] == tg_filter.name]

    if tg_filter.id:
        generator_list = [d for d in generator_list if d["id"] == tg_filter.id]

    from fastapi_pagination.utils import disable_installed_extensions_check

    disable_installed_extensions_check()
    return dict_paginate(generator_list)


# targets
@router.get("/targets", response_model=Page[TargetRead])
async def read_targets(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    target_filter: TargetFilter = FilterDepends(TargetFilter),
) -> Any:
    query = select(Target)
    query = target_filter.filter(query)
    query = target_filter.sort(query)

    return await paginate(db, query)


@router.post("/targets", response_model=TargetRead, status_code=201)
async def write_target(
    values: TargetCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    # Check if target name is already in use
    existing_target = await target_crud.get_all(db, filter_by={"name": values.name})
    if existing_target:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A target with this name already exists"}])

    dynamic_policies = await dynamic_policy_crud.get_all(
        db, load_relations=False, filter_by={"id": values.dynamic_policies}
    )
    policies = await policy_crud.get_all(db, load_relations=False, filter_by={"id": values.policies})

    del values.dynamic_policies
    del values.policies

    target = await target_crud.create(
        db,
        values,
    )

    target.dynamic_policies = dynamic_policies
    target.policies = policies

    await db.commit()
    await db.refresh(target)

    return target


@router.get("/targets/{id}", response_model=TargetRead)
async def read_target(request: Request, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> Any:
    target = await target_crud.get(db, id, load_relations=True)

    if target is None:
        raise NotFoundException("target not found")

    return target


@router.put("/targets/{id}", response_model=TargetRead)
# @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_targets(
    request: Request,
    id: int,
    values: TargetUpdate,
    # current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    target = await target_crud.get(db, id)

    if target is None:
        raise NotFoundException("target not found")

    dynamic_policies = await dynamic_policy_crud.get_all(
        db, load_relations=False, filter_by={"id": values.dynamic_policies}
    )
    policies = await policy_crud.get_all(db, load_relations=False, filter_by={"id": values.policies})

    del values.policies
    del values.dynamic_policies

    target = await target_crud.update(
        db,
        target.id,
        values,
    )

    target.dynamic_policies = dynamic_policies
    target.policies = policies

    await db.commit()
    await db.refresh(target)

    return target


@router.delete("/targets/{id}")
# # @cache("{username}_post_cache", resource_id_name="id", to_invalidate_extra={"{username}_posts": "{username}"})
async def erase_target(
    request: Request,
    id: int,
    # current_user: Annotated[NetworkRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    target = await target_crud.get(db, id)

    if target is None:
        raise NotFoundException("target not found")

    await target_crud.delete(db, target.id)
    return {"message": "Target deleted"}
