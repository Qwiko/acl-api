from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_mixins.timestamp import TimestampsMixin

from ..core.db.database import Base
from .network import Network
from .service import Service

if TYPE_CHECKING:
    from .revision import Revision
    from .target import Target
    from .test import Test
else:
    Target = "Target"
    Revision = "Revision"
    Test = "Test"


class PolicyActionEnum(str, Enum):
    ACCEPT = "accept"
    DENY = "deny"
    NEXT = "next"
    REJECT = "reject"
    REJECT_WITH_TCP_RST = "reject-with-tcp-rst"


class PolicyOptionEnum(str, Enum):
    ESTABLISHED = "established"
    IS_FRAGMENT = "is-fragment"
    TCP_ESTABLISHED = "tcp-established"
    TCP_INITIAL = "tcp-initial"


class Policy(Base, TimestampsMixin):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("id", "name", name="uq_policy_name"),)

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    name: Mapped[str] = mapped_column(String)
    comment: Mapped[Optional[str]] = mapped_column(String)

    tests: Mapped[List["Test"]] = relationship(
        secondary="test_policy_association", lazy="joined", back_populates="policies", init=False
    )

    @property
    def tests_ids(self) -> List[int]:
        return [test.id for test in self.tests]

    targets: Mapped[List["Target"]] = relationship(
        secondary="target_policy_association", lazy="joined", back_populates="policies", init=False
    )

    @property
    def targets_ids(self) -> List[int]:
        return [target.id for target in self.targets]

    terms: Mapped[List["PolicyTerm"]] = relationship(
        foreign_keys="PolicyTerm.policy_id",
        back_populates="policy",
        cascade="all, delete-orphan",
        lazy="joined",
        init=False,
    )

    revisions: Mapped[List["Revision"]] = relationship(
        foreign_keys="Revision.policy_id",
        back_populates="policy",
        cascade="all, delete",
        init=False,
    )

    @property
    def valid_name(self) -> str:
        return self.name.replace(" ", "-")


class PolicyTermSourceNetworkAssociation(Base):
    __tablename__ = "policy_term_source_network_association"

    policy_term_id: Mapped[int] = mapped_column(ForeignKey("policy_terms.id"), primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"), primary_key=True)


class PolicyTermDestinationNetworkAssociation(Base):
    __tablename__ = "policy_term_destination_network_association"

    policy_term_id: Mapped[int] = mapped_column(ForeignKey("policy_terms.id"), primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"), primary_key=True)


class PolicyTermSourceServiceAssociation(Base):
    __tablename__ = "policy_term_source_service_association"

    policy_term_id: Mapped[int] = mapped_column(ForeignKey("policy_terms.id"), primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), primary_key=True)


class PolicyTermDestinationServiceAssociation(Base):
    __tablename__ = "policy_term_destination_service_association"

    policy_term_id: Mapped[int] = mapped_column(ForeignKey("policy_terms.id"), primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), primary_key=True)


class PolicyTerm(Base):
    __tablename__ = "policy_terms"
    __table_args__ = (
        UniqueConstraint("policy_id", "name", name="uq_policy_term_name"),
        UniqueConstraint("policy_id", "nested_policy_id", name="uq_policy_term_nested"),
        CheckConstraint("policy_id != nested_policy_id", name="ck_policy_term_nested_not_equal"),
    )

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id"),
        index=True,
    )
    policy: Mapped["Policy"] = relationship(foreign_keys=[policy_id], back_populates="terms", lazy="selectin")

    name: Mapped[str] = mapped_column(String)

    source_networks: Mapped[Optional[List["Network"]]] = relationship(
        secondary="policy_term_source_network_association", lazy="selectin"
    )

    destination_networks: Mapped[Optional[List["Network"]]] = relationship(
        secondary="policy_term_destination_network_association", lazy="selectin"
    )

    source_services: Mapped[Optional[List["Service"]]] = relationship(
        secondary="policy_term_source_service_association", lazy="selectin"
    )

    destination_services: Mapped[Optional[List["Service"]]] = relationship(
        secondary="policy_term_destination_service_association", lazy="selectin"
    )

    option: Mapped[Optional[PolicyOptionEnum]] = mapped_column(SQLAlchemyEnum(PolicyOptionEnum))

    logging: Mapped[Optional[bool]] = mapped_column(Boolean)

    action: Mapped[Optional[PolicyActionEnum]] = mapped_column(SQLAlchemyEnum(PolicyActionEnum))

    negate_source_networks: Mapped[Optional[bool]] = mapped_column(Boolean)
    negate_destination_networks: Mapped[Optional[bool]] = mapped_column(Boolean)
    nested_policy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policies.id"), default=None)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def valid_name(self) -> str:
        return self.policy.valid_name + "-" + self.name.replace(" ", "-")

    @property
    def source_networks_ids(self) -> List[int]:
        return [source_network.id for source_network in self.source_networks]

    @property
    def destination_networks_ids(self) -> List[int]:
        return [destination_network.id for destination_network in self.destination_networks]

    @property
    def source_services_ids(self) -> List[int]:
        return [source_service.id for source_service in self.source_services]

    @property
    def destination_services_ids(self) -> List[int]:
        return [destination_service.id for destination_service in self.destination_services]
