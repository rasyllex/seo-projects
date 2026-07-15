"""
Модуль запросов к XMLRiver API.

Архитектура: один SERP — источник для всего. `fetch_serps()` тянет выдачу один
раз на ключ+ПС+гео, парсит её в структуру {organic, features} и кэширует.
Из готового SERP считаются: позиции, конкуренты, сниппеты, n-граммы, фичи —
без повторных запросов. Ошибочные ответы в кэш НЕ попадают.
"""

import os
import random
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm
from dotenv import load_dotenv

from cache import serp_key, get_serp, put_serp, save_cache
from serp_parse import parse_serp
import pandas as pd

from text_miner import (
    snippet_ngrams_wide, title_ngrams_wide, url_champions, _doc_highlights,
)
from clusterer import build_clusters, cluster_map, clusters_rows

load_dotenv(Path(__file__).parents[2] / "configs" / "positions" / "config.env")

XMLRIVER_YANDEX_URL = "https://xmlriver.com/yandex/xml"
XMLRIVER_GOOGLE_URL = "https://xmlriver.com/search/xml"

GOOGLE_LOC_DEFAULT = os.getenv("GOOGLE_LOC", "1011969")       # Москва (Criteria ID)
GOOGLE_LR_DEFAULT = os.getenv("GOOGLE_LR", "ru")
GOOGLE_COUNTRY_DEFAULT = os.getenv("GOOGLE_COUNTRY", "2643")  # Россия

YANDEX_RETRIES = 3
GOOGLE_RETRIES = 5
GOOGLE_PAGES = 3            # страницы 1..3 (XMLRiver нумерует с 1)
SAVE_EVERY = 20


# ============================ утилиты домена ============================

def _normalize_domain(domain: str) -> str:
    d = domain.strip().lower()
    if d.startswith("http://"):
        d = d[7:]
    elif d.startswith("https://"):
        d = d[8:]
    d = d.split("/")[0].split("?")[0].split("#")[0]
    if ":" in d:
        d = d.split(":")[0]
    if d.startswith("www."):
        d = d[4:]
    return d


