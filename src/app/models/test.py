from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_mixins.timestamp import TimestampsMixin

from ..core.db.database import Base
from .dynamic_policy import DynamicPolicy
from .policy import Policy


class TestDynamicPolicyAssociation(Base):
    __tablename__ = "test_dynamic_policy_association"

    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), primary_key=True)
    dynamic_policy_id: Mapped[int] = mapped_column(ForeignKey("dynamic_policies.id"), primary_key=True)


class TestPolicyAssociation(Base):
    __tablename__ = "test_policy_association"

    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), primary_key=True)


class Test(Base, TimestampsMixin):
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    name: Mapped[str] = mapped_column(String)
    comment: Mapped[Optional[str]] = mapped_column(String)

    dynamic_policies: Mapped[List["DynamicPolicy"]] = relationship(
        secondary="test_dynamic_policy_association", lazy="selectin", back_populates="tests"
    )
    policies: Mapped[List["Policy"]] = relationship(
        secondary="test_policy_association", lazy="selectin", back_populates="tests"
    )

    cases: Mapped[List["TestCase"]] = relationship(
        foreign_keys="TestCase.test_id",
        back_populates="test",
        cascade="all, delete",
        lazy="joined",
        init=False,
    )

    @property
    def dynamic_policies_ids(self) -> List[int]:
        return [dynamic_policy.id for dynamic_policy in self.dynamic_policies]

    @property
    def policies_ids(self) -> List[int]:
        return [policy.id for policy in self.policies]


class TestCase(Base, TimestampsMixin):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), index=True)
    test: Mapped["Test"] = relationship(
        foreign_keys=[test_id], back_populates="cases", single_parent=True, lazy="selectin"
    )

    name: Mapped[str] = mapped_column(String)

    expected_action: Mapped[str] = mapped_column(String)

    source_network: Mapped[Optional[INET]] = mapped_column(INET)

    destination_network: Mapped[Optional[INET]] = mapped_column(INET)

    source_port: Mapped[Optional[int]] = mapped_column(Integer)

    destination_port: Mapped[Optional[int]] = mapped_column(Integer)

    protocol: Mapped[Optional[str]] = mapped_column(String)
