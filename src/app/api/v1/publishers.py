from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination import paginate as dict_paginate
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import and_

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
    values: PublisherCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    # Check if the publisher name exists
    existing_publisher = await publisher_crud.get_all(db, filter_by={"name": values.name})
    if existing_publisher:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A publisher with this name already exists"}])

    # Check if the target exists
    target = await target_crud.get(db, values.target)
    if target is None:
        raise RequestValidationError([{"loc": ["body", "target"], "msg": "That target does not exist"}])

    del values.target

    publisher = await publisher_crud.create(
        db,
        values,
        {"target": target},
    )

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
    id: int,
    values: PublisherUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    publisher = await publisher_crud.get(db, id)

    if publisher is None:
        raise NotFoundException("Publisher not found")

    # Check if the publisher name exists
    result = await db.execute(
        select(Publisher).where(and_(Publisher.name == values.name, Publisher.id.notin_([publisher.id])))
    )
    existing_publisher = result.unique().scalars().one_or_none()
    if existing_publisher:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A publisher with this name already exists"}])

    # Check if the target exists
    target = await target_crud.get(db, values.target)
    if target is None:
        raise RequestValidationError([{"loc": ["body", "target"], "msg": "That target does not exist"}])

    del values.target

    publisher = await publisher_crud.update(
        db,
        publisher.id,
        values,
        {"target": target},
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
