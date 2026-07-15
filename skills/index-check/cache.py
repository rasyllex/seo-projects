"""
Кэширование результатов в JSON.
TTL: 24 часа.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# Путь к кэшу: data/index-check/cache.json
CACHE_FILE = Path(__file__).parents[2] / "data" / "index-check" / "cache.json"
CACHE_TTL = timedelta(hours=24)


def load_cache():
    """Загружает кэш из файла."""
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_cache(cache):
    """Сохраняет кэш в файл."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def is_cache_valid(entry):
    """Проверяет, не просрочен ли кэш."""
    if "date" not in entry:
        return False
    try:
        cached_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
        return datetime.now().date() - cached_date < CACHE_TTL
    except ValueError:
        return False
