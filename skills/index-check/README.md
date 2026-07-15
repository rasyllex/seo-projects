# Скилл: Проверка индексации

## Описание
Проверяет, проиндексированы ли страницы в Google и Яндекс.

## Установка
```bash
cd D:\projects\seo-agency\skills\index-check
pip install -r requirements.txt
```

## Запуск
```bash
# Мок-режим
python run.py --input path/to/urls.xlsx --engines google,yandex

# Реальный API
python run.py --input path/to/urls.xlsx --engines google,yandex --real

# Указать путь к выходному файлу
python run.py --input path/to/urls.xlsx --output path/to/output.xlsx
```

## Выход
По умолчанию: `D:\projects\seo-agency\data\index-check\output.xlsx` — таблица с колонками: url, google, yandex, date

## Структура
- `run.py` — оркестратор
- `checker.py` — проверка индексации (сейчас мок-режим)
- `cache.py` — кэширование в JSON (TTL 24ч)
- Кэш хранится в: `D:\projects\seo-agency\data\index-check\cache.json`
