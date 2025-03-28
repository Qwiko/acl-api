from datetime import datetime
from typing import Annotated, List, Optional
from typing_extensions import Self

from pydantic import BaseModel, Field, model_validator, PositiveInt, field_validator
from pydantic.networks import IPvAnyAddress

from ..core.schemas import TimestampSchema
from .policy import PolicyTermRead


class TestBase(BaseModel):
    name: str  # Annotated[str, Field(min_length=2, max_length=30, examples=["This is my Test name"])]


class TestRead(TimestampSchema, TestBase):
    id: int
    policies_ids: Annotated[List[PositiveInt], Field(serialization_alias="policies", default_factory=list)]
    dynamic_policies_ids: Annotated[
        List[PositiveInt], Field(serialization_alias="dynamic_policies", default_factory=list)
    ]
    cases: List["TestCaseReadBrief"]


class TestReadBrief(TestBase):
    id: int


class TestCreated(TimestampSchema, TestBase):
    id: int


class TestCreate(TestBase):
    policies: Annotated[List[PositiveInt], Field(default_factory=list)]
    dynamic_policies: Annotated[List[PositiveInt], Field(default_factory=list)]


class TestUpdate(TestBase):
    policies: Annotated[List[PositiveInt], Field(default_factory=list)]
    dynamic_policies: Annotated[List[PositiveInt], Field(default_factory=list)]


class TestDelete(TestBase):
    pass


## TestCase
class TestCaseBase(BaseModel):
    name: Annotated[str, Field(max_length=100, examples=["This is my test_case name"])]
    expected_action: str
    source_network: Optional[IPvAnyAddress] = None
    destination_network: Optional[IPvAnyAddress] = None
    source_port: Optional[PositiveInt] = None
    destination_port: Optional[PositiveInt] = None
    protocol: Optional[str] = None

    @field_validator("expected_action")
    @classmethod
    def validate_expected_action(cls, v: str) -> str:
        if v not in ["accept", "deny", "next", "reject", "reject-with-tcp-rst"]:
            raise ValueError("not a valid expected_action.")
        return v


class TestCaseRead(TimestampSchema, TestCaseBase):
    id: int
    test_id: int


class TestCaseReadBrief(TestCaseBase):
    id: int


class TestCaseCreate(TestCaseBase):
    pass


class TestCaseUpdate(TestCaseBase):
    pass


class TestCaseDelete(TestCaseBase):
    pass


class TestMatchedTerm(BaseModel):
    id: int
    policy_id: int
    name: str


class TestRunRead(BaseModel):
    test_id: int
    case_name: str
    case_id: int
    passed: bool
    matched_term: TestMatchedTerm | None
