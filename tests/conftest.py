from typing import Any, Callable, Generator

import pytest
from faker import Faker
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from src.app.core.config import settings
from src.app.core.db.database import Base
from src.app.core.security import User, get_current_user
from src.app.main import app

DATABASE_URI = settings.POSTGRES_URI
DATABASE_PREFIX = settings.POSTGRES_SYNC_PREFIX

sync_engine = create_engine(DATABASE_PREFIX + DATABASE_URI)
local_session = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


fake = Faker()


@pytest.fixture(scope="session", autouse=True)
def drop_all_tables_before_tests():
    # Drop all tables before any tests are run
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, Any, None]:
    def override_get_current_user():
        return User(id=1, username="testuser")

    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as _client:
        yield _client
    app.dependency_overrides = {}
    sync_engine.dispose()


@pytest.fixture
def db() -> Generator[Session, Any, None]:
    session = local_session()
    yield session
    session.close()


def override_dependency(dependency: Callable[..., Any], mocked_response: Any) -> None:
    app.dependency_overrides[dependency] = lambda: mocked_response
