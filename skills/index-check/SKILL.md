# Скилл: Проверка индексации

## Назначение
Проверяет, проиндексированы ли страницы в Google и Яндекс.

## Архитектура
- `run.py` — оркестратор. Читает Excel, вызывает checker, сохраняет результат с цветами.
- `checker.py` — запросы к API. Поддерживает XMLRiver с оператором `site:`.
- `cache.py` — кэширование в JSON. TTL 24 часа. Ключ: url + engine.

## Запуск
```bash
cd D:\projects\seo-agency\skills\index-check
python run.py --input path/to/urls.xlsx --engines google,yandex
```

## Аргументы
- `--input` — путь к Excel с колонкой `url`
- `--engines` — список поисковиков через запятую (google,yandex,bing)
- `--output` — путь к выходному Excel (опционально, по умолчанию data/index-check/output.xlsx)
- `--real` — использовать реальный API (иначе мок)

## Выходные данные
`D:\projects\seo-agency\data\index-check\output.xlsx` с колонками:
- `url` — адрес страницы
- `google` — True/False
- `yandex` — True/False
- `date` — дата проверки

Цветовая индикация:
- Зелёный — проиндексирована везде
- Жёлтый — проиндексирована частично
- Красный — нигде не проиндексирована

## Зависимости
- requests
- pandas
- tqdm
- openpyxl

## Пути
- Кэш: `D:\projects\seo-agency\data\index-check\cache.json`
- Выходной файл: `D:\projects\seo-agency\data\index-check\output.xlsx`
