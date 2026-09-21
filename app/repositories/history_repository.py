# Copyright (c) 2024 PJSC VimpelCom
"""Чтение истории диалога из таблицы n8n Postgres Chat Memory."""
import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

from app.config import settings
from app.db import get_cursor, qualified_table, quote_ident


class HistoryRepository:
    def __init__(self) -> None:
        self._table = qualified_table(settings.chat_memory_schema, settings.chat_memory_table)
        self._session_col = quote_ident(settings.chat_memory_session_id_column)
        self._message_col = quote_ident(settings.chat_memory_message_column)
        self._id_col = quote_ident(settings.chat_memory_id_column)
        self._created_col = (
            quote_ident(settings.chat_memory_created_at_column)
            if settings.chat_memory_created_at_column
            else None
        )

    def list_by_session_key(self, session_key: str) -> list[dict[str, Any]]:
        created_select = f", {self._created_col} AS created_at" if self._created_col else ""
        order_by = (
            f"{self._created_col} ASC, {self._id_col} ASC"
            if self._created_col
            else f"{self._id_col} ASC"
        )
        with get_cursor() as cur:
            cur.execute(
                f"""
                SELECT {self._message_col} AS message{created_select}
                FROM {self._table}
                WHERE {self._session_col} = %s
                ORDER BY {order_by}
                """,
                (session_key,),
            )
            rows = cur.fetchall()

        history: list[dict[str, Any]] = []
        for row in rows:
            parsed = self._parse_message_row(row)
            if parsed:
                history.append(parsed)
        return history

    def _parse_message_row(self, row: dict[str, Any]) -> Optional[dict[str, Any]]:
        raw_message = row.get("message")
        if raw_message is None:
            logger.warning("parse_message_row: raw_message is None")
            return None

        if isinstance(raw_message, str):
            try:
                payload = json.loads(raw_message)
            except json.JSONDecodeError:
                logger.warning("parse_message_row: JSONDecodeError for raw_message=%s", raw_message[:200])
                return None
        elif isinstance(raw_message, dict):
            payload = raw_message
        else:
            logger.warning("parse_message_row: unexpected type %s", type(raw_message))
            return None

        role = self._map_role(payload)
        content = self._extract_content(payload)
        if not role:
            logger.warning(
                "parse_message_row: unmapped role, type=%s, role=%s",
                payload.get("type"),
                payload.get("role"),
            )
            return None

        created_at = row.get("created_at")
        if isinstance(created_at, datetime):
            created = created_at
        else:
            created = None

        return {"role": role, "content": content, "created_at": created}

    @staticmethod
    def _map_role(payload: dict[str, Any]) -> Optional[str]:
        msg_type = str(payload.get("type", "")).lower()
        if msg_type in {"human", "user"}:
            return "user"
        if msg_type in {"ai", "assistant", "tool"}:
            return "assistant"
        role = str(payload.get("role", "")).lower()
        if role in {"user", "human"}:
            return "user"
        if role in {"assistant", "ai"}:
            return "assistant"
        return None

    @staticmethod
    def _extract_content(payload: dict[str, Any]) -> str:
        content = payload.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if text:
                        parts.append(str(text))
                elif item:
                    parts.append(str(item))
            return "\n".join(parts)
        return str(content) if content is not None else ""
