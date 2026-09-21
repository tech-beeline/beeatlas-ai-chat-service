# Copyright (c) 2024 PJSC VimpelCom
"""Бизнес-логика сессий."""
from typing import Any, Optional

from app.db import transaction
from app.repositories.session_repository import SessionRepository
from app.services.n8n_webhook import call_chat_workflow

_session_repo = SessionRepository()


def create_session(
    user_id: int, message: str, ui_context: Optional[str] = None
) -> dict[str, Any]:
    """
    Создать сессию и вызвать n8n в одной транзакции.
    При ошибке n8n транзакция откатывается — запись в БД не сохраняется.
    """
    with transaction() as cur:
        row = _session_repo.create_in_transaction(
            cur, user_id, message, ui_context=ui_context
        )
        call_chat_workflow(row["key"], ui_context=ui_context)
        return row


def delete_session(session_key: str) -> Optional[dict[str, Any]]:
    """
    Мягкое удаление сессии по ключу.
    Если deleted_date пустой — проставляется текущие дата и время.
    Если сессия уже удалена — возвращается существующая запись без изменений.
    Если ключ не найден — None.
    """
    return _session_repo.soft_delete(session_key)
