import ipaddress
from typing import Annotated, Any, List, Union, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import cast, exists, func, not_, or_, select
from sqlalchemy.dialects.postgresql import CIDR
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.cruds import dynamic_policy_crud, policy_crud, revision_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...core.utils.generate import generate_acl_from_policy
from ...filters.revision import RevisionFilter
from ...models import Network, NetworkAddress, PolicyTerm, Revision, RevisionConfig
from ...models.policy import PolicyTermDestinationNetworkAssociation, PolicyTermSourceNetworkAssociation
from ...schemas.dynamic_policy import DynamicPolicyRead
from ...schemas.policy import PolicyRead
from ...schemas.revision import (
    DynamicPolicyRevisionCreate,
    DynamicPolicyRevisionRead,
    DynamicPolicyRevisionReadBrief,
    PolicyRevisionCreate,
    PolicyRevisionRead,
    PolicyRevisionReadBrief,
)

router = APIRouter(tags=["revisions"])


def is_valid_cidr(cidr: str) -> bool:
    try:
        ipaddress.ip_network(cidr, strict=False)  # `strict=False` allows single IPs like "192.168.1.1/32"
        return True
    except ValueError:
        return False


async def fetch_addresses(db: AsyncSession, network_ids: List[int], return_networks: List[str] = []) -> List[str]:
    """
    Recursively fetches network addresses in CIDR format, including nested networks.
    
    Parameters:
        db (AsyncSession): The SQLAlchemy async session.
        network_ids (List[int]): List of network IDs to fetch addresses from.
        return_networks (List[str], optional): Accumulator for CIDR addresses. Defaults to an empty list.
    
    Returns:
        List[str]: A list of unique CIDR addresses.
    """
    result = await db.execute(select(Network).where(Network.id.in_(network_ids)))
    db_networks = result.unique().scalars().all()

    nested_ids = []

    for network in db_networks:
        for add in network.addresses:
            if add.address:
                return_networks.append(add.address)
            else:
                nested_ids.append(add.nested_network_id)

    if not nested_ids:
        return list(set(return_networks))

    return await fetch_addresses(db, nested_ids, return_networks)


async def fetch_nested_networks(db: AsyncSession, network_ids: list[int], nested_networks: List = []) -> List:
    result = await db.execute(select(NetworkAddress).where(NetworkAddress.nested_network_id.in_(network_ids)))
    addresses = result.scalars().all()

    if not addresses:
        return list(set(nested_networks))

    # Add the current addresses to the nested_networks list
    nested_networks.extend([a.network_id for a in addresses])

    # Recursively fetch nested networks with the updated list of network_ids
    next_network_ids = list({a.network_id for a in addresses})
    return await fetch_nested_networks(db, next_network_ids, nested_networks)


async def fetch_networks(db: AsyncSession, filter_networks: list) -> list:
    stmt = select(NetworkAddress).where(NetworkAddress.nested_network_id == None)

    filters = or_(*[NetworkAddress.address.op("&&")(cast(network, CIDR)) for network in filter_networks])

    stmt = stmt.where(filters)
    result = await db.execute(stmt)
    network_addresses = result.unique().scalars().all()

    network_addresses_ids = [a.id for a in network_addresses]

    # Unique list
    network_ids = list(set([a.network_id for a in network_addresses]))

    # # Execute query asynchronously (for async SQLAlchemy)
    result = await db.execute(select(Network).where(Network.id.in_(network_ids)))
    networks = result.unique().scalars().all()

    # Filter away networks that contain addresses not originally found in network_addresses_ids.
    # That way it does cover too much.
    full_networks = [
        network for network in networks if set([a.id for a in network.addresses]).issubset(network_addresses_ids)
    ]

    # Get all nested_networks.
    nested_networks_ids = await fetch_nested_networks(db, [a.id for a in full_networks])

    # # Execute query asynchronously (for async SQLAlchemy)
    result = await db.execute(select(Network).where(Network.id.in_(nested_networks_ids)))
    nested_networks = result.unique().scalars().all()

    full_nested_networks = [
        network
        for network in nested_networks
        if set([a.nested_network_id for a in network.addresses]).issubset(network_ids + nested_networks_ids)
    ]

    full_all_networks = full_networks + full_nested_networks

    return full_all_networks


