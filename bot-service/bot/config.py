from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_chat_id: int
    site_url: str
    bot_username: str
    database_path: Path
    google_sheets_id: str | None
    google_credentials_file: Path | None
    timezone: str
    rate_limit_messages: int
    rate_limit_seconds: int
    log_level: str


def _path_from_env(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def load_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("BOT_TOKEN", "").strip()
    admin_id = os.getenv("ADMIN_CHAT_ID", "").strip()
    if not token or token.startswith("1234567890:"):
        raise RuntimeError("Укажите BOT_TOKEN в bot/.env")
    if not admin_id:
        raise RuntimeError("Укажите ADMIN_CHAT_ID в bot/.env")

    credentials = os.getenv("GOOGLE_CREDENTIALS_FILE", "").strip()
    return Settings(
        bot_token=token,
        admin_chat_id=int(admin_id),
        site_url=os.getenv("SITE_URL", "").strip(),
        bot_username=os.getenv("BOT_USERNAME", "").strip().lstrip("@"),
        database_path=_path_from_env(os.getenv("DATABASE_PATH", "data/support_bot.sqlite3")),
        google_sheets_id=os.getenv("GOOGLE_SHEETS_ID", "").strip() or None,
        google_credentials_file=_path_from_env(credentials) if credentials else None,
        timezone=os.getenv("TIMEZONE", "Asia/Yekaterinburg").strip(),
        rate_limit_messages=max(1, int(os.getenv("RATE_LIMIT_MESSAGES", "8"))),
        rate_limit_seconds=max(1, int(os.getenv("RATE_LIMIT_SECONDS", "10"))),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


def load_content() -> dict[str, Any]:
    with (BASE_DIR / "content.json").open(encoding="utf-8") as file:
        content = json.load(file)
    if not content.get("services"):
        raise RuntimeError("Добавьте хотя бы одну услугу в bot/content.json")
    return content
