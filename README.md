# ai-chat-service

Административный сервис пользовательских чат-сессий BeeAtlas (ADR-0016, гибрид n8n + chat-session-service).

Архитектура: [`documentation/visions/chat/ARCHITECTURE.md`](../documentation/visions/chat/ARCHITECTURE.md)

## Возможности

- CRUD метаданных сессий (`chat.chat_session`)
- Асинхронный запуск n8n workflow «beeatlas chat»
- API истории диалога из таблицы n8n Postgres Chat Memory
- Swagger UI: `/docs`

## API

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/session` | Создать сессию, запустить workflow |
| GET | `/api/v1/session/{key}` | Метаданные сессии (polling) |
| GET | `/api/v1/user/{userId}/sessions` | Список сессий пользователя (без soft-deleted) |
| DELETE | `/api/v1/session/{key}` | Мягкое удаление сессии (`deleted_date`) |
| GET | `/api/v1/session/{key}/history` | История Q/A |
| PATCH | `/api/v1/session/{key}/metadata` | Обновить sumContext/description/status (n8n) |
| PATCH | `/api/v1/session/{key}/message` | Новое сообщение, запуск workflow |

## Локальный запуск

```bash
cd ai-chat-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактировать .env
uvicorn app.main:app --reload --port 8080
```

Swagger: http://localhost:8080/docs

## Переменные окружения

Префикс `CHAT_`. Полный список — в [`.env.example`](.env.example).

| Переменная | Описание |
|------------|----------|
| `CHAT_DB_*` | Подключение к PostgreSQL |
| `CHAT_CHAT_SCHEMA` | Схема сессий (по умолчанию `chat`) |
| `CHAT_CHAT_SESSION_TABLE` | Таблица сессий |
| `CHAT_CHAT_MEMORY_*` | Таблица и колонки n8n chat memory |
| `CHAT_N8N_BASE_URL` | Базовый адрес инстанса n8n |
| `CHAT_N8N_CHAT_WEBHOOK_PATH` | Путь webhook workflow «beeatlas chat» |
| `CHAT_N8N_CHAT_WEBHOOK_URL` | Полный URL webhook (опционально, приоритет над base + path) |
| `CHAT_N8N_SSL_VERIFY` | Проверка TLS-сертификата n8n (`false` по умолчанию) |

## Docker

```bash
docker build -t ai-chat-service .
docker run --rm -p 8080:8080 --env-file .env ai-chat-service
```

## Health

`GET /health` → `{"status": "ok", "version": "..."}`
