import asyncio
import json
import logging
from typing import Any, List

import paramiko
import uvloop
from arq.worker import Worker

from ...core.db.database import async_get_db
from ...models import RevisionConfig
from ..cruds import revision_crud, publisher_crud

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


async def push_ssh(ctx: Worker, revision_id: int, publisher_id: int) -> Any:
    db = ctx["db"]
    revision = await revision_crud.get(db=db, obj_id=revision_id, load_relations=True)

    publisher = await publisher_crud.get(db=db, obj_id=publisher_id, load_relations=True)

    target_id = publisher.target_id
    
    remote_host = publisher.ssh_config.host
    username = publisher.ssh_config.username
    password = publisher.ssh_config.password
    port = publisher.ssh_config.port
    
    target_configs_dict: List[RevisionConfig] = [config for config in revision.configs if config.target_id == target_id]

    if not target_configs_dict:
        logging.info({target_id}, "not found in:", {revision_id})
        return False
    target_config_dict = target_configs_dict[0]

    # Create an SSH client instance
    ssh = paramiko.SSHClient()

    # Automatically add the server's host key
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Connect to the remote host
    ssh.connect(remote_host, username=username, password=password, port=port)

    policy_name = json.loads(revision.json_data).get("name")

    logging.info(f"{revision.id}, {policy_name}")

    commands = [
        f'echo """{target_config_dict.config}""" > /opt/nft/{policy_name}.nft',
        f"/opt/nft/add.sh /opt/nft/{policy_name}.nft",
        f"nft -c -f /opt/nft/{policy_name}.nft",
        f"nft add table bridge {policy_name}",
        f"nft flush table bridge {policy_name}",
        f"nft -f /opt/nft/{policy_name}.nft",
    ]
    for command in commands:
        logging.info(command)
        # Execute a command on the remote host
        stdin, stdout, stderr = ssh.exec_command(command)

        # Read the output
        output = stdout.read().decode("utf-8")
        logging.info(output)

    # Close the SSH connection
    ssh.close()

    return True


async def startup(ctx: Worker) -> None:
    ctx["db"] = await anext(async_get_db())
    logging.info("Worker Started")


async def shutdown(ctx: Worker) -> None:
    await ctx["db"].close()
    logging.info("Worker end")
