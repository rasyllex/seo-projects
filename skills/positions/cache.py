"""
Кэширование результатов в JSON.
TTL: 24 часа.
"""

import json
import os
from datetime import datetime, timedelta

CACHE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "positions", "cache.json"))
CACHE_TTL = timedelta(hours=24)


def load_cache():
    """Загружает кэш из файла."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_cache(cache):
    """Сохраняет кэш в файл."""
    os.makedirs(os.path.dirname(CACHE_FILE) or ".", exist_ok=True)
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


def get_cached(keyword, region, engine="yandex", domain="", cache=None):
    """Возвращает позицию из кэша или None."""
    if cache is None:
        cache = load_cache()
    key = f"{keyword}_{region}_{engine}_{domain}"
    if key in cache and is_cache_valid(cache[key]):
        return cache[key]["position"], cache[key].get("url", "")
    return None


def set_cached(keyword, region, engine, domain, position, url="", cache=None):
    """Сохраняет позицию и URL в кэш."""
    if cache is None:
        cache = load_cache()
    key = f"{keyword}_{region}_{engine}_{domain}"
    cache[key] = {
        "position": position,
        "url": url,
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    save_cache(cache)
