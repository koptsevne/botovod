from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import gspread

from database import RequestRecord


logger = logging.getLogger(__name__)

HEADERS = [
    "Дата",
    "Тип",
    "Источник",
    "Имя",
    "Услуга",
    "Вопрос",
    "Контакт",
    "Удобное время",
    "Telegram username",
    "Telegram user ID",
]


class SheetsWriter:
    def __init__(self, spreadsheet_id: str | None, credentials_file: Path | None):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_file = credentials_file

    @property
    def enabled(self) -> bool:
        return bool(self.spreadsheet_id and self.credentials_file)

    def _append_sync(self, record: RequestRecord) -> None:
        if not self.enabled or self.credentials_file is None or self.spreadsheet_id is None:
            return
        client = gspread.service_account(filename=str(self.credentials_file))
        sheet = client.open_by_key(self.spreadsheet_id).sheet1
        if not sheet.row_values(1):
            sheet.append_row(HEADERS, value_input_option="RAW")
        data = asdict(record)
        sheet.append_row(
            [
                datetime.now().astimezone().isoformat(timespec="seconds"),
                data["request_type"],
                data["source"],
                data["name"],
                data["service"],
                data["question"],
                data["contact"],
                data["convenient_time"],
                data["telegram_username"],
                data["telegram_user_id"],
            ],
            value_input_option="RAW",
        )

    async def append(self, record: RequestRecord) -> None:
        if not self.enabled:
            return
        try:
            await asyncio.to_thread(self._append_sync, record)
        except Exception:
            logger.exception("Не удалось записать заявку в Google Sheets")
