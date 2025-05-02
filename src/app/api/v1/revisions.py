import json
from typing import Annotated, Any, Callable, Union

from fastapi.responses import PlainTextResponse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.cruds import deployer_crud, dynamic_policy_crud, policy_crud, revision_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...core.utils import queue
from ...core.utils.generate import generate_acl_from_policy, get_expanded_terms
from ...filters.revision import RevisionFilter
from ...models import (
    Deployment,
    Policy,
    Revision,
    RevisionConfig,
)
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
from .tests import get_tests_run
from ...core.utils.dynamic_policy_helpers import fetch_addresses, fetch_networks, fetch_terms

router = APIRouter(tags=["revisions"])

func: Callable


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
    values: Union[PolicyRevisionCreate, DynamicPolicyRevisionCreate],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    # Run tests and check test coverage
    if isinstance(values, DynamicPolicyRevisionCreate):
        test_dict = await get_tests_run(db=db, dynamic_policy_id=values.dynamic_policy_id)
    else:
        test_dict = await get_tests_run(db=db, policy_id=values.policy_id)

    coverage = test_dict.get("coverage", 0.0)
    if coverage < 1.0:
        raise HTTPException(
            status_code=403, detail=f"Test coverage {round(coverage*100)}% is lower than the required 100%"
        )

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


@router.get("/revisions/{revision_id}", response_model=Union[PolicyRevisionRead, DynamicPolicyRevisionRead])
async def read_revision(request: Request, revision_id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> Any:
    revision = await revision_crud.get(db, revision_id, load_relations=True)

    if revision is None:
        raise NotFoundException("Revision not found")

    return revision


@router.put("/revisions/{revision_id}", response_model=Union[PolicyRevisionRead, DynamicPolicyRevisionRead])
async def update_revision(
    request: Request,
    revision_id: int,
    values: Union[PolicyRevisionCreate, DynamicPolicyRevisionCreate],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    updated_revision = await revision_crud.update(db, revision_id, values)
    return updated_revision


@router.delete("/revisions/{revision_id}")
async def erase_revision(
    request: Request,
    revision_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    await revision_crud.delete(db, revision_id)
    return {"message": "Revision deleted"}


@router.get("/revisions/{revision_id}/raw_config", response_class=PlainTextResponse)  # , response_model=Response)
async def read_revision_config_raw(
    revision_id: int,
    target_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    """
    Get the raw config for a revision and target.
    """
    res = await db.execute(
        select(RevisionConfig)
        .where(RevisionConfig.revision_id == revision_id)
        .where(RevisionConfig.target_id == target_id)
    )

    revision_config: RevisionConfig = res.scalars().one_or_none()

    if revision_config is None:
        raise NotFoundException("RevisionConfig not found")

    return revision_config.config


@router.post("/revisions/{revision_id}/deploy", response_model=Any, status_code=201)
async def deploy_revision(
    revision_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    revision: Revision = await revision_crud.get(db, revision_id, load_relations=True)

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
                **{"revision_id": revision_id, "deployer_id": deployer.id, "deployment_id": deployment.id},
            )
            deployment_ids.append(deployment.id)

    if not deployment_ids:
        raise HTTPException(status_code=404, detail="No associated deployers found for this revision")

    return {"message": "Publish started", "deployment_ids": deployment_ids}
