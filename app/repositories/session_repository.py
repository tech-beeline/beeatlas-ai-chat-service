# Copyright (c) 2024 PJSC VimpelCom
"""Репозиторий chat_session."""
import uuid
from typing import Any, Optional

from app.config import settings
from app.db import get_cursor, qualified_table
from app.schemas.session import UNSET

_SESSION_COLUMNS = (
    "id, key, user_id, last_message, status, sum_context, "
    "description, ui_context, created_at, updated_at"
)


class SessionRepository:
    def __init__(self) -> None:
        self._table = qualified_table(settings.chat_schema, settings.chat_session_table)

    def create(
        self, user_id: int, message: str, ui_context: Optional[str] = None
    ) -> dict[str, Any]:
        key = str(uuid.uuid4())
        with get_cursor() as cur:
            return self._insert(cur, key, user_id, message, ui_context)

    def create_in_transaction(
        self, cur, user_id: int, message: str, ui_context: Optional[str] = None
    ) -> dict[str, Any]:
        """INSERT в рамках внешней транзакции (без commit)."""
        key = str(uuid.uuid4())
        return self._insert(cur, key, user_id, message, ui_context)

    def _insert(
        self,
        cur,
        key: str,
        user_id: int,
        message: str,
        ui_context: Optional[str] = None,
    ) -> dict[str, Any]:
        cur.execute(
            f"""
            INSERT INTO {self._table}
                (key, user_id, last_message, status, sum_context, description,
                 ui_context, updated_at)
            VALUES (%s, %s, %s, 'process', NULL, NULL, %s, NULL)
            RETURNING {_SESSION_COLUMNS}
            """,
            (key, user_id, message, ui_context),
        )
        return dict(cur.fetchone())

    def get_by_key(self, session_key: str) -> Optional[dict[str, Any]]:
        with get_cursor() as cur:
            cur.execute(
                f"""
                SELECT {_SESSION_COLUMNS}
                FROM {self._table}
                WHERE key = %s
                """,
                (session_key,),
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def list_by_user_id(self, user_id: int) -> list[dict[str, Any]]:
        with get_cursor() as cur:
            cur.execute(
                f"""
                SELECT {_SESSION_COLUMNS}
                FROM {self._table}
                WHERE user_id = %s
                  AND deleted_date IS NULL
                ORDER BY COALESCE(updated_at, created_at) DESC
                """,
                (user_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def soft_delete(self, session_key: str) -> Optional[dict[str, Any]]:
        """Мягкое удаление: проставить deleted_date, если ещё не заполнен."""
        with get_cursor() as cur:
            cur.execute(
                f"""
                UPDATE {self._table}
                SET deleted_date = now(), updated_at = now()
                WHERE key = %s
                  AND deleted_date IS NULL
                RETURNING {_SESSION_COLUMNS}, deleted_date
                """,
                (session_key,),
            )
            row = cur.fetchone()
            if row is not None:
                return dict(row)

            # Сессия уже удалена или не существует — различим по наличию ключа
            cur.execute(
                f"""
                SELECT {_SESSION_COLUMNS}, deleted_date
                FROM {self._table}
                WHERE key = %s
                """,
                (session_key,),
            )
            existing = cur.fetchone()
        return dict(existing) if existing else None

    def update_message(
        self,
        session_key: str,
        message: str,
        ui_context: Any = UNSET,
    ) -> Optional[dict[str, Any]]:
        fields: list[str] = [
            "last_message = %s",
            "status = 'process'",
            "updated_at = now()",
        ]
        params: list[Any] = [message]

        if ui_context is not UNSET:
            fields.append("ui_context = %s")
            params.append(ui_context)

        params.append(session_key)
        with get_cursor() as cur:
            cur.execute(
                f"""
                UPDATE {self._table}
                SET {", ".join(fields)}
                WHERE key = %s
                RETURNING {_SESSION_COLUMNS}
                """,
                params,
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def update_metadata(
        self,
        session_key: str,
        *,
        sum_context: Any = UNSET,
        description: Any = UNSET,
        status: Any = UNSET,
    ) -> Optional[dict[str, Any]]:
        fields: list[str] = ["updated_at = now()"]
        params: list[Any] = []

        if sum_context is not UNSET:
            fields.append("sum_context = %s")
            params.append(sum_context)
        if description is not UNSET:
            fields.append("description = %s")
            params.append(description)
        if status is not UNSET:
            fields.append("status = %s")
            params.append(status)

        if len(fields) == 1:
            return self.get_by_key(session_key)

        params.append(session_key)
        with get_cursor() as cur:
            cur.execute(
                f"""
                UPDATE {self._table}
                SET {", ".join(fields)}
                WHERE key = %s
                RETURNING {_SESSION_COLUMNS}
                """,
                params,
            )
            row = cur.fetchone()
        return dict(row) if row else None
