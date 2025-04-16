import asyncio
import logging
from typing import Any

import paramiko
import uvloop
from arq.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ....models import Deployer, DeployerProxmoxNftConfig, RevisionConfig

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = logging.getLogger("deploy_proxmox_nft")


async def deploy_proxmox_nft(ctx: Worker, revision_id: int, deployer_id: int, *args, **kwargs) -> Any:
    db = ctx["db"]

    deployer_result = await db.execute(
        select(Deployer)
        .options(selectinload(Deployer.config).selectin_polymorphic([DeployerProxmoxNftConfig]))
        .where(Deployer.id == deployer_id)
    )
    deployer = deployer_result.scalars().one_or_none()

    target_id = deployer.target_id

    remote_host = deployer.config.host
    username = deployer.config.username
    password = deployer.config.password
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

    # Create an SSH client instance
    ssh = paramiko.SSHClient()

    # Automatically add the server's host key
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Connect to the remote host
    ssh.connect(remote_host, username=username, password=password, port=port)

    commands = [
        "mkdir -p /opt/nft",
        # "chmod +x /opt/nft/add.sh",
        f'echo """{revision_config.config}""" > /opt/nft/{revision_config.filename}',
        # f"/opt/nft/add.sh /opt/nft/{revision_config.filter_name}.nft",
        f"nft -c -f /opt/nft/{revision_config.filename}",
        f"nft add table bridge {revision_config.filter_name}",
        f"nft flush table bridge {revision_config.filter_name}",
        # f"nft -f /opt/nft/{revision_config.filename}",
    ]

    for command in commands:
        logger.info("Executing command: %s", command)

        # Execute a command on the remote host
        _, stdout, stderr = ssh.exec_command(command)

        # Read the output
        output = stdout.read().decode("utf-8")

        if stderr:
            error = stderr.read().decode("utf-8")
            if error:
                raise RuntimeError(f"Error executing command: {error}")

        logger.info("Output: %s", output)

    # Close the SSH connection
    ssh.close()
