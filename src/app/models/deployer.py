from typing import TYPE_CHECKING, Optional

from pydantic.networks import IPvAnyAddress
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_mixins.serialize import SerializeMixin
from sqlalchemy_mixins.timestamp import TimestampsMixin

from ..core.db.database import Base
from ..schemas.custom_validators import DNSHostname

if TYPE_CHECKING:
    from .deployment import Deployment
    from .revision import Revision
    from .target import Target
    from .test import Test
else:
    Deployment = "Deployment"
    Target = "Target"
    Revision = "Revision"
    Test = "Test"


class Deployer(Base, SerializeMixin, TimestampsMixin):
    __tablename__ = "deployers"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)
    name: Mapped[str] = mapped_column(String, unique=True)
    mode: Mapped[str] = mapped_column(String)

    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), init=False)
    target: Mapped["Target"] = relationship(
        "Target", foreign_keys=[target_id], back_populates="deployers", single_parent=True
    )

    config: Mapped["DeployerConfig"] = relationship(
        "DeployerConfig", back_populates="deployer", lazy="selectin", uselist=False, cascade="all, delete-orphan"
    )

    deployments = relationship("Deployment", back_populates="deployer")


class DeployerConfig(Base):
    __tablename__ = "deployer_configs"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)
    type: Mapped[str] = mapped_column(String, nullable=False)

    deployer_id: Mapped[int] = mapped_column(ForeignKey("deployers.id"), unique=True, init=False)
    deployer = relationship("Deployer", foreign_keys=[deployer_id], back_populates="config")

    __mapper_args__ = {
        "polymorphic_identity": "base",
        "polymorphic_on": "type",
    }


class DeployerProxmoxNftConfig(DeployerConfig):
    __tablename__ = "deployer_proxmox_nft_configs"

    id: Mapped[int] = mapped_column(ForeignKey("deployer_configs.id"), primary_key=True, init=False)

    host: Mapped[IPvAnyAddress | DNSHostname] = mapped_column(String)
    username_envvar: Mapped[str] = mapped_column(String)
    password_envvar: Mapped[Optional[str]] = mapped_column(String)
    ssh_key_envvar: Mapped[Optional[str]] = mapped_column(String)

    port: Mapped[int] = mapped_column(Integer, default=22)

    __mapper_args__ = {"polymorphic_identity": "proxmox_nft"}


class DeployerNetmikoConfig(DeployerConfig):
    __tablename__ = "deployer_netmiko_configs"

    id: Mapped[int] = mapped_column(ForeignKey("deployer_configs.id"), primary_key=True, init=False)

    host: Mapped[IPvAnyAddress | DNSHostname] = mapped_column(String)
    username_envvar: Mapped[str] = mapped_column(String)
    password_envvar: Mapped[Optional[str]] = mapped_column(String)
    enable_envvar: Mapped[Optional[str]] = mapped_column(String)  # Enable password
    ssh_key_envvar: Mapped[Optional[str]] = mapped_column(String)

    port: Mapped[int] = mapped_column(Integer, default=22)

    __mapper_args__ = {"polymorphic_identity": "netmiko"}


class DeployerGitConfig(DeployerConfig):
    __tablename__ = "deployer_git_configs"

    id: Mapped[int] = mapped_column(ForeignKey("deployer_configs.id"), primary_key=True, init=False)

    repo_url: Mapped[str] = mapped_column(String, nullable=False)
    branch: Mapped[str] = mapped_column(String, nullable=False)
    folder_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ssh_key_envvar: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_token_envvar: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    __mapper_args__ = {"polymorphic_identity": "git"}
