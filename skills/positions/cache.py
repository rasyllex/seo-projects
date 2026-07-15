"""
Кэширование ПОИСКОВОЙ ВЫДАЧИ (SERP) в JSON.

Кэшируем сам список URL, а НЕ вычисленную позицию. Тогда из одного SERP
считаются и позиция любого домена, и конкуренты — кэш переиспользуется.
Ключ не содержит домен. TTL: 24 часа (rolling, с точностью до секунды).
Ошибочные ответы (сетевые/API) в кэш НЕ кладутся — этим занимается fetcher.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

CACHE_FILE = Path(__file__).parents[2] / "data" / "positions" / "cache.json"
CACHE_TTL = timedelta(hours=24)
_TS_FMT = "%Y-%m-%dT%H:%M:%S"


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


def serp_key(keyword, geo, engine):
    """Ключ SERP-кэша. geo: Яндекс — region; Google — 'loc:country'."""
    return f"serp_{keyword}_{geo}_{engine}"


def is_cache_valid(entry):
    """Проверяет TTL записи (rolling 24 часа)."""
    ts = entry.get("ts")
    if not ts:
        return False
    try:
        return datetime.now() - datetime.strptime(ts, _TS_FMT) < CACHE_TTL
    except (ValueError, TypeError):
        return False


def get_serp(cache, key):
    """Возвращает закэшированную структуру SERP или None."""
    entry = cache.get(key)
    if entry and is_cache_valid(entry):
        return entry.get("serp")
    return None


def put_serp(cache, key, serp):
    """Кладёт структуру SERP в кэш (только для успешных ответов).

    serp = {"organic": [...], "features": {...}} — из неё считаются позиции,
    конкуренты, сниппеты, n-граммы и фичи (сырые данные, переиспользуются)."""
    cache[key] = {"serp": serp, "ts": datetime.now().strftime(_TS_FMT)}
