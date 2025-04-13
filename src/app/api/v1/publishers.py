from typing import Annotated, Any

from aerleon.lib.plugin_supervisor import BUILTIN_GENERATORS
from fastapi import APIRouter, Depends, Request
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination import paginate as dict_paginate
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...core.cruds import publisher_crud, target_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...filters.publisher import PublisherFilter
from ...models import Publisher
from ...schemas.publisher import PublisherCreate, PublisherRead, PublisherReadBrief, PublisherUpdate


router = APIRouter(tags=["publishers"])




# publishers
@router.get("/publishers", response_model=Page[PublisherReadBrief])
async def read_publishers(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    publisher_filter: PublisherFilter = FilterDepends(PublisherFilter),
) -> Any:
    query = select(Publisher)
    query = publisher_filter.filter(query)
    query = publisher_filter.sort(query)

    return await paginate(db, query)


@router.post("/publishers", response_model=PublisherRead, status_code=201)
async def write_publisher(
    request: Request,
    values: PublisherCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    
    data_dict = values.model_dump()
    
    del data_dict["target"]
    
    target = await target_crud.get(db, values.target)
    
    publisher = Publisher(**data_dict, target=target)
    
    db.add(publisher)
    await db.commit()

    return publisher


@router.get("/publishers/{id}", response_model=PublisherRead)
async def read_publisher(request: Request, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> Any:
    publisher = await publisher_crud.get(db, id, load_relations=True)

    if Publisher is None:
        raise NotFoundException("Publisher not found")

    return publisher


@router.put("/publishers/{id}", response_model=PublisherRead)
# @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_publishers(
    request: Request,
    id: int,
    values: PublisherUpdate,
    # current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    publisher = await publisher_crud.get(db, id)

    if publisher is None:
        raise NotFoundException("Publisher not found")

   
    publisher = await publisher_crud.update(
        db,
        publisher.id,
        values,
    )

    return publisher


@router.delete("/publishers/{id}")
# # @cache("{username}_post_cache", resource_id_name="id", to_invalidate_extra={"{username}_posts": "{username}"})
async def erase_publisher(
    request: Request,
    id: int,
    # current_user: Annotated[NetworkRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    publisher = await publisher_crud.get(db, id)

    if publisher is None:
        raise NotFoundException("Publisher not found")

    await publisher_crud.delete(db, publisher.id)
    return {"message": "Publisher deleted"}
