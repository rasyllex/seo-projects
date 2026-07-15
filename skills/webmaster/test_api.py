"""
Тестовый скрипт для отладки Яндекс.Вебмастер API.
Проверяет базовую связность и правильность конфигурации.
"""

import sys
from pathlib import Path
from urllib.parse import quote

try:
    import requests
except ImportError:
    print("[ОШИБКА] Библиотека requests не установлена. Установите: pip install requests")
    sys.exit(1)

# Загружаем конфиг
BASE = Path(__file__).resolve().parents[2]
ENV_PATH = BASE / "configs" / "webmaster" / ".env"


def load_env(path):
    """Простой парсер .env → dict."""
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def test_connection():
    """Шаг 1: Проверка токена и получение user_id."""
    env = load_env(ENV_PATH)
    token = env.get("YANDEX_WEBMASTER_TOKEN")
    
    if not token:
        print(f"[ОШИБКА] Токен не найден в {ENV_PATH}")
        print("Убедитесь, что файл содержит строку:")
        print("YANDEX_WEBMASTER_TOKEN=y0_...")
        return None
    
    print(f"[OK] Токен загружен из {ENV_PATH}")
    print(f"[INFO] Токен: {token[:20]}...{token[-10:]}")
    
    # Проверяем токен
    url = "https://api.webmaster.yandex.net/v4/user/"
    headers = {"Authorization": f"OAuth {token}"}
    
    print("\n[ТЕСТ 1] Проверка токена...")
    print(f"[INFO] Запрос к: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            user_id = data.get("user_id")
            print(f"[OK] Токен валидный! user_id: {user_id}")
            return user_id, token
        elif response.status_code == 401:
            print(f"[ОШИБКА] Токен невалидный (401 Unauthorized)")
            print(f"[INFO] Ответ API: {response.text}")
            return None
        else:
            print(f"[ОШИБКА] Неожиданный код ответа: {response.status_code}")
            print(f"[INFO] Ответ API: {response.text}")
            return None
            
    except Exception as e:
        print(f"[ОШИБКА] Ошибка при запросе: {e}")
        return None


def test_hosts(user_id, token):
    """Шаг 2: Получение списка хостов."""
    url = f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts"
    headers = {"Authorization": f"OAuth {token}"}
    
    print(f"\n[ТЕСТ 2] Получение списка хостов...")
    print(f"[INFO] Запрос к: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            hosts = data.get("hosts", [])
            print(f"[OK] Найдено хостов: {len(hosts)}")
            
            for host in hosts:
                host_id = host.get("host_id")
                display_url = host.get("unicode_host_url", host_id)
                verified = host.get("verified", False)
                print(f"  - {display_url} (host_id: {host_id}, verified: {verified})")
            
            return hosts
        else:
            print(f"[ОШИБКА] Код ответа: {response.status_code}")
            print(f"[INFO] Ответ API: {response.text}")
            return []
            
    except Exception as e:
        print(f"[ОШИБКА] Ошибка при запросе: {e}")
        return []


def test_queries(host_id, user_id, token):
    """Шаг 3: Тест запроса популярных запросов для конкретного хоста."""
    encoded_host = quote(host_id, safe='')
    url = f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{encoded_host}/search-queries/popular"
    headers = {"Authorization": f"OAuth {token}"}
    params = {
        "query_indicator": ["TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION"],
        "device_type_indicator": "ALL",
        "offset": 0,
        "limit": 10,
        "order_by": "TOTAL_SHOWS"
    }
    
    print(f"\n[ТЕСТ 3] Запрос популярных запросов для {host_id}...")
    print(f"[INFO] URL (закодированный): {url}")
    print(f"[INFO] Параметры: {params}")
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            queries = data.get("queries", [])
            count = data.get("count", 0)
            print(f"[OK] Получено запросов: {len(queries)} (всего доступно: {count})")
            
            for i, q in enumerate(queries[:3], 1):
                text = q.get("query_text", "")
                shows = q.get("indicators", {}).get("TOTAL_SHOWS", 0)
                clicks = q.get("indicators", {}).get("TOTAL_CLICKS", 0)
                pos = q.get("indicators", {}).get("AVG_SHOW_POSITION", 0.0)
                print(f"  {i}. {text} (показы: {shows}, клики: {clicks}, позиция: {pos:.1f})")
            
            return True
        else:
            print(f"[ОШИБКА] Код ответа: {response.status_code}")
            print(f"[INFO] Ответ API: {response.text}")
            print(f"\n[ПОДСКАЗКА] Возможные причины ошибки 400:")
            print("  1. host_id не соответствует формату (должен быть https:domain:443)")
            print("  2. Сайт не подтверждён в Вебмастере")
            print("  3. Недостаточно данных по запросам (новый сайт)")
            return False
            
    except Exception as e:
        print(f"[ОШИБКА] Ошибка при запросе: {e}")
        return False


def main():
    print("=" * 70)
    print("ДИАГНОСТИКА ЯНДЕКС.ВЕБМАСТЕР API")
    print("=" * 70)
    
    # Шаг 1: Проверка токена
    result = test_connection()
    if not result:
        print("\n[ИТОГ] Исправьте токен и запустите скрипт снова.")
        return
    
    user_id, token = result
    
    # Шаг 2: Получение хостов
    hosts = test_hosts(user_id, token)
    if not hosts:
        print("\n[ИТОГ] Не удалось получить список хостов.")
        print("[ПОДСКАЗКА] Добавьте сайт в Яндекс.Вебмастер (webmaster.yandex.ru)")
        return
    
    # Шаг 3: Тест запроса для первого хоста (или bashgaz02.ru)
    test_host = None
    for host in hosts:
        host_id = host.get("host_id")
        if "bashgaz02" in host_id:
            test_host = host_id
            break
    
    if not test_host and hosts:
        test_host = hosts[0].get("host_id")
    
    if test_host:
        test_queries(test_host, user_id, token)
    
    print("\n" + "=" * 70)
    print("[ИТОГ] Диагностика завершена")
    print("=" * 70)


if __name__ == "__main__":
    main()
