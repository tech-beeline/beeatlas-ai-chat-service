# Copyright (c) 2024 PJSC VimpelCom
"""Подключение к PostgreSQL и инициализация схемы."""
import logging
import re
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import settings

logger = logging.getLogger(__name__)

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def quote_ident(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'


def qualified_table(schema: str, table: str) -> str:
    return f"{quote_ident(schema)}.{quote_ident(table)}"


def _table_exists(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cur.fetchone() is not None


def _column_exists(cur, schema: str, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        """,
        (schema, table, column),
    )
    return cur.fetchone() is not None


def _ensure_chat_memory_created_at(cur) -> None:
    """Если таблица n8n chat memory уже есть — добавить created_at с DEFAULT now()."""
    column = settings.chat_memory_created_at_column
    if not column:
        return

    schema = settings.chat_memory_schema
    table = settings.chat_memory_table

    if not _table_exists(cur, schema, table):
        logger.info(
            "Chat memory table %s.%s not found — skip created_at migration",
            schema,
            table,
        )
        return

    if _column_exists(cur, schema, table, column):
        return

    mem_table = qualified_table(schema, table)
    col = quote_ident(column)
    cur.execute(
        f"""
        ALTER TABLE {mem_table}
        ADD COLUMN {col} TIMESTAMPTZ DEFAULT now()
        """
    )
    logger.info(
        "Added column %s to %s.%s (DEFAULT now())",
        column,
        schema,
        table,
    )


def _ensure_session_deleted_date(cur) -> None:
    """Добавить deleted_date в существующую таблицу сессий (мягкое удаление)."""
    schema = settings.chat_schema
    table = settings.chat_session_table

    if not _table_exists(cur, schema, table):
        return

    if _column_exists(cur, schema, table, "deleted_date"):
        return

    session_table = qualified_table(schema, table)
    cur.execute(
        f"""
        ALTER TABLE {session_table}
        ADD COLUMN deleted_date TIMESTAMPTZ
        """
    )
    logger.info("Added column deleted_date to %s.%s", schema, table)


def _ensure_session_ui_context(cur) -> None:
    """Добавить ui_context в существующую таблицу сессий."""
    schema = settings.chat_schema
    table = settings.chat_session_table

    if not _table_exists(cur, schema, table):
        return

    if _column_exists(cur, schema, table, "ui_context"):
        return

    session_table = qualified_table(schema, table)
    cur.execute(
        f"""
        ALTER TABLE {session_table}
        ADD COLUMN ui_context TEXT
        """
    )
    logger.info("Added column ui_context to %s.%s", schema, table)


def _ensure_session_updated_at_nullable(cur) -> None:
    """Разрешить updated_at = NULL (при создании сессии ещё не было обновлений)."""
    schema = settings.chat_schema
    table = settings.chat_session_table

    if not _table_exists(cur, schema, table):
        return

    cur.execute(
        """
        SELECT is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = 'updated_at'
        """,
        (schema, table),
    )
    row = cur.fetchone()
    if row is None:
        return

    is_nullable = row["is_nullable"] if isinstance(row, dict) else row[0]
    column_default = row["column_default"] if isinstance(row, dict) else row[1]
    if is_nullable == "YES" and column_default is None:
        return

    session_table = qualified_table(schema, table)
    cur.execute(
        f"""
        ALTER TABLE {session_table}
        ALTER COLUMN updated_at DROP NOT NULL,
        ALTER COLUMN updated_at DROP DEFAULT
        """
    )
    logger.info("Made column updated_at nullable on %s.%s", schema, table)


def init_schema() -> None:
    session_table = qualified_table(settings.chat_schema, settings.chat_session_table)
    with get_cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_ident(settings.chat_schema)}")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {session_table} (
                id           BIGSERIAL PRIMARY KEY,
                key          TEXT NOT NULL UNIQUE,
                user_id      INT NOT NULL,
                last_message TEXT,
                status       TEXT NOT NULL DEFAULT 'process',
                sum_context  TEXT,
                description  TEXT,
                ui_context   TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ,
                deleted_date TIMESTAMPTZ
            )
            """
        )
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{settings.chat_session_table}_user_id
            ON {session_table} (user_id)
            """
        )
        _ensure_session_deleted_date(cur)
        _ensure_session_ui_context(cur)
        _ensure_session_updated_at_nullable(cur)
        _ensure_chat_memory_created_at(cur)


def get_connection():
    return psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        dbname=settings.db_name,
    )


@contextmanager
def get_cursor():
    conn = get_connection()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def transaction():
    """Транзакция: commit при успешном выходе из блока, rollback при исключении."""
    conn = get_connection()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
