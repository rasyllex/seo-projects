# Скилл: Краулер (Selenium)

## Назначение
Обход сайтов, где контент строится JavaScript'ом. Многопоточно: пул из 4 браузеров (по умолчанию), обход по внутренним ссылкам, HTML-кэш, автогенерация имени выходного файла.

## Архитектура
- `run.py` — CLI; обход «волнами»: фронтир раздаётся `ThreadPoolExecutor`, ссылки со страниц образуют следующую волну; автогенерация имени Excel-файла.
- `crawler.py`:
  - `DriverPool` — один драйвер на поток-воркер (`threading.local`); браузер не потокобезопасен, делить один драйвер между потоками нельзя. С `--rotate-browsers` воркеры получают Chrome/Firefox по счётчику. `quit_all()` гасит все браузеры в `finally`.
  - `init_driver(browser, headless, user_agent, proxy)` — Chrome (headless=new, anti-detection: excludeSwitches + CDP navigator.webdriver) или Firefox (prefs). Прокси: `--proxy-server=` для Chrome, `network.proxy.*` для Firefox, поддержка http и socks5.
  - `crawl_page` / `crawl_with_scroll` — загрузка + ожидание JS; таймаут рендерера не валит воркера — DOM забирается как есть.
- `cache.py` — кэш `data/crawler-selenium/html/<домен>/<md5(url)>.html`, единый формат с requests-краулером.
- `parser.py` — внутренние ссылки + пример извлечения динамического контента.
- `seo.py` — SEO-обогащение (единый модуль с requests-краулером).
- `robots.py` — разбор robots.txt по спецификации Google.
- `exporter.py` — сохранение в Excel.

## Ротация браузеров (`--rotate-browsers`)
Воркеры получают Chrome и Firefox по очереди: у страниц чередуются движки (Blink/Gecko) и отпечатки. Требует установленного Firefox. По умолчанию — все воркеры Chrome.

## Прокси
`--proxy` → `PROXY` из `configs/crawler-selenium/config.env`. Браузеры не поддерживают `user:pass@` в флаге:
- ssh-туннель: `ssh -N -D 1080 root@<vps>` → `socks5://127.0.0.1:1080`
- или IP-whitelist на прокси-сервере → `http://<vps>:3128`

## Ретраи
`--retries` (по умолчанию 3): повтор `driver.get` на таймаут/сбой рендерера с паузой 2с, 4с, 6с. Если после всех попыток страница открылась частично — забираем DOM как есть, воркер не падает.

## Автогенерация имени файла
В `run.py:generate_output_filename()`:
- Извлекает домен из `--url`
- Убирает `www.`
- Добавляет timestamp в формате `YYYYMMDD_HH-MM`
- Результат: `{домен}_{дата}_{время}.xlsx` в `data/crawler-selenium/`

## Отличие от requests-краулера
| | requests | Selenium |
|---|---|---|
| JS | нет | да |
| Скорость | ~10-16 стр/сек | ~1 стр/3-5 сек на браузер |
| Ресурсы | копейки | ~300-500 МБ RAM на браузер |
| Потоки по умолчанию | 8 | 4 |

## Зависимости
selenium, webdriver-manager, beautifulsoup4, python-dotenv, pandas, openpyxl, lxml (+ установленные Chrome/Firefox)
