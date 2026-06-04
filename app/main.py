import logging
import logging.config
from contextlib import asynccontextmanager
from importlib import import_module
from typing import Iterator

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.common.exceptions.exception_handlers import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.config import settings
from app.mysql.init_db import init_db
from app.mysql.database import engine
from app.mongodb.database import connect_mongo
from app.cache.redis_client import redis_client


# ======================================
# LOGGING
# ======================================

LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "level": "DEBUG" if settings.DEBUG else "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "uvicorn.access": {"level": "INFO"},
        "sqlalchemy.engine": {"level": "WARNING"},
        "motor": {"level": "WARNING"},
        "passlib": {"level": "WARNING"},
        "python_multipart": {"level": "WARNING"},
        "urllib3": {"level": "WARNING"},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


# ======================================
# ROUTES
# ======================================

def get_route_modules() -> list[str]:
    return [
        "app.routes.auth_route",
        "app.routes.room_route",
        "app.routes.user_route",
        "app.routes.notification_route",
        # Uncomment when implemented:
        # "app.routes.chat_route",
        # "app.routes.ai_route",
    ]


def iter_routers() -> Iterator[APIRouter]:
    for module_path in get_route_modules():
        module = import_module(module_path)
        router = getattr(module, "router", None)
        if isinstance(router, APIRouter):
            yield router


# ======================================
# STARTUP / SHUTDOWN
# ======================================

def connect_mysql() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    logger.info("MySQL connected")


def connect_redis() -> None:
    redis_client.ping()
    logger.info("Redis connected")


@asynccontextmanager
async def lifespan(_: FastAPI):
    connect_mysql()
    init_db()
    await connect_mongo()
    connect_redis()
    logger.info("App started | env=%s debug=%s", settings.APP_ENV, settings.DEBUG)
    yield
    logger.info("App stopped")


# ======================================
# APP
# ======================================

app = FastAPI(
    title="AI Guesthouse API",
    version="1.0.0",
    lifespan=lifespan,
    # Hide docs in production
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# ======================================
# CORS
# ======================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,       # required for cookie-based auth
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-CSRF-Token"],
)

# ======================================
# EXCEPTION HANDLERS
# ======================================

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


# ======================================
# HEALTH
# ======================================

@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    return {"message": "AI Guesthouse API is running"}


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


# ======================================
# REGISTER ROUTERS
# ======================================

for api_router in iter_routers():
    app.include_router(api_router)
