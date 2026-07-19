# Скилл: Краулер (requests)

## Описание
Многопоточный обход сайта через requests: сохраняет HTML-кэш и извлекает зоны (title, h1, h2, description) в Excel. По умолчанию **8 потоков** — обход идёт «волнами»: фронтир ссылок раздаётся пулу потоков, найденные ссылки образуют следующую волну.

## Установка
```bash
pip install -r requirements.txt
```

## Запуск
```bash
# базовый (8 потоков)
python run.py --domain example.com --max-pages 100

# медленнее и вежливее (сайт слабый/боится нагрузки)
python run.py --domain example.com --threads 2 --delay 1.5

# ротация User-Agent (случайный браузерный UA на каждый запрос)
python run.py --domain example.com --rotate-ua

# через прокси
python run.py --domain example.com --proxy http://user:pass@host:3128
python run.py --domain example.com --proxy-file proxies.txt   # список, ротация
```

## Аргументы
| Флаг | По умолчанию | Что делает |
|---|---|---|
| `--domain` | — | домен для обхода |
| `--max-pages` | 100 | лимит страниц |
| `--threads` | **8** | размер пула потоков |
| `--retries` | 3 | повторы на таймаут/сеть/5xx с паузой 2с, 4с, 6с (4xx не ретраятся) |
| `--delay` | 0.5 | пауза после запроса в каждом потоке |
| `--respect-robots` | выкл | не краулить URL, закрытые в robots.txt (по умолчанию — только помечать в отчёте) |
| `--rotate-ua` | выкл | случайный UA из пула ~10 реальных браузерных на каждый запрос |
| `--proxy` | — | один прокси `http://user:pass@host:port` |
| `--proxy-file` | — | файл со списком прокси (по одному в строке), случайный на запрос |
| `--output` | ../../data/crawler-requests/output.xlsx | путь к Excel |

## Прокси: обход блокировки зарубежного трафика
Многие российские сайты блокируют запросы из-за границы. Решение — прокси с российским IP (например, свой VPS со Squid). Прописывается один раз в `config.env`:
```bash
cp config.env.example config.env
# PROXY=http://user:pass@203.0.113.10:3128
```
Дальше все обходы идут через него автоматически; CLI-флаги `--proxy`/`--proxy-file` имеют приоритет. Логин/пароль в логах маскируются.

## Кастомное извлечение (XPath)
Как custom extraction в Screaming Frog — свои колонки по XPath:
```bash
python run.py --domain example.com \
  --xpath 'phone=(//a[starts-with(@href,"tel:")])[1]//text()' \
  --xpath 'og_title=//meta[@property="og:title"]/@content'
```
`--xpath` можно указывать несколько раз, формат `имя_колонки=//выражение`. Каждое станет колонкой в отчёте.

## Выход
`../../data/crawler-requests/output.xlsx` — реестр по каждой странице (поля отобраны из полноценного тех-аудита, всё извлекается при обходе, без доп. запросов):

| Поле | Что показывает |
|---|---|
| `url`, `status_code`, `content_type` | адрес, код ответа, тип |
| **`indexable`** (Да/Нет) | **открыта ли страница для индексации** |
| **`indexability_status`** | причина закрытия: `noindex` / `Blocked by robots.txt` / `Canonicalised` / `Redirect` / `HTTP 4xx` |
| `meta_robots` | директивы `<meta name=robots>` (+ учитывается X-Robots-Tag) |
| `canonical` | канонический URL (самоканоникал или на другой адрес) |
| `title`, `h1`, `h2`, `description` | зоны |
| `word_count` | слов в body (тонкие страницы) |
| `size_bytes`, `response_time` | вес и время ответа |
| `crawl_depth` | глубина от главной |
| `schema_types` | типы Schema.org (JSON-LD + microdata) |
| *(кастомные)* | ваши XPath-колонки |

Плюс `../../data/crawler-requests/cache/<домен>/` — HTML-кэш (повторный запуск не качает заново).

## Структура
- `run.py` — оркестратор
- `crawler.py` — многопоточный обход волнами, ротация UA, прокси, глубина
- `parser.py` — извлечение ссылок
- `seo.py` — обогащение страницы: индексируемость, canonical, schema, word_count, кастомные XPath
- `robots.py` — разбор robots.txt (индексируемость + опция вежливого обхода)
- `exporter.py` — запись Excel (единый порядок колонок с Selenium-краулером)
- `cache.py` — сохранение/загрузка HTML-кэша

## Вежливость
8 потоков × delay 0.5с ≈ до 16 запросов/сек — для крупного сайта нормально, мелкий может лечь. Не уверен — начинай с `--threads 2 --delay 1`.
