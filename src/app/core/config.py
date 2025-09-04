import os
from enum import Enum

from pydantic_settings import BaseSettings
from starlette.config import Config

current_file_dir = os.path.dirname(os.path.realpath(__file__))
env_path = os.path.join(current_file_dir, "..", "..", ".env")
config = Config(env_path)


class AppSettings(BaseSettings):
    REVISON_NEEDED_COVERAGE: float = config("TEST_COVERAGE", default=0)


class LDAPSettings(BaseSettings):
    LDAP_SERVER_URI: str = config("LDAP_SERVER_URI", default="")
    LDAP_BIND_DN: str = config("LDAP_BIND_DN", default="")
    LDAP_BIND_PASSWORD: str = config("LDAP_BIND_PASSWORD", default="")

    LDAP_USER_BIND_DN: str = config("LDAP_USER_BIND_DN", default="cn={username},ou=people,dc=example,dc=org")

    LDAP_USER_SEARCH_BASE: str = config("LDAP_USER_SEARCH_BASE", default="ou=people,dc=example,dc=org")
    LDAP_USER_SEARCH_FILTER: str = config("LDAP_USER_SEARCH_FILTER", default="(uid={username})")

    LDAP_USERNAME_ATTR: str = config("LDAP_USERNAME_ATTR", default="cn")
    LDAP_NAME_ATTR: str = config("LDAP_NAME_ATTR", default="displayName")
    LDAP_EMAIL_ATTR: str = config("LDAP_EMAIL_ATTR", default="mail")

    JWT_SECRET_KEY: str = config("JWT_SECRET_KEY", default="supersecret")
    JWT_ALGORITHM: str = config("JWT_ALGORITHM", default="HS256")
    JWT_EXPIRE_MINUTES: int = config("JWT_EXPIRE_MINUTES", default=60)


class DatabaseSettings(BaseSettings):
    pass


class PostgresSettings(DatabaseSettings):
    POSTGRES_USER: str = config("POSTGRES_USER", default="postgres")
    POSTGRES_PASSWORD: str = config("POSTGRES_PASSWORD", default="postgres")
    POSTGRES_SERVER: str = config("POSTGRES_SERVER", default="localhost")
    POSTGRES_PORT: int = config("POSTGRES_PORT", default=5432)
    POSTGRES_DB: str = config("POSTGRES_DB", default="postgres")
    POSTGRES_SYNC_PREFIX: str = config("POSTGRES_SYNC_PREFIX", default="postgresql://")
    POSTGRES_ASYNC_PREFIX: str = config("POSTGRES_ASYNC_PREFIX", default="postgresql+asyncpg://")
    POSTGRES_URI: str = f"{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"
    POSTGRES_URL: str | None = config("POSTGRES_URL", default=None)


class TestSettings(BaseSettings): ...


class RedisQueueSettings(BaseSettings):
    REDIS_QUEUE_HOST: str = config("REDIS_QUEUE_HOST", default="localhost")
    REDIS_QUEUE_PORT: int = config("REDIS_QUEUE_PORT", default=6379)


class EnvironmentOption(Enum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentSettings(BaseSettings):
    ENVIRONMENT: EnvironmentOption = config("ENVIRONMENT", default="local")


class Settings(
    AppSettings,
    LDAPSettings,
    PostgresSettings,
    TestSettings,
    RedisQueueSettings,
    EnvironmentSettings,
):
    pass


settings = Settings()
