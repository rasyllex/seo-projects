"""
Скилл: Выгрузка Яндекс.Вебмастер
Точка входа.

Мок:   python run.py --host-id https:example.com:443
Реал:  python run.py --host-id https:example.com:443 --real
       (токен и user_id берутся из configs/webmaster/.env — см. README.md)
"""

import argparse
from pathlib import Path

from webmaster_client import (
    get_popular_queries,
    get_indexation_status,
    get_external_links,
)
from exporter import to_excel

BASE = Path(__file__).resolve().parents[2]            # корень проекта
ENV_PATH = BASE / "configs" / "webmaster" / ".env"
DEFAULT_OUT = BASE / "data" / "webmaster" / "webmaster.xlsx"


def load_env(path):
    """Простой парсер .env → dict (без внешних зависимостей)."""
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def main():
    parser = argparse.ArgumentParser(description="Выгрузка Яндекс.Вебмастер")
    parser.add_argument("--host-id", required=True, help="ID хоста (https:example.com:443)")
    parser.add_argument("--token", default=None, help="OAuth-токен (по умолчанию — из .env)")
    parser.add_argument("--output", default=str(DEFAULT_OUT), help="Путь к выходному Excel")
    parser.add_argument("--real", action="store_true", help="Использовать реальный API")
    parser.add_argument("--limit", type=int, default=None,
                        help="Максимум строк на лист (по умолчанию — всё, что отдаёт API)")
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    token = args.token or env.get("YANDEX_WEBMASTER_TOKEN")
    user_id = env.get("YANDEX_WEBMASTER_USER_ID")

    if args.real and (not token or not user_id):
        raise SystemExit(f"Для --real заполни токен и user_id в {ENV_PATH} (см. README.md)")

    print(f"-> Выгрузка Вебмастер для {args.host_id} ({'РЕАЛ' if args.real else 'мок'})")

    queries = get_popular_queries(args.host_id, token, user_id, limit=args.limit, use_real=args.real)
    indexation = get_indexation_status(args.host_id, token, user_id, limit=args.limit, use_real=args.real)
    links = get_external_links(args.host_id, token, user_id, limit=args.limit, use_real=args.real)

    print(f"-> Запросов: {len(queries)}")
    print(f"-> Страниц в поиске: {len(indexation)}")
    print(f"-> Ссылок: {len(links)}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    to_excel({"Запросы": queries, "Индексация": indexation, "Ссылки": links}, output_path)
    print(f"[OK] Результат сохранён: {output_path}")


if __name__ == "__main__":
    main()
