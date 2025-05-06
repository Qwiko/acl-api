from ..core.config import settings
from ..core.logger import logging

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = settings.DEFAULT_RATE_LIMIT_LIMIT
DEFAULT_PERIOD = settings.DEFAULT_RATE_LIMIT_PERIOD
