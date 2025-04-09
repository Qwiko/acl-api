from ipaddress import ip_network
from typing import Any, List, Tuple

from aerleon.api import Generate
from aerleon.lib import naming
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ...models import Network, Policy, PolicyTerm, Service, Target

# from ...crud.crud_networks import crud_networks
# from ...crud.crud_services import crud_services, crud_service_entries


def exclude_networks(excluded_networks: List):
    main_networks = []

    # Add IPv4 main network only if we have IPv4 networks in excluded_networks
    if [net for net in excluded_networks if net.version == 4]:
        main_networks.append(ip_network("0.0.0.0/0"))

    # Add IPv6 main network only if we have IPv6 networks in excluded_networks
    if [net for net in excluded_networks if net.version == 6]:
        main_networks.append(ip_network("::/0"))

    remaining_networks = {net: [net] for net in main_networks}

    for exclude in excluded_networks:
        for main_net in main_networks:
            if exclude.version == main_net.version:  # Process IPv4 and IPv6 separately
                new_remaining = []
                for net in remaining_networks[main_net]:
                    if exclude.subnet_of(net):
                        new_remaining.extend(net.address_exclude(exclude))
                    else:
                        new_remaining.append(net)
                remaining_networks[main_net] = new_remaining

    flatten_nets = [net for nets in remaining_networks.values() for net in nets]

    return flatten_nets


async def get_protocols(db: AsyncSession, service: Service) -> list:
    """Return all used protocols for the service"""

    # nested_service_id = service.get("id")
    # service_entries = await crud_service_entries
    protocols = []
    # for service_entry in service_entries:
    #     if nested_service_id:
    #         nested_service = (
    #             db.session.query(Service).filter(Service.service_id == service_entry.nested_service_id).one_or_none()
    #         )
    #         protocols.extend(nested_service.get_protocols())
    #     else:
    #         protocols.append(service_entry.protocol)

    # Unique list
    return list(set(protocols))


async def get_networks(db: AsyncSession, network: Network) -> list:
    networks = []

    for address in network.addresses:
        if address.nested_network_id:
            result = await db.execute(select(Network).where(Network.id == address.nested_network_id))
            nested_network = result.unique().scalars().all()
            networks.append(await get_networks(db, nested_network))
            continue
        networks.append(address.address)

    return networks


async def get_definitions(db: AsyncSession, negated_terms: List[PolicyTerm] = []) -> list:
    network_dict = {}

    db_networks_data = await db.execute(select(Network).options(selectinload(Network.addresses)))

    networks_data = db_networks_data.scalars().all()

    for network in networks_data:
        network_addresses_arr = []
        for network_address in network.addresses:
            if network_address.nested_network_id:
                db_result = await db.execute(
                    select(Network)
                    .where(Network.id == network_address.nested_network_id)
                    .options(selectinload(Network.addresses))
                )
                nested_network = db_result.scalar_one_or_none()
                if not nested_network:
                    continue

                network_addresses_arr.append(nested_network.hashed_name)
            else:
                network_addresses_arr.append(
                    {
                        "address": str(network_address.address),
                        "comment": network_address.comment,
                    }
                )
        network_dict.update({network.hashed_name: {"values": network_addresses_arr}})

    for negated_term in negated_terms:
        if negated_term.negate_source_networks and negated_term.source_networks:
            networks = []
            for source_network in negated_term.source_networks:
                nets = await get_networks(db, source_network)
                networks.extend(nets)
            negated_networks = exclude_networks(networks)
            network_dict.update(
                {negated_term.hashed_name + "src": {"values": [{"address": str(a)} for a in negated_networks]}}
            )

        if negated_term.negate_destination_networks and negated_term.destination_networks:
            networks = []
            for destination_network in negated_term.destination_networks:
                nets = await get_networks(db, destination_network)
                networks.extend(nets)
            negated_networks = exclude_networks(networks)
            network_dict.update(
                {negated_term.hashed_name + "dst": {"values": [{"address": str(a)} for a in negated_networks]}}
            )

    service_dict = {}

    db_services_data = await db.execute(select(Service).options(selectinload(Service.entries)))

    services_data = db_services_data.scalars().all()

    for service in services_data:
        entries_arr = []
        for service_entry in service.entries:
            if service_entry.nested_service_id:
                db_result = await db.execute(
                    select(Service)
                    .where(Service.id == service_entry.nested_service_id)
                    .options(selectinload(Service.entries))
                )
                nested_service = db_result.scalar_one_or_none()
                if not nested_service:
                    continue

                entries_arr.append(nested_service.name)
            else:
                entry_arr = {"protocol": service_entry.protocol}
                if service_entry.port:
                    entry_arr.update({"port": service_entry.port})
                entries_arr.append(entry_arr)
        service_dict.update({service.name: entries_arr})

    return {"networks": network_dict, "services": service_dict}


async def get_expanded_terms(db: AsyncSession, terms: List[PolicyTerm]) -> List[PolicyTerm]:
    all_terms = []

    for term in terms:
        if term.nested_policy_id:
            res = await db.execute(
                select(Policy)
                .where(Policy.id == term.nested_policy_id)
                .options(selectinload(Policy.terms).options(selectinload(PolicyTerm.policy)))
            )
            nested_policy = res.unique().scalar_one_or_none()
            if not nested_policy:
                continue
            nested_terms = await get_expanded_terms(db, nested_policy.terms)
            all_terms.extend(nested_terms)
            continue
        all_terms.append(term)

    # print([a.valid_name for a in all_terms])
    return all_terms


