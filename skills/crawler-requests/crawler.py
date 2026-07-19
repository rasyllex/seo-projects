"""
Логика обхода сайта: многопоточный BFS «волнами».

Волна = текущий фронтир ссылок раздаётся пулу потоков (по умолчанию 8),
собранные ссылки образуют следующую волну. Потокобезопасно по построению:
visited пополняется до раздачи, результаты собираются в главном потоке.

Прокси: --proxy / --proxy-file / переменная PROXY в config.env.
Кейс: сайт блокирует зарубежный трафик — прописываешь российский прокси
в config.env один раз, и все обходы идут через него.
"""

import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from seo import extract_page, extract_links
from cache import save_html_cache, load_html_cache
from robots import Robots

# Адаптированный путь: D:\projects\seo-agency\configs\crawler-requests\config.env
load_dotenv(Path(__file__).parents[2] / "configs" / "crawler-requests" / "config.env")

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Пул реальных юзер-агентов для --rotate-ua (случайный на каждый запрос)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 YaBrowser/24.6.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

_tls = threading.local()        # своя Session в каждом потоке

# Анти-бот cookie-заглушка (Beget и подобные): первая отдача — крошечный
# <script>, ставящий cookie и перезагружающий страницу. requests JS не
# исполняет, поэтому ловим стаб, ставим cookie и повторяем запрос.
_COOKIE_GATE_RE = re.compile(r"document\.cookie\s*=\s*['\"]([^=]+)=([^'\";]+)")


def _pass_cookie_gate(session, resp, url, headers, proxies):
    """Если ответ — cookie-заглушка, ставит cookie и повторяет запрос. Иначе — resp как есть."""
    if len(resp.content) < 2000 and "document.cookie" in resp.text:
        m = _COOKIE_GATE_RE.search(resp.text)
        if m:
            session.cookies.set(m.group(1), m.group(2))
            return session.get(url, timeout=30, headers=headers, proxies=proxies)
    return resp


def mask_proxy(proxy):
    """Прячет логин/пароль прокси в логах: http://***:***@host:port."""
    if not proxy:
        return ""
    try:
        p = urlparse(proxy)
        host = f"{p.hostname}:{p.port}" if p.port else (p.hostname or "***")
        if p.username or p.password:
            return f"{p.scheme}://***:***@{host}"
        return f"{p.scheme}://{host}"
    except Exception:
        return "***"


def load_proxies(proxy=None, proxy_file=None):
    """Список прокси: CLI --proxy → CLI --proxy-file → PROXY из config.env."""
    if proxy:
        return [proxy.strip()]
    if proxy_file:
        lines = Path(proxy_file).read_text(encoding="utf-8").splitlines()
        return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
    env = os.getenv("PROXY", "").strip()
    return [env] if env else []


