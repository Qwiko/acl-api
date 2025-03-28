import asyncio
from typing import Annotated, Any, List

from fastapi import APIRouter, Depends, Request, Response
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import exists, or_

from ...core.cruds import address_crud, network_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...filters.network import NetworkFilter
from ...models import DynamicPolicy, Network, NetworkAddress, PolicyTerm
from ...models.dynamic_policy import DynamicPolicyDestinationFilterAssociation, DynamicPolicySourceFilterAssociation
from ...models.policy import PolicyTermDestinationNetworkAssociation, PolicyTermSourceNetworkAssociation
from ...schemas.network import (
    NetworkAddressCreate,
    NetworkAddressRead,
    NetworkAddressUpdate,
    NetworkCreate,
    NetworkCreated,
    NetworkRead,
    NetworkUpdate,
    NetworkUsage,
)

router = APIRouter(tags=["networks"])


@router.get("/networks", response_model=Page[NetworkRead])
async def read_networks(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    network_filter: NetworkFilter = FilterDepends(NetworkFilter),
) -> Any:
    query = select(Network).outerjoin(NetworkAddress, (Network.id == NetworkAddress.network_id))
    query = network_filter.filter(query)
    query = network_filter.sort(query)

    count_query = select(func.count()).select_from(Network)
    count_query = network_filter.filter(count_query)

    return await paginate(db, query, count_query=count_query)


@router.post("/networks", response_model=NetworkCreated, status_code=201)
async def write_network(
    request: Request,
    data: NetworkCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    network_dict = data.model_dump()
    network = Network(addresses=[], **network_dict)

    db.add(network)
    await db.commit()

    return network


@router.get("/networks/{id}", response_model=NetworkRead)
async def read_network(request: Request, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> dict:
    network = await network_crud.get(db, id, True)

    if not network:
        raise NotFoundException("Network not found")

    return network


@router.put("/networks/{id}", response_model=NetworkCreated)
# @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_network(
    request: Request,
    id: int,
    values: NetworkUpdate,
    # current_user: Annotated[NetworkRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, Any]:
    updated_network = await network_crud.update(db, id, values)
    return updated_network


@router.delete("/networks/{id}")
async def erase_network(
    request: Request,
    id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    await network_crud.delete(db, id)
    return {"message": "Network deleted"}


@router.get("/networks/{id}/usage", response_model=NetworkUsage)
async def read_network_usage(request: Request, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> Any:
    network = await network_crud.get(db, id, True)

    if not network:
        raise NotFoundException("Network not found")

    dynamic_policies_stmt = (
        select(DynamicPolicy.id)
        .distinct()
        .where(
            or_(
                exists(
                    select(DynamicPolicySourceFilterAssociation.dynamic_policy_id).where(
                        (DynamicPolicySourceFilterAssociation.dynamic_policy_id == DynamicPolicy.id)
                        & (DynamicPolicySourceFilterAssociation.network_id == id)
                    )
                ),
                exists(
                    select(DynamicPolicyDestinationFilterAssociation.dynamic_policy_id).where(
                        (DynamicPolicyDestinationFilterAssociation.dynamic_policy_id == DynamicPolicy.id)
                        & (DynamicPolicyDestinationFilterAssociation.network_id == id)
                    )
                ),
            )
        )
    )

    policies_stmt = (
        select(PolicyTerm.policy_id)
        .distinct()
        .where(
            or_(
                exists(
                    select(PolicyTermSourceNetworkAssociation.policy_term_id).where(
                        (PolicyTermSourceNetworkAssociation.policy_term_id == PolicyTerm.id)
                        & (PolicyTermSourceNetworkAssociation.network_id == id)
                    )
                ),
                exists(
                    select(PolicyTermDestinationNetworkAssociation.policy_term_id).where(
                        (PolicyTermDestinationNetworkAssociation.policy_term_id == PolicyTerm.id)
                        & (PolicyTermDestinationNetworkAssociation.network_id == id)
                    )
                ),
            )
        )
    )

    networks_stmt = select(NetworkAddress.network_id).distinct().where(NetworkAddress.nested_network_id == id)

    d_result = db.execute(dynamic_policies_stmt)
    p_result = db.execute(policies_stmt)
    n_result = db.execute(networks_stmt)

    results = await asyncio.gather(d_result, p_result, n_result)

    # Unpack results
    dynamic_policies = results[0].scalars().all()
    policies = results[1].scalars().all()
    networks = results[2].scalars().all()

    return {"dynamic_policies": dynamic_policies, "policies": policies, "networks": networks}


# NetworkAddress
@router.get("/networks/{network_id}/addresses", response_model=List[NetworkAddressRead])
async def read_addresses(
    request: Request,
    response: Response,
    network_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    page: int = 1,
    items_per_page: int = 10,
) -> List:
    db_network = await db.execute(select(Network).where(Network.id == network_id))
    if db_network is None:
        raise NotFoundException("Network not found")

    db_addresses = await db.execute(select(NetworkAddress).where(NetworkAddress.network_id == network_id))

    addresses = db_addresses.scalars().all()
    response.headers["content-range"] = "addresses 0-2/2"
    response.headers["Access-Control-Expose-Headers"] = "Content-Range"

    return addresses


@router.post("/networks/{network_id}/addresses", response_model=NetworkAddressRead, status_code=201)
async def write_network_address(
    request: Request,
    network_id: int,
    values: NetworkAddressCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> NetworkAddressRead:
    network = await network_crud.get(db, network_id)

    if network is None:
        raise NotFoundException("Network not found")

    network_address = await address_crud.create(db, values, {"network_id": network.id, "network": network})

    return network_address


@router.get("/networks/{network_id}/addresses/{id}", response_model=NetworkAddressRead)
async def read_network_address(
    request: Request, network_id: int, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]
) -> dict:
    network = await network_crud.get(db, network_id)
    if network is None:
        raise NotFoundException("Network not found")
    filter_by = {"network_id": network.id}
    address = await address_crud.get(db, id, filter_by=filter_by)

    if address is None:
        raise NotFoundException("Network address not found")

    return address


@router.put("/networks/{network_id}/addresses/{id}", response_model=NetworkAddressRead)
# @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_network_address(
    request: Request,
    network_id: int,
    id: int,
    values: NetworkAddressUpdate,
    # current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    network = await network_crud.get(db, network_id)

    if network is None:
        raise NotFoundException("Network not found")

    filter_by = {"network_id": network.id}
    address = await address_crud.get(db, id, filter_by=filter_by)

    if address is None:
        raise NotFoundException("Network address not found")

    network_address = await address_crud.update(db, address.id, values)

    return network_address


@router.delete("/networks/{network_id}/addresses/{id}")
# @cache("{username}_post_cache", resource_id_name="id", to_invalidate_extra={"{username}_posts": "{username}"})
async def erase_network_address(
    request: Request,
    network_id: int,
    id: int,
    # current_user: Annotated[NetworkRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    network = await network_crud.get(db, network_id)

    if network is None:
        raise NotFoundException("Network not found")

    filter_by = {"network_id": network.id}
    address = await address_crud.get(db, id, filter_by=filter_by)

    if address is None:
        raise NotFoundException("Network address not found")

    await address_crud.delete(db, address.id)
    
    return {"message": "Network address deleted"}
