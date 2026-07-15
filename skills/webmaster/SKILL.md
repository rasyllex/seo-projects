# Скилл: Выгрузка Яндекс.Вебмастер

## Назначение
Выгружает данные из Яндекс.Вебмастера: популярные запросы, страницы в поиске (индексацию), внешние ссылки.

## Архитектура
- `run.py` — оркестратор. Читает токен и user_id из `configs/webmaster/.env`, вызывает клиент и экспортёр.
- `webmaster_client.py` — запросы к API Вебмастера через requests (в скелете — мок-режим).
- `exporter.py` — сохранение в многостраничный Excel.

## Конфигурация
Секреты — в `configs/webmaster/.env` (не в папке скилла, не в Git):
```
YANDEX_WEBMASTER_TOKEN=y0_...
YANDEX_WEBMASTER_USER_ID=1234567
```
Как получить токен — см. `README.md`.

## Запуск
```bash
python run.py --host-id https:example.com:443 --real --output data/webmaster/webmaster.xlsx
```

## Аргументы
- `--host-id` — ID хоста в Вебмастере (формат: `https:example.com:443`)
- `--real` — использовать реальный API (без флага — мок)
- `--limit` — максимум строк на лист (по умолчанию — всё, что отдаёт API)
- `--output` — путь к выходному Excel
- `--token` — токен вручную (необязательно; по умолчанию берётся из `.env`)

## Выходные данные
Многостраничный Excel:
- **Запросы** — query_text, impressions, clicks, position
- **Индексация** — url, title, last_access, status (страницы в поиске)
- **Ссылки** — source_url, target_url, discovery_date

## API (v4)
База: `https://api.webmaster.yandex.net/v4`, авторизация — заголовок `Authorization: OAuth {token}`.
Эндпоинты (все под `/user/{user_id}/hosts/{host_id}`):
- Запросы: `search-queries/popular/` (indicators: TOTAL_SHOWS, TOTAL_CLICKS, AVG_SHOW_POSITION)
- Индексация: `search-urls/in-search/samples/` (выборка страниц в поиске)
- Ссылки: `links/external/samples/` (выборка внешних ссылок)

> Примечание: индексация и ссылки — это **выборки** (samples), а не полный дамп. Для полных чисел есть отдельные счётчики (история индексации, суммарные ссылки).
