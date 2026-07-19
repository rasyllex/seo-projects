#!/usr/bin/env python3
"""
Краулер через Selenium: многопоточный обход сайта с JS-рендерингом.

По умолчанию 4 потока (= 4 браузера). Умеет: обходить сайт по внутренним
ссылкам, скроллить страницы (lazy-load), кэшировать HTML, ротацию браузеров
Chrome/Firefox и работу через прокси.
"""
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from crawler import DriverPool, crawl_page, crawl_with_scroll, response_headers
from cache import cache_path, save_html_cache, load_html_cache
from seo import extract_page, parse_xpath_args, extract_links
from exporter import to_excel
from robots import Robots


# Пути относительно корня проекта seo-agency
PROJECT_ROOT = Path(__file__).parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "crawler-selenium"
CONFIG_DIR = PROJECT_ROOT / "configs" / "crawler-selenium"
HTML_CACHE_DIR = DATA_DIR / "html"


def generate_output_filename(url):
    """Генерирует имя файла: {домен}_{дата}_{время}.xlsx"""
    domain = urlparse(url).netloc
    # Убираем www. если есть
    domain_clean = domain.replace("www.", "")
    
    # Дата и время: YYYYMMDD_HH-MM
    timestamp = datetime.now().strftime("%Y%m%d_%H-%M")
    
    filename = f"{domain_clean}_{timestamp}.xlsx"
    return DATA_DIR / filename


def main():
    parser = argparse.ArgumentParser(description="Selenium Crawler")
    parser.add_argument("--url", required=True, help="Стартовый URL")
    parser.add_argument("--max-pages", type=int, default=10, help="Максимум страниц (по умолчанию 10)")
    parser.add_argument("--threads", type=int, default=4, help="Потоки = браузеры (по умолчанию 4)")
    parser.add_argument("--rotate-browsers", action="store_true",
                        help="Ротация браузеров: воркеры получают Chrome/Firefox по очереди")
    parser.add_argument("--proxy", default=None,
                        help="Прокси host:port (или PROXY в config.env); auth-прокси браузеры не умеют")
    parser.add_argument("--output-dir", default=None, help="Папка для отрендеренного HTML")
    parser.add_argument("--output", default=None, help="Путь к Excel-реестру зон")
    parser.add_argument("--xpath", action="append", default=None, metavar="ИМЯ=XPATH",
                        help="Кастомное извлечение: имя_колонки=//xpath (можно несколько раз)")
    parser.add_argument("--scrolls", type=int, default=0, help="Скроллов на страницу (lazy-load)")
    parser.add_argument("--wait", type=int, default=3, help="Секунд ожидания JS")
    parser.add_argument("--retries", type=int, default=3,
                        help="Повторы на таймаут/сбой рендерера с паузой 2с,4с,6с (по умолчанию 3)")
    parser.add_argument("--respect-robots", action="store_true",
                        help="Не краулить URL, закрытые в robots.txt (по умолчанию только помечать)")
    parser.add_argument("--no-headless", action="store_true", help="Браузер с окном")
    args = parser.parse_args()
    xpath_map = parse_xpath_args(args.xpath)

    start_url = args.url if args.url.startswith("http") else f"https://{args.url}"
    domain = urlparse(start_url).netloc
    proxy = args.proxy or os.getenv("PROXY", "").strip() or None

    # Определяем пути с автогенерацией имени файла
    output_dir = Path(args.output_dir) if args.output_dir else HTML_CACHE_DIR
    output_path = Path(args.output) if args.output else generate_output_filename(start_url)

    print(f"-> Обход: {start_url}")
    print(f"-> Максимум страниц: {args.max_pages} | потоков: {args.threads}"
          f"{' | ротация браузеров' if args.rotate_browsers else ''}"
          f"{' | прокси' if proxy else ''}")

    pool = DriverPool(headless=not args.no_headless,
                      rotate_browsers=args.rotate_browsers, proxy=proxy)

    def fetch(url):
        """Кэш → браузер. Возвращает (url, html|None, из_кэша, x_robots)."""
        path = cache_path(url, domain, output_dir)
        cached = load_html_cache(path)
        if cached:
            return url, cached, True, ""
        try:
            driver = pool.get()
            if args.scrolls > 0:
                html = crawl_with_scroll(driver, url, scrolls=args.scrolls,
                                         wait_time=args.wait, retries=args.retries)
            else:
                html = crawl_page(driver, url, wait_time=args.wait, retries=args.retries)
            x_robots = response_headers(driver).get("x-robots-tag", "")
            save_html_cache(path, html)
            return url, html, False, x_robots
        except Exception as e:
            print(f"  [WARN] {url}: {e}")
            return url, None, False, ""

    visited, results = set(), []
    frontier = [start_url]
    depth = {start_url: 0}
    # robots.txt (через тот же прокси, если задан)
    robots = Robots(start_url, proxies={"http": proxy, "https": proxy} if proxy else None)
    if args.respect_robots:
        print("-> Уважаю robots.txt: закрытые URL не краулятся")
    if xpath_map:
        print(f"-> Кастомные XPath: {', '.join(xpath_map)}")
    try:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            while frontier and len(visited) < args.max_pages:
                batch = []
                for u in frontier:
                    if u not in visited and u not in batch:
                        batch.append(u)
                    if len(visited) + len(batch) >= args.max_pages:
                        break
                if not batch:
                    break
                visited.update(batch)
                frontier = []

                for url, html, from_cache, x_robots in executor.map(fetch, batch):
                    if html is None:
                        continue
                    mark = "CACHE" if from_cache else "OK"
                    print(f"[{len(results) + 1}] [{mark}] {url} ({len(html)} симв.)")
                    # обогащение — единый формат с requests-краулером
                    results.append(extract_page(
                        html, url, status_code=200, content_type="text/html",
                        x_robots=x_robots, crawl_depth=depth.get(url, 0),
                        html_file=str(cache_path(url, domain, output_dir)),
                        xpath_map=xpath_map, robots_blocked=not robots.allowed(url)))
                    for link in extract_links(html, url):
                        if link not in visited:
                            if args.respect_robots and not robots.allowed(link):
                                continue
                            depth.setdefault(link, depth.get(url, 0) + 1)
                            frontier.append(link)
    finally:
        pool.quit_all()

    # Реестр зон в Excel (как в requests-краулере) + отрендеренный HTML на диске
    output_path.parent.mkdir(parents=True, exist_ok=True)
    to_excel(results, output_path)

    print(f"\n[OK] Страниц: {len(results)} | реестр: {output_path}")
    print(f"     Отрендеренный HTML: {output_dir / domain}/")


if __name__ == "__main__":
    main()
