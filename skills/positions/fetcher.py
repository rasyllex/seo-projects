"""
Модуль запросов к XMLRiver API.
Поддерживает мок-режим и реальные API Яндекса и Google.
Работает в многопоточном режиме через ThreadPoolExecutor.
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
from tqdm import tqdm

from dotenv import load_dotenv

from cache import is_cache_valid

# Загружаем config.env из папки скилла
config_path = Path(__file__).parent.parent.parent / "configs" / "positions" / "config.env"
load_dotenv(config_path)

XMLRIVER_YANDEX_URL = "https://xmlriver.com/yandex/xml"
XMLRIVER_GOOGLE_URL = "https://xmlriver.com/search/xml"

# Google: Moscow по умолчанию
GOOGLE_LOC_DEFAULT = os.getenv("GOOGLE_LOC", "1011969")
GOOGLE_LR_DEFAULT = os.getenv("GOOGLE_LR", "ru")


def fetch_positions(keywords, domain, region=213, engine="yandex", use_real=False, cache=None, max_workers=8, google_loc=None):
    """
    Проверяет позиции домена по списку ключей с использованием многопоточности.

    Args:
        keywords: список строк
        domain: строка (например, "example.com" или "https://www.example.com/")
        region: int (код региона Яндекса, 213 = Москва)
        engine: "yandex" или "google"
        use_real: bool (использовать реальный API)
        cache: dict (кэш из cache.py)
        max_workers: int, количество потоков (по умолчанию 8)

    Returns:
        список словарей [{"keyword": ..., "position": ..., "url": ..., "date": ...}]
    """
    if cache is None:
        cache = {}

    normalized_domain = _normalize_domain(domain)
    cache_lock = threading.Lock()
    results = [None] * len(keywords)

    tasks = [
        (i, keyword, normalized_domain, region, engine, use_real, cache, cache_lock, google_loc)
        for i, keyword in enumerate(keywords)
    ]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_process_keyword, task) for task in tasks]
        for future in tqdm(as_completed(futures), total=len(keywords), desc=f"Проверка позиций ({engine})"):
            idx, result = future.result()
            results[idx] = result

    return results


def _process_keyword(args):
    """Обрабатывает один keyword: кэш -> запрос -> сохранение."""
    idx, keyword, normalized_domain, region, engine, use_real, cache, cache_lock, google_loc = args
    cache_key = f"{keyword}_{region}_{engine}_{normalized_domain}"

    # Проверяем кэш
    with cache_lock:
        cached = cache.get(cache_key)
    if cached and is_cache_valid(cached):
        return idx, {
            "keyword": keyword,
            "position": cached["position"],
            "url": cached.get("url", ""),
            "date": cached["date"]
        }

    # Запрос позиции
    if use_real:
        position, found_url = _fetch_from_api(keyword, normalized_domain, region, engine, google_loc)
    else:
        position = _mock_position()
        found_url = ""

    result = {
        "keyword": keyword,
        "position": position,
        "url": found_url,
        "date": datetime.now().strftime("%Y-%m-%d")
    }

    # Сохраняем в кэш
    with cache_lock:
        cache[cache_key] = result

    # Небольшая задержка, чтобы не перегружать API
    time.sleep(0.1 if not use_real else 0.15)

    return idx, result


def _mock_position():
    """Генерирует случайную позицию для тестирования (1-100)."""
    return random.choice([0, 0, 3, 5, 7, 8, 10, 12, 15, 20, 35, 50, 65, 80, 95])


def _normalize_domain(domain: str) -> str:
    """Приводит домен к единому виду для сравнения.

    Поддерживает как чистый домен (example.com, www.example.com),
    так и полный URL (https://www.example.com/path).
    """
    d = domain.strip().lower()

    # Убираем протокол
    if d.startswith("http://"):
        d = d[7:]
    elif d.startswith("https://"):
        d = d[8:]

    # Убираем путь, параметры, порт
    d = d.split("/")[0].split("?")[0].split("#")[0]
    if ":" in d:
        d = d.split(":")[0]

    # Убираем www.
    if d.startswith("www."):
        d = d[4:]

    return d


def _domain_matches(url: str, target: str) -> bool:
    """Проверяет, что URL принадлежит целевому домену."""
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host == target or host.endswith("." + target)
    except Exception:
        return False


def _fetch_from_api(keyword, domain, region, engine, google_loc=None):
    """
    Реальный запрос к XMLRiver API.
    Возвращает кортеж (позиция домена, найденный URL) — (0, "") если не найден.
    """
    if engine == "google":
        return _fetch_google(keyword, domain, google_loc)
    return _fetch_yandex(keyword, domain, region)


def _fetch_yandex(keyword, domain, region):
    """Запрос позиции в Яндексе через XMLRiver."""
    import requests

    user_id = os.getenv("XMLRIVER_USER_ID")
    api_key = os.getenv("XMLRIVER_API_KEY")

    if not user_id or not api_key:
        raise ValueError("Не заданы XMLRIVER_USER_ID или XMLRIVER_API_KEY в config.env")

    params = {
        "user": user_id,
        "key": api_key,
        "query": keyword,
        "lr": region,
        "groupby": 100,  # ТОП-100 за один запрос
    }

    for attempt in range(3):
        try:
            response = requests.get(XMLRIVER_YANDEX_URL, params=params, timeout=90)
            response.raise_for_status()
            return _parse_xml_for_position_and_url(response.content, domain)
        except requests.RequestException as e:
            print(f"  [WARN] Ошибка запроса для '{keyword}' (попытка {attempt + 1}/3): {e}")
            time.sleep(2 * (attempt + 1))
        except ET.ParseError as e:
            print(f"  [WARN] Ошибка парсинга XML для '{keyword}': {e}")
            return 0, ""
    return 0, ""


def _fetch_google(keyword, domain, google_loc=None):
    """Запрос позиции в Google через XMLRiver. Google отдаёт ~10 URL за страницу."""
    import requests

    user_id = os.getenv("XMLRIVER_USER_ID")
    api_key = os.getenv("XMLRIVER_API_KEY")

    if not user_id or not api_key:
        raise ValueError("Не заданы XMLRIVER_USER_ID или XMLRIVER_API_KEY в config.env")

    target_domain = _normalize_domain(domain)
    collected = 0

    # Ходим по страницам, пока не найдём домен или не соберём 30 результатов
    for page in range(3):
        params = {
            "user": user_id,
            "key": api_key,
            "query": keyword,
            "loc": google_loc if google_loc else GOOGLE_LOC_DEFAULT,
            "lr": GOOGLE_LR_DEFAULT,
            "page": page,
        }

        # Ретраи при временных ошибках XMLRiver (500, 111)
        last_err = None
        for attempt in range(2):
            try:
                response = requests.get(XMLRIVER_GOOGLE_URL, params=params, timeout=20)
                response.raise_for_status()
                if not response.content.strip():
                    raise ET.ParseError("пустой ответ")
                root = ET.fromstring(response.content)
                response_el = root.find("response") or root
                err = response_el.find("error")
                if err is not None:
                    code = err.get("code", "?")
                    msg = (err.text or "").strip()
                    last_err = f"{code} {msg}"
                    if code in ("500", "111", "32", "33"):
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    print(f"  [WARN] XMLRiver Google ошибка для '{keyword}' (page {page}): {code} {msg}")
                    return 0, ""
                break
            except requests.RequestException as e:
                last_err = str(e)
                time.sleep(1.5 * (attempt + 1))
            except ET.ParseError as e:
                print(f"  [WARN] Ошибка парсинга XML для '{keyword}' (page {page}): {e}")
                return 0, ""
        else:
            print(f"  [WARN] XMLRiver Google ошибка для '{keyword}' (page {page}) после ретраев: {last_err}")
            return 0, ""

        groups = root.findall(".//group")
        if not groups:
            break

        for group in groups:
            for url_el in group.findall(".//url"):
                url = (url_el.text or "").strip()
                collected += 1
                if _domain_matches(url, target_domain):
                    return collected, url

        if collected >= 30:
            break

        time.sleep(0.5)

    return 0, ""


def _parse_xml_for_position_and_url(content, domain):
    """Парсит XML ответ XMLRiver и ищет позицию домена + URL."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"  [WARN] Ошибка парсинга XML: {e}")
        return 0, ""

    response_el = root.find("response") or root
    err = response_el.find("error")
    if err is not None:
        code = err.get("code", "?")
        msg = (err.text or "").strip()
        print(f"  [WARN] XMLRiver ошибка: {code} {msg}")
        return 0, ""

    target_domain = _normalize_domain(domain)

    for i, group in enumerate(root.findall(".//group"), start=1):
        for url_el in group.findall(".//url"):
            url = (url_el.text or "").strip()
            if _domain_matches(url, target_domain):
                return i, url

    return 0, ""


# =============================================================================
# Сбор ТОП-N конкурентов (URLs из выдачи)
# =============================================================================


def fetch_competitors(keywords, region=213, engine="yandex", top_n=10, max_workers=8, use_real=False, google_loc=None):
    """
    Собирает ТОП-N URL из поисковой выдачи для каждого ключевого слова.

    Args:
        keywords: список строк
        region: int (код региона Яндекса, 213 = Москва)
        engine: "yandex" или "google"
        top_n: сколько URL собирать (по умолчанию 10)
        max_workers: int, количество потоков
        use_real: bool (использовать реальный API)

    Returns:
        список словарей [{"keyword": ..., "url_1": ..., "url_2": ..., ...}]
    """
    results = [None] * len(keywords)

    tasks = [
        (i, keyword, region, engine, top_n, use_real, google_loc)
        for i, keyword in enumerate(keywords)
    ]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_process_competitor, task) for task in tasks]
        for future in tqdm(as_completed(futures), total=len(keywords), desc=f"Сбор конкурентов ({engine})"):
            idx, result = future.result()
            results[idx] = result

    return results


