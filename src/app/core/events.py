import asyncio
import logging

from sqlalchemy import event, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import and_, exists, or_

from app.models import DynamicPolicy, Network, NetworkAddress, Policy, PolicyTerm, Service, ServiceEntry, Target
from app.models.dynamic_policy import DynamicPolicyDestinationFilterAssociation, DynamicPolicySourceFilterAssociation
from app.models.policy import (
    PolicyTermDestinationNetworkAssociation,
    PolicyTermDestinationServiceAssociation,
    PolicyTermSourceNetworkAssociation,
    PolicyTermSourceServiceAssociation,
)


async def handle_network(session: AsyncSession, obj: Network):
    network_id = obj.id
    dynamic_policies_stmt = (
        select(DynamicPolicy)
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

    policy_ids_stmt = (
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

    networks_stmt = select(NetworkAddress.network).distinct().where(NetworkAddress.nested_network_id == network_id)

    dynamic_policies = (await session.execute(dynamic_policies_stmt)).unique().scalars().all()

    policy_ids = (await session.execute(policy_ids_stmt)).scalars().all()

    policies_stmt = select(Policy).distinct().where(Policy.id.in_(policy_ids))
    policies = (await session.execute(policies_stmt)).unique().scalars().all()

    networks = (await session.execute(networks_stmt)).unique().scalars().all()

    # Loop over all referenced networks and run the same function for them
    for nested_ref_network in networks:
        handle_network(session, nested_ref_network)

    # Set policy to edited = true
    for policy in policies:
        policy.edited = True

    # Set dynamic_policy to edited = true
    for dynamic_policy in dynamic_policies:
        dynamic_policy.edited = True


async def handle_service(session: AsyncSession, obj: Service):
    service_id = obj.id
    policy_ids_stmt = (
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

    services_stmt = select(ServiceEntry.service).distinct().where(ServiceEntry.nested_service_id == service_id)

    policy_ids = (await session.execute(policy_ids_stmt)).scalars().all()

    policies_stmt = select(Policy).distinct().where(Policy.id.in_(policy_ids))
    policies = (await session.execute(policies_stmt)).unique().scalars().all()

    services = (await session.execute(services_stmt)).unique().scalars().all()

    # Loop over all referenced networks and run the same function for them
    for nested_ref_service in services:
        handle_service(session, nested_ref_service)

    # Set policy to edited = true
    for policy in policies:
        policy.edited = True
    await session.commit()


async def handle_target(session: AsyncSession, obj: Target):
    policies_stmt = select(Policy).distinct().where(Policy.targets.any(Target.id == obj.id))
    dynamic_policies_stmt = select(DynamicPolicy).distinct().where(DynamicPolicy.targets.any(Target.id == obj.id))

    policies = (await session.execute(policies_stmt)).unique().scalars().all()
    dynamic_policies = (await session.execute(dynamic_policies_stmt)).unique().scalars().all()

    # Set policy to edited = true
    for policy in policies:
        policy.edited = True

    for dynamic_policy in dynamic_policies:
        dynamic_policy.edited = True


async def handle_policy(session: AsyncSession, obj: Policy):
    policies_stmt = select(PolicyTerm.policy).distinct().where(PolicyTerm.nested_policy_id == obj.id)

    policies = (await session.execute(policies_stmt)).unique().scalars().all()

    # Set policy to edited = true
    for policy in policies:
        policy.edited = True

    # TODO Dynamic Policy Terms


def register_events():
    pass
    # @event.listens_for(Session, "after_flush")
    # def after_flush(session: Session, flush_context):
    #     async def internal_func(obj_data):
    #         from app.core.db.database import async_get_db

    #         async_session = await anext(async_get_db())
    #         for obj in obj_data:
    #             if isinstance(obj, Network):
    #                 await handle_network(async_session, obj)
    #             elif isinstance(obj, Service):
    #                 await handle_service(async_session, obj)
    #             elif isinstance(obj, Target):
    #                 await handle_target(async_session, obj)
    #             elif isinstance(obj, Policy):
    #                 await handle_policy(async_session, obj)
    #         await async_session.commit()
    #         await async_session.close()

    #     asyncio.create_task(internal_func(session.new.union(session.dirty).union(session.deleted)))
