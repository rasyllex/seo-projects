# Скилл: Съём позиций

## Назначение
Проверяет позиции домена в Яндексе и Google по списку ключевых слов через XMLRiver API.

- **Яндекс**: возвращает позицию в ТОП-100 за один запрос.
- **Google**: собирает ТОП-30 постранично (~10 URL за запрос).

## Архитектура
- `run.py` — оркестратор. Читает Excel, валидирует входные данные, вызывает fetcher, сохраняет результат.
- `fetcher.py` — запросы к XMLRiver API. Работает в многопоточном режиме через `ThreadPoolExecutor`. Запрашивает SERP один раз и извлекает из него и позицию домена, и конкурентов.
- `cache.py` — кэширование SERP в JSON. TTL 24 часа. Ключ: `serp_<keyword>_<region>_<engine>`.
- `validate_input.py` — проверяет входной Excel перед обработкой.

## Быстрый старт

1. Скопируйте `config.env.example` в `config.env` и добавьте реальные ключи XMLRiver.
2. Подготовьте Excel с колонкой `keyword` или используйте `data/keywords_example.xlsx`.
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Запустите:
   ```bash
   # Мок-режим
   python run.py --input data/keywords_example.xlsx --domain example.com

   # Реальный API — Яндекс
   python run.py --input data/keywords_example.xlsx --domain example.com --engine yandex --real

   # Реальный API — Google
   python run.py --input data/keywords_example.xlsx --domain example.com --engine google --real

   # Полный отчёт: позиции + конкуренты по Яндексу и Google (4 листа)
   python run.py --input data/keywords_example.xlsx --domain example.com --real --competitors
   ```

## Аргументы
- `--input` — путь к Excel с колонкой `keyword`
- `--domain` — домен для проверки (example.com)
- `--region` — код региона Яндекса (213 = Москва, по умолчанию)
- `--engine` — поисковая система: `yandex` или `google` (по умолчанию `yandex`)
- `--real` — использовать реальный XMLRiver API (иначе мок-режим)
- `--output` — путь к выходному Excel (по умолчанию `data/output.xlsx`)
- `--threads` — количество потоков для параллельных запросов (по умолчанию `8`)
- `--competitors` — собрать ТОП-10 конкурентов по Яндексу и Google в отдельные листы
- `--top-n` — количество конкурентов для сбора (по умолчанию `10`)

## Выходные данные
`data/output.xlsx` с колонками:
- `keyword` — ключевое слово
- `position` — позиция домена (0 = не найден)
- `url` — найденный URL домена в выдаче (пусто, если не найден)
- `date` — дата проверки

## Один проход
При использовании `--competitors` скилл не делает отдельных запросов для позиций и отдельных для конкурентов. Вместо этого:

1. Запрашивается SERP по ключевому слову (Яндекс — ТОП-100, Google — ТОП-30).
2. Из того же ответа извлекается:
   - позиция и URL целевого домена;
   - ТОП-10 URL конкурентов.
3. SERP кэшируется, поэтому повторный запрос использует сохранённые данные.

Это сокращает расход API-запросов примерно в 2 раза.

## Многопоточность
Скилл использует `concurrent.futures.ThreadPoolExecutor` с 8 потоками по умолчанию. Потоки безопасно работают с общим кэшем SERP через `threading.Lock`.

## Ретраи
- **Яндекс**: до 3 попыток с задержкой 2s, 4s, 6s.
- **Google**: до 5 попыток при ошибках `500`, `111`, `32`, `33` с нарастающей задержкой.

## Зависимости
- requests
- pandas
- tqdm
- openpyxl
- python-dotenv

## API
- Яндекс: `https://xmlriver.com/yandex/xml` — параметры: user, key, query, lr, groupby=100
- Google: `https://xmlriver.com/search/xml` — параметры: user, key, query, loc, lr, page