def _domain_matches(url: str, target: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host == target or host.endswith("." + target)
    except Exception:
        return False


def _keys():
    user_id = os.getenv("XMLRIVER_USER_ID")
    api_key = os.getenv("XMLRIVER_API_KEY")
    if not user_id or not api_key:
        raise ValueError("Не заданы XMLRIVER_USER_ID или XMLRIVER_API_KEY в config.env")
    return user_id, api_key


# ============================ SERP: реальные запросы ============================
# Возвращают структуру {organic, features} при успехе, None при сбое (не кэшируется).

def _fetch_serp_yandex(keyword, region):
    user_id, api_key = _keys()
    params = {"user": user_id, "key": api_key, "query": keyword, "lr": region, "groupby": 100}
    for attempt in range(YANDEX_RETRIES):
        try:
            resp = requests.get(XMLRIVER_YANDEX_URL, params=params, timeout=90)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            err = (root.find("response") or root).find("error")
            if err is not None:
                print(f"  [WARN] XMLRiver Яндекс '{keyword}': {err.get('code','?')} {(err.text or '').strip()}")
                time.sleep(2 * (attempt + 1))
                continue
            return parse_serp(resp.content, "yandex")
        except requests.RequestException as e:
            print(f"  [WARN] Сеть Яндекс '{keyword}' ({attempt + 1}/{YANDEX_RETRIES}): {e}")
            time.sleep(2 * (attempt + 1))
        except ET.ParseError as e:
            print(f"  [WARN] XML Яндекс '{keyword}': {e}")
            return None
    return None


def _google_page(keyword, loc, country, page):
    """Одна страница Google. Возвращает (content|None, ok). ok=False — фатальный сбой."""
    user_id, api_key = _keys()
    params = {
        "user": user_id, "key": api_key, "query": keyword,
        "loc": loc or GOOGLE_LOC_DEFAULT,
        "country": country or GOOGLE_COUNTRY_DEFAULT,
        "lr": GOOGLE_LR_DEFAULT,
        "page": page,
    }
    for attempt in range(GOOGLE_RETRIES):
        try:
            resp = requests.get(XMLRIVER_GOOGLE_URL, params=params, timeout=20)
            resp.raise_for_status()
            if not resp.content.strip():
                raise ET.ParseError("пустой ответ")
            root = ET.fromstring(resp.content)
            err = (root.find("response") or root).find("error")
            if err is not None:
                code = err.get("code", "?")
                if code in ("500", "111", "32", "33"):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                print(f"  [WARN] XMLRiver Google '{keyword}' (page {page}): {code} {(err.text or '').strip()}")
                return None, False
            return resp.content, True
        except requests.RequestException as e:
            print(f"  [WARN] Сеть Google '{keyword}' page {page} ({attempt + 1}/{GOOGLE_RETRIES}): {e}")
            time.sleep(1.5 * (attempt + 1))
        except ET.ParseError as e:
            print(f"  [WARN] XML Google '{keyword}' (page {page}): {e}")
            return None, False
    return None, False


def _fetch_serp_google(keyword, loc, country):
    merged = {"organic": [], "features": {}}
    for page in range(1, GOOGLE_PAGES + 1):
        content, ok = _google_page(keyword, loc, country, page)
        if not ok:
            return None
        if content is None:
            break
        serp = parse_serp(content, "google")
        if not serp["organic"]:
            break
        merged["organic"].extend(serp["organic"])
        if page == 1:                       # фичи (related/PAA/KG) — на первой странице
            merged["features"] = serp["features"]
        time.sleep(0.3)
    for i, o in enumerate(merged["organic"], start=1):   # сквозная нумерация
        o["pos"] = i
    return merged


def _mock_serp(engine, mock_domain=None):
    """Фейковый SERP для мок-режима (иногда содержит целевой домен)."""
    hit = random.randint(1, 30) if (mock_domain and random.random() < 0.6) else -1
    organic = []
    for i in range(1, 31):
        url = f"https://{mock_domain}/" if i == hit else f"https://example-{engine}-{i}.com/"
        organic.append({
            "pos": i, "url": url, "domain": _normalize_domain(url),
            "title": f"Пример {i}: купить окна в москве недорого с установкой",
            "snippet": "Компания продаёт пластиковые окна в москве по низкой цене с установкой и доставкой",
            "highlights": ["окна", "москве"], "cache": "", "breadcrumbs": "",
        })
    return {"organic": organic, "features": {}}


# ============================ Оркестрация SERP ============================

def fetch_serps(keywords, engine="yandex", region=213, google_loc=None, google_country=None,
                use_real=False, cache=None, max_workers=8, mock_domain=None):
    """Тянет SERP по каждому ключу (с кэшем). Возвращает список (keyword, serp|None)."""
    if cache is None:
        cache = {}
    geo = str(region) if engine == "yandex" \
        else f"{google_loc or GOOGLE_LOC_DEFAULT}:{google_country or GOOGLE_COUNTRY_DEFAULT}"
    lock = threading.Lock()
    results = [None] * len(keywords)
    done = {"n": 0}

    def work(i, keyword):
        if not use_real:                    # мок не трогает кэш
            time.sleep(0.02)
            return i, keyword, _mock_serp(engine, mock_domain)

        key = serp_key(keyword, geo, engine)
        with lock:
            cached = get_serp(cache, key)
        if cached is not None:
            return i, keyword, cached

        serp = _fetch_serp_google(keyword, google_loc, google_country) if engine == "google" \
            else _fetch_serp_yandex(keyword, region)

        if serp is not None:
            with lock:
                put_serp(cache, key, serp)
                done["n"] += 1
                if done["n"] % SAVE_EVERY == 0:
                    save_cache(cache)
        time.sleep(0.15)
        return i, keyword, serp

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(work, i, kw) for i, kw in enumerate(keywords)]
        for future in tqdm(as_completed(futures), total=len(keywords), desc=f"SERP ({engine})"):
            i, keyword, serp = future.result()
            results[i] = (keyword, serp)
    return results


# ============================ Из SERP → таблицы ============================

def positions_from_serps(serps, domain):
    """position: >0 — позиция, 0 — не найден, -1 — запрос не удался."""
    target = _normalize_domain(domain)
    today = datetime.now().strftime("%Y-%m-%d")
    out = []
    for keyword, serp in serps:
        if serp is None:
            out.append({"keyword": keyword, "position": -1, "url": "", "date": today})
            continue
        pos, found = 0, ""
        for o in serp["organic"]:
            if _domain_matches(o["url"], target):
                pos, found = o["pos"], o["url"]
                break
        out.append({"keyword": keyword, "position": pos, "url": found, "date": today})
    return out


