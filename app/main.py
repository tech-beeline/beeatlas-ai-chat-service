# Copyright (c) 2024 PJSC VimpelCom
"""chat-session-service — административный сервис сессий чат-бота BeeAtlas."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.sessions import router as sessions_router
from app.config import settings
from app.db import init_schema

logger = logging.getLogger(__name__)


def _read_tech_version() -> str:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "TECH_VERSION")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip() or "unknown"
    except OSError:
        return "unknown"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    init_schema()
    if not settings.resolved_n8n_chat_webhook_url:
        logger.warning(
            "n8n chat webhook is not configured "
            "(set CHAT_N8N_BASE_URL + CHAT_N8N_CHAT_WEBHOOK_PATH or CHAT_N8N_CHAT_WEBHOOK_URL)"
        )
    yield


app = FastAPI(
    title="AI Chat Session Service",
    description="Административный сервис пользовательских чат-сессий BeeAtlas",
    version=_read_tech_version(),
    lifespan=lifespan,
)

app.include_router(sessions_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0]
    msg = first_error.get("msg", "Ошибка валидации")
    # Pydantic добавляет префикс "Value error, " к сообщениям из ValueError
    if msg.startswith("Value error, "):
        msg = msg.removeprefix("Value error, ")
    return JSONResponse(
        status_code=422,
        content={"detail": msg},
    )


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": _read_tech_version()}


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "service": "ai-chat-service",
        "docs": "/docs",
        "health": "/health",
    }
