from typing import List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import CIDR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import TextClause
from sqlalchemy_mixins.serialize import SerializeMixin
from sqlalchemy_mixins.timestamp import TimestampsMixin

from ..core.db.database import Base


class Network(Base, SerializeMixin, TimestampsMixin):
    __tablename__ = "networks"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    name: Mapped[str] = mapped_column(String)

    addresses: Mapped[List["NetworkAddress"]] = relationship(
        "NetworkAddress",
        foreign_keys="NetworkAddress.network_id",
        back_populates="network",
        cascade="all, delete",
        lazy="selectin",
        init=False,
    )


class NetworkAddress(Base, SerializeMixin, TimestampsMixin):
    __tablename__ = "network_addresses"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"))

    address: Mapped[Optional[CIDR]] = mapped_column(CIDR)
    comment: Mapped[Optional[str]] = mapped_column(String)

    network: Mapped["Network"] = relationship(
        "Network", foreign_keys=[network_id], back_populates="addresses", single_parent=True
    )

    nested_network_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("networks.id"), server_default=TextClause("NULL")
    )

    nested_network: Mapped[Optional["Network"]] = relationship("Network", foreign_keys=[nested_network_id], init=False)
