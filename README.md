# Сайт таролога

Единая папка проекта: сайт и Telegram-бот теперь лежат вместе.

## Структура

- `index.html` — главная страница сайта.
- `style.css` — стили сайта.
- `script.js` — скрипты сайта.
- `site-config.js` — настройки сайта, включая ссылку на Telegram-бота.
- `assets/` — изображения и другие ресурсы сайта.
- `bot-service/` — рабочий Telegram-бот.

## Запуск бота

```bash
cd "/Users/nikkling/Documents/taro_can/проект-сайта-таролога/bot-service"
.venv/bin/python3 bot/app.py
```

Если виртуальное окружение нужно пересоздать:

```bash
cd "/Users/nikkling/Documents/taro_can/проект-сайта-таролога/bot-service"
python3 -m venv .venv
source .venv/bin/activate
pip install -r bot/requirements.txt
python3 bot/app.py
```

## Важно

Файл `bot-service/bot/.env` содержит локальные секреты бота. Его нельзя загружать в GitHub.

