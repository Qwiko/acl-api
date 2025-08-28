import logging
from datetime import datetime, timezone
from functools import wraps
from io import StringIO

from arq.jobs import Job, JobDef
from arq.worker import Worker
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.database import local_session
from app.models import Deployment

additional_loggers = [
    "base_functions",
    "deploy_git",
    "deploy_proxmox_nft",
    "deploy_netmiko",
    "paramiko",
    "git",
    "http.client",
    "urllib3",
    "asyncio",
]

logger = logging.getLogger("base_functions")


async def job_startup(ctx: Worker) -> None:
    """Function to be called before job execution."""
    job = Job(ctx["job_id"], ctx["redis"])
    job_def: JobDef = await job.info()

    # Set up logging
    log_stream = StringIO()
    log_handler = logging.StreamHandler(log_stream)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    log_handler.setLevel(logging.INFO)
    log_handler.setFormatter(formatter)

    for logger_name in additional_loggers:
        logger_instance = logging.getLogger(logger_name)
        logger_instance.setLevel(logging.INFO)
        logger_instance.addHandler(log_handler)

    # Get deployment_id from job kwargs
    deployment_id = job_def.kwargs.get("deployment_id")
    if not deployment_id:
        raise ValueError("No deployment_id provided in job kwargs")

    db: AsyncSession = local_session()
    ctx["db"] = db

    deployment = await db.get(Deployment, deployment_id)
    if not deployment:
        raise ValueError(f"Deployment {deployment_id} not found")

    # Set the deployment status to "running"
    logger.info("Setting job status: running")
    deployment.status = "running"
    await db.commit()

    logger.info("Starting function: %s", job_def.function)

    ctx["deployment"] = deployment
    ctx["log_stream"] = log_stream
    ctx["log_handler"] = log_handler


async def job_shutdown(ctx: Worker) -> None:
    """Function to be called after job completion."""
    job = Job(ctx["job_id"], ctx["redis"])
    job_def: JobDef = await job.info()

    # Save the status to the database
    if job_def.success:
        logger.info("Job completed, setting job status: completed")
        ctx["deployment"].status = "completed"
    else:
        logger.error("Job failed, setting job status: failed")
        ctx["deployment"].status = "failed"

    # Save the log stream to the database
    ctx["deployment"].output = ctx["log_stream"].getvalue()
    await ctx["db"].commit()

    for logger_name in additional_loggers:
        logger_instance = logging.getLogger(logger_name)
        logger_instance.removeHandler(ctx["log_handler"])

    # Close log stream, handler and db
    ctx["log_stream"].close()
    ctx["log_handler"].close()
    await ctx["db"].close()
