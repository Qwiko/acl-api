from datetime import datetime
from typing import Annotated, Any, List, Optional, Text, Union

from pydantic import BaseModel, Field, PositiveInt, ValidationError, field_validator, model_validator
from pydantic_core import InitErrorDetails, PydanticCustomError

from ..core.schemas import TimestampSchema
from .custom_validators import EnsureListUnique
from ..models.policy import PolicyActionEnum, PolicyOptionEnum


class PolicyBase(BaseModel):
    name: str  # Annotated[str, Field(min_length=2, max_length=30, examples=["This is my Policy name"])]
    comment: Annotated[str | None, Field(max_length=300, examples=["This is my policy comment"], default=None)]


class PolicyRead(TimestampSchema, PolicyBase):
    id: int

    targets_ids: Annotated[List[PositiveInt], Field(serialization_alias="targets", default_factory=list)]
    tests_ids: Annotated[List[PositiveInt], Field(serialization_alias="tests", default_factory=list)]
    terms: Annotated[List[Union["PolicyTermRead", "PolicyTermNestedRead"]], Field(default_factory=list)]


class PolicyReadBrief(TimestampSchema, PolicyBase):
    id: int


class PolicyCreated(TimestampSchema, PolicyBase):
    id: int

    targets_ids: Annotated[List[PositiveInt], Field(serialization_alias="targets", default_factory=list)]
    tests_ids: Annotated[List[PositiveInt], Field(serialization_alias="tests", default_factory=list)]
    terms: Annotated[List[Union["PolicyTermRead", "PolicyTermNestedRead"]], Field(default_factory=list)]


class PolicyCreate(PolicyBase):
    targets: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]
    tests: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]

    terms: List[Union["PolicyTermCreate", "PolicyTermNestedCreate"]] = Field(default_factory=list)


class PolicyUpdate(PolicyBase):
    targets: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]
    tests: Annotated[Optional[List[PositiveInt]], Field(default_factory=list), EnsureListUnique]

    terms: List[Union["PolicyTermUpdate", "PolicyTermNestedUpdate"]] = Field(default_factory=list)


class PolicyUpdateInternal(PolicyUpdate):
    updated_at: datetime


class PolicyDelete(PolicyBase):
    pass


class PolicyUsage(BaseModel):
    policies: Annotated[List[PositiveInt], Field(default_factory=list)]


from ..models import PolicyTerm


## PolicyTerm
class PolicyTermSharedBase(BaseModel):
    name: Annotated[
        str, Field()
    ]  # Annotated[str, Field(min_length=2, max_length=30, examples=["This is my Policy name"])]

    enabled: Annotated[bool, Field(default=False)]

    @model_validator(mode="before")
    @classmethod
    def check_exclusive_fields(cls, data: Any) -> Any:
        # Only check if we have raw data from create or update
        if isinstance(data, PolicyTerm):
            return data

        errors = []

        check_fields = [
            "action",
            "logging",
            "option",
            "negate_source_networks",
            "negate_destination_networks",
            "source_networks",
            "destination_networks",
            "source_services",
            "destination_services",
        ]
        for check_field in check_fields:
            if data.get(check_field) and data.get("nested_policy_id"):
                errors.append(
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "duplicated",
                            f"Cannot have nested_policy_id together with {check_field}.",
                        ),
                        loc=("body", check_field),
                        input=cls,
                    )
                )
        if errors:
            raise ValidationError.from_exception_data(
                "DuplicatedError",
                [
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "duplicated",
                            "Cannot have nested_policy_id together with other options.",
                        ),
                        loc=("body", "nested_policy_id"),
                        input=cls,
                    ),
                ]
                + errors,
            )

        return data


class PolicyTermBase(PolicyTermSharedBase):
    option: Optional[PolicyOptionEnum] = None

    logging: Annotated[bool, Field(default=False)]

    action: PolicyActionEnum = PolicyActionEnum.ACCEPT

    negate_source_networks: Annotated[bool, Field(default=False)]
    negate_destination_networks: Annotated[bool, Field(default=False)]


class PolicyTermNestedBase(PolicyTermSharedBase):
    nested_policy_id: Annotated[PositiveInt, Field()]


class PolicyTermReadInternal(PolicyTermBase):
    # id: int
    policy_id: int

    source_networks_ids: Annotated[List[int], Field(serialization_alias="source_networks", default_factory=list)]
    destination_networks_ids: Annotated[
        List[PositiveInt], Field(serialization_alias="destination_networks", default_factory=list)
    ]

    source_services_ids: Annotated[
        List[PositiveInt], Field(serialization_alias="source_services", default_factory=list)
    ]
    destination_services_ids: Annotated[
        List[PositiveInt], Field(serialization_alias="destination_services", default_factory=list)
    ]


class PolicyTermRead(TimestampSchema, PolicyTermReadInternal):
    # position: PositiveInt
    pass


class PolicyTermNestedRead(PolicyTermNestedBase):
    # id: int
    policy_id: int

    # position: PositiveInt


class PolicyTermReadBrief(PolicyTermBase):
    # id: int
    # position: PositiveInt
    pass


class PolicyTermNestedReadBrief(PolicyTermNestedBase):
    # id: int
    # position: PositiveInt
    pass


class PolicyTermCreate(PolicyTermBase):
    # position: Annotated[PositiveInt | None, Field(default=1)]
    source_networks: Annotated[List[PositiveInt], Field(default_factory=list)]
    destination_networks: Annotated[List[PositiveInt], Field(default_factory=list)]

    source_services: Annotated[List[PositiveInt], Field(default_factory=list)]
    destination_services: Annotated[List[PositiveInt], Field(default_factory=list)]


class PolicyTermNestedCreate(PolicyTermNestedBase):
    # position: Annotated[PositiveInt | None, Field(default=1)]
    pass


class PolicyTermUpdate(PolicyTermBase):
    # position: Annotated[PositiveInt | None, Field(default=1)]

    source_networks: Annotated[List[PositiveInt], Field(default_factory=list)]
    destination_networks: Annotated[List[PositiveInt], Field(default_factory=list)]

    source_services: Annotated[List[PositiveInt], Field(default_factory=list)]
    destination_services: Annotated[List[PositiveInt], Field(default_factory=list)]


class PolicyTermNestedUpdate(PolicyTermNestedBase):
    # position: Annotated[PositiveInt | None, Field(default=1)]
    pass


class PolicyTermDelete(PolicyTermBase):
    pass


# Revisions
class PolicyRevisionBase(BaseModel):
    comment: Annotated[str | None, Field(max_length=100, examples=["This is my revision comment"], default=None)]


class PolicyRevisionRead(TimestampSchema, PolicyRevisionBase):
    id: int
    policy_id: int

    configs: Annotated[List["PolicyRevisionConfigRead"], Field(default_factory=list)]


class PolicyRevisionReadBrief(TimestampSchema, PolicyRevisionBase):
    id: int


class PolicyRevisionCreate(PolicyRevisionBase):
    pass


class PolicyRevisionConfigReadBase(BaseModel):
    pass


class PolicyRevisionConfigRead(PolicyRevisionConfigReadBase):
    id: int
    target_id: int
    filter_name: str
    config: Text
