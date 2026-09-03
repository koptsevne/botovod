from __future__ import annotations

import html
import json
import logging
import os
import sqlite3
import ssl
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, time as clock_time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent
CONTENT_PATH = BASE_DIR / "content.json"
ENV_PATH = BASE_DIR / ".env"

logger = logging.getLogger(__name__)
user_states: dict[int, dict[str, Any]] = {}
rate_events: dict[int, deque[float]] = defaultdict(deque)
last_warning: dict[int, float] = {}
ssl_context: ssl.SSLContext | None = None


@dataclass
class Settings:
    bot_token: str
    admin_chat_id: int
    site_url: str
    bot_username: str
    database_path: Path
    timezone: str
    rate_limit_messages: int
    rate_limit_seconds: int


def load_env() -> dict[str, str]:
    values = dict(os.environ)
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", maxsplit=1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings() -> Settings:
    env = load_env()
    token = env.get("BOT_TOKEN", "").strip()
    admin_chat_id = env.get("ADMIN_CHAT_ID", "").strip()
    if not token:
        raise RuntimeError("Укажите BOT_TOKEN в bot/.env")
    if not admin_chat_id or not admin_chat_id.lstrip("-").isdigit():
        raise RuntimeError("Укажите ADMIN_CHAT_ID в bot/.env")
    return Settings(
        bot_token=token,
        admin_chat_id=int(admin_chat_id),
        site_url=env.get("SITE_URL", "").strip(),
        bot_username=env.get("BOT_USERNAME", "").strip(),
        database_path=Path(env.get("DATABASE_PATH", BASE_DIR / "data" / "support_bot.sqlite3")),
        timezone=env.get("TIMEZONE", "Asia/Yekaterinburg"),
        rate_limit_messages=int(env.get("RATE_LIMIT_MESSAGES", "20")),
        rate_limit_seconds=int(env.get("RATE_LIMIT_SECONDS", "60")),
    )


def load_content() -> dict[str, Any]:
    return json.loads(CONTENT_PATH.read_text(encoding="utf-8"))


def api_url(settings: Settings, method: str) -> str:
    return f"https://api.telegram.org/bot{settings.bot_token}/{method}"


def api_call(settings: Settings, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global ssl_context
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        api_url(settings, method),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    if ssl_context is None:
        try:
            import certifi

            ssl_context = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ssl_context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=35, context=ssl_context) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API error {exc.code}: {body}") from exc
    if not result.get("ok"):
        raise RuntimeError(str(result))
    return result


def safe(value: Any) -> str:
    return html.escape(str(value or "—"))


def button(text: str, callback_data: str) -> dict[str, str]:
    return {"text": text, "callback_data": callback_data}


