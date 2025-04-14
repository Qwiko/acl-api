from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter

from ..models import Deployment


class DeploymentFilter(Filter):
    id: Optional[int] = None
    id__in: Optional[list[int]] = None
    id__ilike: Optional[str] = None
    id__like: Optional[str] = None
    id__neq: Optional[str] = None
    status: Optional[str] = None
    status__ilike: Optional[str] = None
    status__like: Optional[str] = None
    status__neq: Optional[str] = None
    deployer_id: Optional[int] = None
    deployer_id__in: Optional[list[int]] = None
    revision_id: Optional[int] = None
    revision_id__in: Optional[list[int]] = None

    order_by: list[str] = ["id"]
    q: Optional[str] = None

    class Constants(Filter.Constants):
        model = Deployment
        search_model_fields = ["status"]
        search_field_name = "q"
