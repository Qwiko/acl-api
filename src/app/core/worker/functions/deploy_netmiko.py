import asyncio
import logging
from typing import Any

import uvloop
from arq.worker import Worker
from netmiko import ConnectHandler
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ....models import Deployer, DeployerNetmikoConfig, RevisionConfig

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = logging.getLogger("deploy_netmiko")


async def deploy_netmiko(ctx: Worker, revision_id: int, deployer_id: int, *args, **kwargs) -> Any:
    db = ctx["db"]

    deployer_result = await db.execute(
        select(Deployer)
        .options(selectinload(Deployer.config).selectin_polymorphic([DeployerNetmikoConfig]))
        .where(Deployer.id == deployer_id)
    )
    deployer = deployer_result.scalars().one_or_none()

    target_id = deployer.target_id

    remote_host = deployer.config.host
    username = deployer.config.username
    password = deployer.config.password
    enable = deployer.config.enable
    ssh_key = deployer.config.ssh_key
    port = deployer.config.port

    revision_config_res = await db.execute(
        select(RevisionConfig)
        .where(RevisionConfig.revision_id == revision_id)
        .where(RevisionConfig.target_id == target_id)
    )

    revision_config: RevisionConfig = revision_config_res.scalars().one_or_none()

    if not revision_config:
        logger.error("No revision config found for the given revision and target.")
        return False

    network_device = {
        "device_type": "autodetect",  # autodetect the device type
        "host": remote_host,
        "username": username,
        "password": password,
        "port": port,  # optional, defaults to 22
        "secret": enable,  # optional, defaults to ''
    }

    net_connect = ConnectHandler(**network_device)

    acl_lines = [line.strip() for line in revision_config.config.strip().splitlines() if line.strip()]

    output = net_connect.send_config_set(acl_lines)
    logger.info(output)

    net_connect.disconnect()
