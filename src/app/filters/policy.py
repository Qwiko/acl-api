from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter

from ..models import Policy, PolicyTerm


class PolicyFilter(Filter):
    id: Optional[int] = None
    id__in: Optional[list[int]] = None
    id__ilike: Optional[str] = None
    id__like: Optional[str] = None
    id__neq: Optional[str] = None
    name: Optional[str] = None
    name__ilike: Optional[str] = None
    name__like: Optional[str] = None
    name__neq: Optional[str] = None
    
    order_by: list[str] = ["id"]

    q: Optional[str] = None

    class Constants(Filter.Constants):
        model = Policy
        search_model_fields = ["name"]
        search_field_name = "q"


class PolicyTermFilter(Filter):
    id: Optional[int] = None
    id__in: Optional[list[int]] = None
    id__ilike: Optional[str] = None
    id__like: Optional[str] = None
    id__neq: Optional[str] = None
    name: Optional[str] = None
    name__ilike: Optional[str] = None
    name__like: Optional[str] = None
    name__neq: Optional[str] = None
    
    position: Optional[int] = None
    
    order_by: list[str] = ["position"]

    q: Optional[str] = None

    class Constants(Filter.Constants):
        model = PolicyTerm
        search_model_fields = ["name"]
        search_field_name = "q"
