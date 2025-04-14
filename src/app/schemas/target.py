from typing import Annotated, List, Optional

from aerleon.lib.plugin_supervisor import BUILTIN_GENERATORS
from pydantic import BaseModel, Field, PositiveInt, field_validator

from ..core.schemas import TimestampSchema

from .custom_validators import EnsureListUnique
from enum import Enum


class TargetInetModeEnum(str, Enum):
    INET = "inet"
    INET6 = "inet6"
    MIXED = "mixed"


class TargetBase(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]

    generator: Annotated[str, Field(examples=["cisco", "juniper"])]

    inet_mode: Annotated[
        Optional[TargetInetModeEnum], Field(examples=["inet", "inet6", "mixed"], default=TargetInetModeEnum.INET)
    ]

    @field_validator("generator")
    @classmethod
    def validate_generator(cls, v: str) -> str:
        if v not in [g[0] for g in BUILTIN_GENERATORS]:
            raise ValueError("not a valid generator.")
        return v


class TargetRead(TimestampSchema, TargetBase):
    id: int
    policies_ids: Annotated[List[PositiveInt], Field(serialization_alias="policies", default_factory=list)]
    dynamic_policies_ids: Annotated[
        List[PositiveInt], Field(serialization_alias="dynamic_policies", default_factory=list)
    ]


class TargetReadBrief(TimestampSchema, TargetBase):
    id: int


class TargetCreated(TimestampSchema, TargetBase):
    id: int


class TargetCreate(TargetBase):
    policies: Annotated[List[PositiveInt], Field(default_factory=list), EnsureListUnique]
    dynamic_policies: Annotated[List[PositiveInt], Field(default_factory=list), EnsureListUnique]


class TargetUpdate(TargetBase):
    policies: Annotated[List[PositiveInt], Field(default_factory=list), EnsureListUnique]
    dynamic_policies: Annotated[List[PositiveInt], Field(default_factory=list), EnsureListUnique]


class TargetDelete(TargetBase):
    pass
