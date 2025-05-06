from typing import Optional

from fastapi_filter.base.filter import BaseFilterModel
from fastapi_filter.contrib.sqlalchemy import Filter

from ..models import Target
from pydantic import ValidationInfo, field_validator
from collections import defaultdict


class TargetGeneratorFilter(BaseFilterModel):
    id: Optional[str] = None
    id__in: Optional[list[str]] = None

    name: Optional[str] = ""

    order_by: list[str] = ["id"]
    q: Optional[str] = ""

    # Override functions
    @field_validator("*", mode="before")
    def split_str(cls, value, field: ValidationInfo):
        if (
            field.field_name is not None
            and (
                field.field_name == cls.Constants.ordering_field_name
                or field.field_name.endswith("__in")
                or field.field_name.endswith("__not_in")
            )
            and isinstance(value, str)
        ):
            if not value:
                # Empty string should return [] not ['']
                return []
            return list(value.split(","))
        return value

    @field_validator("*", mode="before", check_fields=False)
    def validate_order_by(cls, value, field: ValidationInfo):
        if field.field_name != cls.Constants.ordering_field_name:
            return value

        if not value:
            return None

        field_name_usages = defaultdict(list)
        duplicated_field_names = set()

        for field_name_with_direction in value:
            field_name = field_name_with_direction.replace("-", "").replace("+", "")

            # if not hasattr(cls.Constants.model, field_name):
            #     raise ValueError(f"{field_name} is not a valid ordering field.")

            field_name_usages[field_name].append(field_name_with_direction)
            if len(field_name_usages[field_name]) > 1:
                duplicated_field_names.add(field_name)

        if duplicated_field_names:
            ambiguous_field_names = ", ".join(
                [
                    field_name_with_direction
                    for field_name in sorted(duplicated_field_names)
                    for field_name_with_direction in field_name_usages[field_name]
                ]
            )
            raise ValueError(
                f"Field names can appear at most once for {cls.Constants.ordering_field_name}. "
                f"The following was ambiguous: {ambiguous_field_names}."
            )

        return value


class TargetFilter(Filter):
    id: Optional[int] = None
    id__in: Optional[list[int]] = None
    id__ilike: Optional[str] = None
    id__like: Optional[str] = None
    id__neq: Optional[str] = None
    name: Optional[str] = None
    name__ilike: Optional[str] = None
    name__like: Optional[str] = None
    name__neq: Optional[str] = None
    generator: Optional[str] = None
    generator__ilike: Optional[str] = None
    generator__like: Optional[str] = None
    generator__neq: Optional[str] = None

    inet_mode: Optional[str] = None

    order_by: list[str] = ["id"]
    q: Optional[str] = None

    class Constants(Filter.Constants):
        model = Target
        search_model_fields = ["name", "generator"]
        search_field_name = "q"
