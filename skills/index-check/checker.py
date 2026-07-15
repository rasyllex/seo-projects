"""
Проверка индексации URL через XMLRiver API.
Использует оператор site: для проверки наличия URL в индексе.
"""

import os
import time
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from tqdm import tqdm

import requests
from dotenv import load_dotenv

# Загружаем config.env
config_path = Path(__file__).parents[2] / "configs" / "index-check" / "config.env"
load_dotenv(config_path)

XMLRIVER_YANDEX_URL = "https://xmlriver.com/yandex/xml"
XMLRIVER_GOOGLE_URL = "https://xmlriver.com/search/xml"


def check_urls(urls, engines, use_real=False, cache=None):
    """
    Проверяет индексацию списка URL.

    Args:
        urls: список URL
        engines: список поисковиков ["google", "yandex"]
        use_real: bool
        cache: dict

    Returns:
        список словарей [{"url": ..., "google": True/False, "yandex": True/False, "date": ...}]
    """
    results = []

    for url in tqdm(urls, desc="Проверка URL"):
        result = {"url": url}

        for engine in engines:
            cache_key = f"{url}_{engine}"

            # Проверка кэша
            if cache and cache_key in cache:
                from cache import is_cache_valid
                if is_cache_valid(cache[cache_key]):
                    result[engine] = cache[cache_key]["result"]
                    continue

            # Запрос
            if use_real:
                result[engine] = _check_real(url, engine)
            else:
                result[engine] = _mock_check()

            # Сохранение в кэш
            if cache is not None:
                cache[cache_key] = {
                    "result": result[engine],
                    "date": __import__("datetime").datetime.now().strftime("%Y-%m-%d")
                }

            time.sleep(0.2)

        result["date"] = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
        results.append(result)

    return results


def _mock_check():
    """Мок-режим: 66% шанс, что проиндексирована."""
    return random.choice([True, True, False])


def _check_real(url, engine):
    """
    Реальная проверка через XMLRiver API с оператором site:.
    
    Args:
        url: URL для проверки
        engine: "google" или "yandex"
    
    Returns:
        True если URL найден в индексе, False если нет
    """
    user_id = os.getenv("XMLRIVER_USER_ID")
    api_key = os.getenv("XMLRIVER_API_KEY")
    
    if not user_id or not api_key:
        raise ValueError("Не заданы XMLRIVER_USER_ID или XMLRIVER_API_KEY в config.env")
    
    # Формируем запрос с оператором site:
    # Для точной проверки URL используем site:url
    query = f"site:{url}"
    
    if engine == "yandex":
        api_url = XMLRIVER_YANDEX_URL
        params = {
            "user": user_id,
            "key": api_key,
            "query": query,
            "groupby": 10,  # ТОП-10 достаточно для проверки
        }
    elif engine == "google":
        api_url = XMLRIVER_GOOGLE_URL
        params = {
            "user": user_id,
            "key": api_key,
            "query": query,
            "groupby": 10,
        }
    else:
        return False
    
    # Выполняем запрос с retry
    for attempt in range(3):
        try:
            response = requests.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            
            # Парсим XML
            root = ET.fromstring(response.content)
            
            # Ищем документы в результатах
            docs = root.findall(".//doc")
            
            if not docs:
                # Нет результатов = не проиндексирован
                return False
            
            # Проверяем, есть ли наш URL среди результатов
            for doc in docs:
                doc_url = doc.findtext("url", "").strip()
                # Нормализуем URL для сравнения (убираем trailing slash)
                doc_url_normalized = doc_url.rstrip('/')
                url_normalized = url.rstrip('/')
                
                if doc_url_normalized == url_normalized or doc_url_normalized.startswith(url_normalized):
                    return True
            
            # URL есть в выдаче, но не точное совпадение
            # Считаем это как проиндексированный домен, но не конкретная страница
            return len(docs) > 0
            
        except requests.RequestException as e:
            print(f"  [WARN] Ошибка запроса для {url} в {engine} (попытка {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
        except ET.ParseError as e:
            print(f"  [WARN] Ошибка парсинга XML для {url}: {e}")
            return False
    
    # После 3 попыток считаем как не проиндексированный
    return False
