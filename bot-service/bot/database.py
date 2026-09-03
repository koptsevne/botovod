from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RequestRecord:
    request_type: str
    source: str
    name: str = ""
    service: str = ""
    question: str = ""
    contact: str = ""
    convenient_time: str = ""
    telegram_username: str = ""
    telegram_user_id: int = 0


class Database:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    service TEXT NOT NULL DEFAULT '',
                    question TEXT NOT NULL DEFAULT '',
                    contact TEXT NOT NULL DEFAULT '',
                    convenient_time TEXT NOT NULL DEFAULT '',
                    telegram_username TEXT NOT NULL DEFAULT '',
                    telegram_user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _save_sync(self, record: RequestRecord) -> int:
        fields = asdict(record)
        fields["created_at"] = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO requests (
                    request_type, source, name, service, question, contact,
                    convenient_time, telegram_username, telegram_user_id, created_at
                ) VALUES (
                    :request_type, :source, :name, :service, :question, :contact,
                    :convenient_time, :telegram_username, :telegram_user_id, :created_at
                )
                """,
                fields,
            )
            return int(cursor.lastrowid)

    async def save(self, record: RequestRecord) -> int:
        return await asyncio.to_thread(self._save_sync, record)
