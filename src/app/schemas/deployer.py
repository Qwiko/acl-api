from typing import Annotated, Optional

from pydantic import BaseModel, Field, PositiveInt
from pydantic.networks import IPvAnyAddress

from ..core.schemas import TimestampSchema
from ..schemas.custom_validators import DNSHostname


class DeployerBase(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]


class DeployerRead(TimestampSchema, DeployerBase):
    id: int
    target_id: Annotated[PositiveInt, Field(serialization_alias="target")]
    ssh_config: Optional["DeployerSSHConfig"]  # = {}


class DeployerReadBrief(TimestampSchema, DeployerBase):
    id: int


class DeployerCreated(TimestampSchema, DeployerBase):
    id: int


class DeployerCreate(DeployerBase):
    target: Annotated[Optional[PositiveInt], Field()]


class DeployerUpdate(DeployerBase):
    target: Annotated[Optional[PositiveInt], Field()]


class DeployerDelete(DeployerBase):
    pass


class DeployerSSHConfig(BaseModel):
    id: int
    host: IPvAnyAddress | DNSHostname
    username: str
    port: int
    password: Optional[str]
    ssh_key: Optional[str]
