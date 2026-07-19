"""
HTML-кэш: сохранение и загрузка по URL.
"""

import os
import hashlib
from pathlib import Path

# Адаптированный путь: D:\projects\seo-agency\data\crawler-requests\cache\
CACHE_DIR = Path(__file__).parents[2] / "data" / "crawler-requests" / "cache"


def _get_safe_filename(url):
    """Генерирует безопасное имя файла из URL."""
    return hashlib.md5(url.encode()).hexdigest() + ".html"


def get_cache_path(url, domain):
    """Возвращает путь к файлу кэша."""
    domain_dir = CACHE_DIR / domain.replace(":", "_")
    domain_dir.mkdir(parents=True, exist_ok=True)
    return domain_dir / _get_safe_filename(url)


def save_html_cache(url, html, domain):
    """Сохраняет HTML в кэш."""
    path = get_cache_path(url, domain)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def load_html_cache(url, domain):
    """Загружает HTML из кэша или возвращает None."""
    path = get_cache_path(url, domain)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None
