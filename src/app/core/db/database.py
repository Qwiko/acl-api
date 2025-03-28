from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, sessionmaker

from ..config import settings


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


DATABASE_URI = settings.POSTGRES_URI
DATABASE_PREFIX = settings.POSTGRES_ASYNC_PREFIX
DATABASE_URL = f"{DATABASE_PREFIX}{DATABASE_URI}"

async_engine = create_async_engine(DATABASE_URL, echo=False, future=True)

local_session = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


async def async_get_db() -> AsyncSession:
    async_session = local_session
    async with async_session() as db:
        yield db
