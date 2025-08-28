from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, PositiveInt, StrictBool, field_validator

from ..core.schemas import TimestampSchema
from ..models.dynamic_policy import DynamicPolicyDefaultActionEnum, DynamicPolicyFilterActionEnum
from .custom_validators import EnsureListUnique


class DynamicPolicyBase(BaseModel):
    name: str  # Annotated[str, Field(min_length=2, max_length=30, examples=["This is my DynamicPolicy name"])]
    comment: Annotated[str | None, Field(max_length=100, examples=["This is my dynamic policy comment"], default=None)]


class DynamicPolicyRead(TimestampSchema, DynamicPolicyBase):
    id: PositiveInt
    
    edited: StrictBool

    filter_action: Optional[DynamicPolicyFilterActionEnum]

    default_action: Optional[DynamicPolicyDefaultActionEnum]

    targets_ids: Annotated[List[PositiveInt], Field(serialization_alias="targets", default_factory=list)]
    tests_ids: Annotated[List[PositiveInt], Field(serialization_alias="tests", default_factory=list)]

    source_filters_ids: Annotated[List[PositiveInt], Field(serialization_alias="source_filters", default_factory=list)]
    destination_filters_ids: Annotated[
        List[PositiveInt], Field(serialization_alias="destination_filters", default_factory=list)
    ]

    policy_filters_ids: Annotated[List[PositiveInt], Field(serialization_alias="policy_filters", default_factory=list)]


class DynamicPolicyReadBrief(TimestampSchema, DynamicPolicyBase):
    id: PositiveInt
    edited: StrictBool

class DynamicPolicyCreated(TimestampSchema, DynamicPolicyBase):
    id: PositiveInt


class DynamicPolicyCreate(DynamicPolicyBase):
    filter_action: Optional[DynamicPolicyFilterActionEnum] = None

    default_action: Optional[DynamicPolicyDefaultActionEnum] = None

    targets: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]
    tests: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]

    source_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]
    destination_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]

    policy_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]


class DynamicPolicyUpdate(DynamicPolicyBase):
    filter_action: Optional[DynamicPolicyFilterActionEnum] = None

    default_action: Optional[DynamicPolicyDefaultActionEnum] = None

    targets: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]
    tests: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]

    source_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]
    destination_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]

    policy_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]


class DynamicPolicyDelete(DynamicPolicyBase):
    pass
