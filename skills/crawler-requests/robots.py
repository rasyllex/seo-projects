"""
Разбор robots.txt для проверки индексируемости и вежливого обхода.

Скачивается один раз на домен. Свой матчер по спецификации Google (не стандартный
urllib.robotparser — он НЕ понимает wildcard'ы вроде `/*?*`, `/*.pdf`):
  - `*` — любая последовательность символов;
  - `$` — конец URL;
  - выигрывает правило с самым длинным совпавшим паттерном; при равной длине Allow > Disallow.
Сопоставление идёт по пути + строке запроса (`/ctl20?features_hash=...`).

Используется в двух местах:
  - индексируемость: URL под Disallow → indexable=Нет, статус Blocked by robots.txt;
  - обход: с --respect-robots краулер не заходит на закрытые URL.
"""

import re
from urllib.parse import urlparse

import requests


def _compile(pattern):
    """Паттерн robots.txt → regex (Google: * = любое, $ = конец)."""
    out = ["^"]
    for ch in pattern:
        if ch == "*":
            out.append(".*")
        elif ch == "$":
            out.append("$")
        else:
            out.append(re.escape(ch))
    return re.compile("".join(out))


def _parse(text, user_agent):
    """Возвращает список правил [(allow_bool, regex, длина_паттерна)] для нашего UA.
    Группы User-agent разбираются по стандарту: подряд идущие User-agent делят
    один блок правил; берём точную группу для UA, иначе `*`."""
    ua = user_agent.lower()
    groups = {}                       # agent(lower) -> [(allow, pattern)]
    current_agents = []
    last_was_rule = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            if last_was_rule:         # новый блок после правил
                current_agents = []
                last_was_rule = False
            current_agents.append(value.lower())
            groups.setdefault(value.lower(), [])
        elif field in ("allow", "disallow"):
            last_was_rule = True
            for a in current_agents:
                groups[a].append((field == "allow", value))

    raw_rules = groups.get(ua) or groups.get("*") or []
    # пустой Disallow = «разрешено всё» → пропускаем (не ограничивает)
    return [(allow, _compile(p), len(p)) for allow, p in raw_rules if p]


class Robots:
    """robots.txt одного домена. Без robots.txt — всё разрешено."""

    def __init__(self, base_url, user_agent="*", proxies=None):
        self.user_agent = user_agent
        self.rules = []
        self._loaded = False
        self._fetch(base_url, proxies)

    def _fetch(self, base_url, proxies):
        p = urlparse(base_url if "://" in base_url else f"https://{base_url}")
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        try:
            r = requests.get(robots_url, timeout=15, proxies=proxies,
                             headers={"User-Agent": self.user_agent})
            if r.status_code == 200 and r.text.strip():
                self.rules = _parse(r.text, self.user_agent)
                self._loaded = True
                print(f"-> robots.txt загружен: {robots_url} (правил: {len(self.rules)})")
            else:
                print(f"-> robots.txt нет (HTTP {r.status_code}) — обход без ограничений")
        except requests.RequestException as e:
            print(f"-> robots.txt недоступен ({e}) — обход без ограничений")

    def allowed(self, url):
        """Разрешён ли URL. Правило с самым длинным совпадением; Allow > Disallow при равенстве."""
        if not self._loaded:
            return True
        p = urlparse(url)
        path = p.path or "/"
        if p.query:
            path += "?" + p.query
        best = None                   # (длина, allow)
        for allow, rx, plen in self.rules:
            if rx.match(path):
                if best is None or plen > best[0] or (plen == best[0] and allow):
                    best = (plen, allow)
        return True if best is None else best[1]
