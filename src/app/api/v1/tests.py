from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ...core.utils.generate import get_policy_and_definitions_from_policy
from ...core.cruds import case_crud, dynamic_policy_crud, policy_crud, test_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...core.utils.acl_test import run_tests
from ...core.utils.generate import get_expanded_terms
from ...filters.test import TestCaseFilter, TestFilter
from ...models import Test, TestCase, Policy
from ...schemas.test import (
    TestCaseCreate,
    TestCaseRead,
    TestCaseUpdate,
    TestCreate,
    TestCreated,
    TestRead,
    TestResultRead,
    TestUpdate,
)

router = APIRouter(tags=["tests"])


@router.get("/tests", response_model=Page[TestRead])
async def read_tests(
    db: Annotated[AsyncSession, Depends(async_get_db)],
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
    data: TestCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    test = await test_crud.create(db, data)

    return test


@router.get("/tests/{id}", response_model=TestRead)
async def read_test(request: Request, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]) -> dict:
    test = await test_crud.get(db, id, True)

    if not test:
        raise NotFoundException("Test not found")

    return test


@router.put("/tests/{id}", response_model=TestCreated)
# @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_test(
    request: Request,
    id: int,
    values: TestUpdate,
    # current_user: Annotated[TestRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, Any]:
    updated_test = await test_crud.update(db, id, values)
    return updated_test


@router.delete("/tests/{id}")
async def erase_test(
    request: Request,
    id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    await test_crud.delete(db, id)
    return {"message": "Test deleted"}


# TestCase
@router.get("/tests/{test_id}/cases", response_model=Page[TestCaseRead])
async def read_cases(
    request: Request,
    response: Response,
    test_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    case_filter: TestCaseFilter = FilterDepends(TestCaseFilter),
) -> Any:
    db_test = await db.execute(select(Test).where(Test.id == test_id))
    if db_test is None:
        raise NotFoundException("Test not found")

    query = select(TestCase).where(TestCase.test_id == test_id)
    query = case_filter.filter(query)
    query = case_filter.sort(query)

    return await paginate(db, query)


@router.post("/tests/{test_id}/cases", response_model=TestCaseRead, status_code=201)
async def write_test_case(
    request: Request,
    test_id: int,
    values: TestCaseCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TestCaseRead:
    test = await test_crud.get(db, test_id)

    if test is None:
        raise NotFoundException("Test not found")

    test_case = await case_crud.create(db, values, {"test_id": test.id, "test": test})

    return test_case


@router.get("/tests/{test_id}/cases/{id}", response_model=TestCaseRead)
async def read_test_case(
    request: Request, test_id: int, id: int, db: Annotated[AsyncSession, Depends(async_get_db)]
) -> dict:
    test = await test_crud.get(db, test_id)
    if test is None:
        raise NotFoundException("Test not found")
    filter_by = {"test_id": test.id}
    case = await case_crud.get(db, id, filter_by=filter_by)

    if case is None:
        raise NotFoundException("Test case not found")

    return case


@router.put("/tests/{test_id}/cases/{id}", response_model=TestCaseRead)
# @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_test_case(
    request: Request,
    test_id: int,
    id: int,
    values: TestCaseUpdate,
    # current_user: Annotated[UserRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    test = await test_crud.get(db, test_id)

    if test is None:
        raise NotFoundException("Test not found")

    filter_by = {"test_id": test.id}
    case = await case_crud.get(db, id, filter_by=filter_by)

    if case is None:
        raise NotFoundException("Test case not found")

    test_case = await case_crud.update(db, case.id, values)

    return test_case


@router.delete("/tests/{test_id}/cases/{id}")
# @cache("{username}_post_cache", resource_id_name="id", to_invalidate_extra={"{username}_posts": "{username}"})
async def erase_test_case(
    request: Request,
    test_id: int,
    id: int,
    # current_user: Annotated[TestRead, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    test = await test_crud.get(db, test_id)

    if test is None:
        raise NotFoundException("Test not found")

    filter_by = {"test_id": test.id}
    case = await case_crud.get(db, id, filter_by=filter_by)

    if case is None:
        raise NotFoundException("Test case not found")

    await case_crud.delete(db, case.id)

    return {"message": "Test case deleted"}


from .revisions import fetch_addresses, fetch_networks, fetch_terms


@router.get("/run_tests", response_model=TestResultRead)
async def get_tests_run(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(async_get_db)],
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


    policy_dict, definitions = await get_policy_and_definitions_from_policy(db, policy, expanded_terms, default_action=policy.default_action if hasattr(policy, "default_action") else None)

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
               policy_dict, definitions, expanded_terms, case.expected_action, **{key: val for key, val in kwargs.items() if val}
            )

            obj = {"passed": match, "case": case, "matched_term": matched_term}

            all_matches.append(obj)

    matched_ids = [match.get("matched_term").id for match in all_matches if match.get("matched_term")]

    not_matched_terms = [term for term in expanded_terms if term.id not in matched_ids]

    return {"tests": all_matches, "not_matched_terms": not_matched_terms}
