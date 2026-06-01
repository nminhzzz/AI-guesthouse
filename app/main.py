from contextlib import asynccontextmanager
from importlib import import_module
from typing import Iterator

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text

from app.common.exceptions.exception_handlers import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.mysql.init_db import init_db
from app.mysql.session import engine
from app.mongodb.database import connect_mongo
from app.cache.redis_client import redis_client


def get_route_modules() -> list[str]:
    return [
        "app.routes.auth_route",
        "app.routes.room_route",
        "app.routes.user_route",
        "app.routes.chat_route",
        "app.routes.ai_route",
    ]


def iter_routers() -> Iterator[APIRouter]:
    for module_path in get_route_modules():
        module = import_module(module_path)
        router = getattr(module, "router", None)
        if isinstance(router, APIRouter):
            yield router


def connect_mysql() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def connect_redis() -> None:
    redis_client.ping()


@asynccontextmanager
async def lifespan(_: FastAPI):
    connect_mysql()
    init_db()
    await connect_mongo()
    connect_redis()
    print("App started")
    yield
    print("App stopped")


app = FastAPI(
    title="AI Guesthouse API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    return {"message": "AI Guesthouse API is running"}


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


for api_router in iter_routers():
    app.include_router(api_router)