import asyncio
import json
import logging
from typing import Any, List

import paramiko
import uvloop
from arq.worker import Worker
from sqlalchemy import select

from ...core.db.database import async_get_db
from ...models import RevisionConfig, DeployerSSHConfig
from ..cruds import revision_crud, deployer_crud, deployment_crud

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


async def push_ssh(ctx: Worker, revision_id: int, deployer_id: int, deployment_id: int) -> Any:
    db = ctx["db"]
    revision = await revision_crud.get(db=db, obj_id=revision_id, load_relations=True)

    deployer = await deployer_crud.get(db=db, obj_id=deployer_id, load_relations=True)
    deployment = await deployment_crud.get(db=db, obj_id=deployment_id, load_relations=False)

    ssh_config_res = await db.execute(select(DeployerSSHConfig).where(DeployerSSHConfig.deployer_id == deployer_id))
    ssh_config = ssh_config_res.scalars().first()

    deployment.status = "running"
    await db.commit()
    await db.refresh(deployment)

    target_id = deployer.target_id

    remote_host = ssh_config.host
    username = ssh_config.username
    password = ssh_config.password
    port = ssh_config.port

    target_configs_dict: List[RevisionConfig] = [config for config in revision.configs if config.target_id == target_id]

    if not target_configs_dict:
        logging.info({target_id}, "not found in:", {revision_id})
        return False
    target_config_dict = target_configs_dict[0]

    outputs = []

    # Create an SSH client instance
    ssh = paramiko.SSHClient()

    # Automatically add the server's host key
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    outputs.append(f"Connecting to {remote_host} as {username}")
    # Connect to the remote host
    try:
        ssh.connect(remote_host, username=username, password=password, port=port)
    except paramiko.SSHException as e:
        outputs.append(f"SSH connection error: {e}")
        deployment.status = "failed"
        deployment.output = "\n".join(outputs)
        await db.commit()
        await db.refresh(deployment)
        return False

    outputs.append(f"Connected to {remote_host} as {username}")

    policy_name = json.loads(revision.json_data).get("name")

    commands = [
        # "mkdir -p /opt/nft",
        # "chmod +x /opt/nft/add.sh",
        f'echo """{target_config_dict.config}""" > /opt/nft/{policy_name}.nft',
        # f"/opt/nft/add.sh /opt/nft/{policy_name}.nft",
        f"nft -c -f /opt/nft/{policy_name}.nft",
        f"nft add table bridge {policy_name}",
        f"nft flush table bridge {policy_name}",
        f"nft -f /opt/nft/{policy_name}.nft",
    ]

    for command in commands:
        outputs.append(f"Executing command: {command}")
        # Execute a command on the remote host
        stdin, stdout, stderr = ssh.exec_command(command)

        # Read the output

        output = stdout.read().decode("utf-8")

        if stderr:
            error = stderr.read().decode("utf-8")
            if error:
                outputs.append(f"Error: {error}")
                deployment.status = "failed"
                deployment.output = "\n".join(outputs)
                await db.commit()
                await db.refresh(deployment)
                return False
        outputs.append(f"Output: {output}")
        logging.info(f"Output: {output}")

    # Close the SSH connection
    ssh.close()
    outputs.append("SSH connection closed")
    deployment.status = "completed"
    deployment.output = "\n".join(outputs)
    await db.commit()
    await db.refresh(deployment)
    return True


async def startup(ctx: Worker) -> None:
    ctx["db"] = await anext(async_get_db())
    logging.info("Worker Started")


async def shutdown(ctx: Worker) -> None:
    await ctx["db"].close()
    logging.info("Worker end")