def _process_competitor(args):
    """Обрабатывает один keyword для сбора конкурентов."""
    idx, keyword, region, engine, top_n, use_real, google_loc = args

    if use_real:
        if engine == "google":
            urls = _fetch_competitors_google(keyword, top_n)
        else:
            urls = _fetch_competitors_yandex(keyword, region, top_n)
    else:
        urls = [f"https://example-competitor-{engine}-{i}.com/" for i in range(1, top_n + 1)]

    result = {"keyword": keyword}
    for i in range(1, top_n + 1):
        result[f"url_{i}"] = urls[i - 1] if i <= len(urls) else ""

    # Небольшая задержка, чтобы не перегружать API
    time.sleep(0.1 if not use_real else 0.15)

    return idx, result


def _fetch_competitors_yandex(keyword, region, top_n):
    """Собирает ТОП-N URL из Яндекса."""
    import requests

    user_id = os.getenv("XMLRIVER_USER_ID")
    api_key = os.getenv("XMLRIVER_API_KEY")

    if not user_id or not api_key:
        raise ValueError("Не заданы XMLRIVER_USER_ID или XMLRIVER_API_KEY в config.env")

    params = {
        "user": user_id,
        "key": api_key,
        "query": keyword,
        "lr": region,
        "groupby": top_n,  # ТОП-N за один запрос
    }

    for attempt in range(3):
        try:
            response = requests.get(XMLRIVER_YANDEX_URL, params=params, timeout=90)
            response.raise_for_status()
            return _parse_xml_for_competitors(response.content, top_n)
        except requests.RequestException as e:
            print(f"  [WARN] Ошибка запроса конкурентов для '{keyword}' (попытка {attempt + 1}/3): {e}")
            time.sleep(2 * (attempt + 1))
        except ET.ParseError as e:
            print(f"  [WARN] Ошибка парсинга XML для '{keyword}': {e}")
            return []
    return []


