"""
Разбор сырого XML-ответа XMLRiver в структуру SERP.

Возвращает:
{
  "organic": [{pos, url, domain, title, snippet, highlights, cache, breadcrumbs}],
  "features": {                       # в основном Google
     "related_searches": [...],
     "paa": [...],                    # People Also Ask
     "knowledge_graph": {...},        # непустые поля карточки
  }
}
Из этой структуры считаются позиции, конкуренты, сниппеты, n-граммы и фичи —
всё из одного оплаченного ответа.
"""

import re
import xml.etree.ElementTree as ET

# Разметка подсветки приходит в двух видах:
#   Яндекс — настоящие XML-элементы: <passage>...<hlword>окна</hlword>...</passage>
#   Google (опция «Подсветка ключевых слов» в XMLRiver) — ТЕКСТ внутри CDATA:
#     <passage><![CDATA[ <hlword>Купить окна</hlword> в магазине... ]]></passage>
# Оба вида приводим к одной «размеченной строке» и разбираем её регуляркой.
_HL_RE = re.compile(r"<\s*(hlword|b)\s*>(.*?)<\s*/\s*\1\s*>", re.S | re.I)


def _marked(el):
    """Текст элемента, где ЛЮБАЯ подсветка (элемент или CDATA-разметка)
    приведена к литеральному <hlword>...</hlword>."""
    if el is None:
        return ""
    parts = [el.text or ""]
    for child in el:
        inner = "".join(child.itertext())
        if child.tag.lower() in ("hlword", "b"):
            parts.append(f"<hlword>{inner}</hlword>")
        else:
            parts.append(_marked(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _plain(marked):
    """Чистый текст: разметка подсветки снимается, слова остаются."""
    return _HL_RE.sub(lambda m: m.group(2), marked).strip()


def _txt(el):
    """Текст элемента без разметки подсветок (и элементной, и CDATA)."""
    return _plain(_marked(el))


def _phrases(marked):
    """Фразы из ПОДРЯД идущих подсветок (между ними только пробелы).
    «<hlword>Пластиковые</hlword> <hlword>окна</hlword>» → «Пластиковые окна»."""
    phrases, cur, last_end = [], [], None
    for m in _HL_RE.finditer(marked):
        w = m.group(2).strip()
        if not w:
            continue
        if last_end is not None and marked[last_end:m.start()].strip():
            if cur:                     # непустой текст между подсветками — разрыв
                phrases.append(" ".join(cur))
                cur = []
        cur.append(w)
        last_end = m.end()
    if cur:
        phrases.append(" ".join(cur))
    return phrases


def _highlights(doc):
    """Подсветки документа как фразы (title + пассажи), без разбиения n-грамм.
    Дедуп в пределах документа, порядок сохраняется."""
    phrases = []
    for el in [doc.find("title"), *doc.findall(".//passage")]:
        phrases.extend(_phrases(_marked(el)))
    seen, out = set(), []
    for p in phrases:
        pl = p.lower()
        if pl and pl not in seen:
            seen.add(pl)
            out.append(p)
    return out


def _organic(root, engine):
    rows = []
    for i, doc in enumerate(root.findall(".//doc"), start=1):
        url = (doc.findtext("url") or "").strip()
        if not url:
            continue
        snippet = " ".join(_txt(p) for p in doc.findall(".//passage")).strip()
        cache = (doc.findtext("saved-copy-url") if engine == "yandex" else doc.findtext("cachelink")) or ""
        rows.append({
            "pos": len(rows) + 1,
            "url": url,
            "domain": (doc.findtext("domain") or "").strip(),
            "title": _txt(doc.find("title")),
            "snippet": snippet,
            "highlights": _highlights(doc),
            "cache": cache.strip(),
            "breadcrumbs": (doc.findtext("breadcrumbs") or "").strip(),
        })
    return rows


def _google_features(root):
    feats = {}
    rs = [_txt(q) for q in root.findall(".//relatedSearches/query")]
    if not rs:
        rs = [_txt(i) for i in root.findall(".//relatedSearches/item")]
    rs = [x for x in rs if x]
    if rs:
        feats["related_searches"] = rs

    paa = []
    for item in root.findall(".//relatedQuestions/item"):
        q = _txt(item.find("question"))
        if q:
            paa.append({
                "question": q,
                "answer": _txt(item.find("snippet")),
                "url": (item.findtext("url") or "").strip(),
            })
    if paa:
        feats["paa"] = paa

    kg = root.find(".//knowledge_graph")
    if kg is not None:
        kgd = {c.tag: (c.text or "").strip() for c in kg if (c.text or "").strip()}
        if kgd:
            feats["knowledge_graph"] = kgd
    return feats


def parse_serp(content, engine):
    """content: bytes|str сырого XML. engine: 'yandex'|'google'."""
    root = ET.fromstring(content)
    serp = {"organic": _organic(root, engine), "features": {}}
    if engine == "google":
        serp["features"] = _google_features(root)
    return serp
