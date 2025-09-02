from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_mixins.timestamp import TimestampsMixin

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.deployer import Deployer
    from app.models.revision import Revision
    from app.models.target import Target
    from app.models.test import Test
else:
    Deployer = "Deployer"
    Target = "Target"
    Revision = "Revision"
    Test = "Test"


class Deployment(Base, TimestampsMixin):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)

    deployer_id: Mapped[int] = mapped_column(ForeignKey("deployers.id"))
    deployer: Mapped["Deployer"] = relationship("Deployer", back_populates="deployments")

    revision_id: Mapped[int] = mapped_column(ForeignKey("revisions.id"))
    revision: Mapped["Revision"] = relationship("Revision", back_populates="deployments")

    status: Mapped[str] = mapped_column(String)

    output: Mapped[Optional[str]] = mapped_column(Text, init=False)
