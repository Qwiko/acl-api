from typing import TYPE_CHECKING, Optional

from pydantic.networks import IPvAnyAddress
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_mixins.timestamp import TimestampsMixin

from app.models.base import Base

from app.schemas.custom_validators import DNSHostname

if TYPE_CHECKING:
    from app.models.deployment import Deployment
    from app.models.revision import Revision
    from app.models.target import Target
    from app.models.test import Test
else:
    Deployment = "Deployment"
    Target = "Target"
    Revision = "Revision"
    Test = "Test"


class Deployer(Base, TimestampsMixin):
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

    deployments: Mapped[list["Deployment"]] = relationship("Deployment", back_populates="deployer")


class DeployerConfig(Base):
    __tablename__ = "deployer_configs"
    __mapper_args__ = {
        "polymorphic_identity": "base",
        "polymorphic_on": "type",
    }

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)
    type: Mapped[str] = mapped_column(String, nullable=False)

    deployer_id: Mapped[int] = mapped_column(ForeignKey("deployers.id"), unique=True, init=False)
    deployer: Mapped[list["Deployer"]] = relationship("Deployer", foreign_keys=[deployer_id], back_populates="config")


class DeployerProxmoxNftConfig(DeployerConfig):
    __tablename__ = "deployer_proxmox_nft_configs"
    __mapper_args__ = {"polymorphic_identity": "proxmox_nft"}

    id: Mapped[int] = mapped_column(ForeignKey("deployer_configs.id"), primary_key=True, init=False)

    host: Mapped[IPvAnyAddress | DNSHostname] = mapped_column(String)
    username: Mapped[str] = mapped_column(String)

    password_envvar: Mapped[Optional[str]] = mapped_column(String)
    ssh_key_envvar: Mapped[Optional[str]] = mapped_column(String)

    port: Mapped[int] = mapped_column(Integer, default=22)


class DeployerNetmikoConfig(DeployerConfig):
    __tablename__ = "deployer_netmiko_configs"
    __mapper_args__ = {"polymorphic_identity": "netmiko"}

    id: Mapped[int] = mapped_column(ForeignKey("deployer_configs.id"), primary_key=True, init=False)

    host: Mapped[IPvAnyAddress | DNSHostname] = mapped_column(String)
    username: Mapped[str] = mapped_column(String)

    password_envvar: Mapped[Optional[str]] = mapped_column(String)
    enable_envvar: Mapped[Optional[str]] = mapped_column(String)  # Enable password
    ssh_key_envvar: Mapped[Optional[str]] = mapped_column(String)

    port: Mapped[int] = mapped_column(Integer, default=22)


class DeployerGitConfig(DeployerConfig):
    __tablename__ = "deployer_git_configs"
    __mapper_args__ = {"polymorphic_identity": "git"}

    id: Mapped[int] = mapped_column(ForeignKey("deployer_configs.id"), primary_key=True, init=False)

    repo_url: Mapped[str] = mapped_column(String, nullable=False)
    branch: Mapped[str] = mapped_column(String, nullable=False)
    folder_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    ssh_key_envvar: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_token_envvar: Mapped[Optional[str]] = mapped_column(String, nullable=True)
