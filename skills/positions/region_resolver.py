"""
Разрешение названий городов/регионов в коды для Яндекса и Google.

Использует справочники из knowledge_base/:
- yandex_regions.csv — для Яндекса
- google_geo.csv — для Google
"""

import csv
import difflib
import re
from pathlib import Path

KNOWLEDGE_BASE = Path(__file__).parent.parent.parent / "knowledge_base" / "positions"


def _normalize(text):
    """Приводит строку к нижнему регистру, убирает лишние пробелы, ё->е."""
    text = str(text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("ё", "е")
    return text


def _normalize_loose(text):
    """Убирает пробелы и дефисы для нечёткого сравнения."""
    return _normalize(text).replace(" ", "").replace("-", "")


def resolve_yandex(city_name):
    """
    Возвращает список кортежей (region_id, name) по названию города/региона.
    Сначала ищет точное совпадение, затем по подстроке.
    """
    path = KNOWLEDGE_BASE / "yandex_regions.csv"
    query = _normalize(city_name)
    query_loose = _normalize_loose(city_name)

    exact = []
    partial = []

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = int(row["id"])
            name = row["city_name"].strip()
            city_norm = _normalize(row["city_name"])
            lemma_norm = _normalize(row["lemmatized_city"])
            city_loose = _normalize_loose(row["city_name"])
            lemma_loose = _normalize_loose(row["lemmatized_city"])

            if query == city_norm or query == lemma_norm:
                exact.append((rid, name))
            elif query_loose == city_loose or query_loose == lemma_loose:
                exact.append((rid, name))
            elif query in city_norm or query in lemma_norm:
                partial.append((rid, name))
            elif query_loose in city_loose or query_loose in lemma_loose:
                partial.append((rid, name))

    results = exact or partial
    seen = set()
    unique = []
    for rid, name in results:
        if rid not in seen:
            seen.add(rid)
            unique.append((rid, name))
    return unique


def _translit(text):
    """Простая транслитерация русского текста в латиницу."""
    mapping = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    result = []
    for ch in text.lower():
        if ch in mapping:
            result.append(mapping[ch])
        elif ch.isalnum() or ch in " -":
            result.append(ch)
    return "".join(result).strip()


def resolve_google(city_name):
    """
    Пытается найти Criteria ID города в Google-справочнике.
    Использует транслитерацию, подстроковый поиск и fuzzy matching.
    Возвращает список кортежей (criteria_id, name).
    """
    path = KNOWLEDGE_BASE / "google_geo.csv"
    base = _translit(city_name).lower()
    base_no_hyphens = base.replace("-", "").replace(" ", "")

    queries = {
        base,
        base_no_hyphens,
        base.replace("-na-", "-on-"),
        base.replace(" na ", " on "),
        base_no_hyphens.replace("na", "on"),
        re.sub(r"\s+", "-", base),
        re.sub(r"\s+", " ", base),
    }
    queries = {q.strip() for q in queries if q.strip()}

    names = []
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Country Code") != "RU" or row.get("Target Type") != "City":
                continue
            if row.get("Status") != "Active":
                continue
            name = row["Name"].strip()
            names.append(name.lower())
            rows.append(row)

    # Сначала пробуем точное/подстроковое совпадение
    for i, name in enumerate(names):
        name_raw = name.replace("-", "").replace(" ", "")
        for q in queries:
            q_raw = q.replace("-", "").replace(" ", "")
            if q in name or q_raw in name_raw:
                return [(int(rows[i]["Criteria ID"]), rows[i]["Name"])]

    # Fuzzy matching по всем городам России
    normalized_names = [n.replace("-", "").replace(" ", "") for n in names]
    close = []
    if base_no_hyphens:
        close = difflib.get_close_matches(base_no_hyphens, normalized_names, n=3, cutoff=0.75)

    matches = []
    for c in close:
        idx = normalized_names.index(c)
        cid = int(rows[idx]["Criteria ID"])
        matches.append((cid, rows[idx]["Name"]))

    # Убираем дубликаты
    seen = set()
    unique = []
    for cid, name in matches:
        if cid not in seen:
            seen.add(cid)
            unique.append((cid, name))
    return unique


def resolve(city_name, engine="yandex"):
    """Универсальная функция разрешения региона."""
    if engine == "yandex":
        return resolve_yandex(city_name)
    return resolve_google(city_name)
