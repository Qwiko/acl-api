from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, field_validator, PositiveInt, AfterValidator

from ..core.schemas import TimestampSchema

def require_sorted_unique(v):
    if v != sorted(set(v)):
        raise ValueError('list entries are not unique')
    return v

RequireListUniqueDuringValidation = AfterValidator(require_sorted_unique)

class DynamicPolicyBase(BaseModel):
    name: str  # Annotated[str, Field(min_length=2, max_length=30, examples=["This is my DynamicPolicy name"])]
    comment: Annotated[str | None, Field(max_length=100, examples=["This is my Dynamicpolicy comment"], default=None)]

    @field_validator("filter_action", check_fields=False)
    @classmethod
    def validate_filter_action(cls, v: str) -> str:
        if not v:
            return v
        if v not in ["accept", "deny", "next", "reject", "reject-with-tcp-rst"]:
            raise ValueError("not a valid filter_action.")
        return v

    @field_validator("default_action", check_fields=False)
    @classmethod
    def validate_default_action(cls, v: str) -> str:
        if not v:
            return v
        if v not in ["accept", "accept-log", "deny", "deny-log"]:
            raise ValueError("not a valid default action.")
        return v

class DynamicPolicyRead(TimestampSchema, DynamicPolicyBase):
    id: PositiveInt

    filter_action: Optional[str]

    default_action: Optional[str]

    targets_ids: Annotated[List[PositiveInt], Field(serialization_alias="targets", default_factory=list)]
    tests_ids: Annotated[List[PositiveInt], Field(serialization_alias="tests", default_factory=list)]

    source_filters_ids: Annotated[List[PositiveInt], Field(serialization_alias="source_filters", default_factory=list)]
    destination_filters_ids: Annotated[
        List[PositiveInt], Field(serialization_alias="destination_filters", default_factory=list)
    ]

    policy_filters_ids: Annotated[List[PositiveInt], Field(serialization_alias="policy_filters", default_factory=list)]


class DynamicPolicyReadBrief(TimestampSchema, DynamicPolicyBase):
    id: PositiveInt


class DynamicPolicyCreated(TimestampSchema, DynamicPolicyBase):
    id: PositiveInt


class DynamicPolicyCreate(DynamicPolicyBase):
    filter_action: Optional[str]

    default_action: Optional[str]

    targets: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), RequireListUniqueDuringValidation]
    tests: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), RequireListUniqueDuringValidation]

    source_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), RequireListUniqueDuringValidation]
    destination_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), RequireListUniqueDuringValidation]

    policy_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), RequireListUniqueDuringValidation]


class DynamicPolicyUpdate(DynamicPolicyBase):
    filter_action: Optional[str]

    default_action: Optional[str]

    targets: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), RequireListUniqueDuringValidation]
    tests: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), RequireListUniqueDuringValidation]

    source_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), RequireListUniqueDuringValidation]
    destination_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), RequireListUniqueDuringValidation]

    policy_filters: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), RequireListUniqueDuringValidation]


class DynamicPolicyDelete(DynamicPolicyBase):
    pass
