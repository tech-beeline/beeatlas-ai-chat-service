# Copyright (c) 2024 PJSC VimpelCom
"""Вызов webhook n8n."""
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class N8nWebhookError(Exception):
    """Ошибка при вызове webhook n8n."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def call_chat_workflow(
    session_key: str, *, ui_context: Optional[str] = None
) -> None:

    url = settings.resolved_n8n_chat_webhook_url
    if not url:
        raise N8nWebhookError(
            "n8n chat webhook is not configured "
            "(set CHAT_N8N_BASE_URL + CHAT_N8N_CHAT_WEBHOOK_PATH or CHAT_N8N_CHAT_WEBHOOK_URL)"
        )

    payload = {"key": session_key, "uiContext": ui_context}
    try:
        with httpx.Client(
            timeout=settings.n8n_webhook_timeout_seconds,
            verify=settings.n8n_ssl_verify,
        ) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500] if exc.response is not None else ""
        logger.error(
            "n8n chat workflow returned HTTP %s for session_key=%s: %s",
            exc.response.status_code if exc.response else "?",
            session_key,
            body,
        )
        raise N8nWebhookError(
            f"n8n returned HTTP {exc.response.status_code}: {body or exc.response.reason_phrase}",
            status_code=exc.response.status_code,
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception(
            "Failed to call n8n chat workflow for session_key=%s",
            session_key,
        )
        raise N8nWebhookError(f"failed to call n8n: {exc}") from exc


def trigger_chat_workflow(
    session_key: str, *, ui_context: Optional[str] = None
) -> None:
    """Fire-and-forget POST на webhook (для PATCH /message). Ошибки только в лог."""
    try:
        call_chat_workflow(session_key, ui_context=ui_context)
    except N8nWebhookError as exc:
        logger.error(
            "Background n8n chat workflow failed for session_key=%s: %s",
            session_key,
            exc,
        )
