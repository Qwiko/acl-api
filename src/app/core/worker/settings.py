from arq.connections import RedisSettings

from ...core.config import settings
from .functions import deploy_proxmox_nft, deploy_netmiko, deploy_git
from .base_functions import job_shutdown, job_startup

REDIS_QUEUE_HOST = settings.REDIS_QUEUE_HOST
REDIS_QUEUE_PORT = settings.REDIS_QUEUE_PORT


class WorkerSettings:
    functions = [deploy_proxmox_nft, deploy_netmiko, deploy_git]
    redis_settings = RedisSettings(host=REDIS_QUEUE_HOST, port=REDIS_QUEUE_PORT)
    on_job_start = job_startup
    after_job_end = job_shutdown
    handle_signals = False
    max_jobs = 1  # Messes up the logging if we run multiple jobs in parallel, use multiple docker containers instead
