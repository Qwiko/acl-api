import asyncio
from typing import Annotated, Any, List

from fastapi import APIRouter, Depends, Request, Response
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import exists, or_

from ...core.cruds import entry_crud, service_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...filters.service import ServiceFilter
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
async def write_service(
    request: Request, data: ServiceCreate, db: Annotated[AsyncSession, Depends(async_get_db)]
) -> dict:
    service_dict = data.model_dump()
    service = Service(entries=[], **service_dict)

    db.add(service)
    await db.commit()

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
    db_service_result = await db.execute(select(Service).where(Service.id == id))
    db_service = db_service_result.scalars().first()
    if db_service is None:
        raise NotFoundException("Service not found")

    for key, value in vars(values).items():
        setattr(db_service, key, value)

    await db.commit()
    await db.refresh(db_service)
    return db_service


@router.delete("/services/{id}")
async def erase_service(
    request: Request,
    id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    await service_crud.delete(db, id)
    return {"message": "Service deleted"}


@router.get("/services/{id}/usage", response_model=ServiceUsage)
async def read_service_usage(request: Request, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> Any:
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
@router.get("/services/{service_id}/entries", response_model=List[ServiceEntryRead])
async def read_service_entries(
    request: Request,
    response: Response,
    service_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> List:
    db_service = await db.execute(select(Service).where(Service.id == service_id))
    if db_service is None:
        raise NotFoundException("Service not found")

    db_entries = await db.execute(select(ServiceEntry).where(ServiceEntry.service_id == service_id))

    entries = db_entries.scalars().all()
    response.headers["content-range"] = "entries 0-2/2"
    response.headers["Access-Control-Expose-Headers"] = "Content-Range"

    return entries


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
    address = await entry_crud.get(db, id, filter_by=filter_by)

    if address is None:
        raise NotFoundException("Service address not found")

    return address


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
    address = await entry_crud.get(db, id, filter_by=filter_by)

    if address is None:
        raise NotFoundException("Service address not found")

    service_entry = await entry_crud.update(db, address.id, values)

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
