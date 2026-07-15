"""
Клиент Google Search Console API.
Мок-режим (use_real=False) — заглушки; реальный режим (use_real=True) — Search Console API v1.

Отчёты (searchanalytics.query в разных разрезах + sitemaps.list):
- Запросы, Страницы, Запрос+Страница — эффективность поиска
- Динамика — по датам
- Устройства, Страны, Вид в выдаче — сегменты
- Sitemaps — карты сайта и их статус

Авторизация (первый найденный вариант в configs/gsc/):
1. service_account.json — Service Account (сайт должен быть расшарен на его email)
2. token.json — OAuth-токен пользователя (authorized_user, с refresh_token)
"""

import random
from datetime import date, timedelta
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
PAGE_SIZE = 25000  # максимум строк за один запрос searchanalytics.query

# (имя вкладки, dimensions). searchAppearance нельзя комбинировать с другими.
REPORTS = [
    ("Запросы", ["query"]),
    ("Страницы", ["page"]),
    ("Запрос+Страница", ["query", "page"]),
    ("Динамика", ["date"]),
    ("Устройства", ["device"]),
    ("Страны", ["country"]),
    ("Вид в выдаче", ["searchAppearance"]),
]


def authenticate(config_dir):
    """Возвращает авторизованный сервис Search Console API."""
    from googleapiclient.discovery import build

    config_dir = Path(config_dir)
    sa_path = config_dir / "service_account.json"
    token_path = config_dir / "token.json"

    if sa_path.exists():
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            str(sa_path), scopes=SCOPES)
    elif token_path.exists():
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
    else:
        raise RuntimeError(
            f"Не найдены креденшалы: положи service_account.json или token.json в {config_dir}")

    return build("searchconsole", "v1", credentials=creds)


def list_sites(service):
    """Список сайтов, доступных этому аккаунту в GSC."""
    resp = service.sites().list().execute()
    return [(s["siteUrl"], s["permissionLevel"]) for s in resp.get("siteEntry", [])]


def get_all_reports(site_url, start_date, end_date, use_real=False,
                    config_dir=None, limit=None):
    """
    Выгружает все отчёты. Возвращает {"имя вкладки": [строки], ...}.
    Упавший отчёт не роняет остальные — вместо него пустой список.
    """
    if not use_real:
        return _mock_reports(site_url, start_date, end_date)

    service = authenticate(config_dir)
    reports = {}
    for name, dims in REPORTS:
        try:
            reports[name] = fetch_report(service, site_url, start_date, end_date,
                                         dims, limit=limit)
            print(f"   {name}: {len(reports[name])} строк")
        except Exception as e:
            print(f"   [!] {name}: не выгружен ({e})")
            reports[name] = []

    try:
        reports["Sitemaps"] = get_sitemaps(service, site_url)
        print(f"   Sitemaps: {len(reports['Sitemaps'])} строк")
    except Exception as e:
        print(f"   [!] Sitemaps: не выгружен ({e})")
        reports["Sitemaps"] = []

    return reports


def fetch_report(service, site_url, start_date, end_date, dimensions, limit=None):
    """Один отчёт searchanalytics.query с пагинацией."""
    rows, start_row = [], 0
    while limit is None or len(rows) < limit:
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": PAGE_SIZE,
            "startRow": start_row,
        }
        resp = _query(service, site_url, body)
        batch = resp.get("rows", [])
        if not batch:
            break
        for r in batch:
            keys = dict(zip(dimensions, r.get("keys", [])))
            rows.append({
                **keys,
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr": round(r.get("ctr", 0), 4),
                "position": round(r.get("position", 0), 1),
            })
        start_row += len(batch)
        if len(batch) < PAGE_SIZE:
            break
    return rows if limit is None else rows[:limit]


def get_sitemaps(service, site_url):
    """Карты сайта: путь, статус, ошибки/предупреждения, количество URL."""
    resp = service.sitemaps().list(siteUrl=site_url).execute()
    rows = []
    for s in resp.get("sitemap", []):
        contents = s.get("contents", [])
        submitted = sum(int(c.get("submitted", 0)) for c in contents)
        rows.append({
            "path": s.get("path"),
            "type": s.get("type"),
            "last_submitted": s.get("lastSubmitted"),
            "last_downloaded": s.get("lastDownloaded"),
            "is_pending": s.get("isPending"),
            "urls_submitted": submitted,
            "errors": s.get("errors"),
            "warnings": s.get("warnings"),
        })
    return rows


def _query(service, site_url, body):
    """Один запрос к searchanalytics.query с понятными ошибками."""
    from googleapiclient.errors import HttpError
    try:
        return service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    except HttpError as e:
        if e.resp.status == 403:
            raise RuntimeError(
                f"403 — нет доступа к {site_url}. Проверь, что аккаунт добавлен "
                f"в пользователи этого ресурса в GSC (и формат: sc-domain:site.ru "
                f"или https://site.ru/).") from e
        if e.resp.status == 404:
            raise RuntimeError(f"404 — ресурс {site_url} не найден в GSC.") from e
        raise


# --- Мок-режим -----------------------------------------------------------

_SAMPLE_QUERIES = [
    "купить диван москва", "доставка цветов", "seo продвижение",
    "заказать пиццу", "ремонт квартир", "купить ноутбук",
    "аренда авто", "дизайн интерьера", "строительство дома", "замена окон",
]


def _mock_metrics():
    impressions = random.randint(100, 10000)
    ctr = random.uniform(0.005, 0.15)
    return {
        "clicks": int(impressions * ctr),
        "impressions": impressions,
        "ctr": round(ctr, 4),
        "position": round(random.uniform(3.0, 35.0), 1),
    }


def _mock_reports(site_url, start_date, end_date):
    """Случайные данные во всех разрезах для отладки пайплайна без API.
    Порядок ключей — как в REPORTS, чтобы состав вкладок совпадал с реалом."""
    d0, d1 = date.fromisoformat(start_date), date.fromisoformat(end_date)
    return {
        "Запросы": [{"query": q, **_mock_metrics()}
                    for q in random.sample(_SAMPLE_QUERIES, 8)],
        "Страницы": [{"page": f"{site_url}/page-{i}", **_mock_metrics()}
                     for i in range(1, 11)],
        "Запрос+Страница": [{"query": random.choice(_SAMPLE_QUERIES),
                             "page": f"{site_url}/page-{i}", **_mock_metrics()}
                            for i in range(1, random.randint(20, 40))],
        "Динамика": [{"date": str(d0 + timedelta(days=i)), **_mock_metrics()}
                     for i in range((d1 - d0).days + 1)],
        "Устройства": [{"device": d, **_mock_metrics()}
                       for d in ("MOBILE", "DESKTOP", "TABLET")],
        "Страны": [{"country": c, **_mock_metrics()}
                   for c in ("rus", "blr", "kaz", "uzb", "deu")],
        "Вид в выдаче": [{"searchAppearance": "TRANSLATED_RESULT", **_mock_metrics()}],
        "Sitemaps": [{"path": f"{site_url}/sitemap.xml", "type": "WEB",
                      "last_submitted": start_date, "last_downloaded": end_date,
                      "is_pending": False, "urls_submitted": random.randint(50, 500),
                      "errors": 0, "warnings": random.randint(0, 5)}],
    }
