from typing import Optional

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.sqlalchemy import Filter

from app.models import Test, TestCase


class TestCaseFilter(Filter):
    id: Optional[int] = None
    id__in: Optional[list[int]] = None
    id__ilike: Optional[str] = None
    id__like: Optional[str] = None
    id__neq: Optional[str] = None
    name: Optional[str] = None

    order_by: list[str] = ["id"]
    q: Optional[str] = None

    class Constants(Filter.Constants):
        model = TestCase
        search_model_fields = ["name"]
        search_field_name = "q"


class TestFilter(Filter):
    id: Optional[int] = None
    id__in: Optional[list[int]] = None
    id__ilike: Optional[str] = None
    id__like: Optional[str] = None
    id__neq: Optional[str] = None
    name: Optional[str] = None
    name__ilike: Optional[str] = None
    name__like: Optional[str] = None
    name__neq: Optional[str] = None
    cases: Optional[TestCaseFilter] = FilterDepends(with_prefix("cases", TestCaseFilter))

    order_by: list[str] = ["id"]
    q: Optional[str] = None

    class Constants(Filter.Constants):
        model = Test
        search_model_fields = ["name"]
        search_field_name = "q"