def _session():
    s = getattr(_tls, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": DEFAULT_UA})
        _tls.session = s
    return s


def _fetch(url, domain, delay, rotate_ua, proxies, retries=3):
    """Одна страница: кэш → HTTP с ретраями.
    Повтор на таймаут/сетевую ошибку/5xx с нарастающей паузой (2с, 4с, 6с…).
    Возвращает (url, html|None, status, content_type, x_robots, response_time, err|None)."""
    html = load_html_cache(url, domain)
    if html is not None:
        return url, html, 200, "text/html", "", None, None

    last_err, last_status = "", 0
    for attempt in range(1, retries + 1):
        headers = {"User-Agent": random.choice(USER_AGENTS)} if rotate_ua else None
        req_proxies = None
        if proxies:
            p = random.choice(proxies)          # ротация: случайный на каждый запрос
            req_proxies = {"http": p, "https": p}
        try:
            t0 = time.monotonic()
            sess = _session()
            resp = sess.get(url, timeout=30, headers=headers, proxies=req_proxies)
            resp = _pass_cookie_gate(sess, resp, url, headers, req_proxies)   # beget-ворота
            rt = round(time.monotonic() - t0, 3)
            status = resp.status_code
            ctype = resp.headers.get("Content-Type", "").split(";")[0].strip()
            x_robots = resp.headers.get("X-Robots-Tag", "")
            if status >= 500:                   # серверная ошибка — повторяем
                last_status, last_err = status, f"HTTP {status}"
                raise requests.RequestException(last_err)
            resp.raise_for_status()             # 4xx — не ретраим, отдаём как ошибку
            save_html_cache(url, resp.text, domain)
            time.sleep(delay)                   # вежливость: пауза между запросами
            return url, resp.text, status, ctype, x_robots, rt, None
        except requests.RequestException as e:
            if getattr(e, "response", None) is not None:
                last_status = e.response.status_code
                if last_status < 500:           # 4xx — окончательно, без повторов
                    return url, None, last_status, "", "", None, str(e)
            last_err = str(e)
            if attempt < retries:
                time.sleep(2 * attempt)         # 2с, 4с, 6с…
    time.sleep(delay)
    return url, None, last_status, "", "", None, f"после {retries} попыток: {last_err}"


def crawl(domain, max_pages=100, delay=0.5, threads=8, rotate_ua=False,
          proxy=None, proxy_file=None, xpath_map=None, retries=3,
          respect_robots=False, start_url=None):
    """
    Обходит сайт с главной страницы. Многопоточно (по умолчанию 8 потоков).

    Returns:
        список словарей-строк реестра (url, status_code, indexable, meta_robots,
        canonical, зоны, word_count, crawl_depth, schema_types, кастомные XPath…)
    """
    proxies = load_proxies(proxy, proxy_file)
    if proxies:
        tail = f" … и ещё {len(proxies) - 1}" if len(proxies) > 1 else ""
        print(f"-> Прокси: {mask_proxy(proxies[0])}{tail}")
    if rotate_ua:
        print(f"-> Ротация User-Agent: {len(USER_AGENTS)} вариантов")
    if xpath_map:
        print(f"-> Кастомные XPath: {', '.join(xpath_map)}")

    start_url = start_url or f"https://{domain}/"
    # robots.txt: грузим один раз на домен (через тот же прокси, если задан)
    robots = Robots(start_url, proxies={"http": proxies[0], "https": proxies[0]} if proxies else None)
    if respect_robots:
        print("-> Уважаю robots.txt: закрытые URL не краулятся")

    visited, results = set(), []
    frontier = [start_url]
    depth = {start_url: 0}                   # глубина от главной

    with ThreadPoolExecutor(max_workers=threads) as executor:
        while frontier and len(visited) < max_pages:
            # собираем волну (без дублей, не выходя за лимит)
            batch = []
            for u in frontier:
                if u not in visited and u not in batch:
                    batch.append(u)
                if len(visited) + len(batch) >= max_pages:
                    break
            if not batch:
                break
            visited.update(batch)
            frontier = []

            # волна уходит в пул потоков
            fetched = executor.map(
                lambda u: _fetch(u, domain, delay, rotate_ua, proxies, retries), batch)
            for url, html, status, ctype, x_robots, rt, err in fetched:
                print(f"[{len(results) + 1}] {status or 'ERR'} {url}")
                if err:
                    print(f"  [WARN] {err}")
                    continue
                results.append(extract_page(
                    html, url, status_code=status, content_type=ctype,
                    x_robots=x_robots, response_time=rt, crawl_depth=depth.get(url, 0),
                    xpath_map=xpath_map, robots_blocked=not robots.allowed(url)))
                # обход: с --respect-robots не идём на закрытые в robots.txt ссылки
                for link in extract_links(html, url):
                    if link not in visited:
                        if respect_robots and not robots.allowed(link):
                            continue
                        depth.setdefault(link, depth.get(url, 0) + 1)
                        frontier.append(link)

    return results
