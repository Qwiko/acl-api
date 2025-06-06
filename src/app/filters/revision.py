from typing import Optional

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.sqlalchemy import Filter

from ..models import Revision, RevisionConfig
from .target import TargetFilter


class RevisionConfigFilter(Filter):
    target_id: Optional[TargetFilter] = FilterDepends(with_prefix("targets", TargetFilter))

    order_by: list[str] = ["id"]

    class Constants(Filter.Constants):
        model = RevisionConfig


class RevisionFilter(Filter):
    id: Optional[int] = None
    id__in: Optional[list[int]] = None
    id__ilike: Optional[str] = None
    id__like: Optional[str] = None
    id__neq: Optional[str] = None
    comment: Optional[str] = None
    comment__ilike: Optional[str] = None
    comment__like: Optional[str] = None
    comment__neq: Optional[str] = None

    policy_id: Optional[int] = None
    dynamic_policy_id: Optional[int] = None

    configs: Optional[RevisionConfigFilter] = FilterDepends(with_prefix("configs", RevisionConfigFilter))

    order_by: list[str] = ["id"]

    q: Optional[str] = None

    class Constants(Filter.Constants):
        model = Revision
        search_model_fields = ["comment"]
        search_field_name = "q"
