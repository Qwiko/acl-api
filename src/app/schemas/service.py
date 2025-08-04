from typing import Annotated, List
from typing_extensions import Self

from pydantic import BaseModel, Field, model_validator, PositiveInt, field_validator

from ..core.schemas import TimestampSchema


class ServiceBase(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]


class ServiceRead(TimestampSchema, ServiceBase):
    id: int
    entries: List["ServiceEntryReadBrief"]


class ServiceReadBrief(ServiceBase):
    id: int


class ServiceCreated(TimestampSchema, ServiceBase):
    id: int
    entries: List["ServiceEntryReadBrief"]


class ServiceCreate(ServiceBase):
    entries: List["ServiceEntryCreate"] = Field(default_factory=list)


class ServiceUpdate(ServiceBase):
    entries: List["ServiceEntryUpdate"] = Field(default_factory=list)


class ServiceDelete(ServiceBase):
    pass


class ServiceUsage(BaseModel):
    policies: Annotated[List[PositiveInt], Field(default_factory=list)]
    services: Annotated[List[PositiveInt], Field(default_factory=list)]


## ServiceEntry
class ServiceEntryBase(BaseModel):
    protocol: Annotated[str | None, Field(max_length=100, examples=["This is my service entry protocol"], default=None)]
    port: Annotated[str | None, Field(examples=["80 or 80-8080"], default=None)]
    nested_service_id: Annotated[PositiveInt | None, Field(default=None)]

    @model_validator(mode="after")
    def cannot_use_nested_with_protocol_or_port(self: Self) -> Self:
        protocol = self.protocol
        port = self.port
        nested_service_id = self.nested_service_id

        if nested_service_id is not None and (protocol is not None or port is not None):
            raise ValueError("cannot use nested_service_id together with protocol and port")

        if protocol in ["tcp", "udp"] and ((protocol and not port) or (port and not protocol)):
            raise ValueError("protocol and port must be declared together")

        if not protocol and not port and not nested_service_id:
            raise ValueError("need to have protocol and port or nested_service_id")

        return self

    @model_validator(mode="after")
    def icmp_validator(self: Self) -> Self:
        protocol = self.protocol
        port = self.port
        nested_service_id = self.nested_service_id

        # Skip when nested_service_id is not None
        if nested_service_id is not None:
            return self

        if protocol == "icmp" and port is not None:
            raise ValueError("port must be None when protocol is icmp")

        return self

    @field_validator("port", mode="after")
    def parse_and_validate_port(cls, v):
        # If None return
        if not v:
            return v
        # Handle string like "80-8000"
        if "-" in v:
            try:
                start_str, end_str = v.split("-", maxsplit=1)
                start, end = int(start_str), int(end_str)
                if not (0 <= start <= 65535 and 0 <= end <= 65535):
                    raise ValueError("Port numbers must be between 0 and 65535")
                if start > end:
                    raise ValueError("Range start cannot be greater than range end")
                return v
            except (ValueError, TypeError):
                raise ValueError("Invalid port range format: expected 'start-end'")
        # Handle all other cases
        else:
            try:
                va = int(v)
                if not (0 <= va <= 65535):
                    raise ValueError("Port number must be between 0 and 65535")
                return v
            except (ValueError, TypeError):
                raise ValueError("Port must be an integer or string in 'start-end' format")


class ServiceEntryRead(TimestampSchema, ServiceEntryBase):
    # id: int
    service_id: int


class ServiceEntryReadBrief(ServiceEntryBase):
    pass


class ServiceEntryCreate(ServiceEntryBase):
    pass


class ServiceEntryUpdate(ServiceEntryBase):
    pass


class ServiceEntryDelete(ServiceEntryBase):
    pass