def competitors_from_serps(serps, top_n=10):
    out = []
    for keyword, serp in serps:
        row = {"keyword": keyword}
        org = serp["organic"] if serp else []
        for i in range(1, top_n + 1):
            row[f"url_{i}"] = org[i - 1]["url"] if i <= len(org) else ""
        out.append(row)
    return out


def snippets_from_serps(serps, kw2cluster=None):
    """Плоская таблица: cluster, keyword, pos, domain, url, title, highlights.
    Подсветки: родные (Яндекс) или синтетические по словам запроса (Google)."""
    kw2cluster = kw2cluster or {}
    out = []
    for keyword, serp in serps:
        if not serp:
            continue
        for o in serp["organic"]:
            out.append({
                "cluster": kw2cluster.get(keyword, ""),
                "keyword": keyword, "pos": o["pos"], "domain": _normalize_domain(o["url"]),
                "url": o["url"], "title": o["title"],
                "highlights": ", ".join(_doc_highlights(keyword, o)),
            })
    return out


def clusters_from_serps(serps, method="middle", threshold=4, depth=20, url_map=None):
    """Кластеризация по ТОПам. Возвращает (кластеры, {kw: вершина}, строки листа).
    url_map: {keyword: url нашего сайта} — попадает в лист clusters_<engine>."""
    clusters = build_clusters(serps, method=method, threshold=threshold, depth=depth)
    return clusters, cluster_map(clusters), clusters_rows(clusters, url_map)


def _by_cluster(serps, clusters, extract, build):
    """Общий каркас: агрегат `build(extract(...))` отдельно по каждому кластеру,
    результат — одна таблица с колонкой cluster (вершина кластера)."""
    frames = []
    for c in clusters:
        member = set(c["keywords"])
        items = [extract(o) for kw, s in serps if s and kw in member
                 for o in s["organic"] if extract(o)]
        df = build(items)
        if len(df):
            df.insert(0, "cluster", c["vertex"])
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def ngrams_from_serps(serps, clusters):
    """n-граммы сниппетов (1/2/3, широкая раскладка) — внутри каждого кластера."""
    return _by_cluster(serps, clusters,
                       lambda o: o.get("snippet"), snippet_ngrams_wide)


def title_freq_from_serps(serps, clusters):
    """n-граммы по леммам title (1/2/3, широкая раскладка) — внутри каждого кластера."""
    return _by_cluster(serps, clusters,
                       lambda o: o.get("title"), title_ngrams_wide)


def highlights_from_serps(serps, clusters):
    """Подсветки, ранжированные внутри каждого кластера: cluster, highlight, freq.
    Яндекс — родная разметка, Google — синтетика по словам запроса."""
    from collections import Counter
    rows = []
    for c in clusters:
        member = set(c["keywords"])
        cnt = Counter()
        for kw, s in serps:
            if not s or kw not in member:
                continue
            for o in s["organic"]:
                for w in _doc_highlights(kw, o):
                    wl = w.strip().lower()
                    if wl:
                        cnt[wl] += 1
        for w, f in cnt.most_common():
            rows.append({"cluster": c["vertex"], "highlight": w, "freq": f})
    return rows


def url_champions_from_serps(serps_by_engine):
    """url-чемпионы: частота url в ТОПе по всем ключам и ПС (глобальный список)."""
    return url_champions(serps_by_engine)


def url_champions_by_cluster(serps, clusters):
    """url-чемпионы внутри каждого кластера: cluster, url, title, count."""
    from collections import Counter
    rows = []
    for c in clusters:
        member = set(c["keywords"])
        cnt = Counter()
        titles = {}
        for kw, s in serps:
            if not s or kw not in member:
                continue
            for o in s["organic"]:
                u = (o.get("url") or "").strip()
                if not u:
                    continue
                cnt[u] += 1
                if u not in titles and o.get("title"):
                    titles[u] = o["title"]
        for u, n in cnt.most_common():
            rows.append({"cluster": c["vertex"], "url": u,
                         "title": titles.get(u, ""), "count": n})
    return rows


def features_from_serps(serps):
    """Google-фичи в длинную таблицу: keyword, feature, value."""
    out = []
    for keyword, serp in serps:
        if not serp:
            continue
        f = serp.get("features", {})
        for q in f.get("related_searches", []):
            out.append({"keyword": keyword, "feature": "related_search", "value": q})
        for p in f.get("paa", []):
            out.append({"keyword": keyword, "feature": "paa", "value": p["question"]})
        for k, v in f.get("knowledge_graph", {}).items():
            out.append({"keyword": keyword, "feature": f"knowledge:{k}", "value": v})
    return out
