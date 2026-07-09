# Скилл: Съём позиций

## Описание
Проверяет позиции сайта в Google и Яндекс по списку ключевых слов через XMLRiver API.

Поддерживает указание региона как числовым кодом (`--region`), так и названием города (`--city "Ростов на дону"`).

📹 Видео-инструкция по работе со скиллом: https://activate.infoprotector.com/online/?url=protection.infoprotector.com/file/1e1e7b8a-9e9e-4f9f-bc90-be04f5c6454e/selcdn

## Установка
```bash
pip install -r requirements.txt
```

Или вручную:
```bash
pip install requests pandas tqdm openpyxl python-dotenv
```

## Настройка
Скопируйте шаблон конфига и добавьте ключи XMLRiver:
```bash
cp config.env.example config.env
```

Отредактируйте `config.env`:
```env
XMLRIVER_USER_ID=your_user_id
XMLRIVER_API_KEY=your_api_key
```

## Запуск

### По названию города
```bash
# Яндекс — Москва
python run.py --input data/keywords_example.xlsx --domain example.com --city "Москва" --engine yandex --real

# Яндекс — Ростов-на-Дону
python run.py --input data/keywords_example.xlsx --domain example.com --city "Ростов на дону" --engine yandex --real

# Яндекс + Google + конкуренты для одного города
python run.py --input data/keywords_example.xlsx --domain example.com --city "Ростов на дону" --real --competitors
```

### По коду региона
```bash
# Мок-режим (без реального API)
python run.py --input data/keywords_example.xlsx --domain example.com

# Реальный API — Яндекс, регион 213 (Москва)
python run.py --input data/keywords_example.xlsx --domain example.com --engine yandex --real

# Реальный API — Google
python run.py --input data/keywords_example.xlsx --domain example.com --engine google --real

# Реальный API — Яндекс, Ростов-на-Дону (id=39)
python run.py --input data/keywords_example.xlsx --domain example.com --engine yandex --region 39 --real
```

### Дополнительные параметры
```bash
# Количество потоков (по умолчанию 8)
python run.py --input data/keywords_example.xlsx --domain example.com --engine yandex --real --threads 4

# Сбор ТОП-10 конкурентов по Яндексу и Google
python run.py --input data/keywords_example.xlsx --domain example.com --real --competitors

# Сбор ТОП-20 конкурентов
python run.py --input data/keywords_example.xlsx --domain example.com --real --competitors --top-n 20
```

## Как работает `--city`

1. Для **Яндекса** скилл ищет город в `knowledge_base/yandex_regions.csv` и берёт его `id`.
2. Для **Google** скилл пытается найти город в `knowledge_base/google_geo.csv` через транслитерацию. Если не находит — использует регион по умолчанию из `config.env` и выводит предупреждение.

Если по названию найдено несколько регионов, скилл выведет список и попросит уточнить название или использовать `--region`.

## Выход
- Без `--competitors`: `data/output.xlsx` — таблица с колонками: keyword, position, url, date
- С `--competitors`: `data/output.xlsx` с 4 листами:
  - `positions_yandex` — позиции домена в Яндексе
  - `positions_google` — позиции домена в Google
  - `competitors_yandex` — ТОП-10 конкурентов в Яндексе
  - `competitors_google` — ТОП-10 конкурентов в Google
- `data/cache.json` — кэш результатов

## Структура
- `run.py` — оркестратор
- `fetcher.py` — запросы к API через `ThreadPoolExecutor` с ретраями
- `cache.py` — кэширование в JSON (TTL 24ч)
- `validate_input.py` — проверка входного Excel
- `region_resolver.py` — разрешение названий городов в коды регионов
- `knowledge_base/` — справочники регионов для Яндекса и Google

## Особенности
- **Многопоточность**: по умолчанию 8 потоков, настраивается через `--threads`.
- **Ретраи**: автоматические повторные попытки при временных ошибках XMLRiver.
- **HTTPS**: используются безопасные эндпоинты XMLRiver.
- **Нормализация домена**: поддерживает `example.com`, `www.example.com`, `https://www.example.com/`.
- **Кэш**: ключ кэша включает keyword + region + engine + domain.
- **Регионы по названию**: `--city` работает для Яндекса точно, для Google — best-effort с fallback.
