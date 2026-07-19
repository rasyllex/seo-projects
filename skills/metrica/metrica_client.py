"""
Клиент Яндекс.Метрика API (Reporting / Stat API v1).
Мок-режим (use_real=False) — заглушки; реальный режим (use_real=True) — API.
Выгрузка полная: все отчёты по строкам забираются постранично (offset), без лимитов.
"""

import random
from datetime import date, timedelta

import requests

STAT_API = "https://api-metrika.yandex.net/stat/v1/data"
TIMEOUT = 60
PAGE = 10000  # строк за один запрос (макс. у API — 100 000)


def _headers(token):
    return {"Authorization": f"OAuth {token}"}


def _stat(token, params):
    """Один запрос к Stat API с обработкой ошибок."""
    resp = requests.get(STAT_API, headers=_headers(token), params=params, timeout=TIMEOUT)
    if resp.status_code == 401:
        raise RuntimeError("401 — неверный или просроченный токен")
    if resp.status_code == 403:
        raise RuntimeError("403 — нет доступа к счётчику")
    if resp.status_code >= 400:
        try:
            msg = resp.json().get("message") or resp.json().get("errors")
        except Exception:
            msg = resp.text[:200]
        raise RuntimeError(f"{resp.status_code} — {msg}")
    return resp.json()


def _stat_all(token, params):
    """Все строки отчёта постранично (offset), без лимита."""
    out, offset = [], 1
    while True:
        page = dict(params)
        page["limit"] = PAGE
        page["offset"] = offset
        data = _stat(token, page)
        rows = data.get("data", [])
        out.extend(rows)
        total = data.get("total_rows")
        if len(rows) < PAGE or (total is not None and len(out) >= total):
            break
        offset += PAGE
    return out


def _month_periods(months):
    """Список (первый день, последний день) для последних `months` месяцев по возрастанию."""
    y, m = date.today().year, date.today().month
    out = []
    for _ in range(months):
        first = date(y, m, 1)
        nxt = date(y + (m == 12), (m % 12) + 1, 1)
        out.append((first, nxt - timedelta(days=1)))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(out))


def get_visits_by_url(counter_id, token, days=30, use_real=False):
    """Визиты по посадочным URL: pageviews, users, bounce_rate, duration."""
    if not use_real:
        return [{"url": f"https://example.com/page-{i+1}",
                 "pageviews": random.randint(100, 5000),
                 "users": random.randint(50, 2000),
                 "bounce_rate": round(random.uniform(20, 90), 1),
                 "duration": round(random.uniform(5, 300), 1)}
                for i in range(random.randint(10, 30))]

    rows = []
    for it in _stat_all(token, {
        "ids": counter_id, "dimensions": "ym:s:startURL",
        "metrics": "ym:s:pageviews,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds",
        "date1": f"{days}daysAgo", "date2": "today", "sort": "-ym:s:pageviews",
    }):
        m = it.get("metrics", [0, 0, 0, 0])
        rows.append({"url": it["dimensions"][0].get("name"),
                     "pageviews": int(m[0]), "users": int(m[1]),
                     "bounce_rate": round(m[2], 1), "duration": round(m[3], 1)})
    return rows


def get_monthly_trend(counter_id, token, months=12, use_real=False):
    """Тренд по месяцам: pageviews, users."""
    if not use_real:
        return [{"month": f"2026-{i+1:02d}",
                 "pageviews": random.randint(10000, 100000),
                 "users": random.randint(5000, 50000)}
                for i in range(months)]

    rows = []
    for first, last in _month_periods(months):
        tot = _stat(token, {
            "ids": counter_id, "metrics": "ym:s:pageviews,ym:s:users",
            "date1": first.isoformat(), "date2": last.isoformat(),
        }).get("totals", [0, 0])
        rows.append({"month": first.strftime("%Y-%m"),
                     "pageviews": int(tot[0]), "users": int(tot[1])})
    return rows


