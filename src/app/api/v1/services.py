import asyncio
from typing import Annotated, Any, Callable, List

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import and_, exists, or_

from ...core.cruds import entry_crud, service_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...filters.service import ServiceEntryFilter, ServiceFilter
from ...models import PolicyTerm, Service, ServiceEntry
from ...models.policy import PolicyTermDestinationServiceAssociation, PolicyTermSourceServiceAssociation
from ...schemas.service import (
    ServiceCreate,
    ServiceCreated,
    ServiceEntryCreate,
    ServiceEntryRead,
    ServiceEntryUpdate,
    ServiceRead,
    ServiceUpdate,
    ServiceUsage,
)

router = APIRouter(tags=["services"])

func: Callable


@router.get("/services", response_model=Page[ServiceRead])
async def read_services(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    service_filter: ServiceFilter = FilterDepends(ServiceFilter),
) -> Any:
    query = select(Service).outerjoin(ServiceEntry, (Service.id == ServiceEntry.service_id))
    query = service_filter.filter(query)
    query = service_filter.sort(query)

    count_query = select(func.count()).select_from(Service)
    count_query = service_filter.filter(count_query)

    return await paginate(db, query, count_query=count_query)


@router.post("/services", response_model=ServiceCreated, status_code=201)
async def write_service(values: ServiceCreate, db: Annotated[AsyncSession, Depends(async_get_db)]) -> dict:
    # Check if the service name already exists
    found_service = await service_crud.get_all(db, filter_by={"name": values.name})
    if found_service:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A service with this name already exists"}])

    service = await service_crud.create(db, values)

    return service


@router.get("/services/{id}", response_model=ServiceRead)
async def read_service(request: Request, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> dict:
    result = await db.execute(select(Service).where(Service.id == id).options(selectinload(Service.entries)))
    service = result.scalar_one_or_none()

    if not service:
        raise NotFoundException("Service not found")

    return service


@router.put("/services/{id}", response_model=ServiceCreated)
# @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_service(
    request: Request,
    id: int,
    values: ServiceUpdate,
    # current_user: Annotated[ServiceRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, Any]:
    # Check if the service exists
    service = await service_crud.get(db, id)
    if service is None:
        raise NotFoundException("Service not found")

    # Check if the service name exists
    result = await db.execute(select(Service).where(and_(Service.name == values.name, Service.id.notin_([id]))))
    existing_service = result.unique().scalars().one_or_none()
    if existing_service:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A service with this name already exists"}])

    updated_service = await service_crud.update(db, id, values)
    return updated_service


@router.delete("/services/{id}")
async def erase_service(
    id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    nested_entry = await entry_crud.get_all(db, filter_by={"nested_service_id": id})
    if nested_entry:
        raise HTTPException(status_code=403, detail="Cannot delete service with nested entry")

    await service_crud.delete(db, id)
    return {"message": "Service deleted"}


@router.get("/services/{id}/usage", response_model=ServiceUsage)
async def read_service_usage(id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> Any:
    service = await service_crud.get(db, id, True)

    if not service:
        raise NotFoundException("Service not found")

    policies_stmt = (
        select(PolicyTerm.policy_id)
        .distinct()
        .where(
            or_(
                exists(
                    select(PolicyTermSourceServiceAssociation.policy_term_id).where(
                        (PolicyTermSourceServiceAssociation.policy_term_id == PolicyTerm.id)
                        & (PolicyTermSourceServiceAssociation.service_id == id)
                    )
                ),
                exists(
                    select(PolicyTermDestinationServiceAssociation.policy_term_id).where(
                        (PolicyTermDestinationServiceAssociation.policy_term_id == PolicyTerm.id)
                        & (PolicyTermDestinationServiceAssociation.service_id == id)
                    )
                ),
            )
        )
    )

    services_stmt = select(ServiceEntry.service_id).distinct().where(ServiceEntry.nested_service_id == id)

    p_result = db.execute(policies_stmt)
    s_result = db.execute(services_stmt)

    results = await asyncio.gather(p_result, s_result)

    # Unpack results

    policies = results[0].scalars().all()
    services = results[1].scalars().all()

    return {"policies": policies, "services": services}


# ServiceEntry
@router.get("/services/{service_id}/entries", response_model=Page[ServiceEntryRead])
async def read_service_entries(
    service_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    service_entry_filter: ServiceEntryFilter = FilterDepends(ServiceEntryFilter),
) -> List:
    query = select(ServiceEntry).where(ServiceEntry.service_id == service_id)
    query = service_entry_filter.filter(query)
    query = service_entry_filter.sort(query)

    return await paginate(db, query)


@router.post("/services/{service_id}/entries", response_model=ServiceEntryRead, status_code=201)
async def write_entries(
    request: Request,
    service_id: int,
    values: ServiceEntryCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> ServiceEntryRead:
    service = await service_crud.get(db, service_id)

    if service is None:
        raise NotFoundException("Service not found")

    # Check if the nested service exists
    if values.nested_service_id:
        nested_service = await service_crud.get(db, values.nested_service_id)
        if nested_service is None:
            raise RequestValidationError([{"loc": ["body", "nested_service_id"], "msg": "Nested service not found"}])

    # Check if the entry already exists
    existing_entry = await entry_crud.get_all(
        db,
        filter_by={
            "protocol": values.protocol,
            "port": values.port,
            "service_id": service.id,
            "nested_service_id": values.nested_service_id,
        },
    )
    if existing_entry:
        raise RequestValidationError(
            [{"loc": ["body", "protocol", "port"], "msg": "Network protocol + port already exists"}]
        )

    service_entries = await entry_crud.create(db, values, {"service_id": service.id, "service": service})

    return service_entries


@router.get("/services/{service_id}/entries/{id}", response_model=ServiceEntryRead)
async def read_service_entries(
    request: Request, service_id: int, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]
) -> dict:
    service = await service_crud.get(db, service_id)
    if service is None:
        raise NotFoundException("Service not found")
    filter_by = {"service_id": service.id}
    entry = await entry_crud.get(db, id, filter_by=filter_by)

    if entry is None:
        raise NotFoundException("Service entry not found")

    return entry


@router.put("/services/{service_id}/entries/{id}", response_model=ServiceEntryRead)
# @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_service_entries(
    request: Request,
    service_id: int,
    id: int,
    values: ServiceEntryUpdate,
    # current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    service = await service_crud.get(db, service_id)

    if service is None:
        raise NotFoundException("Service not found")

    filter_by = {"service_id": service.id}
    entry = await entry_crud.get(db, id, filter_by=filter_by)

    if entry is None:
        raise NotFoundException("Service entry not found")

    service_entry = await entry_crud.update(db, entry.id, values)

    return service_entry


@router.delete("/services/{service_id}/entries/{id}")
# @cache("{username}_post_cache", resource_id_name="id", to_invalidate_extra={"{username}_posts": "{username}"})
async def erase_service_entries(
    request: Request,
    service_id: int,
    id: int,
    # current_user: Annotated[serviceRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    service = await service_crud.get(db, service_id)

    if service is None:
        raise NotFoundException("Service not found")

    filter_by = {"service_id": service.id}
    address = await entry_crud.get(db, id, filter_by=filter_by)

    if address is None:
        raise NotFoundException("Service address not found")

    await entry_crud.delete(db, address.id)
    return {"message": "Service entry deleted"}
