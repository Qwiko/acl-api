from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, PositiveInt, field_validator, model_validator
from pydantic.networks import IPvAnyAddress

from ..core.schemas import TimestampSchema
from ..schemas.custom_validators import DNSHostname


class DeployerModeEnum(str, Enum):
    PROXMOX_NFT = "proxmox_nft"
    NETMIKO = "netmiko"
    GIT = "git"
    HTTP = "http"
    CUSTOM = "custom"


class DeployerBase(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]


class DeployerRead(TimestampSchema, DeployerBase):
    id: int
    target_id: Annotated[PositiveInt, Field(serialization_alias="target")]
    mode: DeployerModeEnum

    config: Annotated[
        Union["DeployerProxmoxNftConfigRead", "DeployerNetmikoConfigRead", "DeployerGitConfigRead"], Field()
    ]


class DeployerReadBrief(TimestampSchema, DeployerBase):
    id: int
    target_id: Annotated[PositiveInt, Field(serialization_alias="target")]
    mode: DeployerModeEnum


class DeployerCreated(TimestampSchema, DeployerBase):
    id: int


class DeployerCreate(DeployerBase):
    target: Annotated[Optional[PositiveInt], Field()]
    mode: DeployerModeEnum
    config: Union["DeployerProxmoxNftConfigCreate", "DeployerNetmikoConfigCreate", "DeployerGitConfigCreate"]

    @model_validator(mode="before")
    @classmethod
    def dispatch_data(cls, values):
        mode = values.get("mode")
        config = values.get("config")

        if mode == DeployerModeEnum.PROXMOX_NFT:
            values["config"] = DeployerProxmoxNftConfigCreate(**config)
        elif mode == DeployerModeEnum.NETMIKO:
            values["config"] = DeployerNetmikoConfigCreate(**config)
        elif mode == DeployerModeEnum.GIT:
            values["config"] = DeployerGitConfigCreate(**config)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        return values


class DeployerUpdate(DeployerBase):
    target: Annotated[Optional[PositiveInt], Field()]


class DeployerDelete(DeployerBase):
    pass


class DeployerProxmoxNftConfigCreate(BaseModel):
    # id: int

    host: Union[IPvAnyAddress, DNSHostname]

    username: str
    port: int
    password_envvar: Optional[str] = None
    ssh_key_envvar: Optional[str] = None

    @field_validator("host", mode="after")
    @classmethod
    def validate_host(cls, v):
        # Convert to string to save to db.
        return str(v)


class DeployerProxmoxNftConfigRead(BaseModel):
    # id: int
    host: IPvAnyAddress | DNSHostname
    username: str
    port: int


class DeployerNetmikoConfigCreate(BaseModel):
    # id: int

    host: Union[IPvAnyAddress, DNSHostname]

    username: str
    port: int
    password_envvar: Optional[str] = None
    enable_envvar: Optional[str] = None  # Enable password
    ssh_key_envvar: Optional[str] = None

    @field_validator("host", mode="after")
    @classmethod
    def validate_host(cls, v):
        # Convert to string to save to db.
        return str(v)


class DeployerNetmikoConfigRead(BaseModel):
    # id: int
    host: IPvAnyAddress | DNSHostname
    username: str
    port: int


class DeployerGitConfigCreate(BaseModel):
    # id: int
    # Optional for Git and defaults to deploy_with_git
    repo_url: str
    branch: str
    folder_path: Optional[str] = None
    ssh_key_envvar: Optional[str] = None
    auth_token_envvar: Optional[str] = None

    @field_validator("folder_path")
    @classmethod
    def validate_folder_path(cls, v):
        if v.startswith("/") or v.endswith("/"):
            print("HERE1")
            raise ValueError("folder_path must not start or end with '/'")
        if "//" in v:
            print("HERE")
            raise ValueError("folder_path must not contain empty segments")
        return v


class DeployerGitConfigRead(BaseModel):
    # id: int
    repo_url: str
    branch: str
    folder_path: Optional[str] = None
