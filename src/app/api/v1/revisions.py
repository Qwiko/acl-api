import ipaddress
import json
from typing import Annotated, Any, List, Optional, Union, Callable

from arq.jobs import Job as ArqJob
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_, cast, exists, func, not_, or_, select
from sqlalchemy.dialects.postgresql import CIDR
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from ...core.cruds import dynamic_policy_crud, policy_crud, deployer_crud, deployment_crud, revision_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...core.utils import queue
from ...core.utils.generate import generate_acl_from_policy, get_expanded_terms
from ...filters.revision import RevisionFilter
from ...models import (
    DynamicPolicy,
    Network,
    NetworkAddress,
    Policy,
    PolicyTerm,
    Deployment,
    Revision,
    RevisionConfig,
)
from ...models.policy import PolicyTermDestinationNetworkAssociation, PolicyTermSourceNetworkAssociation
from ...schemas.dynamic_policy import DynamicPolicyRead

from ...schemas.policy import PolicyRead, PolicyTermRead
from ...schemas.revision import (
    DynamicPolicyRevisionCreate,
    DynamicPolicyRevisionRead,
    DynamicPolicyRevisionReadBrief,
    PolicyRevisionCreate,
    PolicyRevisionRead,
    PolicyRevisionReadBrief,
)

router = APIRouter(tags=["revisions"])

func: Callable


def is_valid_cidr(cidr: str) -> bool:
    try:
        ipaddress.ip_network(cidr, strict=False)  # `strict=False` allows single IPs like "192.168.1.1/32"
        return True
    except ValueError:
        return False


async def fetch_addresses(db: AsyncSession, network_ids: List[int], return_networks: List[str] = None) -> List[str]:
    """
    Recursively fetches network addresses in CIDR format, including nested networks.

    Parameters:
        db (AsyncSession): The SQLAlchemy async session.
        network_ids (List[int]): List of network IDs to fetch addresses from.
        return_networks (List[str], optional): Accumulator for CIDR addresses. Defaults to an empty list.

    Returns:
        List[str]: A list of unique CIDR addresses.
    """
    if return_networks is None:
        return_networks = []

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


