from typing import Annotated, List
from typing_extensions import Self

from pydantic import BaseModel, Field, model_validator, PositiveInt, field_validator
from pydantic.networks import IPvAnyNetwork

from ..core.schemas import TimestampSchema


class NetworkBase(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]


class NetworkRead(TimestampSchema, NetworkBase):
    id: int
    addresses: List["NetworkAddressRead"]


class NetworkReadBrief(NetworkBase):
    id: int


class NetworkCreated(TimestampSchema, NetworkBase):
    id: int
    addresses: List["NetworkAddressCreate"] = Field(default_factory=list)


class NetworkCreate(NetworkBase):
    addresses: List["NetworkAddressCreate"] = Field(default_factory=list)


class NetworkUpdate(NetworkBase):
    addresses: List["NetworkAddressUpdate"] = Field(default_factory=list)


class NetworkDelete(NetworkBase):
    pass


class NetworkUsage(BaseModel):
    dynamic_policies: Annotated[List[PositiveInt], Field(default_factory=list)]
    policies: Annotated[List[PositiveInt], Field(default_factory=list)]
    networks: Annotated[List[PositiveInt], Field(default_factory=list)]


## NetworkAddress
class NetworkAddressBase(BaseModel):
    address: Annotated[IPvAnyNetwork | None, Field(examples=["1.1.1.1/32", "2606:4700:4700::1111"], default=None)]
    comment: Annotated[str | None, Field(max_length=100, examples=["This is my network_address comment"], default=None)]
    nested_network_id: Annotated[PositiveInt | None, Field(default=None)]

    @model_validator(mode="after")
    def cannot_use_nested_with_address_or_comment(self: Self) -> Self:
        address = self.address
        comment = self.comment
        nested_network_id = self.nested_network_id

        if nested_network_id is not None and (address is not None or comment is not None):
            raise ValueError("cannot use nested_network_id together with address or comment")

        if comment and not address:
            raise ValueError("need to declare address together with comment")

        if not address and not comment and not nested_network_id:
            raise ValueError("need to have address and comment or nested_network_id")

        return self

    # Save address as string to db.
    @field_validator("address", mode="after")
    @classmethod
    def validate_address(cls, v):
        # Convert to string to save to db.
        return str(v)


class NetworkAddressRead(TimestampSchema, NetworkAddressBase):
    pass


class NetworkAddressReadBrief(NetworkAddressBase):
    pass


class NetworkAddressCreate(NetworkAddressBase):
    pass


class NetworkAddressUpdate(NetworkAddressBase):
    pass
