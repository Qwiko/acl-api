from typing import Annotated, Optional

from pydantic import BaseModel, Field, PositiveInt

from ..core.schemas import TimestampSchema


class DeploymentBase(BaseModel):
    pass


class DeploymentRead(TimestampSchema, DeploymentBase):
    id: int
    deployer_id: Annotated[PositiveInt, Field(serialization_alias="deployer")]
    revision_id: Annotated[PositiveInt, Field(serialization_alias="revision")]

    status: str
    output: Optional[str]


class DeploymentReadBrief(TimestampSchema, DeploymentBase):
    id: int
    deployer_id: Annotated[PositiveInt, Field(serialization_alias="deployer")]
    revision_id: Annotated[PositiveInt, Field(serialization_alias="revision")]
    status: str
