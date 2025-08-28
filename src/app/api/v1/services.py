import asyncio
from typing import Annotated, Any, Callable, List

from fastapi import APIRouter, Depends, Request, Response, Security
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import and_, exists, or_

from app.core.cruds import entry_crud, service_crud
from app.core.db.database import async_get_db
from app.core.exceptions.http_exceptions import NotFoundException
from app.core.security import User, get_current_user
from app.filters.service import ServiceFilter
from app.models import PolicyTerm, Service, ServiceEntry
from app.models.policy import PolicyTermDestinationServiceAssociation, PolicyTermSourceServiceAssociation
from app.schemas.service import (
    ServiceCreate,
    ServiceCreated,
    ServiceRead,
    ServiceUpdate,
    ServiceUsage,
)

router = APIRouter(tags=["services"])

func: Callable


@router.get("/services", response_model=Page[ServiceRead])
async def read_services(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["services:read"])],
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
    values: ServiceCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["services:write"])],
) -> dict:
    # Check if the service name already exists
    found_service = await service_crud.get_all(db, filter_by={"name": values.name})
    if found_service:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A service with this name already exists"}])

    entries = values.entries or []
    del values.entries

    service = Service(**values.model_dump())

    service.entries = [ServiceEntry(**entry.model_dump(), service=service, service_id=service.id) for entry in entries]

    db.add(service)
    await db.commit()

    return service


@router.get("/services/{service_id}", response_model=ServiceRead)
async def read_service(
    request: Request,
    service_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["services:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict:
    result = await db.execute(select(Service).where(Service.id == service_id).options(selectinload(Service.entries)))
    service = result.scalar_one_or_none()

    if not service:
        raise NotFoundException("Service not found")

    return service


@router.put("/services/{service_id}", response_model=ServiceCreated)
async def put_service(
    request: Request,
    service_id: int,
    values: ServiceUpdate,
    current_user: Annotated[User, Security(get_current_user, scopes=["services:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, Any]:
    # Check if the service exists
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.unique().scalars().one_or_none()
    if not service:
        raise NotFoundException("Service not found")

    # Check if the service name already exists
    result = await db.execute(select(Service).where(and_(Service.name == values.name, Service.id.notin_([service_id]))))
    existing_service = result.unique().scalars().one_or_none()
    if existing_service:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A service with this name already exists"}])

    entries = values.entries or []
    del values.entries

    # Update the existing service
    for k, v in values.model_dump(exclude_unset=True).items():
        setattr(service, k, v)

    # Clear existing cases and add new ones
    service.entries.clear()
    for entry in entries:
        new_entry = ServiceEntry(**entry.model_dump(), service=service, service_id=service.id)
        service.entries.append(new_entry)

    await db.commit()
    await db.refresh(service)
    return service


@router.delete("/services/{service_id}")
async def erase_service(
    service_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["services:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    nested_entry = await entry_crud.get_all(db, filter_by={"nested_service_id": service_id})
    if nested_entry:
        raise HTTPException(status_code=403, detail="Cannot delete service with nested entry")

    await service_crud.delete(db, service_id)
    return {"message": "Service deleted"}


@router.get("/services/{service_id}/usage", response_model=ServiceUsage)
async def read_service_usage(
    service_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["services:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    service = await service_crud.get(db, service_id, True)

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
                        & (PolicyTermSourceServiceAssociation.service_id == service_id)
                    )
                ),
                exists(
                    select(PolicyTermDestinationServiceAssociation.policy_term_id).where(
                        (PolicyTermDestinationServiceAssociation.policy_term_id == PolicyTerm.id)
                        & (PolicyTermDestinationServiceAssociation.service_id == service_id)
                    )
                ),
            )
        )
    )

    services_stmt = select(ServiceEntry.service_id).distinct().where(ServiceEntry.nested_service_id == service_id)

    p_result = db.execute(policies_stmt)
    s_result = db.execute(services_stmt)

    results = await asyncio.gather(p_result, s_result)

    # Unpack results

    policies = results[0].scalars().all()
    services = results[1].scalars().all()

    return {"policies": policies, "services": services}
