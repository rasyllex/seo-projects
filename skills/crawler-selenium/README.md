# Скилл: Краулер (Selenium)

## Описание
Многопоточный обход сайта с **JS-рендерингом**: реальный браузер выполняет JavaScript, поэтому виден контент, который requests не получит (SPA, ленивая подгрузка, динамические цены). По умолчанию **4 потока = 4 параллельных браузера**. Умеет скроллить (lazy-load), ротацию браузеров Chrome/Firefox и работу через прокси.

## Установка
```bash
pip install -r requirements.txt
```
Нужен установленный Chrome (для `--rotate-browsers` — ещё и Firefox). Драйверы скачиваются автоматически (webdriver-manager).

## Запуск
```bash
# базовый обход (4 браузера)
python skills/crawler-selenium/run.py --url https://example.com --max-pages 10

# одна страница с прокруткой (бесконечная лента)
python skills/crawler-selenium/run.py --url https://example.com/catalog --max-pages 1 --scrolls 5

# ротация браузеров: воркеры получают Chrome и Firefox по очереди
python skills/crawler-selenium/run.py --url https://example.com --rotate-browsers

# через прокси (host:port, БЕЗ логина/пароля — см. ниже)
python skills/crawler-selenium/run.py --url https://example.com --proxy http://203.0.113.10:3128
python skills/crawler-selenium/run.py --url https://example.com --proxy socks5://127.0.0.1:1080

# посмотреть браузер глазами
python skills/crawler-selenium/run.py --url https://example.com --max-pages 1 --no-headless
```

## Аргументы
| Флаг | По умолчанию | Что делает |
|---|---|---|
| `--url` | — | стартовый URL |
| `--max-pages` | 10 | лимит страниц |
| `--threads` | **4** | параллельные браузеры |
| `--rotate-browsers` | выкл | Chrome ↔ Firefox по очереди (разные движки/отпечатки) |
| `--proxy` | — | `host:port` / `socks5://host:port` (или PROXY в config.env) |
| `--retries` | 3 | повторы на таймаут/сбой рендерера с паузой 2с, 4с, 6с |
| `--respect-robots` | выкл | не краулить URL, закрытые в robots.txt (по умолчанию — только помечать) |
| `--scrolls` | 0 | прокруток на страницу (lazy-load) |
| `--wait` | 3 | секунд ожидания JS после загрузки |
| `--no-headless` | — | браузер с окном |
| `--output-dir` | data/crawler-selenium/html | папка кэша |
| `--output` | auto | путь к Excel (по умолчанию автогенерация: {домен}_{YYYYMMDD}_{HH-MM}.xlsx) |

## Прокси: обход блокировки зарубежного трафика
Браузеры **не умеют прокси с логином/паролем** через флаг. Два рабочих способа со своим VPS в РФ:

1. **SSH-туннель (SOCKS5)** — проще всего, Squid не нужен:
   ```bash
   ssh -N -D 1080 root@<vps-ip> &
   python skills/crawler-selenium/run.py --url https://сайт.ru --proxy socks5://127.0.0.1:1080
   ```
2. **IP-whitelist в Squid** — разрешить свой IP в конфиге на VPS, тогда auth не нужен:
   ```bash
   python skills/crawler-selenium/run.py --url https://сайт.ru --proxy http://<vps-ip>:3128
   ```
Постоянный вариант — `PROXY=` в `configs/crawler-selenium/config.env` (см. config.env.example).

## Кастомное извлечение (XPath)
Свои колонки по XPath (по отрендеренному DOM — работает и с JS-контентом):
```bash
python skills/crawler-selenium/run.py --url https://example.com \
  --xpath 'price=(//*[contains(@class,"price")])[1]//text()'
```
`--xpath` можно указывать несколько раз, формат `имя=//выражение`.

## Выход
- `data/crawler-selenium/{домен}_{YYYYMMDD}_{HH-MM}.xlsx` — реестр по каждой странице: `url, status_code, indexable, indexability_status, meta_robots, canonical, title, h1, h2, description, word_count, size_bytes, crawl_depth, schema_types, html_file` + кастомные XPath. **Единый формат с requests-краулером**, плюс колонка `html_file` на отрендеренный HTML.
- `data/crawler-selenium/html/<домен>/<md5(url)>.html` — рендеренный HTML каждой страницы

## Структура
- `run.py` — CLI, обход волнами, автогенерация имени файла
- `crawler.py` — DriverPool (драйвер на поток), init_driver (chrome/firefox, headless, прокси), загрузка/скролл
- `parser.py` — внутренние ссылки, извлечение динамического контента
- `cache.py` — HTML-кэш
- `seo.py` — SEO-обогащение (единый с requests-краулером)
- `robots.py` — разбор robots.txt
- `exporter.py` — сохранение в Excel

## Когда что использовать
requests-краулер — быстрый и дешёвый, для обычных сайтов. Selenium — когда контент появляется только после JS. Правило: сначала попробуй requests; если в HTML нет нужного контента — бери Selenium.
