"""
Клиент Яндекс.Вебмастер API.
Реализует реальные запросы к API v4 с пагинацией и обработкой ошибок.

Эндпоинты (все под /user/{user_id}/hosts/{host_id}):
    - Запросы:    search-queries/popular/
    - Индексация: search-urls/in-search/samples/
    - Ссылки:     links/external/samples/
Авторизация: заголовок Authorization: OAuth {token}
"""

import random
import time
from urllib.parse import quote

import requests

API_BASE = "https://api.webmaster.yandex.net/v4"
PAGE_SIZE_QUERIES = 500  # Максимальный размер для популярных запросов
PAGE_SIZE_SAMPLES = 100  # Максимальный размер для индексации и ссылок


def _make_request(url, headers, params=None, max_retries=3):
    """Универсальная функция для HTTP-запросов с ретраями."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise ValueError("Ошибка 401: Неверный OAuth-токен. Проверь YANDEX_WEBMASTER_TOKEN в .env")
            elif response.status_code == 403:
                raise ValueError("Ошибка 403: Доступ запрещён. Проверь права доступа к хосту.")
            elif response.status_code == 404:
                raise ValueError(f"Ошибка 404: Ресурс не найден. Проверь host_id: {url}")
            elif response.status_code == 400:
                error_text = response.text
                raise ValueError(f"Ошибка 400: Неверный запрос. Ответ API: {error_text}")
            else:
                print(f"  [WARN] HTTP {response.status_code} (попытка {attempt + 1}/{max_retries}): {response.text}")
                
        except requests.RequestException as e:
            print(f"  [WARN] Ошибка сети (попытка {attempt + 1}/{max_retries}): {e}")
        
        if attempt < max_retries - 1:
            time.sleep(2 * (attempt + 1))
    
    raise RuntimeError(f"Не удалось выполнить запрос после {max_retries} попыток: {url}")


def get_popular_queries(host_id, token, user_id=None, limit=None, use_real=False):
    """
    Популярные запросы: query_text, impressions, clicks, position.
    
    Args:
        host_id: ID хоста (например, https:example.com:443)
        token: OAuth-токен Яндекс.Вебмастер
        user_id: ID пользователя
        limit: Максимальное количество записей (None = все)
        use_real: Использовать реальный API (True) или мок (False)
    """
    if not use_real:
        # Мок-режим
        sample = ["купить диван москва", "доставка цветов", "seo продвижение",
                  "заказать пиццу", "ремонт квартир", "купить ноутбук"]
        return [{"query_text": random.choice(sample),
                 "impressions": random.randint(1000, 50000),
                 "clicks": random.randint(10, 2000),
                 "position": round(random.uniform(3.0, 25.0), 1)}
                for _ in range(random.randint(10, 30))]
    
    # Реальный режим
    if not token or not user_id:
        raise ValueError("Для реального API нужны token и user_id")
    
    # URL-кодирование host_id (двоеточия превращаются в %3A)
    encoded_host = quote(host_id, safe='')
    url = f"{API_BASE}/user/{user_id}/hosts/{encoded_host}/search-queries/popular"
    
    headers = {"Authorization": f"OAuth {token}"}
    
    all_queries = []
    offset = 0
    
    while True:
        params = {
            "query_indicator": ["TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION"],
            "device_type_indicator": "ALL",
            "offset": offset,
            "limit": PAGE_SIZE_QUERIES,
            "order_by": "TOTAL_SHOWS"  # Сортировка по показам (обязательный параметр)
        }
        
        print(f"  [API] Запрашиваю популярные запросы (offset={offset})...")
        data = _make_request(url, headers, params)
        
        # Структура ответа: {"queries": [...], "count": N}
        queries = data.get("queries", [])
        if not queries:
            break
        
        for q in queries:
            all_queries.append({
                "query_text": q.get("query_text", ""),
                "impressions": q.get("indicators", {}).get("TOTAL_SHOWS", 0),
                "clicks": q.get("indicators", {}).get("TOTAL_CLICKS", 0),
                "position": q.get("indicators", {}).get("AVG_SHOW_POSITION", 0.0)
            })
        
        offset += len(queries)
        
        if limit and offset >= limit:
            all_queries = all_queries[:limit]
            break
        
        if len(queries) < PAGE_SIZE_QUERIES:
            break
    
    return all_queries


def get_indexation_status(host_id, token, user_id=None, limit=None, use_real=False):
    """
    Страницы в поиске (индексация): url, title, last_access, status.
    
    Args:
        host_id: ID хоста
        token: OAuth-токен
        user_id: ID пользователя
        limit: Максимальное количество записей
        use_real: Использовать реальный API
    """
    if not use_real:
        # Мок-режим
        urls = ["https://example.com/page1", "https://example.com/page2", "https://example.com/page3"]
        return [{"url": u, "title": "Пример страницы", "last_access": "2026-01-01", "status": "В поиске"}
                for u in urls]
    
    # Реальный режим
    if not token or not user_id:
        raise ValueError("Для реального API нужны token и user_id")
    
    encoded_host = quote(host_id, safe='')
    url = f"{API_BASE}/user/{user_id}/hosts/{encoded_host}/search-urls/in-search/samples"
    
    headers = {"Authorization": f"OAuth {token}"}
    
    all_pages = []
    offset = 0
    
    while True:
        params = {
            "offset": offset,
            "limit": PAGE_SIZE_SAMPLES
        }
        
        print(f"  [API] Запрашиваю страницы в поиске (offset={offset})...")
        data = _make_request(url, headers, params)
        
        # Структура: {"samples": [...], "count": N}
        samples = data.get("samples", [])
        if not samples:
            break
        
        for s in samples:
            all_pages.append({
                "url": s.get("url", ""),
                "title": s.get("title", ""),
                "last_access": s.get("last_access", ""),
                "status": "В поиске"
            })
        
        offset += len(samples)
        
        if limit and offset >= limit:
            all_pages = all_pages[:limit]
            break
        
        if len(samples) < PAGE_SIZE_SAMPLES:
            break
    
    return all_pages


def get_external_links(host_id, token, user_id=None, limit=None, use_real=False):
    """
    Внешние ссылки: source_url, target_url, discovery_date.
    
    Args:
        host_id: ID хоста
        token: OAuth-токен
        user_id: ID пользователя
        limit: Максимальное количество записей
        use_real: Использовать реальный API
    """
    if not use_real:
        # Мок-режим
        return [{"source_url": f"https://donor{i}.ru/article",
                 "target_url": "https://example.com/page1",
                 "discovery_date": "2026-01-01"}
                for i in range(random.randint(5, 20))]
    
    # Реальный режим
    if not token or not user_id:
        raise ValueError("Для реального API нужны token и user_id")
    
    encoded_host = quote(host_id, safe='')
    url = f"{API_BASE}/user/{user_id}/hosts/{encoded_host}/links/external/samples"
    
    headers = {"Authorization": f"OAuth {token}"}
    
    all_links = []
    offset = 0
    
    while True:
        params = {
            "offset": offset,
            "limit": PAGE_SIZE_SAMPLES
        }
        
        print(f"  [API] Запрашиваю внешние ссылки (offset={offset})...")
        data = _make_request(url, headers, params)
        
        # Структура: {"links": [...], "count": N}
        links = data.get("links", [])
        if not links:
            break
        
        for link in links:
            all_links.append({
                "source_url": link.get("source_url", ""),
                "target_url": link.get("destination_url", ""),  # API возвращает destination_url
                "discovery_date": link.get("discovery_date", "")
            })
        
        offset += len(links)
        
        if limit and offset >= limit:
            all_links = all_links[:limit]
            break
        
        if len(links) < PAGE_SIZE_SAMPLES:
            break
    
    return all_links
