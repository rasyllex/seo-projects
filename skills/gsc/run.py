"""
Скилл: Выгрузка Google Search Console
Точка входа.

Мок:   python run.py --site https://example.com --start 2026-06-01 --end 2026-06-30
Реал:  python run.py --site https://example.com/ --start 2026-06-01 --end 2026-06-30 --real
       (креденшалы берутся из configs/gsc/ — token.json или service_account.json)
Сайты: python run.py --list-sites   (показать доступные ресурсы в GSC)

Выход: data/gsc/<алиас-домена>.xlsx — все отчёты вкладками
       (Сводка, Запросы, Страницы, Запрос+Страница, Динамика,
        Устройства, Страны, Вид в выдаче, Sitemaps)
"""

import argparse
import re
from pathlib import Path

from gsc_client import get_all_reports, authenticate, list_sites
from exporter import to_excel

BASE = Path(__file__).resolve().parents[2]            # корень проекта (seo-agency/)
CONFIG_DIR = BASE / "configs" / "gsc"
OUT_DIR = BASE / "data" / "gsc"


def site_alias(site_url):
    """https://example.com/ или sc-domain:example.com → example-com"""
    alias = site_url.replace("sc-domain:", "")
    alias = re.sub(r"^https?://", "", alias)
    alias = alias.strip("/").split("/")[0].removeprefix("www.")
    return re.sub(r"[^a-z0-9-]+", "-", alias.lower()).strip("-")


def build_summary(reports, site_url, start, end):
    """Сводный лист: итоги периода по данным отчёта «Динамика»."""
    days = reports.get("Динамика", [])
    clicks = sum(r["clicks"] for r in days)
    impressions = sum(r["impressions"] for r in days)
    weighted_pos = (sum(r["position"] * r["impressions"] for r in days) / impressions
                    if impressions else 0)
    by_traffic = lambda r: (r["clicks"], r["impressions"])
    top_query = max(reports.get("Запросы", []), key=by_traffic, default=None)
    top_page = max(reports.get("Страницы", []), key=by_traffic, default=None)

    rows = [
        {"Показатель": "Сайт", "Значение": site_url},
        {"Показатель": "Период", "Значение": f"{start} — {end}"},
        {"Показатель": "Клики", "Значение": clicks},
        {"Показатель": "Показы", "Значение": impressions},
        {"Показатель": "CTR", "Значение": f"{clicks / impressions * 100:.2f}%" if impressions else "—"},
        {"Показатель": "Средняя позиция (взвеш.)", "Значение": f"{weighted_pos:.1f}" if impressions else "—"},
        {"Показатель": "Уникальных запросов", "Значение": len(reports.get("Запросы", []))},
        {"Показатель": "Страниц с показами", "Значение": len(reports.get("Страницы", []))},
    ]
    if top_query:
        rows.append({"Показатель": "Топ-запрос по кликам",
                     "Значение": f"{top_query['query']} ({top_query['clicks']} кл.)"})
    if top_page:
        rows.append({"Показатель": "Топ-страница по кликам",
                     "Значение": f"{top_page['page']} ({top_page['clicks']} кл.)"})
    return rows


def main():
    parser = argparse.ArgumentParser(description="Выгрузка GSC (все отчёты)")
    parser.add_argument("--site", help="Ресурс в GSC: https://site.ru/ или sc-domain:site.ru")
    parser.add_argument("--start", help="Дата начала YYYY-MM-DD")
    parser.add_argument("--end", help="Дата окончания YYYY-MM-DD")
    parser.add_argument("--output", default=None,
                        help="Путь к Excel (по умолчанию data/gsc/<алиас-домена>.xlsx)")
    parser.add_argument("--real", action="store_true", help="Использовать реальный GSC API")
    parser.add_argument("--limit", type=int, default=None,
                        help="Максимум строк на отчёт (по умолчанию — всё)")
    parser.add_argument("--list-sites", action="store_true",
                        help="Показать сайты, доступные аккаунту в GSC, и выйти")
    args = parser.parse_args()

    if args.list_sites:
        service = authenticate(CONFIG_DIR)
        for url, perm in list_sites(service):
            print(f"{url}  ({perm})")
        return

    if not (args.site and args.start and args.end):
        parser.error("нужны --site, --start и --end (или --list-sites)")

    print(f"-> Выгрузка GSC для {args.site} ({'РЕАЛ' if args.real else 'мок'})")
    print(f"-> Период: {args.start} — {args.end}")

    reports = get_all_reports(
        site_url=args.site,
        start_date=args.start,
        end_date=args.end,
        use_real=args.real,
        config_dir=CONFIG_DIR,
        limit=args.limit,
    )

    sheets = {"Сводка": build_summary(reports, args.site, args.start, args.end), **reports}

    output_path = Path(args.output) if args.output else OUT_DIR / f"{site_alias(args.site)}.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    to_excel(sheets, output_path)

    print(f"[OK] Результат сохранён: {output_path}")
    print(f"\n=== Вкладки ===")
    for name, rows in sheets.items():
        print(f"{name}: {len(rows)} строк")


if __name__ == "__main__":
    main()