def get_goals(counter_id, token, goal_id=1, days=30, use_real=False):
    """Достижения целей по дням (сумма по всем целям)."""
    if not use_real:
        return [{"date": f"2026-05-{i+1:02d}", "goal_reaches": random.randint(0, 50)}
                for i in range(min(days, 30))]

    rows = []
    for it in _stat_all(token, {
        "ids": counter_id, "dimensions": "ym:s:date", "metrics": "ym:s:sumGoalReachesAny",
        "date1": f"{days}daysAgo", "date2": "today", "sort": "ym:s:date",
    }):
        m = it.get("metrics", [0])
        rows.append({"date": it["dimensions"][0].get("name"), "goal_reaches": int(m[0])})
    return rows


def get_traffic_sources(counter_id, token, days=30, use_real=False):
    """Распределение по источникам трафика: визиты, пользователи, отказы."""
    if not use_real:
        srcs = ["Переходы из поисковых систем", "Прямые заходы", "Переходы по ссылкам",
                "Социальные сети", "Внутренние переходы"]
        return [{"source": s, "visits": random.randint(50, 2000),
                 "users": random.randint(30, 1500), "bounce_rate": round(random.uniform(20, 90), 1)}
                for s in srcs]

    rows = []
    for it in _stat_all(token, {
        "ids": counter_id, "dimensions": "ym:s:trafficSource",
        "metrics": "ym:s:visits,ym:s:users,ym:s:bounceRate",
        "date1": f"{days}daysAgo", "date2": "today", "sort": "-ym:s:visits",
    }):
        m = it.get("metrics", [0, 0, 0])
        rows.append({"source": it["dimensions"][0].get("name"),
                     "visits": int(m[0]), "users": int(m[1]), "bounce_rate": round(m[2], 1)})
    return rows


def get_search_phrases(counter_id, token, days=30, use_real=False):
    """Поисковые фразы (запросы) с визитами. В Метрике выборка неполная — часть скрыта."""
    if not use_real:
        ph = ["сайт активатор", "seo продвижение уфа", "заказать сайт", "нейросети курс"]
        return [{"phrase": p, "visits": random.randint(1, 50), "users": random.randint(1, 40)} for p in ph]

    rows = []
    for it in _stat_all(token, {
        "ids": counter_id, "dimensions": "ym:s:searchPhrase", "metrics": "ym:s:visits,ym:s:users",
        "date1": f"{days}daysAgo", "date2": "today", "sort": "-ym:s:visits",
    }):
        m = it.get("metrics", [0, 0])
        rows.append({"phrase": it["dimensions"][0].get("name"),
                     "visits": int(m[0]), "users": int(m[1])})
    return rows


def get_by_device(counter_id, token, days=30, use_real=False):
    """Отказы и трафик по типам устройств (desktop / mobile / tablet)."""
    if not use_real:
        devs = ["ПК", "Смартфоны", "Планшеты"]
        return [{"device": d, "visits": random.randint(100, 3000),
                 "users": random.randint(50, 2000), "bounce_rate": round(random.uniform(20, 90), 1)}
                for d in devs]

    rows = []
    for it in _stat_all(token, {
        "ids": counter_id, "dimensions": "ym:s:deviceCategory",
        "metrics": "ym:s:visits,ym:s:users,ym:s:bounceRate",
        "date1": f"{days}daysAgo", "date2": "today", "sort": "-ym:s:visits",
    }):
        m = it.get("metrics", [0, 0, 0])
        rows.append({"device": it["dimensions"][0].get("name"),
                     "visits": int(m[0]), "users": int(m[1]), "bounce_rate": round(m[2], 1)})
    return rows


def get_geography(counter_id, token, days=30, use_real=False):
    """География визитов по городам: визиты, пользователи, отказы."""
    if not use_real:
        cities = ["Москва", "Санкт-Петербург", "Уфа", "Самара", "Екатеринбург"]
        return [{"city": c, "visits": random.randint(20, 1500),
                 "users": random.randint(10, 1000), "bounce_rate": round(random.uniform(20, 90), 1)}
                for c in cities]

    rows = []
    for it in _stat_all(token, {
        "ids": counter_id, "dimensions": "ym:s:regionCity",
        "metrics": "ym:s:visits,ym:s:users,ym:s:bounceRate",
        "date1": f"{days}daysAgo", "date2": "today", "sort": "-ym:s:visits",
    }):
        m = it.get("metrics", [0, 0, 0])
        rows.append({"city": it["dimensions"][0].get("name"),
                     "visits": int(m[0]), "users": int(m[1]), "bounce_rate": round(m[2], 1)})
    return rows


