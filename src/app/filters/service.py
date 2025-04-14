from typing import Optional


from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.sqlalchemy import Filter

from ..models import Service, ServiceEntry


class ServiceEntryFilter(Filter):
    protocol: Optional[str] = None
    port: Optional[str] = None

    class Constants(Filter.Constants):
        model = ServiceEntry


class ServiceFilter(Filter):
    id: Optional[int] = None
    id__in: Optional[list[int]] = None
    id__ilike: Optional[str] = None
    id__like: Optional[str] = None
    id__neq: Optional[str] = None
    name: Optional[str] = None
    name__ilike: Optional[str] = None
    name__like: Optional[str] = None
    name__neq: Optional[str] = None
    entries: Optional[ServiceEntryFilter] = FilterDepends(with_prefix("entries", ServiceEntryFilter))

    order_by: list[str] = ["id"]

    q: Optional[str] = None

    class Constants(Filter.Constants):
        model = Service
        search_model_fields = ["name"]
        search_field_name = "q"
