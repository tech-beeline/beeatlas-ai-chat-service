# Copyright (c) 2024 PJSC VimpelCom
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SessionStatus = Literal["process", "ready", "error"]


class _Unset:
    """Сентинел для отличия «поле не передано» от «передано null»."""
    pass


UNSET = _Unset()


class CreateSessionRequest(BaseModel):
    user_id: int = Field(alias="userId")
    message: str
    ui_context: Optional[str] = Field(default=None, alias="uiContext")

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)


class UpdateMessageRequest(BaseModel):
    message: str
    ui_context: Any = Field(default=UNSET, alias="uiContext")

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    @field_validator("ui_context", mode="before")
    @classmethod
    def reject_non_string_ui_context(cls, v: Any) -> Any:
        if v is UNSET or v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Ошибка типа данных в поле uiContext")
        return v


class SessionMetadataUpdate(BaseModel):
    sum_context: Any = Field(default=UNSET, alias="sumContext")
    description: Any = Field(default=UNSET)
    status: Any = Field(default=UNSET)

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True, coerce_numbers_to_str=False)

    @field_validator("sum_context", "description", mode="before")
    @classmethod
    def reject_non_string(cls, v: Any, info: Any) -> Any:
        if v is None:
            return None
        if not isinstance(v, str):
            field_name = info.field_name
            alias = SessionMetadataUpdate.model_fields[field_name].alias or field_name
            raise ValueError(f"Ошибка типа данных в поле {alias}")
        return v

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: Any) -> Any:
        if v is None:
            raise ValueError("status не может быть null")
        if not isinstance(v, str):
            raise ValueError("Ошибка типа данных в поле status")
        return v


class SessionKeyResponse(BaseModel):
    key: str
    status: SessionStatus


class SessionResponse(BaseModel):
    key: str
    user_id: int = Field(serialization_alias="userId")
    last_message: Optional[str] = Field(default=None, serialization_alias="lastMessage")
    status: SessionStatus
    sum_context: Optional[str] = Field(default=None, serialization_alias="sumContext")
    description: Optional[str] = None
    ui_context: Optional[str] = Field(default=None, serialization_alias="uiContext")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, serialization_alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True, ser_json_by_alias=True)


class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: Optional[datetime] = Field(default=None, serialization_alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)
