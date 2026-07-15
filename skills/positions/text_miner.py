"""
Частотный анализ текстов SERP.
- n-граммы (1/2/3) по текстам сниппетов (униграммы — без стоп-слов; би/триграммы — как есть, чтобы сохранить фразы вроде «с установкой»)
- частотность лемм из title (без стоп-слов), лемматизация pymorphy3
"""

import re
from collections import Counter

import pandas as pd
import pymorphy3

_MORPH = pymorphy3.MorphAnalyzer()
_WORD = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)

# Русские стоп-слова (предлоги, союзы, частицы, местоимения) + мусор
STOPWORDS = set("""
и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне
было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас
нибудь опять уж вам ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была
сам чтоб без будто чего раз тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь
этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда можно при наконец два об другой хоть
после над больше тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой
перед иногда лучше чуть том нельзя такой им более всегда конечно всю между это её также
""".split())

_LEMMA_CACHE = {}


def tokenize(text):
    return [w.lower() for w in _WORD.findall(text or "")]


def _ngrams(tokens, n):
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _ngrams_nostop(tokens, n):
    """n-граммы без стоп-слов: фраза берётся, только если ВСЕ её слова значимые."""
    out = []
    for i in range(len(tokens) - n + 1):
        gram = tokens[i:i + n]
        if all(t not in STOPWORDS and len(t) > 1 for t in gram):
            out.append(" ".join(gram))
    return out


def snippet_ngrams(snippets, top=None):
    """Список {ngram, n, freq}. Униграммы — без стоп-слов; би/триграммы — как есть."""
    counters = {1: Counter(), 2: Counter(), 3: Counter()}
    for s in snippets:
        toks = tokenize(s)
        counters[1].update(t for t in toks if t not in STOPWORDS and len(t) > 1)
        counters[2].update(_ngrams(toks, 2))
        counters[3].update(_ngrams(toks, 3))
    rows = []
    for n in (1, 2, 3):
        for gram, freq in counters[n].most_common(top):
            if freq > 1:                      # выкидываем случайный шум (частота 1)
                rows.append({"ngram": gram, "n": n, "freq": freq})
    return rows


def _lemma(word):
    if word not in _LEMMA_CACHE:
        _LEMMA_CACHE[word] = _MORPH.parse(word)[0].normal_form
    return _LEMMA_CACHE[word]


def title_lemma_freq(titles, top=None):
    """Частотность лемм из title, без стоп-слов."""
    c = Counter()
    for t in titles:
        for w in tokenize(t):
            if w in STOPWORDS or len(w) < 2:
                continue
            lm = _lemma(w)
            if lm in STOPWORDS or len(lm) < 2:
                continue
            c[lm] += 1
    return [{"lemma": lm, "freq": f} for lm, f in c.most_common(top)]


# ============================ широкий формат (3 блока рядом) ============================
# Раскладка как в ручном образце ngrams_yandex: три вертикальных блока (1/2/3-грам)
# бок о бок, у каждого свои колонки ngram|n|freq, отсортированы по убыванию частоты.

def _wide_from_counters(counters, min_freq=2):
    """Три блока (n=1,2,3) рядом → DataFrame с колонками ngram|n|freq × 3."""
    blocks = []
    for n in (1, 2, 3):
        blocks.append([(g, n, f) for g, f in counters[n].most_common() if f >= min_freq])
    height = max((len(b) for b in blocks), default=0)
    records = []
    for i in range(height):
        row = []
        for b in blocks:
            row += list(b[i]) if i < len(b) else ["", "", ""]
        records.append(row)
    return pd.DataFrame(records, columns=["ngram", "n", "freq"] * 3)


def snippet_ngrams_wide(snippets):
    """n-граммы сниппетов (1/2/3) в широкой раскладке. Все — без стоп-слов:
    фраза берётся, только если каждое её слово значимое (напр. «в москве» отбрасывается)."""
    counters = {1: Counter(), 2: Counter(), 3: Counter()}
    for s in snippets:
        toks = tokenize(s)
        counters[1].update(t for t in toks if t not in STOPWORDS and len(t) > 1)
        counters[2].update(_ngrams_nostop(toks, 2))
        counters[3].update(_ngrams_nostop(toks, 3))
    return _wide_from_counters(counters)


