"""
SEO-обогащение страницы: индексируемость, canonical, meta robots, schema и пр.
Поля отобраны из полноценного тех-аудита — те, что извлекаются прямо при обходе,
без дополнительных запросов. Единый модуль для обоих краулеров (requests и Selenium).
"""

import json
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from lxml import html as lxml_html


def normalize_link(href, base_url):
    """Единая нормализация ссылки (одинаковая в обоих краулерах).
    Абсолютный URL того же хоста; схема приводится к схеме старта (http↔https
    не двоятся), якорь убирается, query СОХРАНЯЕТСЯ. None — чужой хост/не http(s)."""
    if "://" not in base_url:
        base_url = "https://" + base_url
    base = urlparse(base_url)
    u = urlparse(urljoin(base_url, (href or "").strip()))
    if u.scheme not in ("http", "https") or u.netloc.lower() != base.netloc.lower():
        return None
    norm = f"{base.scheme}://{u.netloc.lower()}{u.path or '/'}"
    if u.query:
        norm += "?" + u.query
    return norm


def extract_links(html, base_url):
    """Внутренние ссылки, нормализованные единообразно, без дублей, порядок сохранён."""
    soup = BeautifulSoup(html or "", "lxml")
    out, seen = [], set()
    for tag in soup.find_all("a", href=True):
        link = normalize_link(tag["href"], base_url)
        if link and link not in seen:
            seen.add(link)
            out.append(link)
    return out

# Порядок колонок в итоговом Excel (общий для обоих краулеров)
COLUMNS = [
    "url", "status_code", "content_type", "indexable", "indexability_status",
    "meta_robots", "canonical", "title", "h1", "h2", "description",
    "word_count", "size_bytes", "crawl_depth", "schema_types",
    "response_time", "html_file",
]


def _norm(url):
    """Нормализует URL для сравнения canonical (без хвостового слэша, без якоря)."""
    if not url:
        return ""
    p = urlparse(url.strip())
    path = p.path.rstrip("/") or "/"
    return f"{p.scheme}://{p.netloc.lower()}{path}"


def _indexability(status_code, meta_robots, x_robots, canonical, url, robots_blocked=False):
    """Открыта ли страница для индексации и почему нет.
    Порядок проверок: статус → meta/заголовок noindex → robots.txt → canonical.
    Возвращает ('Да'|'Нет', причина)."""
    robots = f"{meta_robots or ''} {x_robots or ''}".lower()
    if status_code and status_code >= 400:
        return "Нет", f"HTTP {status_code}"
    if status_code and 300 <= status_code < 400:
        return "Нет", "Redirect"
    if "noindex" in robots:                       # 1) meta robots + X-Robots-Tag
        return "Нет", "noindex"
    if robots_blocked:                            # 2) запрет в robots.txt (Disallow)
        return "Нет", "Blocked by robots.txt"
    if canonical and _norm(canonical) != _norm(url):
        return "Нет", "Canonicalised"
    return "Да", ""


def _schema_types(soup):
    """Типы Schema.org: из JSON-LD (@type) и микроразметки (itemtype)."""
    types = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in (data if isinstance(data, list) else [data]):
            if isinstance(node, dict):
                t = node.get("@type")
                if isinstance(t, list):
                    types.extend(t)
                elif t:
                    types.append(t)
    for tag in soup.find_all(attrs={"itemtype": True}):
        types.append(tag["itemtype"].rstrip("/").split("/")[-1])
    seen, out = set(), []
    for t in types:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return ", ".join(out)


def parse_xpath_args(pairs):
    """['price=//span[@class="price"]/text()', ...] → {'price': '//span...'}.
    Формат: имя_колонки=выражение. Первое '=' разделяет имя и XPath."""
    out = {}
    for item in pairs or []:
        if "=" not in item:
            raise ValueError(f"XPath без имени: {item!r}. Формат: имя=//выражение")
        name, expr = item.split("=", 1)
        name = name.strip()
        if name and expr.strip():
            out[name] = expr.strip()
    return out


def apply_xpath(html, xpath_map):
    """Применяет пользовательские XPath. Значения нескольких узлов склеиваются ' | '."""
    if not xpath_map:
        return {}
    try:
        tree = lxml_html.fromstring(html or "<html></html>")
    except Exception:
        return {name: "" for name in xpath_map}
    result = {}
    for name, expr in xpath_map.items():
        try:
            nodes = tree.xpath(expr)
        except Exception as e:
            result[name] = f"[ошибка XPath: {e}]"
            continue
        vals = []
        for n in nodes:
            text = n if isinstance(n, str) else (n.text_content() if hasattr(n, "text_content") else str(n))
            text = " ".join(text.split())
            if text:
                vals.append(text)
        result[name] = " | ".join(vals)
    return result


def extract_page(html, url, status_code=200, content_type="",
                 x_robots="", response_time=None, crawl_depth=None,
                 html_file=None, xpath_map=None, robots_blocked=False):
    """Полная строка реестра по одной странице (зоны + SEO-поля + кастомные XPath)."""
    soup = BeautifulSoup(html or "", "lxml")

    title = soup.title.get_text(strip=True) if soup.title else ""
    h1 = soup.h1.get_text(strip=True) if soup.h1 else ""
    h2 = " | ".join(t.get_text(strip=True) for t in soup.find_all("h2"))
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else ""

    robots_tag = soup.find("meta", attrs={"name": "robots"})
    meta_robots = robots_tag["content"].strip() if robots_tag and robots_tag.get("content") else ""

    can_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical = can_tag["href"].strip() if can_tag and can_tag.get("href") else ""

    indexable, status = _indexability(status_code, meta_robots, x_robots, canonical, url,
                                      robots_blocked=robots_blocked)

    body = soup.find("body") or soup
    for junk in body.find_all(["script", "style", "noscript"]):
        junk.extract()
    word_count = len(body.get_text(" ", strip=True).split())

    row = {
        "url": url,
        "status_code": status_code,
        "content_type": content_type,
        "indexable": indexable,
        "indexability_status": status,
        "meta_robots": meta_robots,
        "canonical": canonical,
        "title": title,
        "h1": h1,
        "h2": h2,
        "description": description,
        "word_count": word_count,
        "size_bytes": len(html or ""),
        "schema_types": _schema_types(soup),
    }
    if crawl_depth is not None:
        row["crawl_depth"] = crawl_depth
    if response_time is not None:
        row["response_time"] = response_time
    if html_file is not None:
        row["html_file"] = html_file
    row.update(apply_xpath(html, xpath_map))     # кастомные колонки — в конец
    return row
