import ipaddress
from typing import List, Optional

from sqlalchemy import and_, cast, exists, not_, or_, select
from sqlalchemy.dialects.postgresql import CIDR
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    Network,
    NetworkAddress,
    PolicyTerm,
)
from app.models.dynamic_policy import DynamicPolicyFilterActionEnum
from app.models.policy import PolicyTermDestinationNetworkAssociation, PolicyTermSourceNetworkAssociation


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
    filter_action: Optional[DynamicPolicyFilterActionEnum] = None,
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

    stmt = select(PolicyTerm).distinct().order_by(PolicyTerm.policy_id.asc(), PolicyTerm.id.asc())  # Sort results

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
        conditions.append(PolicyTerm.action == filter_action)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt)

    terms = result.unique().scalars().all()

    customized_terms = []

    for term in terms:
        # Remove the term from the active session so changes are not saved to the db.
        db.expunge(term)
        # Any - Any destination
        if not term.source_networks and not term.destination_networks:
            # Do nothing and use the term as is
            pass

        # Any - some destination
        elif not term.source_networks and term.destination_networks:
            # Filter only if we have destination_networks
            if destination_networks:
                term.destination_networks = [
                    net for net in term.destination_networks if net.id in destination_network_ids
                ]

        # Some source -> some destination
        elif term.source_networks and term.destination_networks:
            # Filter only if we have source_networks
            if source_networks:
                term.source_networks = [net for net in term.source_networks if net.id in source_network_ids]

            # Filter only if we have destination_networks
            if destination_networks:
                term.destination_networks = [
                    net for net in term.destination_networks if net.id in destination_network_ids
                ]

        # Some source -> Any destination
        elif term.source_networks and not term.destination_networks:
            # Filter only if we have source_networks
            if source_networks:
                term.source_networks = [net for net in term.source_networks if net.id in source_network_ids]

        else:
            # Should not ever come here
            pass

        customized_terms.append(term)

    return customized_terms
