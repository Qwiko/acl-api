from typing import Annotated, Any, Union

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.cruds import network_crud, policy_crud, service_crud
from app.core.db.database import async_get_db
from app.core.exceptions.http_exceptions import NotFoundException
from app.core.security import User, get_current_user
from app.filters.policy import PolicyFilter
from app.models import Policy, PolicyTerm, Target, Test
from app.schemas.policy import (
    PolicyCreate,
    PolicyCreated,
    PolicyRead,
    PolicyReadBrief,
    PolicyTermCreate,
    PolicyTermNestedCreate,
    PolicyTermNestedUpdate,
    PolicyTermUpdate,
    PolicyUpdate,
    PolicyUsage,
)

router = APIRouter(tags=["policies"])


# Policy
@router.get("/policies", response_model=Page[PolicyReadBrief])
async def read_policies(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:read"])],
    policy_filter: PolicyFilter = FilterDepends(PolicyFilter),
) -> Any:
    query = select(Policy)
    query = policy_filter.filter(query)
    query = policy_filter.sort(query)
    return await paginate(db, query)


@router.post("/policies", response_model=PolicyCreated, status_code=201)
async def write_policy(
    values: PolicyCreate,
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    # Check if the policy name already exists
    found_policy = await policy_crud.get_all(db, filter_by={"name": values.name})
    if found_policy:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A policy with this name already exists"}])

    targets = values.targets or []
    tests = values.tests or []
    terms = values.terms or []
    del values.targets
    del values.tests
    del values.terms

    # Create the new policy
    policy = Policy(**values.model_dump(), edited=True)

    # Fetch related targets and tests
    targets_db = await db.execute(select(Target).where(Target.id.in_(targets)))
    tests_db = await db.execute(select(Test).where(Test.id.in_(tests)))

    # Assign targets and tests to the policy
    policy.targets = targets_db.unique().scalars().all()
    policy.tests = tests_db.unique().scalars().all()

    # Validate terms
    for term in terms:
        # Check if the term name already exists in the policy
        if len([t for t in terms if t.name == term.name]) > 1:
            raise RequestValidationError([{"loc": ["body", "terms"], "msg": "Term names must be unique"}])

    # Process terms
    # for term_data in terms:
    #     # Check if the nested policy exists
    #     if isinstance(term_data, PolicyTermNestedCreate):
    #         nested_policy_db = await db.execute(select(Policy).where(Policy.id == term_data.nested_policy_id))
    #         if not nested_policy_db.scalars().first():
    #             raise RequestValidationError([{"loc": ["body", "nested_policy_id"], "msg": "Nested policy not found"}])

    #     # Merge Nested and Regular Terms
    #     empty_term = PolicyTermCreate.model_construct()
    #     nested_empty_term = PolicyTermNestedCreate.model_construct()

    #     merged = {**empty_term.model_dump(), **nested_empty_term.model_dump(), **term_data.model_dump()}

    #     term = PolicyTerm(**merged, policy=policy, policy_id=policy.id)
        
    for idx, term in enumerate(terms):
        # Check if the nested policy exists
        if isinstance(term, PolicyTermNestedCreate):
            nested_policy_db = await db.execute(select(Policy).where(Policy.id == term.nested_policy_id))
            if not nested_policy_db.scalars().first():
                raise RequestValidationError([{"loc": ["body", f"terms[{idx}].nested_policy_id"], "msg": "Nested policy not found"}])


            new_term = PolicyTerm(
                **term.model_dump(),
                policy=policy,
                policy_id=policy.id,
                negate_source_networks=None,
                negate_destination_networks=None,
                source_networks=[],
                destination_networks=[],
                source_services=[],
                destination_services=[],
                action=None,
                option=None,
                logging=None,
            )

        elif isinstance(term, PolicyTermCreate):
            if term.negate_source_networks and not term.source_networks:
                term.negate_source_networks = False

            if term.negate_destination_networks and not term.destination_networks:
                term.negate_destination_networks = False

            # Search up nested destination and source networks/services
            source_networks = await network_crud.get_all(
                db, load_relations=False, filter_by={"id": term.source_networks}
            )
            destination_networks = await network_crud.get_all(
                db, load_relations=False, filter_by={"id": term.destination_networks}
            )
            source_services = await service_crud.get_all(
                db, load_relations=False, filter_by={"id": term.source_services}
            )
            destination_services = await service_crud.get_all(
                db, load_relations=False, filter_by={"id": term.destination_services}
            )

            del term.source_networks
            del term.destination_networks
            del term.source_services
            del term.destination_services

            new_term = PolicyTerm(
                **term.model_dump(),
                policy=policy,
                policy_id=policy.id,
                source_networks=source_networks,
                destination_networks=destination_networks,
                source_services=source_services,
                destination_services=destination_services,
            )

        policy.terms.append(new_term)

    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    return policy


@router.get("/policies/{id}", response_model=PolicyRead)
async def read_policy(
    id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await policy_crud.get(db, id, load_relations=True)
    return policy


@router.put("/policies/{policy_id}", response_model=PolicyCreated)
# # @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_policy(
    policy_id: int,
    values: PolicyUpdate,
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    # Check if the test exists
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.unique().scalars().one_or_none()
    if not policy:
        raise NotFoundException("Policy not found")

    # Check if the policy name already exists
    result = await db.execute(select(Policy).where(and_(Policy.name == values.name, Policy.id.notin_([policy_id]))))
    existing_policy = result.unique().scalars().one_or_none()
    if existing_policy:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A policy with this name already exists"}])

    # Grab the targets, tests, and terms from the values
    # and remove them from the values to avoid conflicts
    # targets and tests are integers pointing to the IDs of the targets and tests
    targets = values.targets or []
    tests = values.tests or []
    terms = values.terms or []
    del values.targets
    del values.tests
    del values.terms

    # Fetch related targets and tests
    if targets:
        targets_db = await db.execute(select(Target).where(Target.id.in_(targets)))
        policy.targets = targets_db.unique().scalars().all()
    if tests:
        tests_db = await db.execute(select(Test).where(Test.id.in_(tests)))
        policy.tests = tests_db.unique().scalars().all()

    # Update the existing test
    for k, v in values.model_dump(exclude_unset=True).items():
        print(f"Setting {k} to {v}")
        setattr(policy, k, v)

    # Clear existing terms and add new ones
    for term in list(policy.terms):
        await db.delete(term)
    
    # Set edited=True    
    policy.edited=True
    await db.flush()

    for idx, term in enumerate(terms):
        if isinstance(term, PolicyTermNestedUpdate):
            if term.nested_policy_id == policy_id:
                raise RequestValidationError(
                    [
                        {
                            "loc": ["body", f"terms[{idx}].nested_policy_id"],
                            "msg": "Cannot have a nested policy point to itself",
                        }
                    ]
                )
            nested_policy = await policy_crud.get(db, term.nested_policy_id)
            if not nested_policy:
                # TODO FIX index here
                raise RequestValidationError(
                    [{"loc": ["body", f"terms[{idx}].nested_policy_id"], "msg": "Nested policy not found"}]
                )

            new_term = PolicyTerm(
                **term.model_dump(),
                policy=policy,
                policy_id=policy.id,
                negate_source_networks=None,
                negate_destination_networks=None,
                source_networks=[],
                destination_networks=[],
                source_services=[],
                destination_services=[],
                action=None,
                option=None,
                logging=None,
            )

        elif isinstance(term, PolicyTermUpdate):
            if term.negate_source_networks and not term.source_networks:
                term.negate_source_networks = False

            if term.negate_destination_networks and not term.destination_networks:
                term.negate_destination_networks = False

            # Search up nested destination and source networks/services
            source_networks = await network_crud.get_all(
                db, load_relations=False, filter_by={"id": term.source_networks}
            )
            destination_networks = await network_crud.get_all(
                db, load_relations=False, filter_by={"id": term.destination_networks}
            )
            source_services = await service_crud.get_all(
                db, load_relations=False, filter_by={"id": term.source_services}
            )
            destination_services = await service_crud.get_all(
                db, load_relations=False, filter_by={"id": term.destination_services}
            )

            del term.source_networks
            del term.destination_networks
            del term.source_services
            del term.destination_services

            new_term = PolicyTerm(
                **term.model_dump(),
                policy=policy,
                policy_id=policy.id,
                source_networks=source_networks,
                destination_networks=destination_networks,
                source_services=source_services,
                destination_services=destination_services,
            )

        policy.terms.append(new_term)

    await db.commit()
    await db.refresh(policy)
    return policy


@router.delete("/policies/{policy_id}")
async def erase_policy(
    policy_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    # Check if policy is being used a nested policyterm
    nested_term = await db.execute(select(PolicyTerm).where(PolicyTerm.nested_policy_id == policy_id))

    if nested_term.scalars().all():
        raise HTTPException(status_code=403, detail="Policy is being used in a nested policy term")

    policy = await policy_crud.delete(db, policy_id)
    return {"message": "Policy deleted"}


@router.get("/policies/{policy_id}/usage", response_model=PolicyUsage)
async def read_policy_usage(
    policy_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await policy_crud.get(db, policy_id, True)

    if not policy:
        raise NotFoundException("Policy not found")

    policies_stmt = select(PolicyTerm.policy_id).distinct().where(PolicyTerm.nested_policy_id == policy_id)

    p_result = await db.execute(policies_stmt)

    policies = p_result.unique().scalars().all()

    return {
        "policies": policies,
    }
