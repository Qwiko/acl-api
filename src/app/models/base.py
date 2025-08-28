from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(DeclarativeBase, MappedAsDataclass):
    @property
    def hashed_name(self) -> str:
        """Generate a positive integer hash using the class name and primary key."""
        mapper = inspect(self).mapper

        primary_keys = [getattr(self, key.name) for key in mapper.primary_key]

        if not primary_keys:
            raise ValueError(f"Model {self.__class__.__name__} has no primary key set.")

        # Create a deterministic string representation
        hash_string = f"{self.__class__.__name__}:" + ",".join(map(str, primary_keys))

        # Ensure a positive hash value
        return str(abs(hash(hash_string)))
