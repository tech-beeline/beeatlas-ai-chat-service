# Copyright (c) 2024 PJSC VimpelCom
"""API v1 — управление чат-сессиями."""
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.repositories.history_repository import HistoryRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.session import (
    ChatHistoryItem,
    CreateSessionRequest,
    SessionKeyResponse,
    SessionMetadataUpdate,
    SessionResponse,
    SessionStatus,
    UNSET,
    UpdateMessageRequest,
)
from app.services.n8n_webhook import N8nWebhookError, trigger_chat_workflow
from app.services.session_service import create_session as create_session_with_n8n
from app.services.session_service import delete_session as delete_session_soft

router = APIRouter(prefix="/api/v1", tags=["sessions"])

_session_repo = SessionRepository()
_history_repo = HistoryRepository()


def _to_session_response(row: dict) -> SessionResponse:
    return SessionResponse.model_validate(row)


@router.post("/session", response_model=SessionKeyResponse, status_code=status.HTTP_201_CREATED)
def create_session(body: CreateSessionRequest) -> SessionKeyResponse:
    try:
        row = create_session_with_n8n(
            user_id=body.user_id,
            message=body.message,
            ui_context=body.ui_context,
        )
    except N8nWebhookError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return SessionKeyResponse(key=row["key"], status=row["status"])


@router.get("/session/{session_key}", response_model=SessionResponse)
def get_session(session_key: str) -> SessionResponse:
    row = _session_repo.get_by_key(session_key)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _to_session_response(row)


@router.get("/user/{user_id}/sessions", response_model=list[SessionResponse])
def list_user_sessions(user_id: int) -> list[SessionResponse]:
    rows = _session_repo.list_by_user_id(user_id)
    return [_to_session_response(row) for row in rows]


@router.delete("/session/{session_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_key: str) -> None:
    """Мягкое удаление сессии: проставляет deleted_date, если ещё не заполнен."""
    row = delete_session_soft(session_key)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


@router.get("/session/{session_key}/history", response_model=list[ChatHistoryItem])
def get_session_history(session_key: str) -> list[ChatHistoryItem]:
    if _session_repo.get_by_key(session_key) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    rows = _history_repo.list_by_session_key(session_key)
    return [ChatHistoryItem.model_validate(row) for row in rows]


@router.patch("/session/{session_key}/metadata", response_model=SessionResponse)
def update_session_metadata(session_key: str, body: SessionMetadataUpdate) -> SessionResponse:
    if body.status is not UNSET:
        if body.status not in SessionStatus.__args__:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Не верный статус",
            )
        new_status = body.status
    else:
        new_status = UNSET

    sum_context = body.sum_context if body.sum_context is not UNSET else UNSET
    description = body.description if body.description is not UNSET else UNSET

    if sum_context is UNSET and description is UNSET and new_status is UNSET:
        row = _session_repo.get_by_key(session_key)
    else:
        row = _session_repo.update_metadata(
            session_key,
            sum_context=sum_context,
            description=description,
            status=new_status,
        )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _to_session_response(row)


@router.patch("/session/{session_key}/message", response_model=SessionKeyResponse)
def update_session_message(
    session_key: str,
    body: UpdateMessageRequest,
    background_tasks: BackgroundTasks,
) -> SessionKeyResponse:
    existing = _session_repo.get_by_key(session_key)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if existing["status"] == "process":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is still processing; wait until status is ready",
        )

    row = _session_repo.update_message(
        session_key, body.message, ui_context=body.ui_context
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    background_tasks.add_task(
        trigger_chat_workflow,
        row["key"],
        ui_context=row.get("ui_context"),
    )
    return SessionKeyResponse(key=row["key"], status=row["status"])