async def fetch_terms(
    db: AsyncSession,
    source_networks: List["Network"] = [],
    destination_networks: List["Network"] = [],
    filter_action: Optional[str] = None,
) -> List["PolicyTerm"]:
    """
    Fetches PolicyTerm objects based on source and destination networks, filtering by action if provided.
    
    Parameters:
        db (AsyncSession): The SQLAlchemy async session.
        source_networks (List[Network], optional): List of source networks to filter by. Defaults to an empty list.
        destination_networks (List[Network], optional): List of destination networks to filter by. Defaults to an empty list.
        filter_action (Optional[str], optional): Action filter using SQL LIKE syntax. Defaults to any action.
    
    Returns:
        List[PolicyTerm]: A list of filtered PolicyTerm objects.
    """
    if not filter_action:
        filter_action = "%%"  # SQL LIKE wildcard for matching any action

    # Extract network IDs for both source and destination
    network_ids = {net.id for net in source_networks + destination_networks}
    term_ids = set()

    if network_ids:
        result = await db.execute(
            select(PolicyTermSourceNetworkAssociation.policy_term_id, PolicyTermDestinationNetworkAssociation.policy_term_id)
            .outerjoin(PolicyTermDestinationNetworkAssociation, PolicyTermSourceNetworkAssociation.policy_term_id == PolicyTermDestinationNetworkAssociation.policy_term_id)
            .where(
                or_(
                    PolicyTermSourceNetworkAssociation.network_id.in_(network_ids),
                    PolicyTermDestinationNetworkAssociation.network_id.in_(network_ids)
                )
            )
        )
        term_ids.update(result.scalars().all())

    # Fetch PolicyTerm objects based on the collected term IDs and filtering conditions
    result = await db.execute(
        select(PolicyTerm)
        .where(
            or_(
                PolicyTerm.id.in_(term_ids),  # Terms matching source/destination networks
                not_(
                    exists().where(PolicyTerm.id == PolicyTermSourceNetworkAssociation.policy_term_id)
                ),  # Terms with no associated source networks
                not_(
                    exists().where(PolicyTerm.id == PolicyTermDestinationNetworkAssociation.policy_term_id)
                ),  # Terms with no associated destination networks
            )
        )
        .where(PolicyTerm.action.ilike(filter_action))  # Apply action filter
        .order_by(PolicyTerm.policy_id.asc(), PolicyTerm.lex_order.asc())  # Sort results
    )

    terms = result.unique().scalars().all()
    filtered_terms = []

    # TODO: Optimize filtering to exclude unused networks while preserving term visibility
    for term in terms:
        # Determine if the term matches the requested source or destination networks
        src_match = any(net.id in network_ids for net in term.source_networks)
        dst_match = any(net.id in network_ids for net in term.destination_networks)

        # Include terms based on matching conditions
        if not term.source_networks or not term.destination_networks:  # Any-Any match
            filtered_terms.append(term)
        elif not source_networks and dst_match:  # Match on destination networks only
            filtered_terms.append(term)
        elif src_match and not destination_networks:  # Match on source networks only
            filtered_terms.append(term)
        elif src_match and dst_match:  # Match both source and destination networks
            filtered_terms.append(term)

    return filtered_terms


@router.get("/revisions", response_model=Page[Union[PolicyRevisionReadBrief, DynamicPolicyRevisionReadBrief]])
async def read_revisions(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    revision_filter: RevisionFilter = FilterDepends(RevisionFilter),
) -> Any:
    query = select(Revision)
    query = revision_filter.filter(query)
    query = revision_filter.sort(query)

    count_query = select(func.count()).select_from(Revision)
    count_query = revision_filter.filter(count_query)

    return await paginate(db, query, count_query=count_query)


