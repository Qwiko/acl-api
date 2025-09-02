from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_mixins.timestamp import TimestampsMixin

from app.models.base import Base

from app.models.network import Network

if TYPE_CHECKING:
    from app.models.policy import Policy
    from app.models.revision import Revision
    from app.models.target import Target
    from app.models.test import Test
else:
    Target = "Target"
    Revision = "Revision"
    Test = "Test"
    Policy = "Policy"


class DynamicPolicyFilterActionEnum(str, Enum):
    ACCEPT = "accept"
    DENY = "deny"
    NEXT = "next"
    REJECT = "reject"
    REJECT_WITH_TCP_RST = "reject-with-tcp-rst"


class DynamicPolicyDefaultActionEnum(str, Enum):
    ACCEPT = "accept"
    ACCEPT_LOG = "accept-log"
    DENY = "deny"
    DENY_LOG = "deny-log"


class DynamicPolicy(Base, TimestampsMixin):
    __tablename__ = "dynamic_policies"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    name: Mapped[str] = mapped_column(String)

    edited: Mapped[bool] = mapped_column(Boolean)

    comment: Mapped[Optional[str]] = mapped_column(String)

    custom_aerleon_header: Mapped[Optional[str]] = mapped_column(String)

    filter_action: Mapped[Optional[DynamicPolicyFilterActionEnum]] = mapped_column(
        SQLAlchemyEnum(DynamicPolicyFilterActionEnum)
    )

    default_action: Mapped[Optional[DynamicPolicyDefaultActionEnum]] = mapped_column(
        SQLAlchemyEnum(DynamicPolicyDefaultActionEnum)
    )

    tests: Mapped[List["Test"]] = relationship(
        secondary="test_dynamic_policy_association", lazy="selectin", back_populates="dynamic_policies"
    )

    @property
    def tests_ids(self) -> List[int]:
        return [test.id for test in self.tests]

    targets: Mapped[List["Target"]] = relationship(
        secondary="target_dynamic_policy_association", lazy="selectin", back_populates="dynamic_policies"
    )

    @property
    def targets_ids(self) -> List[int]:
        return [target.id for target in self.targets]

    revisions: Mapped[List["Revision"]] = relationship(
        foreign_keys="Revision.dynamic_policy_id",
        back_populates="dynamic_policy",
        cascade="all, delete",
        init=False,
    )

    source_filters: Mapped[List["Network"]] = relationship(
        secondary="dynamic_policy_source_filter_association", lazy="selectin"
    )

    destination_filters: Mapped[List["Network"]] = relationship(
        secondary="dynamic_policy_destination_filter_association", lazy="selectin"
    )

    policy_filters: Mapped[List["Policy"]] = relationship(
        secondary="dynamic_policy_policy_filter_association", lazy="selectin"
    )

    @property
    def source_filters_ids(self) -> List[int]:
        return [source_filter.id for source_filter in self.source_filters]

    @property
    def destination_filters_ids(self) -> List[int]:
        return [destination_filter.id for destination_filter in self.destination_filters]

    @property
    def policy_filters_ids(self) -> List[int]:
        return [policy_filter.id for policy_filter in self.policy_filters]

    @property
    def valid_name(self) -> str:
        return self.name.replace(" ", "-")


class DynamicPolicySourceFilterAssociation(Base):
    __tablename__ = "dynamic_policy_source_filter_association"

    dynamic_policy_id: Mapped[int] = mapped_column(ForeignKey("dynamic_policies.id"), primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"), primary_key=True)


class DynamicPolicyDestinationFilterAssociation(Base):
    __tablename__ = "dynamic_policy_destination_filter_association"

    dynamic_policy_id: Mapped[int] = mapped_column(ForeignKey("dynamic_policies.id"), primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"), primary_key=True)


class DynamicPolicyPolicyFilterAssociation(Base):
    __tablename__ = "dynamic_policy_policy_filter_association"

    dynamic_policy_id: Mapped[int] = mapped_column(ForeignKey("dynamic_policies.id"), primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), primary_key=True)
