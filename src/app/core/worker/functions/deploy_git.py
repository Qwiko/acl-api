import asyncio
import logging
import os
import tempfile
import uuid
from typing import Any

import uvloop
from arq.worker import Worker
from git import Repo
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ....models import Deployer, DeployerGitConfig, RevisionConfig

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = logging.getLogger("deploy_git")

async def deploy_git(ctx: Worker, revision_id: int, deployer_id: int, *args, **kwargs) -> Any:
    db = ctx["db"]

    deployer_result = await db.execute(
        select(Deployer)
        .options(selectinload(Deployer.config).selectin_polymorphic([DeployerGitConfig]))
        .where(Deployer.id == deployer_id)
    )
    deployer = deployer_result.scalars().one_or_none()

    target_id = deployer.target_id

    repo_url = deployer.config.repo_url
    branch = deployer.config.branch
    ssh_key = deployer.config.ssh_key
    folder_path = deployer.config.folder_path
    auth_token = deployer.config.auth_token

    revision_config_res = await db.execute(
        select(RevisionConfig)
        .where(RevisionConfig.revision_id == revision_id)
        .where(RevisionConfig.target_id == target_id)
    )

    revision_config: RevisionConfig = revision_config_res.scalars().one_or_none()

    if not revision_config:
        logger.error("No revision config found for the given revision and target.")
        return False

    # Step 1: Write the SSH key to a secure temporary file
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as key_file:
        key_file.write(ssh_key)
        key_file.write("\n")  # Ensure the key ends with a newline
        key_path = key_file.name

    # Create a temporary directory to clone the repository
    with tempfile.TemporaryDirectory() as base_folder:
        try:
            # Step 2: Set restrictive permissions on the key (chmod 600)
            os.chmod(key_path, 0o600)

            ssh_cmd = f"ssh -i {key_path} -o StrictHostKeyChecking=no"

            # Step 4: Clone the repo
            logger.info("Cloning repository %s into %s", repo_url, base_folder)
            repo = Repo.clone_from(repo_url, base_folder, env={"GIT_SSH_COMMAND": ssh_cmd}, branch=branch, depth=2)

            # Update the acl-file from the revision config
            # Assuming the acl-file is in the root of the repository
            logger.info("Updating acl-file %s", revision_config.filename)
            if folder_path:
                # If a folder path is provided, create the folder structure
                acl_file_path = f"{base_folder}/{folder_path}/{revision_config.filename}"
                # Create the folder if it doesn't exist
                os.makedirs(f"{base_folder}/{folder_path}", exist_ok=True)
            else:
                # Create at root of the repository
                acl_file_path = f"{base_folder}/{revision_config.filename}"

            logger.info("Saving ACL to path: %s", acl_file_path)
            with open(acl_file_path, "w", encoding="utf-8") as acl_file:
                acl_file.write(revision_config.config)

            logger.info("Checking for changes in the repo, if acl-file was updated/created.")
            # Check for changes in repo
            if not (repo.git.diff(None) or repo.git.diff("HEAD") or repo.untracked_files):
                logger.info("No changes made, skipping")
                return True

            logger.info("Committing changes to %s", acl_file_path)
            # Commit the changes
            repo.index.add([acl_file_path])
            repo.index.commit(
                f"{revision_config.filename} updated, revision_id: {revision_config.revision_id}"
            )
            # Push the changes back to the repository
            logger.info("Pushing changes to the repository")
            repo.git.push()

        except Exception as e:
            logger.error("An error occurred during the deployment process: %s", e)
            raise
        finally:
            # Step 5: Remove the temporary key file
            # Close the repository
            repo.close()
            os.remove(key_path)
