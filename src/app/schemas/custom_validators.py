from pydantic import AfterValidator
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, PydanticCustomError
from pydantic import BaseModel
import re


def require_unique(v):
    """
    Check that the list is unique.
    """
    if len(v) != len(set(v)):
        raise ValueError("not unique")
    return v


EnsureListUnique = AfterValidator(require_unique)

class DNSHostname(str):
    @classmethod
    def validate(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("string required")

        if len(value) > 253:
            raise PydanticCustomError('dns_hostname', 'Hostname too long')

        hostname_regex = re.compile(
            r"^(?=.{1,253}$)(?!-)[A-Z\d-]{1,63}(?<!-)(\.(?!-)[A-Z\d-]{1,63}(?<!-))*\.?$", re.IGNORECASE
        )

        if not hostname_regex.fullmatch(value):
            raise PydanticCustomError('dns_hostname', 'Invalid DNS hostname')

        return value

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler: GetCoreSchemaHandler) -> CoreSchema:
        # Integrate with Pydantic core validation system
        from pydantic_core import core_schema
        return core_schema.no_info_plain_validator_function(cls.validate)