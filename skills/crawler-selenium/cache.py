"""
Кэш HTML-страниц для Selenium-краулера.
Формат единый с requests-краулером: data/html/<домен>/<md5(url)>.html
"""
import hashlib
from pathlib import Path


def cache_path(url, domain, base_dir):
    """Путь к файлу кэша для URL."""
    d = Path(base_dir) / domain.replace(":", "_")
    d.mkdir(parents=True, exist_ok=True)
    return d / (hashlib.md5(url.encode()).hexdigest() + ".html")


def save_html_cache(path: Path, html: str):
    """Сохраняет HTML на диск."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def load_html_cache(path: Path) -> str | None:
    """Загружает HTML из кэша, если есть."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None
