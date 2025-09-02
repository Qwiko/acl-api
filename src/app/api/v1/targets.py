from typing import Annotated, Any

from aerleon.lib.plugin_supervisor import BUILTIN_GENERATORS
from fastapi import APIRouter, Depends, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination import paginate as dict_paginate
from fastapi_pagination.ext.sqlalchemy import paginate
from netutils.lib_mapper import AERLEON_LIB_MAPPER
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.v1.dynamic_policies import dynamic_policy_crud
from app.api.v1.policies import policy_crud
from app.core.cruds import target_crud
from app.core.db.database import async_get_db
from app.core.exceptions.http_exceptions import NotFoundException
from app.core.security import User, get_current_user
from app.filters.target import TargetFilter, TargetGeneratorFilter
from app.models import Target, TargetSubstitution
from app.schemas.target import TargetCreate, TargetRead, TargetUpdate

router = APIRouter(tags=["targets"])


class Generators(BaseModel):
    id: str
    name: str


# targets generators
@router.get("/target_generators", response_model=Page[Generators])
async def read_target_generators(
    current_user: Annotated[User, Security(get_current_user, scopes=["targets:read"])],
    tg_filter: TargetGeneratorFilter = FilterDepends(TargetGeneratorFilter),
) -> Any:
    id__in = tg_filter.id__in if tg_filter.id__in else [AERLEON_LIB_MAPPER.get(a[0], a[0]) for a in BUILTIN_GENERATORS]

    generator_list = sorted(
        [
            {"id": AERLEON_LIB_MAPPER.get(val[0], val[0]), "name": val[2]}
            for val in BUILTIN_GENERATORS
            if tg_filter.q.lower() in val[2].lower() and AERLEON_LIB_MAPPER.get(val[0], val[0]) in id__in
        ],
        key=lambda x: x[tg_filter.order_by[0].strip("+").strip("-")],
    )
    if tg_filter.name:
        generator_list = [d for d in generator_list if d.get("name") == tg_filter.name]

    if tg_filter.id:
        generator_list = [d for d in generator_list if d.get("id") == tg_filter.id]

    from fastapi_pagination.utils import disable_installed_extensions_check

    disable_installed_extensions_check()
    return dict_paginate(generator_list)


# targets
@router.get("/targets", response_model=Page[TargetRead])
async def read_targets(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["targets:read"])],
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
    current_user: Annotated[User, Security(get_current_user, scopes=["targets:write"])],
) -> Any:
    # Check if target name is already in use
    existing_target = await target_crud.get_all(db, filter_by={"name": values.name})
    if existing_target:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A target with this name already exists"}])

    dynamic_policies = await dynamic_policy_crud.get_all(
        db, load_relations=False, filter_by={"id": values.dynamic_policies}
    )
    policies = await policy_crud.get_all(db, load_relations=False, filter_by={"id": values.policies})

    substitutions = values.substitutions

    del values.dynamic_policies
    del values.policies
    del values.substitutions

    target = await target_crud.create(
        db,
        values,
    )

    target.dynamic_policies = dynamic_policies
    target.policies = policies
    target.substitutions = [
        TargetSubstitution(target=target, **substitution.model_dump()) for substitution in substitutions
    ]

    await db.commit()
    await db.refresh(target)

    return target


@router.get("/targets/{id}", response_model=TargetRead)
async def read_target(
    request: Request,
    id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["targets:read"])],
) -> Any:
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
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["targets:write"])],
) -> Any:
    target = await target_crud.get(db, id)

    if target is None:
        raise NotFoundException("target not found")

    dynamic_policies = await dynamic_policy_crud.get_all(
        db, load_relations=False, filter_by={"id": values.dynamic_policies}
    )
    policies = await policy_crud.get_all(db, load_relations=False, filter_by={"id": values.policies})

    substitutions = values.substitutions

    del values.dynamic_policies
    del values.policies
    del values.substitutions

    target = await target_crud.update(
        db,
        target.id,
        values,
    )

    target.dynamic_policies = dynamic_policies
    target.policies = policies
    target.substitutions = [
        TargetSubstitution(target=target, **substitution.model_dump()) for substitution in substitutions
    ]

    await db.commit()
    await db.refresh(target)

    return target


@router.delete("/targets/{id}")
# # @cache("{username}_post_cache", resource_id_name="id", to_invalidate_extra={"{username}_posts": "{username}"})
async def erase_target(
    request: Request,
    id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["targets:write"])],
) -> Any:
    target = await target_crud.get(db, id)

    if target is None:
        raise NotFoundException("target not found")

    await target_crud.delete(db, target.id)
    return {"message": "Target deleted"}
