# Скилл: Выгрузка Яндекс.Вебмастер

## Описание
Выгружает популярные запросы, страницы в поиске (индексацию) и внешние ссылки из Яндекс.Вебмастера в многостраничный Excel.

## 🎥 Видео-инструкция
[Смотреть видео-разбор урока](https://activate.infoprotector.com/online/?url=protection.infoprotector.com/file/5f5a570f-7783-427d-b448-d425af918c37/selcdn)

## Установка
```bash
pip install requests pandas openpyxl
```

## Как получить OAuth-токен (один раз)

Токен даёт скиллу доступ к API Вебмастера. Нужен аккаунт Яндекса, под которым **сайт уже добавлен и подтверждён** в webmaster.yandex.ru.

### Шаг 1. Зарегистрируй приложение
1. Открой [oauth.yandex.ru/client/new](https://oauth.yandex.ru/client/new)
2. Название — любое; платформа — **«Веб-сервисы»**
3. Redirect URI: `https://oauth.yandex.ru/verification_code`
4. **Доступы:** в поле «Название доступа» начни печатать `вебмастер` и выбери **`webmaster:hostinfo`** (просмотр информации о сайтах). Диск/Директ — не трогай.
5. Создай приложение → получишь **ClientID**.

### Шаг 2. Получи токен (быстрый способ)
Открой в браузере (подставь свой ClientID):
```
https://oauth.yandex.ru/authorize?response_type=token&client_id=ТВОЙ_CLIENT_ID
```
Разреши доступ — в адресной строке появится `#access_token=y0_...`. Скопируй значение `access_token`.

### Шаг 3. Узнай user_id (нужен для всех запросов)
```bash
curl -H "Authorization: OAuth ТВОЙ_ТОКЕН" https://api.webmaster.yandex.net/v4/user/
```
В ответе `{"user_id": 1234567}` — это число понадобится дальше.

### Шаг 4. Сохрани в конфиг
В `configs/webmaster/.env` (в Git не коммитим!):
```
YANDEX_WEBMASTER_TOKEN=y0_твой_токен
YANDEX_WEBMASTER_USER_ID=1234567
```

## Запуск
```bash
# Мок-режим (заглушки, без API)
python run.py --host-id https:example.com:443

# Реальный API (токен и user_id берутся из configs/webmaster/.env)
python run.py --host-id https:example.com:443 --real

# Ограничить число строк (для быстрой проверки)
python run.py --host-id https:example.com:443 --real --limit 20
```

`host-id` смотри в кабинете Вебмастера, формат `https:домен:443`.

## Выход
`data/webmaster/webmaster.xlsx` — 3 листа:
- **Запросы** — query_text, impressions, clicks, position
- **Индексация** — url, title, last_access, status
- **Ссылки** — source_url, target_url, discovery_date

## Структура
- `run.py` — оркестратор (читает конфиг, вызывает клиент и экспортёр)
- `webmaster_client.py` — запросы к API (в скелете — мок-режим)
- `exporter.py` — сохранение в многостраничный Excel