@router.post("/revisions", response_model=Union[PolicyRevisionRead, DynamicPolicyRevisionRead], status_code=201)
async def write_revision(
    request: Request,
    values: Union[PolicyRevisionCreate, DynamicPolicyRevisionCreate],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    if isinstance(values, DynamicPolicyRevisionCreate):
        dynamic_policy = await dynamic_policy_crud.get(db, values.dynamic_policy_id, load_relations=True)
        source_addresses = (
            await fetch_addresses(db, dynamic_policy.source_filters_ids) if dynamic_policy.source_filters_ids else []
        )
        destination_addresses = (
            await fetch_addresses(db, dynamic_policy.destination_filters_ids)
            if dynamic_policy.destination_filters_ids
            else []
        )

        source_networks = await fetch_networks(db, source_addresses) if source_addresses else []

        destination_networks = await fetch_networks(db, destination_addresses) if destination_addresses else []

        terms = await fetch_terms(
            db,
            source_networks=source_networks,
            destination_networks=destination_networks,
            filter_action=dynamic_policy.filter_action,
        )

        if not terms:
            raise HTTPException(status_code=403, detail="No terms found for dynamic policy")

        pydantic_model = DynamicPolicyRead.model_validate(dynamic_policy, from_attributes=True)

        # Convert to JSON
        json_data = pydantic_model.model_dump_json()

        revision = await revision_crud.create(
            db,
            values,
            {"dynamic_policy_id": dynamic_policy.id, "dynamic_policy": dynamic_policy, "json_data": json_data},
        )

        for target in dynamic_policy.targets:
            acl_filter, filter_name = await generate_acl_from_policy(
                db, dynamic_policy, terms, target, default_action=dynamic_policy.default_action
            )
            revision.configs.append(
                RevisionConfig(
                    revision_id=revision.id,
                    target=target,
                    target_id=target.id,
                    config=acl_filter,
                    filter_name=filter_name,
                    revision=revision,
                )
            )

    else:
        policy = await policy_crud.get(db, values.policy_id, load_relations=True)
        if policy is None:
            raise NotFoundException("Policy not found")

        # Convert SQLAlchemy object to Pydantic model
        pydantic_model = PolicyRead.model_validate(policy, from_attributes=True)

        # Convert to JSON
        json_data = pydantic_model.model_dump_json()

        revision = await revision_crud.create(
            db, values, {"policy_id": policy.id, "policy": policy, "json_data": json_data}
        )

        for target in policy.targets:
            acl_filter, filter_name = await generate_acl_from_policy(db, policy, policy.terms, target)

            revision.configs.append(
                RevisionConfig(
                    revision_id=revision.id,
                    target=target,
                    target_id=target.id,
                    config=acl_filter,
                    filter_name=filter_name,
                    revision=revision,
                )
            )

    await db.commit()
    await db.refresh(revision)

    return revision


@router.get("/revisions/{id}", response_model=Union[PolicyRevisionRead, DynamicPolicyRevisionRead])
async def read_revision(request: Request, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> Any:
    revision = await revision_crud.get(db, id, load_relations=True)

    if revision is None:
        raise NotFoundException("Revision not found")

    return revision


@router.put("/revisions/{id}", response_model=Union[PolicyRevisionRead, DynamicPolicyRevisionRead])
async def update__revision(
    request: Request,
    id: int,
    values: Union[PolicyRevisionCreate, DynamicPolicyRevisionCreate],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    updated_revision = await revision_crud.update(db, id, values)
    return updated_revision


@router.delete("/revisions/{id}")
async def erase_revision(
    request: Request,
    id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    await revision_crud.delete(db, id)
    return {"message": "Revision deleted"}