def _fetch_competitors_google(keyword, top_n, google_loc=None):
    """Собирает ТОП-N URL из Google."""
    import requests

    user_id = os.getenv("XMLRIVER_USER_ID")
    api_key = os.getenv("XMLRIVER_API_KEY")

    if not user_id or not api_key:
        raise ValueError("Не заданы XMLRIVER_USER_ID или XMLRIVER_API_KEY в config.env")

    urls = []
    page = 0

    while len(urls) < top_n and page < 3:
        params = {
            "user": user_id,
            "key": api_key,
            "query": keyword,
            "loc": google_loc if google_loc else GOOGLE_LOC_DEFAULT,
            "lr": GOOGLE_LR_DEFAULT,
            "page": page,
        }

        last_err = None
        for attempt in range(2):
            try:
                response = requests.get(XMLRIVER_GOOGLE_URL, params=params, timeout=20)
                response.raise_for_status()
                if not response.content.strip():
                    raise ET.ParseError("пустой ответ")
                root = ET.fromstring(response.content)
                response_el = root.find("response") or root
                err = response_el.find("error")
                if err is not None:
                    code = err.get("code", "?")
                    msg = (err.text or "").strip()
                    last_err = f"{code} {msg}"
                    if code in ("500", "111", "32", "33"):
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    print(f"  [WARN] XMLRiver Google ошибка для '{keyword}' (page {page}): {code} {msg}")
                    return urls
                break
            except requests.RequestException as e:
                last_err = str(e)
                time.sleep(1.5 * (attempt + 1))
            except ET.ParseError as e:
                print(f"  [WARN] Ошибка парсинга XML для '{keyword}' (page {page}): {e}")
                return urls
        else:
            print(f"  [WARN] XMLRiver Google ошибка для '{keyword}' (page {page}) после ретраев: {last_err}")
            return urls

        groups = root.findall(".//group")
        if not groups:
            break

        for group in groups:
            for url_el in group.findall(".//url"):
                url = (url_el.text or "").strip()
                if url:
                    urls.append(url)
                if len(urls) >= top_n:
                    return urls[:top_n]

        page += 1
        time.sleep(0.5)

    return urls[:top_n]


def _parse_xml_for_competitors(content, top_n):
    """Парсит XML ответ XMLRiver и извлекает ТОП-N URL."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"  [WARN] Ошибка парсинга XML: {e}")
        return []

    response_el = root.find("response") or root
    err = response_el.find("error")
    if err is not None:
        code = err.get("code", "?")
        msg = (err.text or "").strip()
        print(f"  [WARN] XMLRiver ошибка: {code} {msg}")
        return []

    urls = []
    for group in root.findall(".//group"):
        for url_el in group.findall(".//url"):
            url = (url_el.text or "").strip()
            if url:
                urls.append(url)
            if len(urls) >= top_n:
                return urls[:top_n]

    return urls[:top_n]
