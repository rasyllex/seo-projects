# Скилл: Выгрузка Яндекс.Метрика

## Назначение
Аналитический экспорт из Яндекс.Метрики в многостраничный Excel с дашбордом роста (период к периоду) и разрезами по поведению, источникам, устройствам, географии и запросам.

## Архитектура
- `run.py` — оркестратор. Читает токен из `configs/metrica/.env`, счётчик из `--counter-id`, собирает все вкладки, экспортирует.
- `metrica_client.py` — запросы к Stat API (реал) + мок-режим (`use_real`). Полная постраничная выгрузка (`_stat_all`), без лимитов.
- `exporter.py` — Excel: подсветка отказов > 70% и дельт в «Сводке».

## Конфигурация
Секрет — в `configs/metrica/.env` (не в папке скилла, не в Git):
```
YANDEX_METRICA_TOKEN=y0_...
```
`counter_id` — per-project, из Паспорта проектов / `--counter-id`. Как получить токен — см. `README.md`.

## Запуск
```bash
python run.py --counter-id 12345678 --days 90 --real
```

## Аргументы
- `--counter-id` — ID счётчика Метрики (обязателен)
- `--days` — период в днях (по умолчанию 30); «Сводка» сравнивает его с предыдущим таким же
- `--real` — реальный API (без флага — мок)
- `--output` — путь к Excel (по умолчанию `data/metrica/metrica.xlsx`)

## Вкладки
Сводка · По URL · Длина сессий · Источники · Устройства · География · Запросы · По месяцам · Цели

## API (Stat API v1)
База: `https://api-metrika.yandex.net/stat/v1/data`, авторизация — `Authorization: OAuth {token}`.
Ключевые измерения/метрики:
- Страницы: `ym:s:startURL` + `ym:s:pageviews,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds`
- Длина сессий: фильтр `ym:s:visitDuration>60` и `>180`
- Источники: `ym:s:trafficSource`; органика отдельно — фильтр `ym:s:trafficSource=='organic'`
- Устройства: `ym:s:deviceCategory`; География: `ym:s:regionCity`; Запросы: `ym:s:searchPhrase`
- Цели: `ym:s:sumGoalReachesAny` по `ym:s:date`

## Заметки
- **Органика считается отдельной строкой** в «Сводке» — это KPI SEO (общий трафик может расти за счёт рекламы/бренда).
- Выгрузка полная (пагинация по `offset`). На очень больших счётчиках Метрика может **сэмплировать** данные (`sampled: true`).
- Список счётчиков токена: `management/v1/counters`.
