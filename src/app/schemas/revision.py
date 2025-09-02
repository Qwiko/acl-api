from typing import Annotated, Any, List, Text

from pydantic import BaseModel, Field, Json, ValidationError, model_validator
from pydantic_core import InitErrorDetails, PydanticCustomError

from app.core.schemas import TimestampSchema


# DynamicRevisions
class DynamicPolicyRevisionBase(BaseModel):
    comment: Annotated[str | None, Field(max_length=100, examples=["This is my revision comment"], default=None)]


class DynamicPolicyRevisionRead(TimestampSchema, DynamicPolicyRevisionBase):
    id: int
    dynamic_policy_id: int

    json_data: Annotated[Json[Any], Field(description="Dynamic policy JSON dump")]
    expanded_terms: Annotated[Json[Any], Field(description="Dynamic policy expanded_terms dump")]
    configs: Annotated[List["DynamicPolicyRevisionConfigRead"], Field(default_factory=list)]


class DynamicPolicyRevisionReadBrief(TimestampSchema, DynamicPolicyRevisionBase):
    id: int
    dynamic_policy_id: int


class DynamicPolicyRevisionCreate(DynamicPolicyRevisionBase):
    dynamic_policy_id: int

    @model_validator(mode="before")
    @classmethod
    def check_exclusive_fields(cls, data: Any) -> Any:
        if data.get("policy_id") and data.get("dynamic_policy_id"):
            raise ValidationError.from_exception_data(
                "DuplicatedError",
                [
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "duplicated",
                            "Can only specify either policy_id or dynamic_policy_id, not both.",
                        ),
                        loc=("body", "dynamic_policy_id"),
                        input=cls,
                    ),
                ],
            )

        return data


class DynamicPolicyRevisionConfigReadBase(BaseModel):
    pass


class DynamicPolicyRevisionConfigRead(DynamicPolicyRevisionConfigReadBase):
    id: int
    target_id: int
    filter_name: str
    config: Text


# PolicyRevisions
class PolicyRevisionBase(BaseModel):
    comment: Annotated[str | None, Field(max_length=100, examples=["This is my revision comment"], default=None)]


class PolicyRevisionRead(TimestampSchema, PolicyRevisionBase):
    id: int
    policy_id: int

    json_data: Annotated[Json[Any], Field(description="Policy JSON dump")]
    expanded_terms: Annotated[Json[Any], Field(description="Policy expanded_terms dump")]
    configs: Annotated[List["PolicyRevisionConfigRead"], Field(default_factory=list)]


class PolicyRevisionReadBrief(TimestampSchema, PolicyRevisionBase):
    id: int
    policy_id: int


class PolicyRevisionCreate(PolicyRevisionBase):
    policy_id: int

    @model_validator(mode="before")
    @classmethod
    def check_exclusive_fields(cls, data: Any) -> Any:
        if data.get("policy_id") and data.get("dynamic_policy_id"):
            raise ValidationError.from_exception_data(
                "DuplicatedError",
                [
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "duplicated",
                            "Can only specify either policy_id or dynamic_policy_id, not both.",
                        ),
                        loc=("body", "policy_id"),
                        input=cls,
                    ),
                ],
            )

        return data


class PolicyRevisionConfigReadBase(BaseModel):
    pass


class PolicyRevisionConfigRead(PolicyRevisionConfigReadBase):
    id: int
    target_id: int
    filter_name: str
    config: Text
