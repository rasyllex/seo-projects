"""
Скилл: Краулер (requests)
Точка входа.
"""

import argparse
from pathlib import Path
from datetime import datetime

from crawler import crawl
from exporter import to_excel
from seo import parse_xpath_args

DATA_DIR = Path(__file__).parents[2] / "data" / "crawler-requests"


def generate_output_filename(domain):
    """Генерирует имя файла: {домен}_{дата}_{время}.xlsx"""
    # Убираем www. если есть
    domain_clean = domain.replace("www.", "")
    
    # Дата и время: YYYYMMDD_HH-MM
    timestamp = datetime.now().strftime("%Y%m%d_%H-%M")
    
    filename = f"{domain_clean}_{timestamp}.xlsx"
    return DATA_DIR / filename


def main():
    parser = argparse.ArgumentParser(description="Краулер сайта через requests")
    parser.add_argument("--domain", required=True, help="Домен для обхода")
    parser.add_argument("--start-url", default=None,
                        help="Стартовый URL (по умолчанию https://<домен>/)")
    parser.add_argument("--max-pages", default=100, type=int, help="Максимум страниц")
    parser.add_argument("--delay", default=0.5, type=float, help="Задержка между запросами (в каждом потоке)")
    parser.add_argument("--threads", default=8, type=int, help="Потоки (по умолчанию 8)")
    parser.add_argument("--retries", default=3, type=int,
                        help="Повторы на таймаут/сеть/5xx с паузой 2с,4с,6с (по умолчанию 3)")
    parser.add_argument("--rotate-ua", action="store_true",
                        help="Ротация User-Agent: случайный браузерный UA на каждый запрос")
    parser.add_argument("--proxy", default=None,
                        help="Прокси: http://user:pass@host:port (или PROXY в config.env)")
    parser.add_argument("--proxy-file", default=None,
                        help="Файл со списком прокси (по одному в строке) — ротация на каждый запрос")
    parser.add_argument("--xpath", action="append", default=None, metavar="ИМЯ=XPATH",
                        help="Кастомное извлечение: имя_колонки=//xpath (можно указывать несколько раз)")
    parser.add_argument("--respect-robots", action="store_true",
                        help="Не краулить URL, закрытые в robots.txt (по умолчанию только помечать)")
    parser.add_argument("--output", default=None, help="Путь к выходному Excel")
    args = parser.parse_args()

    print(f"-> Обход сайта: {args.domain}")
    print(f"-> Максимум страниц: {args.max_pages} | потоков: {args.threads}")

    results = crawl(
        domain=args.domain,
        max_pages=args.max_pages,
        delay=args.delay,
        threads=args.threads,
        rotate_ua=args.rotate_ua,
        proxy=args.proxy,
        proxy_file=args.proxy_file,
        xpath_map=parse_xpath_args(args.xpath),
        retries=args.retries,
        respect_robots=args.respect_robots,
        start_url=args.start_url,
    )

    print(f"-> Обход завершён. Страниц: {len(results)}")

    # Генерируем имя файла с доменом и датой/временем
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = generate_output_filename(args.domain)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    to_excel(results, output_path)

    print(f"[OK] Результат сохранён: {output_path}")

    # Статистика
    if results:
        avg_title = sum(len(r.get("title", "")) for r in results) / len(results)
        print(f"\n=== Статистика ===")
        print(f"Всего страниц: {len(results)}")
        print(f"Средняя длина title: {avg_title:.0f} символов")


if __name__ == "__main__":
    main()
