import random

from aerleon.lib.plugin_supervisor import BUILTIN_GENERATORS
from sqlalchemy.orm import Session

from src.app import models
from tests.conftest import fake


def create_network(db: Session) -> models.Network:
    _network = models.Network(name=fake.name())

    db.add(_network)
    db.commit()
    db.refresh(_network)

    return _network


def create_service(db: Session) -> models.Service:
    _service = models.Service(name=fake.name())

    db.add(_service)
    db.commit()
    db.refresh(_service)

    return _service


def create_target(db: Session) -> models.Target:
    _target = models.Target(
        name=fake.name(),
        generator=random.choice(BUILTIN_GENERATORS)[0],
        inet_mode=random.choice(["inet", "inet6", "mixed"]),
    )

    db.add(_target)
    db.commit()
    db.refresh(_target)

    return _target


def create_deployer(db: Session, target: models.Target) -> models.Deployer:
    _deployer = models.Deployer(
        name=fake.name(),
        target=target,
    )

    db.add(_deployer)
    db.commit()
    db.refresh(_deployer)

    return _deployer