def markup(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": [[button(text, data) for text, data in row] for row in rows if row]}


def user_label(user: dict[str, Any]) -> str:
    return " ".join(part for part in [user.get("first_name"), user.get("last_name")] if part).strip()


def username(user: dict[str, Any]) -> str:
    return f"@{user['username']}" if user.get("username") else ""


def services(content: dict[str, Any]) -> list[dict[str, Any]]:
    return list(content.get("services", []))


def topics(content: dict[str, Any]) -> list[dict[str, Any]]:
    return list(content.get("topics", []))


def service_by_id(content: dict[str, Any], service_id: str) -> dict[str, Any] | None:
    for service in services(content):
        if service.get("id") == service_id:
            return service
    return None


def topic_by_id(content: dict[str, Any], topic_id: str) -> dict[str, Any] | None:
    for topic in topics(content):
        if topic.get("id") == topic_id:
            return topic
    return None


def selected_service_from_state(state: dict[str, Any]) -> bool:
    return bool(state.get("service"))


def topic_icon(topic_id: str) -> str:
    icons = {
        "relationships": "❤️",
        "work_money": "💼",
        "personal": "🌙",
        "energy": "🧿",
        "rituals": "🔮",
        "training": "🃏",
        "choose_help": "✨",
    }
    return icons.get(topic_id, "🔮")


def service_icon(service_id: str) -> str:
    icons = {
        "tarot_one_question": "🃏",
        "love_spread": "❤️",
        "compatibility": "❤️",
        "work_money_spread": "💼",
        "diagnostics": "🔮",
        "full_review": "✨",
        "personal_consultation": "🌙",
        "negative_diagnostics": "🧿",
        "energy_cleaning": "🧿",
        "protection": "🧿",
        "ritual_work": "🔮",
        "tarot_basic_training": "🃏",
        "individual_training": "🔮",
        "service_choice": "✨",
    }
    return icons.get(service_id, "🔮")

def main_menu() -> dict[str, Any]:
    return markup(
        [
            [("🔮 Выбрать услугу", "services"), ("🃏 Прайс", "prices")],
            [("✨ Оставить заявку", "booking"), ("🌙 Задать вопрос", "question")],
            [("💫 Связаться со специалистом", "operator")],
            [("🧿 Помощь", "help"), ("☎️ Контакты", "contacts")],
        ]
    )

def topics_menu(content: dict[str, Any]) -> dict[str, Any]:
    rows = [[(f"{topic_icon(topic['id'])} {topic['title']}", f"topic:{topic['id']}")] for topic in topics(content)]
    rows.append([("🃏 Прайс", "prices"), ("💫 Вопрос специалисту", "operator")])
    rows.append([("← В меню", "menu")])
    return markup(rows)

def empty_topic_menu() -> dict[str, Any]:
    return markup(
        [
            [("🌙 Задать вопрос", "question")],
            [("🔮 Все темы", "services"), ("← В меню", "menu")],
        ]
    )

def service_card_menu(topic_id: str, position: int, total: int, service_id: str) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = []
    if service_id:
        rows.append([("✨ Выбрать и записаться", f"select:{service_id}")])
    if total > 1:
        rows.append(
            [
                ("← Предыдущая", f"card:{topic_id}:{(position - 1) % total}"),
                ("Следующая →", f"card:{topic_id}:{(position + 1) % total}"),
            ]
        )
    rows.append([("🔮 Все темы", "services"), ("🃏 Прайс", "prices")])
    rows.append([("🌙 Задать вопрос", "question"), ("← В меню", "menu")])
    return markup(rows)

def selected_service_menu() -> dict[str, Any]:
    return markup(
        [
            [("✨ Оформить заявку", "booking_selected")],
            [("🔮 Выбрать другую", "services"), ("🌙 Задать вопрос", "question")],
            [("← В меню", "menu")],
        ]
    )

def prices_menu(state: dict[str, Any]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = [[("🔮 Выбрать услугу", "services")]]
    if selected_service_from_state(state):
        rows[0].append(("✨ Оставить заявку", "booking_selected"))
    rows.append([("🧿 Уточнить цену", "price_question")])
    rows.append([("← В меню", "menu")])
    return markup(rows)

def help_menu() -> dict[str, Any]:
    return markup(
        [
            [("🔮 Выбрать услугу", "services"), ("🃏 Прайс", "prices")],
            [("💫 Вопрос специалисту", "operator")],
            [("☎️ Контакты", "contacts"), ("← В меню", "menu")],
        ]
    )

def contacts_menu() -> dict[str, Any]:
    return markup(
        [
            [("🔮 Услуги", "services"), ("🌙 Вопрос", "question")],
            [("← В меню", "menu")],
        ]
    )

def booking_topic_menu(content: dict[str, Any]) -> dict[str, Any]:
    icons = ["❤️", "💼", "🌙", "🧿", "🃏", "✨"]
    rows = [[(f"{icons[index] if index < len(icons) else '🔮'} {topic}", f"booking_topic:{index}")] for index, topic in enumerate(content.get("booking_topics", []))]
    rows.append([("✕ Отменить", "menu")])
    return markup(rows)

def contact_method_menu() -> dict[str, Any]:
    return markup(
        [
            [("👤 Использовать мой Telegram", "contact_method:account")],
            [("🌙 Telegram username", "contact_method:telegram"), ("☎️ Телефон", "contact_method:phone")],
            [("✦ Написать вручную", "contact_method:manual")],
            [("✕ Отменить", "menu")],
        ]
    )

def time_menu() -> dict[str, Any]:
    return markup(
        [
            [("🌙 Сегодня", "time:Сегодня"), ("✨ Завтра", "time:Завтра")],
            [("💫 В ближайшее время", "time:В ближайшее время")],
            [("✦ Указать своё время", "time:manual")],
            [("✕ Отменить", "menu")],
        ]
    )

def confirm_menu() -> dict[str, Any]:
    return markup(
        [
            [("✓ Отправить специалисту", "confirm_booking")],
            [("✦ Изменить заявку", "booking_selected"), ("✕ Отменить", "menu")],
        ]
    )

def inactive_step_menu() -> dict[str, Any]:
    return markup([[("← Открыть меню", "menu")]])

def main_menu_text(user: dict[str, Any] | None = None) -> str:
    name = safe((user or {}).get("first_name") or "рада вас видеть")
    return (
        f"🌙 <b>Пространство Таро</b>\n\n"
        f"{name}, выберите, с чем хотите обратиться сегодня.\n\n"
        "✦ Услуги и прайс доступны по карточкам.\n"
        "✦ Если вопрос сложный, я передам его специалисту."
    )

def topics_text() -> str:
    return (
        "🔮 <b>Выберите направление</b>\n\n"
        "О чём вы хотите спросить карты?\n\n"
        "✦ Я покажу только подходящие карточки услуг."
    )

def not_found_text(kind: str = "card") -> str:
    if kind == "topic":
        return "⚠️ <b>Эта тема больше недоступна</b>\n\nВернитесь к направлениям и выберите другой раздел."
    return "⚠️ <b>Эта карточка больше недоступна</b>\n\nВернитесь к направлениям и выберите услугу заново."

def service_card_text(content: dict[str, Any], topic_id: str, position: int) -> tuple[str, str, int, int, str]:
    topic = topic_by_id(content, topic_id)
    if not topic:
        return not_found_text("topic"), "", 0, 0, "not_found"
    service_ids = [service_id for service_id in topic.get("services", []) if service_by_id(content, service_id)]
    if not service_ids:
        return (
            f"{topic_icon(topic_id)} <b>{safe(topic.get('title'))}</b>\n\n"
            "По этому направлению пока нет карточек. Можно задать вопрос специалисту или вернуться ко всем темам.",
            "",
            0,
            0,
            "empty",
        )
    total = len(service_ids)
    position %= total
    service_id = service_ids[position]
    service = service_by_id(content, service_id) or {}
    icon = service_icon(service_id)
    text = (
        f"{icon} <b>{safe(service.get('name'))}</b>\n"
        f"Карточка {position + 1} из {total} · {safe(topic.get('title'))}\n\n"
        f"{safe(service.get('description'))}\n\n"
        f"💎 <b>Стоимость</b>\n{safe(service.get('price'))}\n\n"
        "🧿 Если формат откликается, можно сразу оформить заявку."
    )
    return text, str(service.get("id")), position, total, "ok"

def selected_service_text(service: dict[str, Any]) -> str:
    icon = service_icon(str(service.get("id", "")))
    return (
        f"{icon} <b>Услуга выбрана</b>\n\n"
        f"✦ <b>{safe(service.get('name'))}</b>\n"
        f"💎 {safe(service.get('price'))}\n\n"
        "Можно оформить заявку, выбрать другой формат или задать уточняющий вопрос."
    )

def prices_text(content: dict[str, Any]) -> str:
    lines = ["🃏 <b>Прайс</b>", "", "Актуальные форматы и стоимость:", ""]
    for index, item in enumerate(services(content), start=1):
        icon = service_icon(str(item.get("id", "")))
        lines.append(f"{index}. {icon} <b>{safe(item['name'])}</b>")
        lines.append(f"💎 {safe(item.get('price', 'уточняется'))}")
        lines.append(safe(item.get("description", "")))
        lines.append("")
    lines.append("🧿 Если не знаете, что выбрать, откройте карточки услуг — там проще сориентироваться.")
    return "\n".join(lines).strip()

def contacts_text(settings: Settings, content: dict[str, Any]) -> str:
    contacts = content.get("contacts", {})
    telegram = contacts.get("telegram_label") or "не указан"
    telegram_url = contacts.get("telegram_url") or ""
    instagram = contacts.get("instagram_label") or "не указан"
    instagram_url = contacts.get("instagram_url") or ""
    telegram_text = f'<a href="{safe(telegram_url)}">{safe(telegram)}</a>' if telegram_url else safe(telegram)
    instagram_text = f'<a href="{safe(instagram_url)}">{safe(instagram)}</a>' if instagram_url else safe(instagram)
    site_text = f'<a href="{safe(settings.site_url)}">{safe(settings.site_url)}</a>' if settings.site_url else "не указан"
    return (
        "🌙 <b>Контакты</b>\n\n"
        f"✦ Telegram: {telegram_text}\n"
        f"✦ Instagram: {instagram_text}\n"
        f"✦ Телефон: {safe(contacts.get('phone'))}\n"
        f"✦ Сайт: {site_text}\n"
        f"✦ График: {safe(contacts.get('work_hours'))}"
    )

def faq_text(content: dict[str, Any]) -> str:
    lines = [
        "🧿 <b>Помощь</b>",
        "",
        "Кнопки ведут по сценариям, чтобы не приходилось искать нужный раздел вручную.",
        "",
    ]
    for item in content.get("faq_items", []):
        lines.append(f"✦ <b>{safe(item.get('question'))}</b>")
        lines.append(safe(item.get("answer")))
        lines.append("")
    lines.append("💫 Если вопрос личный или сложный, передайте его специалисту.")
    return "\n".join(lines).strip()

def chosen_service_line(state: dict[str, Any]) -> str:
    if not state.get("service"):
        return ""
    return f"\n\n🔮 Выбранная услуга: <b>{safe(state.get('service'))}</b>"

def booking_step_text(step: str, state: dict[str, Any], error: str = "") -> str:
    error_block = f"\n\n⚠️ {safe(error)}" if error else ""
    if step == "booking_name":
        return (
            "✨ <b>Шаг 1 из 5 — Имя</b>"
            f"{chosen_service_line(state)}\n\n"
            "Как к вам можно обращаться?\n"
            "Напишите имя одним сообщением."
            f"{error_block}"
        )
    if step == "booking_topic":
        return (
            "🔮 <b>Шаг 2 из 5 — Тема</b>"
            f"{chosen_service_line(state)}\n\n"
            "Выберите направление вопроса кнопкой или напишите свой вариант."
            f"{error_block}"
        )
    if step == "booking_description":
        return (
            "🌙 <b>Шаг 3 из 5 — Ситуация</b>"
            f"{chosen_service_line(state)}\n\n"
            "Кратко опишите ситуацию одним сообщением. Можно без лишних деталей — специалист уточнит, если потребуется."
            f"{error_block}"
        )
    if step == "booking_contact":
        return (
            "👤 <b>Шаг 4 из 5 — Контакт</b>\n\n"
            "Выберите удобный способ связи или напишите контакт вручную."
            f"{error_block}"
        )
    if step == "booking_time":
        return (
            "💫 <b>Шаг 5 из 5 — Время</b>\n\n"
            "Когда вам удобнее получить ответ?"
            f"{error_block}"
        )
    return "✨ <b>Заявка</b>\n\nПродолжим заполнение."

def booking_summary(state: dict[str, Any]) -> str:
    return (
        "✨ <b>Проверьте заявку</b>\n\n"
        f"✦ Имя: {safe(state.get('name'))}\n"
        f"✦ Услуга: {safe(state.get('service'))}\n"
        f"✦ Тема: {safe(state.get('topic'))}\n"
        f"✦ Вопрос: {safe(state.get('description'))}\n"
        f"✦ Контакт: {safe(state.get('contact'))}\n"
        f"✦ Удобное время: {safe(state.get('convenient_time'))}\n\n"
        "✓ Если всё верно, отправлю специалисту."
    )

def success_text(request_id: int, content: dict[str, Any], settings: Settings, kind: str = "booking") -> str:
    if kind == "question":
        base = f"✓ <b>Вопрос получен</b>\n\nНомер обращения: {request_id}\n💫 Передам специалисту, если потребуется уточнение."
    elif kind == "operator":
        base = f"✓ <b>Запрос передан специалисту</b>\n\nНомер обращения: {request_id}\nПожалуйста, ожидайте ответа в Telegram."
    else:
        base = f"✓ <b>Заявка принята</b>\n\nНомер заявки: {request_id}\n💫 Информация передана специалисту, с вами свяжутся в ближайшее время."
    return base + after_hours_suffix(content, settings)

def error_text(kind: str = "generic") -> str:
    if kind == "admin_delivery":
        return "⚠️ <b>Данные сохранены</b>\n\nУведомление специалисту временно не доставлено, но заявка не потеряна."
    if kind == "inactive_step":
        return "⚠️ <b>Этот шаг уже не активен</b>\n\nОткройте меню и выберите нужный раздел заново."
    return "✕ Не получилось выполнить действие. Пожалуйста, вернитесь в меню и попробуйте ещё раз."

def cancel_text() -> str:
    return "✕ Заполнение отменено.\n\nВыберите нужный раздел:"

def is_working_time(content: dict[str, Any], settings: Settings) -> bool:
    hours = content.get("working_hours", {})
    try:
        now = datetime.now(ZoneInfo(settings.timezone))
        start = clock_time.fromisoformat(hours.get("start", "10:00"))
        end = clock_time.fromisoformat(hours.get("end", "19:00"))
        weekdays = hours.get("weekdays", [0, 1, 2, 3, 4])
        return now.weekday() in weekdays and start <= now.time().replace(tzinfo=None) < end
    except Exception:
        return True


def after_hours_suffix(content: dict[str, Any], settings: Settings) -> str:
    if is_working_time(content, settings):
        return ""
    return (
        "\n\nСпасибо за сообщение.\n"
        "Сейчас специалист может быть не онлайн, но ваша заявка сохранена. "
        "Мы ответим в ближайшее рабочее время."
    )


def send_message(settings: Settings, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None, disable_web_page_preview: bool = True) -> None:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    api_call(settings, "sendMessage", payload)


def edit_message_text(
    settings: Settings,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: dict[str, Any] | None = None,
    disable_web_page_preview: bool = True,
) -> bool:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        api_call(settings, "editMessageText", payload)
        return True
    except Exception as exc:
        if "message is not modified" not in str(exc).lower():
            logger.info("Не удалось отредактировать сообщение, отправляю новое: %s", exc)
        return False


def edit_message_reply_markup(settings: Settings, chat_id: int, message_id: int, reply_markup: dict[str, Any] | None = None) -> bool:
    payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        api_call(settings, "editMessageReplyMarkup", payload)
        return True
    except Exception:
        logger.exception("Не удалось обновить кнопки сообщения")
        return False


def show_screen(settings: Settings, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None, message_id: int | None = None) -> None:
    if message_id is not None and edit_message_text(settings, chat_id, message_id, text, reply_markup):
        return
    send_message(settings, chat_id, text, reply_markup)


def answer_callback(settings: Settings, callback_id: str, text: str = "") -> None:
    try:
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        api_call(settings, "answerCallbackQuery", payload)
    except Exception:
        logger.exception("Не удалось ответить на callback")


def init_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
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


def save_request(settings: Settings, data: dict[str, Any]) -> int:
    fields = {
        "request_type": data.get("request_type", ""),
        "source": data.get("source", "telegram"),
        "name": data.get("name", ""),
        "service": data.get("service", ""),
        "question": data.get("question", ""),
        "contact": data.get("contact", ""),
        "convenient_time": data.get("convenient_time", ""),
        "telegram_username": data.get("telegram_username", ""),
        "telegram_user_id": data.get("telegram_user_id", 0),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with sqlite3.connect(settings.database_path) as connection:
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


def source_label(source: str) -> str:
    return "Telegram-бот сайта" if source == "site" else "Telegram-бот"


def state_for(user_id: int) -> dict[str, Any]:
    return user_states.setdefault(user_id, {"source": "telegram", "step": ""})


def reset_state(user_id: int, source: str = "telegram") -> dict[str, Any]:
    user_states[user_id] = {"source": source, "step": ""}
    return user_states[user_id]


def is_rate_limited(settings: Settings, user_id: int) -> bool:
    now = time.monotonic()
    history = rate_events[user_id]
    while history and now - history[0] > settings.rate_limit_seconds:
        history.popleft()
    if len(history) >= settings.rate_limit_messages:
        return True
    history.append(now)
    return False


def notify_rate_limit(settings: Settings, chat_id: int, user_id: int) -> None:
    now = time.monotonic()
    if now - last_warning.get(user_id, 0) > settings.rate_limit_seconds:
        last_warning[user_id] = now
        send_message(settings, chat_id, "Сообщения приходят слишком часто. Пожалуйста, подождите несколько секунд.")


def send_admin(settings: Settings, text: str) -> bool:
    try:
        send_message(settings, settings.admin_chat_id, text)
        return True
    except Exception:
        logger.exception("Не удалось отправить уведомление администратору")
        return False


def show_card(settings: Settings, content: dict[str, Any], chat_id: int, topic_id: str, position: int, message_id: int | None = None) -> None:
    text, service_id, position, total, status = service_card_text(content, topic_id, position)
    if status == "empty":
        show_screen(settings, chat_id, text, empty_topic_menu(), message_id)
        return
    if status == "not_found":
        show_screen(settings, chat_id, text, markup([[("Все темы", "services"), ("← В меню", "menu")]]), message_id)
        return
    show_screen(settings, chat_id, text, service_card_menu(topic_id, position, total, service_id), message_id)


def start_booking(settings: Settings, content: dict[str, Any], chat_id: int, user_id: int, message_id: int | None = None) -> None:
    state = state_for(user_id)
    if not state.get("service"):
        show_screen(
            settings,
            chat_id,
            "🔮 <b>Сначала выберите услугу</b>\n\nТак заявка будет заполнена аккуратнее, а специалист сразу увидит нужный формат.",
            topics_menu(content),
            message_id,
        )
        return
    state["step"] = "booking_name"
    send_message(settings, chat_id, booking_step_text("booking_name", state))


def send_booking(settings: Settings, content: dict[str, Any], chat_id: int, user: dict[str, Any], state: dict[str, Any], message_id: int | None = None) -> None:
    if message_id is not None:
        show_screen(settings, chat_id, "💫 Отправляю заявку специалисту…", None, message_id)
    else:
        send_message(settings, chat_id, "💫 Отправляю заявку специалисту…")

    source = state.get("source", "telegram")
    tg_username = username(user)
    user_id = user["id"]
    request_id = save_request(
        settings,
        {
            "request_type": "booking",
            "source": source,
            "name": state.get("name", ""),
            "service": state.get("service", ""),
            "question": f"Тема: {state.get('topic', '—')}\n\n{state.get('description', '')}",
            "contact": state.get("contact", ""),
            "convenient_time": state.get("convenient_time", ""),
            "telegram_username": tg_username,
            "telegram_user_id": user_id,
        },
    )
    admin_text = (
        "<b>Новая заявка с сайта</b>\n\n"
        f"Номер: {request_id}\n"
        f"Источник: {safe(source_label(source))}\n"
        f"Имя: {safe(state.get('name'))}\n"
        f"Услуга: {safe(state.get('service'))}\n"
        f"Тема: {safe(state.get('topic'))}\n"
        f"Вопрос: {safe(state.get('description'))}\n"
        f"Контакт: {safe(state.get('contact'))}\n"
        f"Удобное время: {safe(state.get('convenient_time'))}\n"
        f'Telegram пользователя: {safe(tg_username) if tg_username else "—"} '
        f'(<a href="tg://user?id={user_id}">ID {user_id}</a>)\n\n'
        f"Ответить: <code>/reply {user_id} текст</code>"
    )
    delivered = send_admin(settings, admin_text)
    reset_state(user_id, source)
    text = success_text(request_id, content, settings, "booking") if delivered else error_text("admin_delivery")
    send_message(settings, chat_id, text, main_menu())


def handle_start(settings: Settings, content: dict[str, Any], message: dict[str, Any], args: str = "") -> None:
    user = message.get("from", {})
    source = "site" if args.strip() == "site" else "telegram"
    reset_state(user["id"], source)
    send_message(settings, message["chat"]["id"], main_menu_text(user), main_menu())


def handle_menu(settings: Settings, chat_id: int, user_id: int, user: dict[str, Any] | None = None, message_id: int | None = None) -> None:
    source = state_for(user_id).get("source", "telegram")
    reset_state(user_id, source)
    show_screen(settings, chat_id, main_menu_text(user), main_menu(), message_id)


def inactive_step(settings: Settings, chat_id: int, message_id: int | None = None) -> None:
    show_screen(settings, chat_id, error_text("inactive_step"), inactive_step_menu(), message_id)


def handle_callback(settings: Settings, content: dict[str, Any], callback: dict[str, Any]) -> None:
    data = callback.get("data", "")
    message = callback.get("message", {})
    user = callback.get("from", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    user_id = user.get("id")
    if not chat_id or not user_id:
        return

    answer_callback(settings, callback["id"])
    state = state_for(user_id)

    if data == "menu":
        handle_menu(settings, chat_id, user_id, user, message_id)
    elif data == "help":
        state["step"] = ""
        show_screen(settings, chat_id, faq_text(content), help_menu(), message_id)
    elif data == "services":
        state["step"] = ""
        show_screen(settings, chat_id, topics_text(), topics_menu(content), message_id)
    elif data.startswith("topic:"):
        state["step"] = ""
        show_card(settings, content, chat_id, data.split(":", maxsplit=1)[1], 0, message_id)
    elif data.startswith("card:"):
        try:
            _, topic_id, position = data.split(":", maxsplit=2)
            show_card(settings, content, chat_id, topic_id, int(position), message_id)
        except Exception:
            show_screen(settings, chat_id, not_found_text(), markup([[("Все темы", "services"), ("← В меню", "menu")]]), message_id)
    elif data.startswith("select:"):
        service = service_by_id(content, data.split(":", maxsplit=1)[1])
        if not service:
            show_screen(settings, chat_id, not_found_text(), markup([[("Все темы", "services"), ("← В меню", "menu")]]), message_id)
            return
        state.update({"service": service.get("name", ""), "service_price": service.get("price", ""), "step": ""})
        show_screen(settings, chat_id, selected_service_text(service), selected_service_menu(), message_id)
    elif data == "prices":
        state["step"] = ""
        show_screen(settings, chat_id, prices_text(content), prices_menu(state), message_id)
    elif data == "contacts":
        state["step"] = ""
        show_screen(settings, chat_id, contacts_text(settings, content), contacts_menu(), message_id)
    elif data in {"booking", "booking_selected"}:
        start_booking(settings, content, chat_id, user_id, message_id if data == "booking" and not state.get("service") else None)
    elif data.startswith("booking_topic:"):
        if state.get("step") != "booking_topic":
            inactive_step(settings, chat_id, message_id)
            return
        topic_options = content.get("booking_topics", [])
        try:
            topic = topic_options[int(data.split(":", maxsplit=1)[1])]
        except Exception:
            topic = "Другое"
        state.update({"topic": topic, "step": "booking_description"})
        send_message(settings, chat_id, booking_step_text("booking_description", state))
    elif data.startswith("contact_method:"):
        if state.get("step") != "booking_contact":
            inactive_step(settings, chat_id, message_id)
            return
        method = data.split(":", maxsplit=1)[1]
        if method == "account":
            contact = username(user) or f"Telegram ID {user_id}"
            state.update({"contact": contact, "step": "booking_time"})
            show_screen(settings, chat_id, booking_step_text("booking_time", state), time_menu(), message_id)
            return
        prompts = {
            "telegram": "Отправьте ваш Telegram username, например @username.",
            "phone": "Отправьте номер телефона.",
            "manual": "Напишите удобный контакт для связи.",
        }
        state.update({"contact_method": method})
        send_message(settings, chat_id, f"<b>Шаг 4 из 5 — Контакт</b>\n\n{prompts.get(method, prompts['manual'])}\n\nДля отмены используйте /cancel")
    elif data.startswith("time:"):
        if state.get("step") != "booking_time":
            inactive_step(settings, chat_id, message_id)
            return
        value = data.split(":", maxsplit=1)[1]
        if value == "manual":
            send_message(settings, chat_id, "<b>Шаг 5 из 5 — Время</b>\n\nНапишите удобное время одним сообщением.\n\nДля отмены используйте /cancel")
            return
        state.update({"convenient_time": value, "step": "booking_confirm"})
        show_screen(settings, chat_id, booking_summary(state), confirm_menu(), message_id)
    elif data == "confirm_booking":
        if state.get("step") != "booking_confirm":
            inactive_step(settings, chat_id, message_id)
            return
        send_booking(settings, content, chat_id, user, state, message_id)
    elif data in {"question", "price_question"}:
        state.update({"step": "question", "question_context": "price" if data == "price_question" else "general"})
        send_message(
            settings,
            chat_id,
            "🌙 <b>Вопрос специалисту</b>\n\nНапишите вопрос одним сообщением. Я передам его специалисту или помогу сориентироваться, если вопрос простой.\n\nДля отмены используйте /cancel",
        )
    elif data == "operator":
        state["step"] = "operator"
        send_message(
            settings,
            chat_id,
            "💫 <b>Связь со специалистом</b>\n\nНапишите одним сообщением, по какому вопросу нужна помощь.\n\nДля отмены используйте /cancel"
            + after_hours_suffix(content, settings),
        )
    else:
        show_screen(settings, chat_id, "<b>Эта кнопка больше не активна</b>\n\nОткройте меню и выберите нужный раздел заново.", inactive_step_menu(), message_id)


def handle_text(settings: Settings, content: dict[str, Any], message: dict[str, Any]) -> None:
    chat_id = message["chat"]["id"]
    user = message.get("from", {})
    user_id = user.get("id", chat_id)
    text = (message.get("text") or "").strip()

    if is_rate_limited(settings, user_id):
        notify_rate_limit(settings, chat_id, user_id)
        return

    if text.startswith("/start"):
        args = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""
        handle_start(settings, content, message, args)
        return
    if text == "/help":
        send_message(settings, chat_id, faq_text(content), help_menu())
        return
    if text == "/cancel":
        source = state_for(user_id).get("source", "telegram")
        reset_state(user_id, source)
        send_message(settings, chat_id, cancel_text(), main_menu())
        return
    if text.startswith("/reply") and chat_id == settings.admin_chat_id:
        parts = text.split(maxsplit=2)
        if len(parts) != 3 or not parts[1].lstrip("-").isdigit():
            send_message(settings, chat_id, "Формат ответа: <code>/reply USER_ID текст сообщения</code>")
            return
        api_call(settings, "sendMessage", {"chat_id": int(parts[1]), "text": "<b>Ответ специалиста</b>\n\n" + safe(parts[2]), "parse_mode": "HTML", "reply_markup": main_menu()})
        send_message(settings, chat_id, f"Ответ отправлен пользователю {parts[1]}.")
        return

    state = state_for(user_id)
    step = state.get("step")
    state["last_text"] = text[:2000]

    if step == "booking_name":
        if not text or len(text) > 100:
            send_message(settings, chat_id, booking_step_text("booking_name", state, "Имя должно быть от 1 до 100 символов."))
            return
        state.update({"name": text, "step": "booking_topic"})
        send_message(settings, chat_id, booking_step_text("booking_topic", state), booking_topic_menu(content))
    elif step == "booking_topic":
        if not text or len(text) > 200:
            send_message(settings, chat_id, booking_step_text("booking_topic", state, "Тема должна быть от 1 до 200 символов."), booking_topic_menu(content))
            return
        state.update({"topic": text, "step": "booking_description"})
        send_message(settings, chat_id, booking_step_text("booking_description", state))
    elif step == "booking_description":
        if not text or len(text) > 2000:
            send_message(settings, chat_id, booking_step_text("booking_description", state, "Описание должно быть от 1 до 2000 символов."))
            return
        state.update({"description": text, "step": "booking_contact"})
        send_message(settings, chat_id, booking_step_text("booking_contact", state), contact_method_menu())
    elif step == "booking_contact":
        if not text or len(text) > 200:
            send_message(settings, chat_id, booking_step_text("booking_contact", state, "Контакт должен быть от 1 до 200 символов."), contact_method_menu())
            return
        state.update({"contact": text, "step": "booking_time"})
        send_message(settings, chat_id, booking_step_text("booking_time", state), time_menu())
    elif step == "booking_time":
        if not text or len(text) > 200:
            send_message(settings, chat_id, booking_step_text("booking_time", state, "Время должно быть от 1 до 200 символов."), time_menu())
            return
        state.update({"convenient_time": text, "step": "booking_confirm"})
        send_message(settings, chat_id, booking_summary(state), confirm_menu())
    elif step == "question":
        if not text or len(text) > 2000:
            send_message(settings, chat_id, "Вопрос должен быть текстом от 1 до 2000 символов. Напишите его одним сообщением.")
            return
        source = state.get("source", "telegram")
        selected_service = state.get("service", "")
        kind = "price_question" if state.get("question_context") == "price" else "question"
        request_id = save_request(
            settings,
            {
                "request_type": kind,
                "source": source,
                "service": selected_service,
                "question": f"Услуга: {selected_service}\n\n{text}" if selected_service else text,
                "telegram_username": username(user),
                "telegram_user_id": user_id,
            },
        )
        admin_text = (
            f"<b>{'Уточнение стоимости' if kind == 'price_question' else 'Новый вопрос'}</b>\n\n"
            f"Номер: {request_id}\n"
            f"Источник: {safe(source_label(source))}\n"
            f"Услуга: {safe(selected_service)}\n"
            f"Вопрос: {safe(text)}\n"
            f"Пользователь: {safe(username(user)) if username(user) else '—'} "
            f'(<a href="tg://user?id={user_id}">ID {user_id}</a>)\n\n'
            f"Ответить: <code>/reply {user_id} текст</code>"
        )
        delivered = send_admin(settings, admin_text)
        reset_state(user_id, source)
        reply = success_text(request_id, content, settings, "question") if delivered else error_text("admin_delivery")
        send_message(settings, chat_id, reply, main_menu())
    elif step == "operator":
        if not text or len(text) > 2000:
            send_message(settings, chat_id, "Сообщение должно быть от 1 до 2000 символов. Опишите вопрос одним сообщением.")
            return
        source = state.get("source", "telegram")
        request_id = save_request(
            settings,
            {
                "request_type": "operator",
                "source": source,
                "name": user_label(user) or username(user) or str(user_id),
                "service": state.get("service", ""),
                "question": text,
                "telegram_username": username(user),
                "telegram_user_id": user_id,
            },
        )
        admin_text = (
            "<b>Пользователь просит связаться со специалистом.</b>\n\n"
            f"Номер: {request_id}\n"
            f"Имя/username: {safe(user_label(user))} / {safe(username(user))}\n"
            f"Источник: {'сайт / Telegram-бот' if source == 'site' else 'Telegram-бот'}\n"
            f"Услуга: {safe(state.get('service'))}\n"
            f"Сообщение: {safe(text)}\n"
            f'<a href="tg://user?id={user_id}">Открыть профиль по ID {user_id}</a>\n\n'
            f"Ответить: <code>/reply {user_id} текст</code>"
        )
        delivered = send_admin(settings, admin_text)
        reset_state(user_id, source)
        reply = success_text(request_id, content, settings, "operator") if delivered else error_text("admin_delivery")
        send_message(settings, chat_id, reply, main_menu())
    else:
        send_message(
            settings,
            chat_id,
            "Я помогаю по вопросам сайта, услуг, записи, прайса и связи со специалистом. Выберите раздел в меню — так будет проще не потеряться.",
            main_menu(),
        )


def handle_update(settings: Settings, content: dict[str, Any], update: dict[str, Any]) -> None:
    if "message" in update:
        handle_text(settings, content, update["message"])
    elif "callback_query" in update:
        handle_callback(settings, content, update["callback_query"])


def set_commands(settings: Settings) -> None:
    api_call(
        settings,
        "setMyCommands",
        {
            "commands": [
                {"command": "start", "description": "Открыть главное меню"},
                {"command": "help", "description": "Помощь по боту"},
                {"command": "cancel", "description": "Отменить заполнение"},
            ]
        },
    )


def main() -> None:
    settings = load_settings()
    content = load_content()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    init_database(settings.database_path)
    try:
        api_call(settings, "deleteWebhook", {"drop_pending_updates": False})
    except Exception:
        logger.warning("Не удалось удалить webhook при запуске. Продолжаю запуск через getUpdates.", exc_info=True)
    try:
        set_commands(settings)
    except Exception:
        logger.warning("Не удалось обновить команды меню при запуске. Бот продолжит работу.", exc_info=True)
    offset = 0
    logger.info("Бот запущен: @%s", settings.bot_username or "username не указан")
    while True:
        try:
            result = api_call(settings, "getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message", "callback_query"]})
            for update in result.get("result", []):
                offset = update["update_id"] + 1
                handle_update(settings, content, update)
        except KeyboardInterrupt:
            raise
        except Exception:
            logger.exception("Ошибка обработки обновлений")
            time.sleep(3)


if __name__ == "__main__":
    main()
