import asyncio
from typing import Annotated, Any, Callable, List

from fastapi import APIRouter, Depends, Request, Security
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import and_, exists, or_

from ...core.cruds import address_crud, network_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...core.security import User, get_current_user
from ...filters.network import NetworkFilter
from ...models import DynamicPolicy, Network, NetworkAddress, PolicyTerm
from ...models.dynamic_policy import DynamicPolicyDestinationFilterAssociation, DynamicPolicySourceFilterAssociation
from ...models.policy import PolicyTermDestinationNetworkAssociation, PolicyTermSourceNetworkAssociation
from ...schemas.network import (
    NetworkCreate,
    NetworkCreated,
    NetworkRead,
    NetworkUpdate,
    NetworkUsage,
)

router = APIRouter(tags=["networks"])

func: Callable


@router.get("/networks", response_model=Page[NetworkRead])
async def read_networks(
    current_user: Annotated[User, Security(get_current_user, scopes=["networks:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    network_filter: NetworkFilter = FilterDepends(NetworkFilter),
) -> Any:
    query = select(Network)  # .outerjoin(NetworkAddress, (Network.id == NetworkAddress.network_id))
    query = network_filter.filter(query)
    query = network_filter.sort(query)

    count_query = select(func.count()).select_from(Network)
    count_query = network_filter.filter(count_query)

    return await paginate(db, query, count_query=count_query)


@router.post("/networks", response_model=NetworkCreated, status_code=201)
async def write_network(
    values: NetworkCreate,
    current_user: Annotated[User, Security(get_current_user, scopes=["networks:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    # Check if the network name already exists
    found_network = await network_crud.get_all(db, filter_by={"name": values.name})
    if found_network:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A network with this name already exists"}])

    addresses = values.addresses or []
    del values.addresses

    network = Network(**values.model_dump())

    network.addresses = [
        NetworkAddress(**address.model_dump(), network=network, network_id=network.id) for address in addresses
    ]

    db.add(network)
    await db.commit()

    return network


@router.get("/networks/{network_id}", response_model=NetworkRead)
async def read_network(
    request: Request,
    network_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["networks:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict:
    result = await db.execute(select(Network).where(Network.id == network_id))
    network = result.unique().scalars().one_or_none()

    return network


@router.put("/networks/{network_id}", response_model=NetworkCreated)
async def put_network(
    network_id: int,
    values: NetworkUpdate,
    current_user: Annotated[User, Security(get_current_user, scopes=["networks:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, Any]:
    # Check if the network exists
    result = await db.execute(select(Network).where(Network.id == network_id))
    network = result.unique().scalars().one_or_none()
    if not network:
        raise NotFoundException("Network not found")

    # Check if the network name already exists
    result = await db.execute(select(Network).where(and_(Network.name == values.name, Network.id.notin_([network_id]))))
    existing_network = result.unique().scalars().one_or_none()
    if existing_network:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A network with this name already exists"}])

    addresses = values.addresses or []
    del values.addresses

    # Update the existing network
    for k, v in values.model_dump(exclude_unset=True).items():
        setattr(network, k, v)

    # Clear existing addresses and add new ones
    network.addresses.clear()
    for address in addresses:
        new_address = NetworkAddress(**address.model_dump(), network=network, network_id=network.id)
        # print(new_address)
        network.addresses.append(new_address)

    await db.commit()
    await db.refresh(network)
    return network


@router.delete("/networks/{network_id}")
async def erase_network(
    request: Request,
    network_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["networks:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    nested_address = await address_crud.get_all(db, filter_by={"nested_network_id": network_id})
    if nested_address:
        raise HTTPException(status_code=403, detail="Cannot delete network with nested addresses")

    # Check if the network exists
    network = await network_crud.get(db, network_id)
    if not network:
        raise NotFoundException("Network not found")

    await network_crud.delete(db, network_id)
    return {"message": "Network deleted"}


@router.get("/networks/{network_id}/usage", response_model=NetworkUsage)
async def read_network_usage(
    request: Request,
    network_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["networks:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    network = await network_crud.get(db, network_id, True)

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
                        & (DynamicPolicySourceFilterAssociation.network_id == network_id)
                    )
                ),
                exists(
                    select(DynamicPolicyDestinationFilterAssociation.dynamic_policy_id).where(
                        (DynamicPolicyDestinationFilterAssociation.dynamic_policy_id == DynamicPolicy.id)
                        & (DynamicPolicyDestinationFilterAssociation.network_id == network_id)
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
                        & (PolicyTermSourceNetworkAssociation.network_id == network_id)
                    )
                ),
                exists(
                    select(PolicyTermDestinationNetworkAssociation.policy_term_id).where(
                        (PolicyTermDestinationNetworkAssociation.policy_term_id == PolicyTerm.id)
                        & (PolicyTermDestinationNetworkAssociation.network_id == network_id)
                    )
                ),
            )
        )
    )

    networks_stmt = select(NetworkAddress.network_id).distinct().where(NetworkAddress.nested_network_id == network_id)

    d_result = db.execute(dynamic_policies_stmt)
    p_result = db.execute(policies_stmt)
    n_result = db.execute(networks_stmt)

    results = await asyncio.gather(d_result, p_result, n_result)

    # Unpack results
    dynamic_policies = results[0].scalars().all()
    policies = results[1].scalars().all()
    networks = results[2].scalars().all()

    return {"dynamic_policies": dynamic_policies, "policies": policies, "networks": networks}
