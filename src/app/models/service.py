from typing import Optional, List

from sqlalchemy import ForeignKey, String, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_mixins.timestamp import TimestampsMixin

from ..core.db.database import Base


class Service(Base, TimestampsMixin):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("id", "name", name="uq_service_name"),)

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    name: Mapped[str] = mapped_column(String)

    entries: Mapped[List["ServiceEntry"]] = relationship(
        "ServiceEntry",
        foreign_keys="ServiceEntry.service_id",
        back_populates="service",
        cascade="all, delete-orphan",
        lazy="selectin",
        init=False,
    )


class ServiceEntry(Base, TimestampsMixin):
    __tablename__ = "service_entries"
    __table_args__ = (
        UniqueConstraint("service_id", "nested_service_id", name="uq_service_entry_nested"),
        CheckConstraint("service_id != nested_service_id", name="ck_service_entry_nested_not_equal"),
    )

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id"),
        index=True,
    )

    protocol: Mapped[Optional[str]] = mapped_column(String)
    port: Mapped[Optional[str]] = mapped_column(String)

    service: Mapped["Service"] = relationship(foreign_keys=[service_id], back_populates="entries")

    nested_service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("services.id"))

    nested_service: Mapped[Optional["Service"]] = relationship("Service", foreign_keys=[nested_service_id], init=False)