async def get_service_protocols(db: AsyncSession, service: Service) -> List[str]:
    
    protocols = []

    for entry in service.entries:
        if entry.nested_service_id:
            res = await db.execute(select(Service).where(Service.id == entry.nested_service_id))
            nested_service = res.scalars().one_or_none()
            if not nested_service:
                continue
            protos = await get_service_protocols(db, nested_service)
            protocols.extend(protos)
        else:
            protocols.append(entry.protocol)
    return protocols


async def get_protocol_map(db: AsyncSession, terms: List[PolicyTerm]) -> Any:
    protocol_map = {}

    for term in terms:
        for source_service in term.source_services:
            protos = await get_service_protocols(db, source_service)
            protocol_map.update({source_service.hashed_name: protos})
        for destination_service in term.destination_services:
            protos = await get_service_protocols(db, destination_service)
            protocol_map.update({destination_service.hashed_name: protos})

    return protocol_map


def get_aerleon_terms(terms: List[PolicyTerm], protocol_map) -> List[dict]:
    terms_arr = []

    for term in terms:
        if not term.enabled:
            continue

        term_dict = {
            "name": term.valid_name,
            "action": term.action,
            "source-address": [],
            "destination-address": [],
            "source-port": [],
            "destination-port": [],
            "option": term.option,
        }

        if term.logging:
            term_dict["logging"] = term.logging

        # Networks
        if term.source_networks:
            if term.negate_source_networks:
                term_dict["source-address"].append(term.hashed_name + "src")
            else:
                for source_network in term.source_networks:
                    if source_network:
                        term_dict["source-address"].append(source_network.hashed_name)

        if term.destination_networks:
            if term.negate_destination_networks:
                term_dict["destination-address"].append(term.hashed_name + "dst")
            else:
                for destination_network in term.destination_networks:
                    if destination_network:
                        term_dict["destination-address"].append(destination_network.hashed_name)

        protocols = []
        # Services
        if term.source_services:
            for source_service in term.source_services:
                if source_service:
                    term_dict["source-port"].append(source_service.name)
                    # Add ports
                    protocols.extend(protocol_map.get(source_service.hashed_name))

        if term.destination_services:
            for destination_service in term.destination_services:
                if destination_service:
                    term_dict["destination-port"].append(destination_service.name)
                    # Add ports
                    protocols.extend(protocol_map.get(destination_service.hashed_name))

        if not protocols:
            # Defaults to ip protocol
            terms_arr.append(term_dict)
        else:
            # Unique list of protocols
            protocols = list(set(protocols))

            for protocol in protocols:
                if protocol in ["icmp"]:
                    del term_dict["destination-port"]
                    del term_dict["source-port"]
                
                temp_dict = term_dict.copy() # Copying when iterating
                temp_dict.update({"name": term.valid_name + "-" + protocol, "protocol": protocol})
                terms_arr.append(temp_dict)
    return terms_arr


async def get_policy_and_definitions_from_policy(
    db: AsyncSession, policy: Policy, terms: List[PolicyTerm], target: Target = None, default_action: str = None
) -> Tuple[Any, Any]:
    filter_name = policy.valid_name

    if not target:
        inet_mode = ""
        target_dict = {}
    else:
        inet_mode = target.inet_mode if target.inet_mode else ""

        # Cisco default mode is extended.
        if inet_mode == "inet" and target.generator in ["cisco"]:
            inet_mode = "extended"

        if target.generator == "nftables":
            target_dict = {target.generator: f"{inet_mode} input"}
        else:
            target_dict = {target.generator: f"{filter_name} {inet_mode}"}

    expanded_terms = await get_expanded_terms(db, terms)

    protocol_map = await get_protocol_map(db, expanded_terms)
    
    terms_arr = get_aerleon_terms(expanded_terms, protocol_map)

    if default_action:
        default_term = {}
        if default_action == "accept" or default_action == "accept-log":
            default_term = {
                "name": policy.valid_name + "-Default-Accept",
                "action": "accept",
            }
        elif default_action == "deny" or default_action == "deny-log":
            default_term = {
                "name": policy.valid_name + "-Default-Deny",
                "action": "deny",
            }
        if "log" in default_action:
            default_term.update({"logging": True})
        terms_arr.append(default_term)

    # negated terms
    negated_terms = [term for term in expanded_terms if term.negate_source_networks or term.negate_destination_networks]

    definitions = naming.Naming()
    defs = await get_definitions(db, negated_terms)

    definitions.ParseDefinitionsObject(defs, "")

    policy_dict = {
        "filename": "not_used",
        "filters": [
            {
                "header": {"targets": target_dict, "comment": policy.comment},
                "terms": terms_arr,
            }
        ],
    }
    
    return policy_dict, definitions


async def generate_acl_from_policy(
    db: AsyncSession, policy: Policy, terms: List[PolicyTerm], target: Target, default_action: str = None
) -> Tuple[str, str]:
    """
    Input Policy and Target
    Returns acl as text and filter_name
    """
    policy_dict, definitions = await get_policy_and_definitions_from_policy(db, policy, terms, target, default_action)

    configs = Generate(
        [policy_dict],
        definitions,
    )
    config = configs[configs.keys()[0]]
    if target.generator == "nftables":
        config = config.replace("table inet filtering_policies", f"table bridge {policy.valid_name}")
        config = config.replace("type filter hook input priority 0; policy drop;", "type filter hook postrouting priority 0;")

    return config, policy.valid_name