def get_search_engines(counter_id, token, days=30, use_real=False):
    """Визиты и отказы по поисковым системам (Яндекс, Google и т.д.)."""
    if not use_real:
        engines = ["Яндекс", "Google", "Bing", "DuckDuckGo", "Mail.ru"]
        return [{"search_engine": e, "visits": random.randint(50, 3000),
                 "users": random.randint(30, 2000), "bounce_rate": round(random.uniform(20, 80), 1)}
                for e in engines]

    rows = []
    for it in _stat_all(token, {
        "ids": counter_id, "dimensions": "ym:s:searchEngine",
        "metrics": "ym:s:visits,ym:s:users,ym:s:bounceRate",
        "date1": f"{days}daysAgo", "date2": "today", "sort": "-ym:s:visits",
    }):
        m = it.get("metrics", [0, 0, 0])
        rows.append({"search_engine": it["dimensions"][0].get("name"),
                     "visits": int(m[0]), "users": int(m[1]), "bounce_rate": round(m[2], 1)})
    return rows


def get_exit_pages(counter_id, token, days=30, use_real=False):
    """Страницы выхода (endURL): визиты, пользователи, отказы."""
    if not use_real:
        return [{"url": f"https://example.com/exit-page-{i+1}",
                 "visits": random.randint(100, 2000),
                 "users": random.randint(50, 1500),
                 "bounce_rate": round(random.uniform(10, 90), 1)}
                for i in range(random.randint(10, 20))]

    rows = []
    for it in _stat_all(token, {
        "ids": counter_id, "dimensions": "ym:s:endURL",
        "metrics": "ym:s:visits,ym:s:users,ym:s:bounceRate",
        "date1": f"{days}daysAgo", "date2": "today", "sort": "-ym:s:visits",
    }):
        m = it.get("metrics", [0, 0, 0])
        rows.append({"url": it["dimensions"][0].get("name"),
                     "visits": int(m[0]), "users": int(m[1]), "bounce_rate": round(m[2], 1)})
    return rows


def get_age_gender(counter_id, token, days=30, use_real=False):
    """Пол и возраст: визиты, пользователи."""
    if not use_real:
        segments = ["Мужчины 18-24", "Мужчины 25-34", "Мужчины 35-44", "Мужчины 45+",
                    "Женщины 18-24", "Женщины 25-34", "Женщины 35-44", "Женщины 45+"]
        return [{"segment": s, "visits": random.randint(50, 2000),
                 "users": random.randint(30, 1500)}
                for s in segments]

    rows = []
    for it in _stat_all(token, {
        "ids": counter_id, "dimensions": "ym:s:gender,ym:s:ageInterval",
        "metrics": "ym:s:visits,ym:s:users",
        "date1": f"{days}daysAgo", "date2": "today", "sort": "-ym:s:visits",
    }):
        m = it.get("metrics", [0, 0])
        gender = it["dimensions"][0].get("name", "")
        age = it["dimensions"][1].get("name", "")
        rows.append({"segment": f"{gender} {age}",
                     "visits": int(m[0]), "users": int(m[1])})
    return rows


def get_new_vs_returning(counter_id, token, days=30, use_real=False):
    """Новые vs вернувшиеся посетители."""
    if not use_real:
        return [
            {"type": "Новые", "visits": random.randint(1000, 5000),
             "users": random.randint(800, 4000), "bounce_rate": round(random.uniform(40, 80), 1)},
            {"type": "Вернувшиеся", "visits": random.randint(500, 3000),
             "users": random.randint(400, 2500), "bounce_rate": round(random.uniform(20, 60), 1)}
        ]

    rows = []
    for it in _stat_all(token, {
        "ids": counter_id, "dimensions": "ym:s:isNewUser",
        "metrics": "ym:s:visits,ym:s:users,ym:s:bounceRate",
        "date1": f"{days}daysAgo", "date2": "today", "sort": "-ym:s:visits",
    }):
        m = it.get("metrics", [0, 0, 0])
        dim_id = it["dimensions"][0].get("id", "")
        
        # API возвращает id='yes' для новых и id='no' для вернувшихся
        user_type = "Новые" if dim_id == "yes" else "Вернувшиеся"
            
        rows.append({"type": user_type,
                     "visits": int(m[0]), "users": int(m[1]), "bounce_rate": round(m[2], 1)})
    return rows


