from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter

from app.models import Deployer


class DeployerFilter(Filter):
    id: Optional[int] = None
    id__in: Optional[list[int]] = None
    id__ilike: Optional[str] = None
    id__like: Optional[str] = None
    id__neq: Optional[str] = None

    name: Optional[str] = None
    name__ilike: Optional[str] = None
    name__like: Optional[str] = None
    name__neq: Optional[str] = None

    mode: Optional[str] = None
    mode__ilike: Optional[str] = None
    mode__like: Optional[str] = None
    mode__neq: Optional[str] = None

    target_id: Optional[int] = None
    target_id__in: Optional[list[int]] = None
    target_id__ilike: Optional[str] = None
    target_id__like: Optional[str] = None
    target_id__neq: Optional[str] = None

    order_by: list[str] = ["id"]
    q: Optional[str] = None

    class Constants(Filter.Constants):
        model = Deployer
        search_model_fields = ["name", "mode"]
        search_field_name = "q"