def hstack_wide(*dfs):
    """Склеивает широкие блоки бок о бок (выравнивая по числу строк, добивая пустыми)."""
    height = max((len(d) for d in dfs), default=0)
    parts = [d.reindex(range(height)).fillna("") for d in dfs]
    return pd.concat(parts, axis=1)


def title_ngrams_wide(titles):
    """n-граммы по ЛЕММАМ title (1/2/3) в широкой раскладке, без стоп-слов.
    Униграммный блок = прежняя частотность лемм; би/триграммы — фразы из лемм."""
    counters = {1: Counter(), 2: Counter(), 3: Counter()}
    for t in titles:
        lemmas = []
        for w in tokenize(t):
            if w in STOPWORDS or len(w) < 2:
                continue
            lm = _lemma(w)
            if lm in STOPWORDS or len(lm) < 2:
                continue
            lemmas.append(lm)
        counters[1].update(lemmas)
        counters[2].update(_ngrams(lemmas, 2))
        counters[3].update(_ngrams(lemmas, 3))
    return _wide_from_counters(counters)


def query_highlights(keyword, text):
    """Синтетические подсветки (для Google: XMLRiver не отдаёт разметку).
    Находим в тексте формы слов запроса по леммам; соседние слова склеиваем во фразу."""
    qlem = {_lemma(w) for w in tokenize(keyword)}
    phrases, cur = [], []
    for tok in _WORD.findall(text or ""):
        if _lemma(tok.lower()) in qlem:
            cur.append(tok)
        else:
            if cur:
                phrases.append(" ".join(cur))
                cur = []
    if cur:
        phrases.append(" ".join(cur))
    seen, out = set(), []
    for p in phrases:
        pl = p.lower()
        if pl not in seen:
            seen.add(pl)
            out.append(p)
    return out


def _doc_highlights(keyword, o):
    """Подсветки документа: родные (Яндекс) или синтетические по запросу (Google)."""
    return o.get("highlights") or query_highlights(
        keyword, f"{o.get('title', '')} {o.get('snippet', '')}")


def highlights_ranked(serps_by_engine):
    """Уникальные подсветки из всех ПС, ранжированные по убыванию.
    Колонки: highlight, freq_yandex, freq_google, freq_total."""
    engines = list(serps_by_engine.keys())
    per = {e: Counter() for e in engines}
    total = Counter()
    for e in engines:
        for kw, serp in serps_by_engine[e]:
            if not serp:
                continue
            for o in serp["organic"]:
                for w in _doc_highlights(kw, o):
                    wl = w.strip().lower()
                    if not wl:
                        continue
                    per[e][wl] += 1
                    total[wl] += 1
    rows = []
    for w, f in total.most_common():
        row = {"highlight": w}
        for e in engines:
            row[f"freq_{e}"] = per[e].get(w, 0)
        row["freq_total"] = f
        rows.append(row)
    return rows


def url_champions(serps_by_engine):
    """Сколько раз каждый url встречается в ТОПе (по всем ключам и ПС).
    Колонки: url, title, count."""
    c = Counter()
    titles = {}
    for serps in serps_by_engine.values():
        for _kw, serp in serps:
            if not serp:
                continue
            for o in serp["organic"]:
                u = (o.get("url") or "").strip()
                if not u:
                    continue
                c[u] += 1
                if u not in titles and o.get("title"):
                    titles[u] = o["title"]
    return [{"url": u, "title": titles.get(u, ""), "count": n} for u, n in c.most_common()]


def title_tags_compact(titles):
    """Компактные теги title: леммы без стоп-слов, частота ≥2. Колонки: title_tag, title_freq."""
    c = Counter()
    for t in titles:
        for w in tokenize(t):
            if w in STOPWORDS or len(w) < 2:
                continue
            lm = _lemma(w)
            if lm in STOPWORDS or len(lm) < 2:
                continue
            c[lm] += 1
    rows = [(g, f) for g, f in c.most_common() if f >= 2]
    return pd.DataFrame(rows, columns=["title_tag", "title_freq"])
