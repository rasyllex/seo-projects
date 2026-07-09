"""
Скилл: Съём позиций
Точка входа. Оркестратор.
"""

import argparse
import io
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# На Windows консоль по умолчанию использует cp1252,
# что ломает вывод кириллицы. Переключаем stdout/stderr на UTF-8.
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fetcher import fetch_positions, fetch_competitors
from cache import load_cache, save_cache
from validate_input import validate_excel
from region_resolver import resolve


def _resolve_city(city_name, engine):
    """
    Разрешает название города в код региона.
    Возвращает (region_id, region_name) или (None, None) при неудаче.
    При нескольких совпадениях выводит список и возвращает (None, None).
    """
    matches = resolve(city_name, engine=engine)
    if not matches:
        print(f"[ERROR] Город/регион '{city_name}' не найден в справочнике {engine}.")
        return None, None

    if len(matches) > 1:
        print(f"[ERROR] Найдено несколько совпадений для '{city_name}' в {engine}:")
        for rid, name in matches:
            print(f"  {rid}: {name}")
        print("Уточните название или используйте --region <код>")
        return None, None

    return matches[0]


def main():
    parser = argparse.ArgumentParser(description="Съём позиций через XMLRiver")
    parser.add_argument("--input", required=True, help="Excel с колонкой keyword")
    parser.add_argument("--domain", required=True, help="Домен для проверки")
    parser.add_argument("--region", default=213, type=int, help="Код региона Яндекса (213 = Москва)")
    parser.add_argument(
        "--city",
        help="Название города/региона, например 'Ростов на дону'. Альтернатива --region."
    )
    parser.add_argument("--engine", default="yandex", choices=["yandex", "google"], help="Поисковая система (игнорируется при --competitors)")
    parser.add_argument("--real", action="store_true", help="Использовать реальный API (иначе мок)")
    parser.add_argument("--output", default="data/output.xlsx", help="Путь к выходному Excel")
    parser.add_argument(
        "--threads",
        default=8,
        type=int,
        help="Количество потоков для параллельных запросов (по умолчанию: 8)"
    )
    parser.add_argument(
        "--competitors",
        action="store_true",
        help="Собрать ТОП-10 конкурентов по Яндексу и Google. Создаёт 4 листа: positions_yandex, positions_google, competitors_yandex, competitors_google"
    )
    parser.add_argument(
        "--top-n",
        default=10,
        type=int,
        help="Количество конкурентов для сбора (по умолчанию: 10)"
    )
    args = parser.parse_args()

    # 1. Валидация входных данных
    print("-> Валидация входных данных...")
    is_valid, error_msg = validate_excel(args.input)
    if not is_valid:
        print(f"[ERROR] Ошибка валидации: {error_msg}")
        return
    print("[OK] Входные данные корректны")

    # 2. Загрузка ключей
    df = pd.read_excel(args.input)
    keywords = df["keyword"].dropna().astype(str).tolist()
    print(f"-> Ключей для проверки: {len(keywords)}")

    # 3. Разрешение региона по названию города
    region_yandex = args.region
    region_google = None

    if args.city:
        if args.competitors or args.engine == "yandex":
            rid, name = _resolve_city(args.city, "yandex")
            if rid is None:
                return
            region_yandex = rid
            print(f"-> Регион Яндекса: {name} (id={region_yandex})")

        if args.competitors or args.engine == "google":
            rid, name = _resolve_city(args.city, "google")
            if rid is not None:
                region_google = rid
                print(f"-> Регион Google: {name} (id={region_google})")
            else:
                print(f"[WARN] Для Google не удалось разрешить город '{args.city}'. Будет использован регион по умолчанию.")

    # 4. Загрузка кэша
    cache = load_cache()

    # 5. Получение позиций
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.competitors:
        print(f"-> Проверка позиций для домена: {args.domain} (Яндекс + Google)")

        positions_yandex = fetch_positions(
            keywords=keywords,
            domain=args.domain,
            region=region_yandex,
            engine="yandex",
            use_real=args.real,
            cache=cache,
            max_workers=args.threads
        )
        positions_google = fetch_positions(
            keywords=keywords,
            domain=args.domain,
            region=region_yandex,
            engine="google",
            use_real=args.real,
            cache=cache,
            max_workers=args.threads,
            google_loc=region_google
        )

        print(f"-> Сбор ТОП-{args.top_n} конкурентов по Яндексу...")
        competitors_yandex = fetch_competitors(
            keywords=keywords,
            region=region_yandex,
            engine="yandex",
            top_n=args.top_n,
            max_workers=args.threads,
            use_real=args.real
        )

        print(f"-> Сбор ТОП-{args.top_n} конкурентов по Google...")
        competitors_google = fetch_competitors(
            keywords=keywords,
            region=region_yandex,
            engine="google",
            top_n=args.top_n,
            max_workers=args.threads,
            use_real=args.real,
            google_loc=region_google
        )

        # 6. Сохранение кэша
        save_cache(cache)

        # 7. Сохранение результатов
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            pd.DataFrame(positions_yandex).to_excel(writer, sheet_name="positions_yandex", index=False)
            pd.DataFrame(positions_google).to_excel(writer, sheet_name="positions_google", index=False)
            pd.DataFrame(competitors_yandex).to_excel(writer, sheet_name="competitors_yandex", index=False)
            pd.DataFrame(competitors_google).to_excel(writer, sheet_name="competitors_google", index=False)
        print(f"[OK] Результат сохранён: {output_path} (positions_yandex, positions_google, competitors_yandex, competitors_google)")

        # 8. Статистика
        print("\n=== Статистика Яндекс ===")
        _print_stats(positions_yandex)
        print("\n=== Статистика Google ===")
        _print_stats(positions_google)
    else:
        print(f"-> Проверка позиций для домена: {args.domain} (движок: {args.engine})")

        if args.engine == "google":
            results = fetch_positions(
                keywords=keywords,
                domain=args.domain,
                region=region_yandex,
                engine=args.engine,
                use_real=args.real,
                cache=cache,
                max_workers=args.threads,
                google_loc=region_google
            )
        else:
            results = fetch_positions(
                keywords=keywords,
                domain=args.domain,
                region=region_yandex,
                engine=args.engine,
                use_real=args.real,
                cache=cache,
                max_workers=args.threads
            )

        # 6. Сохранение кэша
        save_cache(cache)

        # 7. Сохранение результатов
        pd.DataFrame(results).to_excel(output_path, index=False)
        print(f"[OK] Результат сохранён: {output_path}")

        # 8. Статистика
        print("\n=== Статистика ===")
        _print_stats(results)


def _print_stats(results):
    total = len(results)
    found = sum(1 for r in results if r["position"] > 0)
    top10 = sum(1 for r in results if 1 <= r["position"] <= 10)
    top100 = sum(1 for r in results if 1 <= r["position"] <= 100)
    avg_pos = sum(r["position"] for r in results if r["position"] > 0) / found if found else 0

    print(f"Всего ключей: {total}")
    print(f"Найдено в выдаче (ТОП-100): {found}")
    print(f"В ТОП-10: {top10}")
    print(f"В ТОП-100: {top100}")
    print(f"Средняя позиция: {avg_pos:.1f}")


if __name__ == "__main__":
    main()
