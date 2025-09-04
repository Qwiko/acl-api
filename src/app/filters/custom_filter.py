from typing import Any, Union, get_args

from fastapi_filter.base.filter import BaseFilterModel
from fastapi_filter.contrib.sqlalchemy import Filter
from fastapi_filter.contrib.sqlalchemy.filter import _orm_operator_transformer
from sqlalchemy import cast, or_
from sqlalchemy.orm import Query
from sqlalchemy.sql.selectable import Select


class CustomFilter(Filter):
    # Custom Constants
    class Constants:  # pragma: no cover
        model: Any
        ordering_field_name: str = "order_by"
        search_model_fields: list[str]
        search_field_name: str = "search"
        prefix: str
        original_filter: type["BaseFilterModel"]
        cast_map: dict = {}

    def filter(self, query: Union[Query, Select]):
        for field_name, value in self.filtering_fields:
            field_value = getattr(self, field_name)
            if isinstance(field_value, Filter):
                query = field_value.filter(query)
            else:
                if "__" in field_name:
                    field_name, operator = field_name.split("__")
                    operator, value = _orm_operator_transformer[operator](value)
                else:
                    operator = "__eq__"

                if field_name == self.Constants.search_field_name and hasattr(self.Constants, "search_model_fields"):
                    search_filters = []
                    for field in self.Constants.search_model_fields:
                        if '__' in field:
                            related_fields = field.split('__')
                            related_field_name = related_fields.pop()
                            
                            base_model = self.Constants.model

                            for related_field in related_fields:
                                model_field = self.model_fields.get(related_field)
                                model_field_inner = get_args(model_field.annotation)[0]
                                base_model = getattr(base_model, related_field).property.mapper.class_
    
                            if related_field_name in model_field_inner.Constants.cast_map:
                                cast_type = model_field_inner.Constants.cast_map.get(related_field_name)
                                search_filters.append(cast(getattr(base_model, related_field_name), cast_type).ilike(f"%{value}%"))
                            else:
                                search_filters.append(getattr(base_model, related_field_name).ilike(f"%{value}%"))
                        else:
                            search_filters.append(getattr(self.Constants.model, field).ilike(f"%{value}%"))
                    query = query.filter(or_(*search_filters))
                else:
                    if field_name in self.Constants.cast_map:
                        model_field = cast(
                            getattr(self.Constants.model, field_name), self.Constants.cast_map.get(field_name)
                        )
                    else:
                        model_field = getattr(self.Constants.model, field_name)
                    query = query.filter(getattr(model_field, operator)(value))
        return query