from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _markup(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(text, data) for text, data in row]
            for row in rows
        ]
    )


def main_menu() -> InlineKeyboardMarkup:
    return _markup(
        [
            [("✦ Выбрать услугу", "services"), ("☾ Смотреть прайс", "prices")],
            [("♡ Оставить заявку", "booking"), ("💬 Задать вопрос", "question")],
            [("𖤓 Обучение", "topic:training")],
            [("👩‍💼 Связаться со специалистом", "operator")],
            [("❔ Помощь", "help"), ("☎️ Контакты", "contacts")],
        ]
    )


def topics_menu(topics: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for topic in topics:
        rows.append([(topic["title"], f"topic:{topic['id']}")])
    rows.append([("☾ Прайс", "prices"), ("💬 Вопрос специалисту", "operator")])
    rows.append([("← Назад в меню", "menu")])
    return _markup(rows)


def service_card_menu(topic_id: str, position: int, total: int, service_id: str) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = [[("♡ Выбрать и записаться", f"select:{service_id}")]]
    navigation: list[tuple[str, str]] = []
    if total > 1:
        previous_position = (position - 1) % total
        next_position = (position + 1) % total
        navigation.append(("← Предыдущая", f"card:{topic_id}:{previous_position}"))
        navigation.append(("Следующая →", f"card:{topic_id}:{next_position}"))
    if navigation:
        rows.append(navigation)
    rows.append([("Все темы", "services"), ("☾ Прайс", "prices")])
    rows.append([("💬 Задать вопрос", "question"), ("← Меню", "menu")])
    return _markup(rows)


def selected_service_menu() -> InlineKeyboardMarkup:
    return _markup(
        [
            [("♡ Оформить заявку", "booking_selected")],
            [("Выбрать другую", "services"), ("💬 Задать вопрос", "question")],
            [("← Назад в меню", "menu")],
        ]
    )


def services_menu() -> InlineKeyboardMarkup:
    return _markup(
        [
            [("Выбрать по карточкам", "services"), ("Показать прайс", "prices")],
            [("Оставить заявку", "booking"), ("Задать вопрос", "question")],
            [("← Назад в меню", "menu")],
        ]
    )


def prices_menu() -> InlineKeyboardMarkup:
    return _markup(
        [
            [("✦ Выбрать услугу", "services"), ("♡ Оставить заявку", "booking")],
            [("Уточнить цену", "price_question")],
            [("← Назад в меню", "menu")],
        ]
    )


def booking_topic_menu(topics: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for index, topic in enumerate(topics):
        rows.append([(topic, f"booking_topic:{index}")])
    rows.append([("← Назад в меню", "menu")])
    return _markup(rows)


def contact_method_menu() -> InlineKeyboardMarkup:
    return _markup(
        [
            [("Использовать мой Telegram", "contact_method:account")],
            [("Telegram username", "contact_method:telegram")],
            [("Телефон", "contact_method:phone")],
            [("Написать вручную", "contact_method:manual")],
            [("← Назад в меню", "menu")],
        ]
    )


def time_menu() -> InlineKeyboardMarkup:
    return _markup(
        [
            [("Сегодня", "time:Сегодня"), ("Завтра", "time:Завтра")],
            [("В ближайшее время", "time:В ближайшее время")],
            [("Указать своё время", "time:manual")],
            [("← Назад в меню", "menu")],
        ]
    )


def confirm_menu() -> InlineKeyboardMarkup:
    return _markup(
        [
            [("✅ Да, отправить", "confirm_booking")],
            [("Изменить", "booking_selected"), ("Отменить", "menu")],
        ]
    )


def back_menu() -> InlineKeyboardMarkup:
    return _markup([[("← Назад в меню", "menu")]])


def training_menu() -> InlineKeyboardMarkup:
    return _markup(
        [
            [("Выбрать обучение", "topic:training"), ("💬 Задать вопрос", "question")],
            [("← Назад в меню", "menu")],
        ]
    )


def help_menu() -> InlineKeyboardMarkup:
    return _markup(
        [
            [("✦ Выбрать услугу", "services"), ("☾ Прайс", "prices")],
            [("♡ Оставить заявку", "booking")],
            [("👩‍💼 Связаться со специалистом", "operator")],
            [("← Назад в меню", "menu")],
        ]
    )
