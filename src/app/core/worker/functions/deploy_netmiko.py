import asyncio
import logging
import os
from typing import Any

import uvloop
from arq.worker import Worker
from netmiko import ConnectHandler, SSHDetect
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException
from netutils.lib_mapper import NETMIKO_LIB_MAPPER_REVERSE
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.utils.revision_hash import revision_hash
from app.models import Deployer, DeployerNetmikoConfig, RevisionConfig

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

    # Get from environment

    password = os.getenv(str(deployer.config.password_envvar))
    enable = os.getenv(str(deployer.config.enable_envvar))
    ssh_key = os.getenv(str(deployer.config.ssh_key_envvar))

    if not password and not ssh_key:
        logger.error("No password or SSH key found in environment variables.")
        raise RuntimeError("No password or SSH key found in environment variables.")

    # Get api_url from environment
    api_url = os.getenv("API_URL")

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

    try:
        generator_netmiko_type = NETMIKO_LIB_MAPPER_REVERSE.get(generator)
        if generator_netmiko_type:
            logger.info("Found device type from NETMIKO_MAPPER: %s", generator_netmiko_type)
            network_device["device_type"] = generator_netmiko_type
        else:
            logger.info("Using SSHDetect to detect device type")
            guesser = SSHDetect(**network_device)

            best_match = guesser.autodetect()

            network_device["device_type"] = best_match

        net_connect = ConnectHandler(**network_device)

        # If we have a enable password, we need to enter enable mode
        # Otherwise we assume we are already in enable mode
        if enable:
            net_connect.enable()

        if not net_connect.check_enable_mode():
            logger.error("Not in enable_mode, disconnecting.")
            net_connect.disconnect()
            raise RuntimeError("Not in enable_mode, disconnecting.")
        
        # Revision hash for auth
        hash = revision_hash(revision_config.config)

        # For certain devices we can use copy to running-config command with http instead of sending the acl one line at a time
        # Only if we have a api_url
        # TODO add temporary authentication here
        if api_url and generator in ["cisco_ios"]:
            logger.info("Trying to get acl from remote API")

            # TODO add some generic function here to copy over the acl.
            output = net_connect.send_command(
                f"copy {api_url}/revisions/{revision_id}/raw_config/{target_id}/{hash} running-config",
                expect_string=r"Destination filename",
                strip_prompt=False,
                strip_command=False,
            )
            logger.info(output)

            output = net_connect.send_command(
                command_string="\n", expect_string=r"#", read_timeout=60, strip_prompt=False, strip_command=False
            )
            logger.info(output)
        elif api_url and generator in ["cisco_nxos"]:
            logger.info("Trying to get acl from remote API")

            output = net_connect.send_command(
                f"copy {api_url}/revisions/{revision_id}/raw_config/{target_id}/{hash} running-config",
                expect_string=r"Enter vrf",
                strip_prompt=False,
                strip_command=False,
            )
            logger.info(output)

            output = net_connect.send_command(
                command_string="management",
                expect_string=r"#",
                read_timeout=60,
                strip_prompt=False,
                strip_command=False,
            )
            logger.info(output)
        else:
            # For other devices, we assume the config is in a format that can be sent directly
            acl_lines = [line.strip() for line in revision_config.config.strip().splitlines() if line.strip()]

            output = net_connect.send_config_set(acl_lines, exit_config_mode=True)
            logger.info(output)

        output = net_connect.save_config()
        logger.info(output)

        net_connect.disconnect()
    except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
        logger.error("Netmiko error: %s", e)
        raise
