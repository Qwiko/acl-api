from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_mixins.timestamp import TimestampsMixin

from ..core.db.database import Base
from .dynamic_policy import DynamicPolicy
from .policy import Policy

if TYPE_CHECKING:
    from .deployer import Deployer
    from .revision import RevisionConfig
else:
    Deployer = "Deployer"
    RevisionConfig = "RevisionConfig"


class TargetDynamicPolicyAssociation(Base):
    __tablename__ = "target_dynamic_policy_association"

    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), primary_key=True)
    dynamic_policy_id: Mapped[int] = mapped_column(ForeignKey("dynamic_policies.id"), primary_key=True)


class TargetPolicyAssociation(Base):
    __tablename__ = "target_policy_association"

    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), primary_key=True)


class Target(Base, TimestampsMixin):
    __tablename__ = "targets"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    name: Mapped[str] = mapped_column(String, unique=True)

    generator: Mapped[str] = mapped_column(String)

    inet_mode: Mapped[Optional[str]] = mapped_column(String)

    dynamic_policies: Mapped[List["DynamicPolicy"]] = relationship(
        secondary="target_dynamic_policy_association", lazy="selectin", back_populates="targets", init=False
    )
    policies: Mapped[List["Policy"]] = relationship(
        secondary="target_policy_association", lazy="selectin", back_populates="targets", init=False
    )

    revisions: Mapped[List["RevisionConfig"]] = relationship(
        foreign_keys="RevisionConfig.target_id",
        back_populates="target",
        cascade="all, delete",
        init=False,
    )

    deployers: Mapped[List["Deployer"]] = relationship(
        foreign_keys="Deployer.target_id",
        lazy="selectin",
        back_populates="target",
        cascade="all, delete",
        init=False,
    )

    @property
    def dynamic_policies_ids(self) -> List[int]:
        return [dynamic_policy.id for dynamic_policy in self.dynamic_policies]

    @property
    def policies_ids(self) -> List[int]:
        return [policy.id for policy in self.policies]

    @property
    def deployers_ids(self) -> List[int]:
        return [deployer.id for deployer in self.deployers]