def _visits_by_url(counter_id, token, days, filt=None):
    params = {"ids": counter_id, "dimensions": "ym:s:startURL", "metrics": "ym:s:visits",
              "date1": f"{days}daysAgo", "date2": "today", "sort": "-ym:s:visits"}
    if filt:
        params["filters"] = filt
    return {it["dimensions"][0]["name"]: int(it["metrics"][0]) for it in _stat_all(token, params)}


def get_session_length_by_url(counter_id, token, days=30, use_real=False):
    """Длина сессий по страницам: доля визитов дольше 1 и 3 минут."""
    if not use_real:
        rows = []
        for i in range(random.randint(10, 20)):
            v = random.randint(50, 1000)
            o1 = random.randint(0, v)
            o3 = random.randint(0, o1)
            rows.append({"url": f"https://example.com/page-{i+1}", "visits": v,
                         "over_1min": o1, "share_1min_%": round(o1 / v * 100, 1),
                         "over_3min": o3, "share_3min_%": round(o3 / v * 100, 1)})
        return rows

    total = _visits_by_url(counter_id, token, days)
    over1 = _visits_by_url(counter_id, token, days, "ym:s:visitDuration>60")
    over3 = _visits_by_url(counter_id, token, days, "ym:s:visitDuration>180")
    rows = []
    for url, v in sorted(total.items(), key=lambda x: -x[1]):
        o1, o3 = over1.get(url, 0), over3.get(url, 0)
        rows.append({"url": url, "visits": v,
                     "over_1min": o1, "share_1min_%": round(o1 / v * 100, 1) if v else 0,
                     "over_3min": o3, "share_3min_%": round(o3 / v * 100, 1) if v else 0})
    return rows


def _period_totals(counter_id, token, date1, date2):
    """Ключевые тоталы за период (+ органика отдельным запросом)."""
    t = _stat(token, {
        "ids": counter_id,
        "metrics": "ym:s:visits,ym:s:users,ym:s:pageviews,ym:s:sumGoalReachesAny,ym:s:bounceRate,ym:s:avgVisitDurationSeconds",
        "date1": date1, "date2": date2,
    }).get("totals", [0] * 6)
    org = _stat(token, {
        "ids": counter_id, "metrics": "ym:s:visits",
        "filters": "ym:s:trafficSource=='organic'", "date1": date1, "date2": date2,
    }).get("totals", [0])
    return {"Визиты": int(t[0]), "Посетители": int(t[1]), "Просмотры": int(t[2]),
            "Органические визиты": int(org[0]), "Достижения целей": int(t[3]),
            "Отказы, %": round(t[4], 1), "Ср. время, сек": round(t[5], 1)}


def get_summary(counter_id, token, days=30, use_real=False):
    """Сводка: текущий период vs предыдущий такой же длины, с дельтами."""
    if not use_real:
        rows = []
        for k in ["Визиты", "Посетители", "Просмотры", "Органические визиты",
                  "Достижения целей", "Отказы, %", "Ср. время, сек"]:
            c, p = random.randint(100, 5000), random.randint(100, 5000)
            rows.append({"Метрика": k, "Текущий период": c, "Прошлый период": p,
                         "Δ %": round((c - p) / p * 100, 1), "Тренд": "↑" if c > p else "↓"})
        return rows

    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    p_end = start - timedelta(days=1)
    p_start = p_end - timedelta(days=days - 1)
    cur = _period_totals(counter_id, token, start.isoformat(), end.isoformat())
    prev = _period_totals(counter_id, token, p_start.isoformat(), p_end.isoformat())

    rows = []
    for k in cur:
        c, p = cur[k], prev[k]
        pct = round((c - p) / p * 100, 1) if p else None
        arrow = "→" if not pct else ("↑" if c > p else "↓")
        rows.append({"Метрика": k, "Текущий период": c, "Прошлый период": p, "Δ %": pct, "Тренд": arrow})
    return rows
