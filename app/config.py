# Copyright (c) 2024 PJSC VimpelCom
"""Конфигурация chat-session-service."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHAT_", env_file=".env", extra="ignore")

    db_host: str = ""
    db_port: int = 5432
    db_user: str = ""
    db_password: str = ""
    db_name: str = ""

    chat_schema: str = "chat"
    chat_session_table: str = "chat_session"

    chat_memory_schema: str = "public"
    chat_memory_table: str = "n8n_chat_histories"
    chat_memory_session_id_column: str = "session_id"
    chat_memory_message_column: str = "message"
    chat_memory_id_column: str = "id"
    chat_memory_created_at_column: str = "created_at"

    n8n_base_url: str = ""
    n8n_chat_webhook_path: str = ""
    n8n_chat_webhook_url: str = ""
    n8n_webhook_timeout_seconds: float = 10.0
    n8n_ssl_verify: bool = False

    @property
    def resolved_n8n_chat_webhook_url(self) -> str:
        """Полный URL webhook: CHAT_N8N_CHAT_WEBHOOK_URL или base_url + path."""
        full = self.n8n_chat_webhook_url.strip()
        if full:
            return full
        base = self.n8n_base_url.strip().rstrip("/")
        path = self.n8n_chat_webhook_path.strip()
        if not base or not path:
            return ""
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base}{path}"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
