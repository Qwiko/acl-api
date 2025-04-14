from typing import Optional, List

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_mixins.timestamp import TimestampsMixin

from ..core.db.database import Base


class Service(Base, TimestampsMixin):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    name: Mapped[str] = mapped_column(String)

    entries: Mapped[List["ServiceEntry"]] = relationship(
        "ServiceEntry",
        foreign_keys="ServiceEntry.service_id",
        back_populates="service",
        cascade="all, delete",
        lazy="selectin",
        init=False,
    )


class ServiceEntry(Base, TimestampsMixin):
    __tablename__ = "service_entries"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))

    protocol: Mapped[Optional[str]] = mapped_column(String)
    port: Mapped[Optional[str]] = mapped_column(String)

    service: Mapped["Service"] = relationship(foreign_keys=[service_id], back_populates="entries", single_parent=True)

    nested_service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("services.id"))

    nested_service: Mapped[Optional["Service"]] = relationship("Service", foreign_keys=[nested_service_id], init=False)
