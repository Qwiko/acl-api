from typing import Annotated, Any, Union

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi_filter import FilterDepends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...core.cruds import network_crud, policy_crud, service_crud, term_crud
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...core.security import User, get_current_user
from ...core.utils.lexirank import get_rank_between
from ...filters.policy import PolicyFilter, PolicyTermFilter
from ...models import Policy, PolicyTerm
from ...schemas.policy import (
    PolicyCreate,
    PolicyCreated,
    PolicyRead,
    PolicyReadBrief,
    PolicyTermCreate,
    PolicyTermNestedCreate,
    PolicyTermNestedRead,
    PolicyTermNestedReadBrief,
    PolicyTermNestedUpdate,
    PolicyTermRead,
    PolicyTermReadBrief,
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

    policy = await policy_crud.create(db, values)
    return policy


@router.get("/policies/{id}", response_model=PolicyRead)
async def read_policy(
    id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await policy_crud.get(db, id, load_relations=True)
    return policy


@router.put("/policies/{id}", response_model=PolicyCreated)
# # @cache("{username}_post_cache", resource_id_name="id", pattern_to_invalidate_extra=["{username}_posts:*"])
async def put_policy(
    id: int,
    values: PolicyUpdate,
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await policy_crud.update(db, id, values)
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


# Terms
@router.get("/policies/{policy_id}/terms", response_model=Page[Union[PolicyTermRead, PolicyTermNestedRead]])
async def read_policy_terms(
    policy_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:read"])],
    policy_term_filter: PolicyTermFilter = FilterDepends(PolicyTermFilter),
) -> Any:
    query = select(PolicyTerm).where(PolicyTerm.policy_id == policy_id)
    query = policy_term_filter.filter(query)
    query = policy_term_filter.sort(query)

    return await paginate(db, query)


@router.post(
    "/policies/{policy_id}/terms", response_model=Union[PolicyTermReadBrief, PolicyTermNestedReadBrief], status_code=201
)
async def write_policy_term(
    request: Request,
    policy_id: int,
    values: Union[PolicyTermCreate, PolicyTermNestedCreate],
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await policy_crud.get(db, policy_id)
    if policy is None:
        raise NotFoundException("Policy not found")

    if [term.name for term in policy.terms if term.name == values.name]:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A term with this name already exists"}])

    # Check if the nested policy exists
    if isinstance(values, PolicyTermNestedCreate):
        nested_policy = await policy_crud.get(db, values.nested_policy_id)
        if not nested_policy:
            raise RequestValidationError([{"loc": ["body", "nested_policy_id"], "msg": "Nested policy not found"}])

        # Check if the nested policy is already being used in another term
        nested_term = await db.execute(
            select(PolicyTerm)
            .where(PolicyTerm.nested_policy_id == values.nested_policy_id)
            .where(PolicyTerm.policy_id == policy_id)
        )
        if nested_term.scalars().all():
            raise RequestValidationError([{"loc": ["body", "nested_policy_id"], "msg": "Nested policy already exists"}])

    # Get existing positions
    result = await db.execute(
        select(PolicyTerm.lex_order).where(PolicyTerm.policy_id == policy_id).order_by(PolicyTerm.lex_order)
    )
    lex_orders = result.unique().scalars().all()

    if values.position:
        position = values.position
    else:
        position = 1

    del values.position

    new_lex_order = ""

    if not lex_orders:
        new_lex_order = get_rank_between("aaaaa", "zzzzz")
    elif position == 1:
        new_lex_order = get_rank_between("aaaaa", lex_orders[0])  # New rank before the first term
    elif position > len(lex_orders):
        new_lex_order = get_rank_between(lex_orders[-1], "zzzzz")  # New rank after the last term (e.g., large value)
    else:
        new_lex_order = get_rank_between(lex_orders[position - 2], lex_orders[position - 1])  # Midpoint between terms

    extra_data = {
        "policy_id": policy.id,
        "policy": policy,
        "lex_order": new_lex_order,
    }

    if isinstance(values, PolicyTermCreate):
        if values.negate_source_networks and not values.source_networks:
            values.negate_source_networks = False

        if values.negate_destination_networks and not values.destination_networks:
            values.negate_destination_networks = False
        # if  values.source_networks:
        #     source_networks = await network_crud.get_all(db, load_relations=False, filter_by={"id": values.source_networks})
        # destination_networks = await network_crud.get_all(
        #     db, load_relations=False, filter_by={"id": values.destination_networks}
        # )
        # source_services = await service_crud.get_all(db, load_relations=False, filter_by={"id": values.source_services})
        # destination_services = await service_crud.get_all(
        #     db, load_relations=False, filter_by={"id": values.destination_services}
        # )
        # del values.source_networks
        # extra_data.update(
        #     {
        #         "source_networks": source_networks,
        #         "destination_networks": destination_networks,
        #         "source_services": source_services,
        #         "destination_services": destination_services,
        #     }
        # )
    else:
        # Add null data
        # Could remove this with init=False in the SQL Model
        extra_data.update(
            {
                "source_networks": [],
                "destination_networks": [],
                "source_services": [],
                "destination_services": [],
                "action": None,
                "logging": None,
                "option": None,
                "negate_source_networks": None,
                "negate_destination_networks": None,
            }
        )

    policy_term = await term_crud.create(
        db,
        values,
        extra_data,
    )

    return policy_term


@router.get("/policies/{policy_id}/terms/{term_id}", response_model=Union[PolicyTermRead, PolicyTermNestedRead])
async def read_policy_term(
    request: Request,
    policy_id: int,
    term_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:read"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await policy_crud.get(db, policy_id)
    if policy is None:
        raise NotFoundException("Policy not found")

    policy_term = await term_crud.get(db, term_id, load_relations=True, filter_by={"policy_id": policy_id})

    if policy_term is None:
        raise NotFoundException("Term not found")

    return policy_term


@router.put("/policies/{policy_id}/terms/{term_id}", response_model=Union[PolicyTermReadBrief, PolicyTermNestedReadBrief])
async def put_policy_terms(
    request: Request,
    policy_id: int,
    term_id: int,
    values: Union[PolicyTermUpdate, PolicyTermNestedUpdate],
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await policy_crud.get(db, policy_id)

    if policy is None:
        raise NotFoundException("Policy not found")

    term = await term_crud.get(db, term_id, filter_by={"policy_id": policy.id})

    if term is None:
        raise NotFoundException("Term not found")

    if [term.name for term in policy.terms if term.id != term_id and term.name == values.name]:
        raise RequestValidationError([{"loc": ["body", "name"], "msg": "A term with this name already exists"}])

    # Check if the nested policy exists
    if isinstance(values, PolicyTermNestedUpdate):
        nested_policy = await policy_crud.get(db, values.nested_policy_id)
        if not nested_policy:
            raise RequestValidationError([{"loc": ["body", "nested_policy_id"], "msg": "Nested policy not found"}])

        # Need to write tests for this first.
        # Need to have where id != term_id
        # TODO
        # Change to term_id in url as well

        # # Check if the nested policy is already being used in another term
        # nested_term = await db.execute(
        #     select(PolicyTerm)
        #     .where(PolicyTerm.nested_policy_id == values.nested_policy_id)
        #     .where(PolicyTerm.policy_id == policy_id)
        # )
        # if nested_term.scalars().all():
        #     raise RequestValidationError([{"loc": ["body", "nested_policy_id"], "msg": "Nested policy already exists"}])
    

    # Get existing positions
    result = await db.execute(
        select(PolicyTerm.lex_order).where(PolicyTerm.policy_id == policy_id).order_by(PolicyTerm.lex_order)
    )
    lex_orders = result.unique().scalars().all()

    new_lex_order = ""

    if values.position:
        if values.position == 1:
            new_lex_order = get_rank_between("aaaaa", lex_orders[0])  # New rank before the first term
        elif values.position > len(lex_orders):
            new_lex_order = get_rank_between(
                lex_orders[-1], "zzzzz"
            )  # New rank after the last term (e.g., large value)
        else:
            new_lex_order = get_rank_between(
                lex_orders[values.position - 2], lex_orders[values.position - 1]
            )  # Midpoint between terms

    del values.position

    if isinstance(values, PolicyTermUpdate):
        if values.negate_source_networks and not values.source_networks:
            values.negate_source_networks = False

        if values.negate_destination_networks and not values.destination_networks:
            values.negate_destination_networks = False

        # Search up nested destination and source networks/services
        source_networks = await network_crud.get_all(db, load_relations=False, filter_by={"id": values.source_networks})
        destination_networks = await network_crud.get_all(
            db, load_relations=False, filter_by={"id": values.destination_networks}
        )
        source_services = await service_crud.get_all(db, load_relations=False, filter_by={"id": values.source_services})
        destination_services = await service_crud.get_all(
            db, load_relations=False, filter_by={"id": values.destination_services}
        )

        del values.source_networks
        del values.destination_networks
        del values.source_services
        del values.destination_services

    term = await term_crud.update(
        db,
        term.id,
        values,
    )

    if isinstance(values, PolicyTermUpdate):
        term.source_networks = source_networks
        term.destination_networks = destination_networks
        term.source_services = source_services
        term.destination_services = destination_services
    elif isinstance(values, PolicyTermNestedUpdate):
        term.source_networks = []
        term.destination_networks = []
        term.source_services = []
        term.destination_services = []
        term.action = None
        term.option = None
        term.logging = None

    if new_lex_order:
        term.lex_order = new_lex_order

    await db.commit()
    await db.refresh(term)

    return term


@router.delete("/policies/{policy_id}/terms/{term_id}")
async def erase_policy_term(
    request: Request,
    policy_id: int,
    term_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["policies:write"])],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> Any:
    policy = await policy_crud.get(db, policy_id)

    if policy is None:
        raise NotFoundException("Policy not found")

    filter_by = {"policy_id": policy.id}
    term = await term_crud.get(db, term_id, filter_by=filter_by)

    if term is None:
        raise NotFoundException("Term not found")

    await term_crud.delete(db, term.id)
    return {"message": "Policy term deleted"}
