# Telegram-бот поддержки сайта

Бот принимает посетителей по ссылке `https://t.me/USERNAME_BOT?start=site`, показывает inline-меню, пошагово собирает заявки, сохраняет их в SQLite и отправляет администратору. Google Sheets можно подключить дополнительно.

В каждом уведомлении администратор получает готовую команду `/reply USER_ID текст`. Отправленная в чат поддержки команда доставит пользователю ответ от имени бота — публичный username посетителя для этого не нужен.

## Быстрый запуск

1. Создайте бота у [@BotFather](https://t.me/BotFather), сохраните токен и username.
2. Узнайте ID личного аккаунта или чата поддержки. Для группового чата добавьте туда бота и выдайте право отправлять сообщения.
3. В терминале из папки проекта выполните:

   ```bash
   cd bot
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

4. Заполните `bot/.env`:

   ```dotenv
   BOT_TOKEN=токен_от_BotFather
   ADMIN_CHAT_ID=123456789
   SITE_URL=https://ваш-сайт.ru
   BOT_USERNAME=username_бота_без_собаки
   ```

5. В `site-config.js` укажите тот же username без `@`:

   ```js
   window.SITE_CONFIG = { telegramBotUsername: "username_bot" };
   ```

6. Запустите бота:

   ```bash
   python app.py
   ```

Для постоянной работы разверните процесс на VPS или PaaS и запустите `python app.py` через systemd, Docker либо менеджер процессов. Токен нужен только окружению бота — в HTML и JavaScript его добавлять нельзя.

## Что и где менять

- `content.json` — услуги, цены, текст обучения, контакты и рабочие часы.
- `.env` — токен, ID администратора, адрес сайта, часовой пояс, лимиты и интеграции.
- `site-config.js` — публичный username бота для кнопки сайта.

После изменения `content.json` или `.env` перезапустите процесс бота.

## База данных

SQLite создаётся автоматически в `bot/data/support_bot.sqlite3`. Таблица `requests` содержит:

| Поле | Назначение |
|---|---|
| `id` | Номер заявки |
| `request_type` | `booking`, `question`, `price_question` или `operator` |
| `source` | `site` для deep-link с сайта, иначе `telegram` |
| `name` | Имя пользователя |
| `service` | Выбранная услуга |
| `question` | Описание ситуации или вопрос |
| `contact` | Telegram username или телефон |
| `convenient_time` | Удобное время для ответа |
| `telegram_username` | Username пользователя |
| `telegram_user_id` | Telegram ID пользователя |
| `created_at` | Дата создания в UTC |

## Google Sheets — необязательно

1. Создайте проект и service account в Google Cloud, включите Google Sheets API.
2. Скачайте JSON-ключ в `bot/service-account.json`.
3. Создайте таблицу и дайте email service account права редактора.
4. Заполните в `.env`:

   ```dotenv
   GOOGLE_SHEETS_ID=id_из_адреса_таблицы
   GOOGLE_CREDENTIALS_FILE=service-account.json
   ```

Первая строка с заголовками создаётся автоматически. Если Google Sheets временно недоступен, заявка всё равно остаётся в SQLite и отправляется администратору.

## Готовая кнопка для другого сайта

```html
<a href="https://t.me/USERNAME_BOT?start=site" target="_blank" rel="noopener">
  Написать в Telegram
</a>
```

Параметр `start=site` сохраняется в заявке как источник `site`.

## Проверка перед публикацией

1. Откройте именно ссылку с `?start=site` и нажмите Start.
2. Пройдите «Записаться» до конца и проверьте сообщение администратора.
3. Проверьте строку в SQLite и, если подключено, в Google Sheets.
4. Проверьте «Задать вопрос» и «Связаться с оператором».
5. Выполните предложенную команду `/reply`, чтобы проверить ответ живого оператора.
6. Временно измените рабочие часы в `content.json`, чтобы проверить автоответ вне графика.
