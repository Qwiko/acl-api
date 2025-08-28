from typing import Annotated, Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security
from fastapi.exceptions import RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.cruds import dynamic_policy_crud, policy_crud, test_crud
from app.core.db.database import async_get_db
from app.core.exceptions.http_exceptions import NotFoundException
from app.core.security import User, get_current_user
from app.core.utils.acl_test import run_tests
from app.core.utils.dynamic_policy_helpers import fetch_addresses, fetch_networks, fetch_terms
from app.core.utils.generate import get_expanded_terms, get_policy_and_definitions_from_policy
from app.filters.test import TestFilter
from app.models import DynamicPolicy, Policy, Test, TestCase
from app.schemas.test import (
    TestCreate,
    TestCreated,
    TestRead,
    TestResultRead,
    TestUpdate,
)

router = APIRouter(tags=["tests"])
func: Callable


@router.get("/tests", response_model=Page[TestRead])
async def read_tests(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["tests:read"])],
    test_filter: TestFilter = FilterDepends(TestFilter),
) -> Any:
    query = select(Test).outerjoin(TestCase, (Test.id == TestCase.test_id))
    query = test_filter.filter(query)
    query = test_filter.sort(query)

    count_query = select(func.count()).select_from(Test)
    count_query = test_filter.filter(count_query)

    return await paginate(db, query, count_query=count_query)


@router.post("/tests", response_model=TestCreated, status_code=201)
async def write_test(
    request: Request,
    values: TestCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["tests:write"])],
) -> Any:
    # Check if the test name already exists
    found_test = await test_crud.get_all(db, filter_by={"name": values.name})
    if found_test:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A service with this name already exists"}])

    dynamic_policies = values.dynamic_policies or []
    policies = values.policies or []
    cases = values.cases or []
    del values.dynamic_policies
    del values.policies
    del values.cases
    
    # Fetch related dynamic_policies and policies
    dynamic_policies_db = await db.execute(select(DynamicPolicy).where(DynamicPolicy.id.in_(dynamic_policies)))
    policies_db = await db.execute(select(Policy).where(Policy.id.in_(policies)))

    # Assign dynamic_policies and policies to the policy
    fetched_dynamic_policies = dynamic_policies_db.unique().scalars().all()
    fetched_policies = policies_db.unique().scalars().all()


    test = Test(**values.model_dump(), dynamic_policies=fetched_dynamic_policies, policies=fetched_policies)

    test.cases = [TestCase(**case.model_dump(), test=test, test_id=test.id) for case in cases]

    db.add(test)
    await db.commit()

    return test


@router.get("/tests/{test_id}", response_model=TestRead)
async def read_test(
    request: Request,
    test_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["tests:read"])],
) -> dict:
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.unique().scalars().one_or_none()

    if not test:
        raise NotFoundException("Test not found")

    return test


@router.put("/tests/{test_id}", response_model=TestCreated)
async def put_test(
    request: Request,
    test_id: int,
    values: TestUpdate,
    current_user: Annotated[User, Security(get_current_user, scopes=["tests:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, Any]:
    # Check if the test exists
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.unique().scalars().one_or_none()
    if not test:
        raise NotFoundException("Test not found")

    # Check if the test name already exists
    result = await db.execute(select(Test).where(and_(Test.name == values.name, Test.id.notin_([test_id]))))
    existing_test = result.unique().scalars().one_or_none()
    if existing_test:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A test with this name already exists"}])
    
    dynamic_policies = values.dynamic_policies or []
    policies = values.policies or []
    cases = values.cases or []
    del values.dynamic_policies
    del values.policies
    del values.cases
    
    # Fetch related dynamic_policies and policies
    dynamic_policies_db = await db.execute(select(DynamicPolicy).where(DynamicPolicy.id.in_(dynamic_policies)))
    policies_db = await db.execute(select(Policy).where(Policy.id.in_(policies)))

    # Assign dynamic_policies and policies to the policy
    fetched_dynamic_policies = dynamic_policies_db.unique().scalars().all()
    fetched_policies = policies_db.unique().scalars().all()

    # Update the existing test
    for k, v in values.model_dump(exclude_unset=True).items():
        setattr(test, k, v)
        
    test.dynamic_policies = fetched_dynamic_policies
    test.policies = fetched_policies
    
    # Clear existing cases and add new ones
    test.cases.clear()
    for case in cases:
        new_case = TestCase(**case.model_dump(), test=test, test_id=test.id)
        test.cases.append(new_case)

    await db.commit()
    await db.refresh(test)
    return test


@router.delete("/tests/{test_id}")
async def erase_test(
    request: Request,
    test_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["tests:write"])],
) -> None:
    await test_crud.delete(db, test_id)
    return {"message": "Test deleted"}


@router.get("/run_tests", response_model=TestResultRead)
async def get_tests_run(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:read", "dynamic_policies:read"])],
    dynamic_policy_id: int = None,
    policy_id: int = None,
) -> Any:
    if not dynamic_policy_id and not policy_id:
        raise HTTPException(status_code=400, detail="Must include either dynamic_policy_id or policy_id.")
    if policy_id:
        policy = await policy_crud.get(db, policy_id)
        if policy is None:
            raise NotFoundException("Policy not found")
        tests = policy.tests

        expanded_terms = await get_expanded_terms(db, policy.terms)

    else:
        policy = await dynamic_policy_crud.get(db, dynamic_policy_id, load_relations=True)
        if policy is None:
            raise NotFoundException("Dynamic policy not found")

        source_addresses = await fetch_addresses(db, policy.source_filters_ids) if policy.source_filters_ids else []
        destination_addresses = (
            await fetch_addresses(db, policy.destination_filters_ids) if policy.destination_filters_ids else []
        )

        source_networks = await fetch_networks(db, source_addresses) if source_addresses else []

        destination_networks = await fetch_networks(db, destination_addresses) if destination_addresses else []

        policy_ids_stmt = select(Policy.id).where(Policy.id.in_(policy.policy_filters_ids))
        policy_ids_res = await db.execute(policy_ids_stmt)
        policy_ids = policy_ids_res.unique().scalars().all()

        expanded_terms = await fetch_terms(
            db,
            source_networks=source_networks,
            destination_networks=destination_networks,
            policy_ids=policy_ids,
            filter_action=policy.filter_action,
        )
        tests = policy.tests

    policy_dict, definitions = await get_policy_and_definitions_from_policy(
        db, policy, expanded_terms, default_action=policy.default_action if hasattr(policy, "default_action") else None
    )

    all_matches = []
    for test in tests:
        for case in test.cases:
            kwargs = {
                "src": case.source_network,
                "dst": case.destination_network,
                "sport": case.source_port,
                "dport": case.destination_port,
                "proto": case.protocol,
            }

            match, matched_term = run_tests(
                policy_dict,
                definitions,
                expanded_terms,
                case.expected_action,
                **{key: val for key, val in kwargs.items() if val},
            )

            obj = {"passed": match, "case": case, "matched_term": matched_term}

            all_matches.append(obj)

    matched_ids = [match.get("matched_term").id for match in all_matches if match.get("matched_term")]

    not_matched_terms = [term for term in expanded_terms if term.id not in matched_ids]

    coverage = round((float(len(list(set(matched_ids)))) / float(len(expanded_terms))), 4)

    return {
        "tests": all_matches,
        "not_matched_terms": not_matched_terms,
        "coverage": coverage,
    }
