# Скилл: Выгрузка Google Search Console

## Назначение
Выгружает из GSC все отчёты, доступные через API, в один Excel — каждый отчёт отдельной вкладкой.

## Архитектура
- `run.py` — оркестратор. Аргументы, сводный лист, алиас домена в имени файла.
- `gsc_client.py` — авторизация (OAuth token.json или Service Account), отчёты
  `searchanalytics.query` во всех разрезах + `sitemaps.list`, пагинация.
- `exporter.py` — Excel: вкладка на отчёт, форматирование, цветовая индикация CTR.
- `authorize.py` — одноразовая OAuth-авторизация (client_secret.json → token.json).

## Конфигурация
`configs/gsc/` — креденшалы (`token.json` или `service_account.json`), в Git не попадают.

## Запуск
```bash
python run.py --site https://site.ru/ --start 2026-06-01 --end 2026-06-30 --real
python run.py --list-sites   # показать доступные ресурсы
```

## Аргументы
- `--site` — ресурс в GSC: `sc-domain:site.ru` или `https://site.ru/`
- `--start` / `--end` — период (YYYY-MM-DD)
- `--output` — путь к Excel (по умолчанию `data/gsc/<алиас-домена>.xlsx`)
- `--real` — реальный API (без него — мок)
- `--limit` — ограничить число строк на отчёт
- `--list-sites` — список доступных сайтов

## Выходные данные
`data/gsc/<алиас-домена>.xlsx` (например `example-com.xlsx`), вкладки:

| Вкладка | Разрез | Колонки |
|---|---|---|
| Сводка | итоги периода | показатель, значение |
| Запросы | query | clicks, impressions, ctr, position |
| Страницы | page | clicks, impressions, ctr, position |
| Запрос+Страница | query+page | clicks, impressions, ctr, position |
| Динамика | date | clicks, impressions, ctr, position |
| Устройства | device | clicks, impressions, ctr, position |
| Страны | country | clicks, impressions, ctr, position |
| Вид в выдаче | searchAppearance | clicks, impressions, ctr, position |
| Sitemaps | карты сайта | path, type, даты, urls_submitted, errors, warnings |

Цветовая индикация CTR: зелёный > 3%, жёлтый 1-3%, красный < 1%.

## Зависимости
google-api-python-client, google-auth, google-auth-oauthlib, pandas, openpyxl

## API
Search Console API v1: `searchanalytics.query` (rowLimit 25000 + startRow),
`sites.list`, `sitemaps.list`. Упавший отчёт не роняет выгрузку — вкладка остаётся пустой.
