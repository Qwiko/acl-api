from typing import Annotated, List, Optional



from aerleon.lib.plugin_supervisor import BUILTIN_GENERATORS
from pydantic import BaseModel, Field, PositiveInt, field_validator

from ..core.schemas import TimestampSchema
from pydantic.networks import IPvAnyAddress
from ..schemas.custom_validators import DNSHostname
from .custom_validators import EnsureListUnique


class PublisherBase(BaseModel):
    name: str


class PublisherRead(TimestampSchema, PublisherBase):
    id: int
    target_id: Annotated[PositiveInt, Field(serialization_alias="target")]
    ssh_config: Optional["PublisherSSHConfig"]



class PublisherReadBrief(TimestampSchema, PublisherBase):
    id: int


class PublisherCreated(TimestampSchema, PublisherBase):
    id: int


class PublisherCreate(PublisherBase):
    target: Annotated[Optional[PositiveInt], Field()]


class PublisherUpdate(PublisherBase):
    target: Annotated[Optional[PositiveInt], Field()]


class PublisherDelete(PublisherBase):
    pass


class PublisherSSHConfig(BaseModel):
    id: int
    host: IPvAnyAddress | DNSHostname
    username: str
    port: int
    password: Optional[str]
    ssh_key: Optional[str]