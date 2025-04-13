from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import CIDR
from pydantic.networks import IPvAnyAddress
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import TextClause
from sqlalchemy_mixins.serialize import SerializeMixin
from sqlalchemy_mixins.timestamp import TimestampsMixin

from ..core.db.database import Base
from ..schemas.custom_validators import DNSHostname

if TYPE_CHECKING:
    from .revision import Revision
    from .target import Target
    from .test import Test
else:
    Target = "Target"
    Revision = "Revision"
    Test = "Test"
    
class Publisher(Base, SerializeMixin, TimestampsMixin):
    __tablename__ = "publishers"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)
    
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), init=False)

    target: Mapped["Target"] = relationship(
        "Target", foreign_keys=[target_id], back_populates="publishers", single_parent=True
    )
    
    name: Mapped[str] = mapped_column(String, unique=True)

    target = relationship("Target", lazy="selectin", back_populates="publishers")

    ssh_config = relationship("PublisherSSHConfig", lazy="selectin", uselist=False, back_populates="publisher")

    publisher_jobs = relationship("PublisherJob", back_populates="publisher")


class PublisherSSHConfig(Base, SerializeMixin, TimestampsMixin):
    __tablename__ = "publisher_ssh_configs"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    host: Mapped[IPvAnyAddress | DNSHostname] = mapped_column(String)
    username: Mapped[str] = mapped_column(String)
    password: Mapped[Optional[str]] = mapped_column(String)
    ssh_key: Mapped[Optional[Text]] = mapped_column(String)
    
    publisher_id: Mapped[int] = mapped_column(ForeignKey("publishers.id"))
    publisher = relationship("Publisher", foreign_keys=[publisher_id], back_populates="ssh_config")
    
    port: Mapped[int] = mapped_column(String, default=22)


class PublisherJob(Base, SerializeMixin, TimestampsMixin):
    __tablename__ = "publisher_jobs"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    publisher_id: Mapped[int] = mapped_column(ForeignKey("publishers.id"))
    
    publisher: Mapped["Publisher"] = relationship("Publisher", back_populates="publisher_jobs")
    
    arq_job_id: Mapped[str] = mapped_column(String)