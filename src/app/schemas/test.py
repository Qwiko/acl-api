from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, PositiveInt, field_validator
from pydantic.networks import IPvAnyAddress

from ..core.schemas import TimestampSchema
from .custom_validators import EnsureListUnique
from .policy import PolicyTermRead, PolicyTermReadInternal


class TestBase(BaseModel):
    name: str  # Annotated[str, Field(min_length=2, max_length=30, examples=["This is my Test name"])]
    comment: Annotated[str | None, Field(max_length=300, examples=["This is my test comment"], default=None)]


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
    policies: Annotated[List[PositiveInt], Field(default_factory=list), EnsureListUnique]
    dynamic_policies: Annotated[List[PositiveInt], Field(default_factory=list), EnsureListUnique]

    cases: List["TestCaseCreate"] = Field(default_factory=list)


class TestUpdate(TestBase):
    policies: Annotated[List[PositiveInt], Field(default_factory=list), EnsureListUnique]
    dynamic_policies: Annotated[List[PositiveInt], Field(default_factory=list), EnsureListUnique]

    cases: List["TestCaseUpdate"] = Field(default_factory=list)


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


class TestCaseRead(TestCaseBase):
    pass


class TestCaseReadBrief(TestCaseBase):
    pass


class TestCaseCreate(TestCaseBase):
    pass


class TestCaseUpdate(TestCaseBase):
    pass


class TestCaseDelete(TestCaseBase):
    pass


class TestResultOneRead(BaseModel):
    case: TestCaseRead
    passed: bool
    matched_term: PolicyTermRead | None


class TestResultRead(BaseModel):
    tests: List[TestResultOneRead]
    not_matched_terms: List[PolicyTermReadInternal]
    coverage: float  # Annotated[float, Field(ge=0.0, le=1.0)]
