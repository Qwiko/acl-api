from typing import Optional

from fastapi_filter import FilterDepends, with_prefix
from sqlalchemy import String

from app.filters.custom_filter import CustomFilter as Filter
from app.models import Network, NetworkAddress


class NetworkAddressFilter(Filter):
    address: Optional[str] = None
    address__ilike: Optional[str] = None
    class Constants(Filter.Constants):
        model = NetworkAddress
        cast_map = {"address": String}

class NetworkFilter(Filter):
    id: Optional[int] = None
    id__in: Optional[list[int]] = None
    id__ilike: Optional[str] = None
    id__like: Optional[str] = None
    id__neq: Optional[str] = None
    name: Optional[str] = None
    name__ilike: Optional[str] = None
    name__like: Optional[str] = None
    name__neq: Optional[str] = None
    addresses: Optional[NetworkAddressFilter] = FilterDepends(with_prefix("addresses", NetworkAddressFilter))

    order_by: list[str] = ["id"]
    q: Optional[str] = None

    class Constants(Filter.Constants):
        model = Network

        search_model_fields = ["name", "addresses__address"]
        search_field_name = "q"
