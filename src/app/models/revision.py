from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_mixins.timestamp import TimestampsMixin

from ..core.db.database import Base

if TYPE_CHECKING:
    from .dynamic_policy import DynamicPolicy
    from .policy import Policy
    from .target import Target
else:
    Target = "Target"
    DynamicPolicy = "DynamicPolicy"
    Policy = "Policy"


class Revision(Base, TimestampsMixin):
    __tablename__ = "revisions"
    __table_args__ = (
        CheckConstraint(
            "(policy_id IS NOT NULL OR dynamic_policy_id IS NOT NULL) AND NOT (policy_id IS NOT NULL AND dynamic_policy_id IS NOT NULL)",
            name="check_policy_or_dynamic_policy_only_one",
        ),
    )

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    comment: Mapped[Optional[str]] = mapped_column(String)

    json_data: Mapped[JSON] = mapped_column(JSON, nullable=False)

    policy_id: Mapped[int | None] = mapped_column(ForeignKey("policies.id"), nullable=True, default=None)
    policy: Mapped["Policy"] = relationship(
        foreign_keys=[policy_id], back_populates="revisions", lazy="selectin", default=None
    )

    dynamic_policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("dynamic_policies.id"), nullable=True, default=None
    )
    dynamic_policy: Mapped["DynamicPolicy"] = relationship(
        foreign_keys=[dynamic_policy_id], back_populates="revisions", lazy="selectin", default=None
    )

    configs: Mapped[List["RevisionConfig"]] = relationship(
        "RevisionConfig", back_populates="revision", cascade="all, delete-orphan", lazy="selectin", init=False
    )


class RevisionConfig(Base):
    __tablename__ = "revision_configs"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    revision_id: Mapped[int] = mapped_column(ForeignKey("revisions.id"), nullable=False, index=True)
    revision: Mapped["Revision"] = relationship("Revision", back_populates="configs")

    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), nullable=False, index=True)
    target: Mapped["Target"] = relationship(foreign_keys=[target_id], lazy="selectin")

    filter_name: Mapped[Optional[str]] = mapped_column(String)

    config: Mapped[str] = mapped_column(Text, nullable=False)
