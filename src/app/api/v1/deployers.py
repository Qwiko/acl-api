from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination import paginate as dict_paginate
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import and_

from ...core.cruds import deployer_crud, target_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...filters.deployer import DeployerFilter
from ...models import Deployer
from ...models.deployer import DeployerConfig, DeployerGitConfig, DeployerProxmoxNftConfig, DeployerNetmikoConfig

from ...schemas.deployer import DeployerCreate, DeployerRead, DeployerReadBrief, DeployerUpdate, DeployerModeEnum

router = APIRouter(tags=["deployers"])


# deployers
@router.get("/deployers", response_model=Page[DeployerReadBrief])
async def read_deployers(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    deployer_filter: DeployerFilter = FilterDepends(DeployerFilter),
) -> Any:
    query = select(Deployer)
    query = deployer_filter.filter(query)
    query = deployer_filter.sort(query)

    return await paginate(db, query)


@router.post("/deployers", response_model=DeployerRead, status_code=201)
async def write_deployer(
    values: DeployerCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    # Check if the Deployer name exists
    existing_deployer = await deployer_crud.get_all(db, filter_by={"name": values.name})
    if existing_deployer:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A Deployer with this name already exists"}])

    # Check if the target exists
    target = await target_crud.get(db, values.target)
    if target is None:
        raise RequestValidationError([{"loc": ["body", "target"], "msg": "That target does not exist"}])

    del values.target

    config = values.config.model_dump()

    if values.mode == DeployerModeEnum.PROXMOX_NFT:
        deployer_child_config = DeployerProxmoxNftConfig(type=values.mode, **config)
    elif values.mode == DeployerModeEnum.NETMIKO:
        deployer_child_config = DeployerNetmikoConfig(type=values.mode, **config)
    elif values.mode == "git":
        deployer_child_config = DeployerGitConfig(type=values.mode, **config)
    else:
        raise RequestValidationError([{"loc": ["body", "mode"], "msg": "Invalid mode"}])

    del values.config

    deployer = Deployer(**values.model_dump(), target=target, config=deployer_child_config)

    db.add(deployer)
    await db.commit()
    await db.refresh(deployer)

    result = await db.execute(
        select(Deployer)
        .options(
            selectinload(Deployer.config).selectin_polymorphic(
                [DeployerNetmikoConfig, DeployerProxmoxNftConfig, DeployerGitConfig]
            )
        )
        .where(Deployer.id == deployer.id)  # Use the id of the newly created deployer
    )
    deployer = result.scalars().one_or_none()

    return deployer


@router.get("/deployers/{id}", response_model=DeployerRead)
async def read_deployer(id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> Any:
    result = await db.execute(
        select(Deployer)
        .options(
            selectinload(Deployer.config).selectin_polymorphic(
                [DeployerProxmoxNftConfig, DeployerNetmikoConfig, DeployerGitConfig]
            )
        )
        .where(Deployer.id == id)
    )
    deployer = result.scalars().one_or_none()

    if deployer is None:
        raise NotFoundException("Deployer not found")

    return deployer


@router.put("/deployers/{id}", response_model=DeployerRead)
# @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_deployers(
    id: int,
    values: DeployerUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    deployer = await deployer_crud.get(db, id)

    if deployer is None:
        raise NotFoundException("Deployer not found")

    # Check if the Deployer name exists
    result = await db.execute(
        select(Deployer).where(and_(Deployer.name == values.name, Deployer.id.notin_([Deployer.id])))
    )
    existing_deployer = result.unique().scalars().one_or_none()
    if existing_deployer:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A Deployer with this name already exists"}])

    # Check if the target exists
    target = await target_crud.get(db, values.target)
    if target is None:
        raise RequestValidationError([{"loc": ["body", "target"], "msg": "That target does not exist"}])

    del values.target

    deployer = await deployer_crud.update(
        db,
        deployer.id,
        values,
        {"target": target},
    )

    result = await db.execute(
        select(Deployer)
        .options(
            selectinload(Deployer.config).selectin_polymorphic(
                [DeployerProxmoxNftConfig, DeployerNetmikoConfig, DeployerGitConfig]
            )
        )
        .where(Deployer.id == deployer.id)  # Use the id of the newly created deployer
    )
    deployer = result.scalars().one_or_none()

    return deployer


@router.delete("/deployers/{id}")
# # @cache("{username}_post_cache", resource_id_name="id", to_invalidate_extra={"{username}_posts": "{username}"})
async def erase_deployer(
    id: int,
    # current_user: Annotated[NetworkRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    deployer = await deployer_crud.get(db, id)

    if deployer is None:
        raise NotFoundException("Deployer not found")

    await deployer_crud.delete(db, deployer.id)
    return {"message": "Deployer deleted"}
