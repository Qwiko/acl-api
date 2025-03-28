from typing import Annotated, List

from aerleon.lib.plugin_supervisor import BUILTIN_GENERATORS
from pydantic import BaseModel, Field, PositiveInt, field_validator

from ..core.schemas import TimestampSchema


class TargetBase(BaseModel):
    name: str
    
    generator: Annotated[str | None, Field(examples=["cisco", "juniper"], default=None)]

    inet_mode: Annotated[str | None, Field(examples=["inet", "inet6", "mixed"], default=None)]
    
    @field_validator("generator")
    @classmethod
    def validate_generator(cls, v: str) -> str:
        if v not in [g[0] for g in BUILTIN_GENERATORS]:
            raise ValueError("not a valid generator.")
        return v

    @field_validator("inet_mode")
    @classmethod
    def validate_inet_mode(cls, v: str) -> str:
        if v not in [None, "inet", "inet6", "mixed"]:
            raise ValueError("not a valid inet mode.")
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
    policies: Annotated[List[PositiveInt], Field(default_factory=list)]
    dynamic_policies: Annotated[List[PositiveInt], Field(default_factory=list)]


class TargetUpdate(TargetBase):
    policies: Annotated[List[PositiveInt], Field(default_factory=list)]
    dynamic_policies: Annotated[List[PositiveInt], Field(default_factory=list)]


class TargetDelete(TargetBase):
    pass
