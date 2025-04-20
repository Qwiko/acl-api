import asyncio
import logging
from typing import Any

import uvloop
from arq.worker import Worker
from netmiko import ConnectHandler, SSHDetect
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ....models import Deployer, DeployerNetmikoConfig, RevisionConfig

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = logging.getLogger("deploy_netmiko")


async def deploy_netmiko(ctx: Worker, revision_id: int, deployer_id: int, *args, **kwargs) -> Any:
    db = ctx["db"]

    deployer_result = await db.execute(
        select(Deployer)
        .options(
            selectinload(Deployer.config).selectin_polymorphic([DeployerNetmikoConfig]), selectinload(Deployer.target)
        )
        .where(Deployer.id == deployer_id)
    )
    deployer = deployer_result.scalars().one_or_none()

    target_id = deployer.target_id
    generator = deployer.target.generator

    remote_host = deployer.config.host
    port = deployer.config.port

    username = deployer.config.username
    password = deployer.config.password
    enable = deployer.config.enable
    ssh_key = deployer.config.ssh_key

    revision_config_res = await db.execute(
        select(RevisionConfig)
        .where(RevisionConfig.revision_id == revision_id)
        .where(RevisionConfig.target_id == target_id)
    )

    revision_config: RevisionConfig = revision_config_res.scalars().one_or_none()

    if not revision_config:
        logger.error("No revision config found for the given revision and target.")
        raise RuntimeError("No revision config found for the given revision and target.")

    network_device = {
        "device_type": "autodetect",  # autodetect the device type
        "host": remote_host,
        "username": username,
        "password": password,
        "port": port,  # optional, defaults to 22
        "secret": enable,  # optional, defaults to ''
        "verbose": True,
    }

    # Mapping aerleon generators to netmiko types
    # Fallback to SSHDetect if we havent setup the mapping yet
    generator_netmiko_mapping = {
        "cisco": "cisco_ios",
        "ciscoasa": "cisco_asa",
        "cisconx": "cisco_nxos",
        "ciscoxr": "cisco_xr",
    }

    try:
        generator_netmiko_type = generator_netmiko_mapping.get(generator)
        if generator_netmiko_type:
            logger.info("Found device type from generator mapping: %s", generator_netmiko_type)
            network_device["device_type"] = generator_netmiko_type
        else:
            logger.info("Using SSHDetect to detect device type")
            guesser = SSHDetect(**network_device)

            best_match = guesser.autodetect()

            network_device["device_type"] = best_match

        net_connect = ConnectHandler(**network_device)

        if enable:
            net_connect.enable()

        if not net_connect.check_enable_mode():
            logger.error("Not in enable_mode, disconnecting.")
            net_connect.disconnect()
            raise RuntimeError("Not in enable_mode, disconnecting.")

        acl_lines = [line.strip() for line in revision_config.config.strip().splitlines() if line.strip()]

        output = net_connect.send_config_set(acl_lines, exit_config_mode=True)
        logger.info(output)

        output = net_connect.save_config()
        logger.info(output)

        net_connect.disconnect()
    except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
        logger.error("Netmiko error: %s", e)
        raise
