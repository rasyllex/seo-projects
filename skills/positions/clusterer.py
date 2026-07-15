"""
Кластеризация запросов по ТОПам: Middle (по умолчанию) и Hard.

У каждой пары запросов считается пересечение URL в ТОП-N выдачи.
Связь = >= threshold общих URL. Вершина кластера — фраза с максимумом связей.

Middle: в кластер входят фразы, связанные с вершиной; зависимые фразы
  дополнительно сравниваются между собой — каждая должна быть связана ещё
  хотя бы с одной фразой кластера (цепочкой, без «все со всеми»).
Hard: кластер — клика: каждая фраза связана с КАЖДОЙ фразой кластера.
  Кластеры мельче и чище, для высококонкурентных тематик.

Работает на закэшированных SERP — ноль дополнительных запросов к API.
"""

DEPTH = 20          # срез ТОПа для сравнения URL
THRESHOLD = 4       # минимум общих URL для связи


def _top_urls(serp, depth=DEPTH):
    return {o["url"] for o in serp["organic"][:depth]}


def _similarity(serps, depth):
    """Попарные пересечения ТОПов. Возвращает (список ключей, {(a,b): n})."""
    kws = [kw for kw, s in serps if s and s["organic"]]
    urls = {kw: _top_urls(s, depth) for kw, s in serps if s and s["organic"]}
    sim = {}
    for i, a in enumerate(kws):
        for b in kws[i + 1:]:
            n = len(urls[a] & urls[b])
            if n:
                sim[(a, b)] = sim[(b, a)] = n
    return kws, sim


def build_clusters(serps, method="middle", threshold=THRESHOLD, depth=DEPTH):
    """Кластеризация по ТОПам. serps: [(keyword, serp|None)]. method: middle|hard.

    Возвращает список кластеров по убыванию размера:
    {"vertex": str, "keywords": [str, ...],            # вершина первой
     "sim_to_vertex": {kw: n}, "links": {kw: n_связей_внутри}}
    Запросы без SERP не кластеризуются (их нет в результате).
    """
    if method not in ("middle", "hard"):
        raise ValueError(f"Неизвестный метод кластеризации: {method}")
    kws, sim = _similarity(serps, depth)

    def link_count(k, pool):
        return sum(1 for o in pool if o != k and sim.get((k, o), 0) >= threshold)

    unassigned = set(kws)
    clusters = []
    while unassigned:
        # вершина: максимум связей; при равенстве — алфавит (детерминизм)
        marker = max(sorted(unassigned), key=lambda k: link_count(k, unassigned))
        cluster = [marker]
        unassigned.discard(marker)

        # кандидаты: связь с вершиной >= threshold, ближние первыми
        cands = sorted((k for k in unassigned if sim.get((marker, k), 0) >= threshold),
                       key=lambda k: (-sim[(marker, k)], k))
        # добираем фразы, пока новые входы открываются
        changed = True
        while changed:
            changed = False
            for k in list(cands):
                if method == "hard":
                    # hard: клика — связь с КАЖДОЙ фразой кластера
                    ok = all(sim.get((k, m), 0) >= threshold for m in cluster)
                else:
                    # middle: связь с вершиной уже есть; цепочка — хотя бы
                    # с одной из уже принятых зависимых фраз
                    ok = len(cluster) == 1 or any(
                        sim.get((k, m), 0) >= threshold for m in cluster[1:])
                if ok:
                    cluster.append(k)
                    cands.remove(k)
                    unassigned.discard(k)
                    changed = True

        clusters.append({
            "vertex": marker,
            "keywords": cluster,
            "sim_to_vertex": {k: sim.get((marker, k), 0) for k in cluster},
            "links": {k: link_count(k, cluster) for k in cluster},
        })
    clusters.sort(key=lambda c: (-len(c["keywords"]), c["vertex"]))
    return clusters


def cluster_map(clusters):
    """{keyword: имя_кластера}; имя кластера = его вершина."""
    m = {}
    for c in clusters:
        for k in c["keywords"]:
            m[k] = c["vertex"]
    return m


def clusters_rows(clusters, url_map=None):
    """Плоская таблица для листа clusters_<engine>.
    url_map: {keyword: url нашего сайта в выдаче} — колонка сразу после кластера."""
    url_map = url_map or {}
    rows = []
    for i, c in enumerate(clusters, start=1):
        for k in c["keywords"]:
            rows.append({
                "cluster_id": i,
                "vertex": c["vertex"],
                "url": url_map.get(k, ""),
                "keyword": k,
                "role": "вершина" if k == c["vertex"] else "фраза",
                "common_urls_with_vertex": c["sim_to_vertex"][k] if k != c["vertex"] else "",
                "links_in_cluster": c["links"][k],
                "cluster_size": len(c["keywords"]),
            })
    return rows
