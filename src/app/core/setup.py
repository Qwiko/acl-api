from collections.abc import AsyncGenerator, Callable
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from typing import Any

import anyio
import fastapi
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from ..middleware.client_cache_middleware import ClientCacheMiddleware
from ..models import *
from .config import (
    AppSettings,
    ClientSideCacheSettings,
    DatabaseSettings,
    EnvironmentOption,
    EnvironmentSettings,
    RedisQueueSettings,
    settings,
)
from .db.database import Base
from .db.database import async_engine as engine
from .utils import queue

from typing import List

from pydantic import BaseModel


class Error(BaseModel):
    root: dict
    field: str


class ErrorBody(BaseModel):
    errors: Error


class ErrorResponse(BaseModel):
    body: ErrorBody


def format_react_admin_errors(exc: RequestValidationError):
    errors = {}

    for error in exc.errors():
        loc = error["loc"]
        field = loc[-1] if len(loc) > 1 else "root"
        msg = error["msg"]

        if field == "root":
            errors.setdefault("root", {})["serverError"] = msg
        else:
            errors[field] = msg

    return errors


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"errors": format_react_admin_errors(exc)},
    )


# -------------- database --------------
async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# -------------- queue --------------
async def create_redis_queue_pool() -> None:
    queue.pool = await create_pool(RedisSettings(host=settings.REDIS_QUEUE_HOST, port=settings.REDIS_QUEUE_PORT))


async def close_redis_queue_pool() -> None:
    await queue.pool.aclose()  # type: ignore


# -------------- application --------------
async def set_threadpool_tokens(number_of_tokens: int = 100) -> None:
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = number_of_tokens


def lifespan_factory(
    settings: (DatabaseSettings | AppSettings | ClientSideCacheSettings | RedisQueueSettings | EnvironmentSettings),
    create_tables_on_start: bool = True,
) -> Callable[[FastAPI], _AsyncGeneratorContextManager[Any]]:
    """Factory to create a lifespan async context manager for a FastAPI app."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator:
        await set_threadpool_tokens()

        if isinstance(settings, DatabaseSettings) and create_tables_on_start:
            await create_tables()

        if isinstance(settings, RedisQueueSettings):
            await create_redis_queue_pool()

        yield

        if isinstance(settings, RedisQueueSettings):
            await close_redis_queue_pool()

    return lifespan


# -------------- application --------------
def create_application(
    router: APIRouter,
    settings: (DatabaseSettings | AppSettings | ClientSideCacheSettings | RedisQueueSettings | EnvironmentSettings),
    create_tables_on_start: bool = True,
    **kwargs: Any,
) -> FastAPI:
    """Creates and configures a FastAPI application based on the provided settings.

    This function initializes a FastAPI application and configures it with various settings
    and handlers based on the type of the `settings` object provided.

    Parameters
    ----------
    router : APIRouter
        The APIRouter object containing the routes to be included in the FastAPI application.

    settings
        An instance representing the settings for configuring the FastAPI application.
        It determines the configuration applied:

        - AppSettings: Configures basic app metadata like name, description, contact, and license info.
        - DatabaseSettings: Adds event handlers for initializing database tables during startup.
        - RedisCacheSettings: Sets up event handlers for creating and closing a Redis cache pool.
        - ClientSideCacheSettings: Integrates middleware for client-side caching.
        - RedisQueueSettings: Sets up event handlers for creating and closing a Redis queue pool.
        - RedisRateLimiterSettings: Sets up event handlers for creating and closing a Redis rate limiter pool.
        - EnvironmentSettings: Conditionally sets documentation URLs and integrates custom routes for API documentation
          based on the environment type.

    create_tables_on_start : bool
        A flag to indicate whether to create database tables on application startup.
        Defaults to True.

    **kwargs
        Additional keyword arguments passed directly to the FastAPI constructor.

    Returns
    -------
    FastAPI
        A fully configured FastAPI application instance.

    The function configures the FastAPI application with different features and behaviors
    based on the provided settings. It includes setting up database connections, Redis pools
    for caching, queue, and rate limiting, client-side caching, and customizing the API documentation
    based on the environment settings.
    """
    # --- before creating application ---
    if isinstance(settings, AppSettings):
        to_update = {
            "title": settings.APP_NAME,
            "description": settings.APP_DESCRIPTION,
            "contact": {"name": settings.CONTACT_NAME, "email": settings.CONTACT_EMAIL},
            "license_info": {"name": settings.LICENSE_NAME},
        }
        kwargs.update(to_update)

    if isinstance(settings, EnvironmentSettings):
        kwargs.update({"docs_url": None, "redoc_url": None, "openapi_url": None})

    lifespan = lifespan_factory(settings, create_tables_on_start=create_tables_on_start)

    application = FastAPI(
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ],
        exception_handlers={RequestValidationError: validation_exception_handler},
        responses={
            422: {
                "description": "Validation Error",
                "model": ErrorResponse,
            },
        },
        lifespan=lifespan,
        **kwargs,
    )
    application.include_router(router)

    add_pagination(application)
    
    if isinstance(settings, ClientSideCacheSettings):
        application.add_middleware(ClientCacheMiddleware, max_age=settings.CLIENT_CACHE_MAX_AGE)

    if isinstance(settings, EnvironmentSettings):
        if settings.ENVIRONMENT != EnvironmentOption.PRODUCTION:
            docs_router = APIRouter()

            @docs_router.get("/docs", include_in_schema=False)
            async def get_swagger_documentation() -> fastapi.responses.HTMLResponse:
                return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")

            @docs_router.get("/redoc", include_in_schema=False)
            async def get_redoc_documentation() -> fastapi.responses.HTMLResponse:
                return get_redoc_html(openapi_url="/openapi.json", title="docs")

            @docs_router.get("/openapi.json", include_in_schema=False)
            async def openapi() -> dict[str, Any]:
                out: dict = get_openapi(title=application.title, version=application.version, routes=application.routes)
                return out

            application.include_router(docs_router)

        return application
