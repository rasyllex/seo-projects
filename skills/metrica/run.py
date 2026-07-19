"""
Скилл: Выгрузка Яндекс.Метрика
Точка входа.

Мок:   python run.py --counter-id 12345678
Реал:  python run.py --counter-id 12345678 --real
       Токен — из configs/metrica/.env. Счётчик — из --counter-id
       (в проде подтягивается из Паспорта проектов, не из .env).
"""

import argparse
from pathlib import Path
from datetime import datetime
import csv

from metrica_client import (
    get_visits_by_url, get_monthly_trend, get_goals,
    get_traffic_sources, get_search_phrases, get_by_device, get_geography,
    get_session_length_by_url, get_summary, get_search_engines,
    get_exit_pages, get_age_gender, get_new_vs_returning,
)
from exporter import to_excel

BASE = Path(__file__).resolve().parents[2]            # корень проекта
ENV_PATH = BASE / "configs" / "metrica" / ".env"
PASSPORT_PATH = BASE / "Паспорт проектов.csv"
DATA_DIR = BASE / "data" / "metrica"


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


def get_domain_by_counter(counter_id):
    """Получает домен из Паспорта проектов по counter_id."""
    if not PASSPORT_PATH.exists():
        return None
    
    try:
        with open(PASSPORT_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                if row.get('metrika_id') == str(counter_id):
                    return row.get('domain')
    except Exception as e:
        print(f"[WARN] Ошибка чтения Паспорта проектов: {e}")
    
    return None


def generate_output_filename(counter_id, days):
    """Генерирует имя файла: {алиас_сайта}_{дата}_{время}_{дней}d.xlsx"""
    domain = get_domain_by_counter(counter_id)
    
    if domain:
        # Алиас: domain без .ru/.com и т.д.
        alias = domain.split('.')[0]
    else:
        # Если домен не найден, используем counter_id
        alias = f"counter_{counter_id}"
    
    # Дата и время: YYYYMMDD_HH-MM (без секунд, с дефисом)
    timestamp = datetime.now().strftime("%Y%m%d_%H-%M")
    
    # Добавляем количество дней
    filename = f"{alias}_{timestamp}_{days}d.xlsx"
    return DATA_DIR / filename


def main():
    parser = argparse.ArgumentParser(description="Выгрузка Яндекс.Метрики")
    parser.add_argument("--counter-id", default=None, help="ID счётчика (по умолчанию — из .env)")
    parser.add_argument("--days", default=30, type=int, help="Период в днях")
    parser.add_argument("--output", default=None, help="Путь к выходному Excel (по умолчанию: {домен}_{дата}_{время}.xlsx)")
    parser.add_argument("--real", action="store_true", help="Использовать реальный API")
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    token = env.get("YANDEX_METRICA_TOKEN")
    counter_id = args.counter_id  # per-project — из Паспорта проектов / --counter-id, не из .env

    if not counter_id:
        raise SystemExit("Укажи счётчик: --counter-id 12345678 (в проде — из Паспорта проектов)")
    if args.real and not token:
        raise SystemExit(f"Для --real заполни YANDEX_METRICA_TOKEN в {ENV_PATH}")

    print(f"-> Выгрузка Метрики для счётчика {counter_id} ({'РЕАЛ' if args.real else 'мок'}, {args.days} дн.)")

    summary = get_summary(counter_id, token, days=args.days, use_real=args.real)
    visits = get_visits_by_url(counter_id, token, days=args.days, use_real=args.real)
    sessions = get_session_length_by_url(counter_id, token, days=args.days, use_real=args.real)
    sources = get_traffic_sources(counter_id, token, days=args.days, use_real=args.real)
    devices = get_by_device(counter_id, token, days=args.days, use_real=args.real)
    geo = get_geography(counter_id, token, days=args.days, use_real=args.real)
    search_engines = get_search_engines(counter_id, token, days=args.days, use_real=args.real)
    exit_pages = get_exit_pages(counter_id, token, days=args.days, use_real=args.real)
    age_gender = get_age_gender(counter_id, token, days=args.days, use_real=args.real)
    new_vs_returning = get_new_vs_returning(counter_id, token, days=args.days, use_real=args.real)
    phrases = get_search_phrases(counter_id, token, days=args.days, use_real=args.real)
    trend = get_monthly_trend(counter_id, token, months=12, use_real=args.real)
    goals = get_goals(counter_id, token, goal_id=1, days=args.days, use_real=args.real)

    print(f"-> URL: {len(visits)}, Страниц выхода: {len(exit_pages)}, Источников: {len(sources)}, "
          f"Устройств: {len(devices)}, Городов: {len(geo)}, Поисковиков: {len(search_engines)}, "
          f"Пол/возраст: {len(age_gender)}, Новые/Верн.: {len(new_vs_returning)}, "
          f"Запросов: {len(phrases)}, Месяцев: {len(trend)}, Целей: {len(goals)}")

    # Генерируем имя файла с алиасом домена, датой/временем и количеством дней
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = generate_output_filename(counter_id, args.days)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)

    to_excel({
        "Сводка": summary,
        "По URL": visits,
        "Страницы выхода": exit_pages,
        "Длина сессий": sessions,
        "Источники": sources,
        "Устройства": devices,
        "География": geo,
        "Поисковики": search_engines,
        "Пол и возраст": age_gender,
        "Новые vs Вернувшиеся": new_vs_returning,
        "Запросы": phrases,
        "По месяцам": trend,
        "Цели": goals,
    }, output_path)
    print(f"[OK] Результат сохранён: {output_path}")


if __name__ == "__main__":
    main()