async def fetch_nested_networks(db: AsyncSession, network_ids: list[int], nested_networks: List = None) -> List:
    if not nested_networks:
        nested_networks = []

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
    policy_ids: List[int] = [],
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
    # Extract network IDs for both source and destination
    source_network_ids = {net.id for net in source_networks}
    destination_network_ids = {net.id for net in destination_networks}

    stmt = (
        select(PolicyTerm).distinct().order_by(PolicyTerm.policy_id.asc(), PolicyTerm.lex_order.asc())
    )  # Sort results

    stmt = stmt.join(
        PolicyTermSourceNetworkAssociation,
        PolicyTerm.id == PolicyTermSourceNetworkAssociation.policy_term_id,
        isouter=True,
    ).join(
        PolicyTermDestinationNetworkAssociation,
        PolicyTerm.id == PolicyTermDestinationNetworkAssociation.policy_term_id,
        isouter=True,
    )

    policy_term_alias = aliased(PolicyTerm)

    source_condition = None
    if source_network_ids:
        # If we have some source filter, only match on that
        source_condition = or_(
            and_(
                PolicyTerm.negate_source_networks.is_(False),
                PolicyTermSourceNetworkAssociation.network_id.in_(source_network_ids),
            ),
            and_(
                PolicyTerm.negate_source_networks.is_(True),
                PolicyTermSourceNetworkAssociation.network_id.notin_(source_network_ids),
            ),
        )
    else:
        # Otherwise we need to match everything else
        source_condition = PolicyTermSourceNetworkAssociation.network_id.notin_(source_network_ids)

    destination_condition = None
    if destination_network_ids:
        # If we have some destination filter, only match on that
        destination_condition = or_(
            and_(
                PolicyTerm.negate_destination_networks.is_(False),
                PolicyTermDestinationNetworkAssociation.network_id.in_(destination_network_ids),
            ),
            and_(
                PolicyTerm.negate_destination_networks.is_(True),
                PolicyTermDestinationNetworkAssociation.network_id.notin_(destination_network_ids),
            ),
        )
    else:
        # Otherwise we need to match everything else
        destination_condition = PolicyTermDestinationNetworkAssociation.network_id.notin_(destination_network_ids)

    conditions = [
        and_(
            or_(
                source_condition,  # Match some source networks
                not_(
                    exists().where(
                        policy_term_alias.id == PolicyTermSourceNetworkAssociation.policy_term_id
                    )  # Or match Any source terms
                ),
            ),
            or_(
                destination_condition,  # Match some destination networks
                not_(
                    exists().where(
                        policy_term_alias.id == PolicyTermDestinationNetworkAssociation.policy_term_id
                    )  # Or match Any destination terms
                ),
            ),
        ),
    ]

    if policy_ids:
        conditions.append(PolicyTerm.policy_id.in_(policy_ids))

    if filter_action:
        conditions.append(PolicyTerm.action.ilike(filter_action))

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt)

    terms = result.unique().scalars().all()

    return terms


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

        policy_ids_stmt = select(Policy.id).where(Policy.id.in_(dynamic_policy.policy_filters_ids))
        policy_ids_res = await db.execute(policy_ids_stmt)
        policy_ids = policy_ids_res.unique().scalars().all()

        source_networks = await fetch_networks(db, source_addresses) if source_addresses else []

        destination_networks = await fetch_networks(db, destination_addresses) if destination_addresses else []

        terms = await fetch_terms(
            db,
            source_networks=source_networks,
            destination_networks=destination_networks,
            policy_ids=policy_ids,
            filter_action=dynamic_policy.filter_action,
        )

        if not terms:
            raise HTTPException(status_code=403, detail="No terms found for dynamic policy")

        policy_pydantic_model = DynamicPolicyRead.model_validate(dynamic_policy, from_attributes=True)

        policy_json_data = policy_pydantic_model.model_dump_json()

        terms_pydantic_model = [
            PolicyTermRead.model_validate(expanded_term, from_attributes=True) for expanded_term in terms
        ]

        terms_json_data = json.dumps([t.model_dump() for t in terms_pydantic_model])

        revision = await revision_crud.create(
            db,
            values,
            {
                "dynamic_policy_id": dynamic_policy.id,
                "dynamic_policy": dynamic_policy,
                "json_data": policy_json_data,
                "expanded_terms": terms_json_data,
            },
        )

        for target in dynamic_policy.targets:
            acl_filter, filter_name, filename = await generate_acl_from_policy(
                db, dynamic_policy, terms, target, default_action=dynamic_policy.default_action
            )
            revision.configs.append(
                RevisionConfig(
                    revision_id=revision.id,
                    target=target,
                    target_id=target.id,
                    filename=filename,
                    config=acl_filter,
                    filter_name=filter_name,
                    revision=revision,
                )
            )

    else:
        policy = await policy_crud.get(db, values.policy_id, load_relations=True)
        if policy is None:
            raise NotFoundException("Policy not found")

        policy_pydantic_model = PolicyRead.model_validate(policy, from_attributes=True)

        policy_json_data = policy_pydantic_model.model_dump_json()

        expanded_terms = await get_expanded_terms(db, policy.terms)

        terms_pydantic_model = [
            PolicyTermRead.model_validate(expanded_term, from_attributes=True) for expanded_term in expanded_terms
        ]

        terms_json_data = json.dumps([t.model_dump() for t in terms_pydantic_model])

        revision = await revision_crud.create(
            db,
            values,
            {
                "policy_id": policy.id,
                "policy": policy,
                "json_data": policy_json_data,
                "expanded_terms": terms_json_data,
            },
        )

        for target in policy.targets:
            acl_filter, filter_name, filename = await generate_acl_from_policy(db, policy, expanded_terms, target)

            revision.configs.append(
                RevisionConfig(
                    revision_id=revision.id,
                    target=target,
                    target_id=target.id,
                    filename=filename,
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
async def update_revision(
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


@router.post("/revisions/{id}/deploy", response_model=Any, status_code=201)
async def deploy_revision(
    id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    revision: Revision = await revision_crud.get(db, id, load_relations=True)

    if revision is None:
        raise NotFoundException("Revision not found")

    target_ids = [config.target_id for config in revision.configs]

    deployment_ids = []

    for target_id in target_ids:
        deployers = await deployer_crud.get_all(db, load_relations=True, filter_by={"target_id": target_id})

        if not deployers:
            continue

        for deployer in deployers:
            # Create a new deployment
            deployment = Deployment(
                deployer_id=deployer.id,
                deployer=deployer,
                revision=revision,
                revision_id=revision.id,
                status="pending",
            )
            db.add(deployment)
            await db.commit()
            await db.refresh(deployment)

            function_map = {
                "git": "deploy_git",
                "netmiko": "deploy_netmiko",
                "proxmox_nft": "deploy_proxmox_nft",
            }

            await queue.pool.enqueue_job(
                function_map.get(deployer.mode),
                _job_id=str(deployment.id),
                **{"revision_id": id, "deployer_id": deployer.id, "deployment_id": deployment.id},
            )
            deployment_ids.append(deployment.id)

    if not deployment_ids:
        raise HTTPException(status_code=404, detail="No associated deployers found for this revision")

    return {"message": "Publish started", "deployment_ids": deployment_ids}
