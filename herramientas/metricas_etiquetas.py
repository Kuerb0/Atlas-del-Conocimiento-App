"""Métricas de la clasificación con varias etiquetas por obra (géneros y subgéneros), a partir de las filas de `evaluar_corpus.py`.

Cada fila trae, además de la etiqueta única de siempre (`g`, `s`, `pg`, `ps`), los conjuntos `gs`/`pgs` (géneros reales y predichos, el principal primero) y `ss`/`pss`
(pares [género, subgénero]). Los resultados antiguos no los tienen: se leen como conjuntos de un solo elemento, así que la serie histórica sigue siendo comparable.

Con una sola etiqueta real por obra (el corpus de Gutenberg/arXiv) lo que importa es:
  · «principal en el conjunto»: la etiqueta real está entre las predichas (recall@k de la etiqueta única; es lo comparable con el acierto de antes),
  · «etiquetas de más»: cuántas etiquetas predice de media de más que las reales (si predice 3 siempre, acierta fácil pero no sirve).
Con varias etiquetas reales (lo que corriges tú en el Observatorio) se añaden precisión, exhaustividad, F1 micro, Jaccard medio, conjunto exacto y F1 macro por etiqueta.
"""
from __future__ import annotations

from collections import defaultdict


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return c - h, c + h


def conjuntos(x: dict) -> dict:
    """{'g': set géneros reales, 'pg': set predichos, 's': set de (género, subgénero) reales, 'ps': predichos} de una fila (también de las antiguas)."""
    gs, pgs = x.get("gs") or [x["g"]], x.get("pgs") or [x["pg"]]
    ss = x.get("ss") if x.get("ss") is not None else ([[x["g"], x["s"]]] if x.get("s") else [])
    pss = x.get("pss") if x.get("pss") is not None else ([[x["pg"], x["ps"]]] if x.get("ps") else [])
    return {"g": set(gs), "pg": set(pgs), "s": {tuple(p) for p in ss}, "ps": {tuple(p) for p in pss}, "g1": x["g"], "s1": (x["g"], x["s"]) if x.get("s") else None}


def _nivel(filas: list[dict], real: str, pred: str, uno: str) -> dict:
    """Métricas de un nivel (géneros o subgéneros). `real`/`pred` son las claves de conjuntos; `uno` la de la etiqueta principal real."""
    cs = [conjuntos(x) for x in filas]
    cs = [c for c in cs if c[real]]                                       # sin etiqueta real (p. ej. un código sin subgénero) no hay nada que medir
    n = len(cs)
    if not n:
        return {"n": 0}
    tp = sum(len(c[real] & c[pred]) for c in cs)
    p_tot, r_tot = sum(len(c[pred]) for c in cs), sum(len(c[real]) for c in cs)
    prec, rec = tp / max(p_tot, 1), tp / max(r_tot, 1)
    k_prin = sum(c[uno] in c[pred] for c in cs)
    por = defaultdict(lambda: [0, 0, 0])                                  # etiqueta -> [tp, fp, fn]
    for c in cs:
        for e in c[real] | c[pred]:
            por[e][0 if e in c[real] and e in c[pred] else 1 if e in c[pred] else 2] += 1
    f1s = [0.0 if t == 0 else 2 * t / (2 * t + fp + fn) for t, fp, fn in por.values()]
    return {"n": n, "principal_en_conjunto": k_prin, "ic_principal": wilson(k_prin, n), "precision": prec, "exhaustividad": rec, "f1_micro": 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec),
            "f1_macro": sum(f1s) / len(f1s), "jaccard": sum(len(c[real] & c[pred]) / len(c[real] | c[pred]) for c in cs) / n, "exacto": sum(c[real] == c[pred] for c in cs) / n,
            "pred_media": p_tot / n, "real_media": r_tot / n, "de_mas": (p_tot - r_tot) / n}


def metricas(filas: list[dict]) -> dict:
    """{'genero': {...}, 'subgenero': {...}} con las métricas anteriores a cada nivel."""
    return {"genero": _nivel(filas, "g", "pg", "g1"), "subgenero": _nivel([x for x in filas if x.get("s") or x.get("ss")], "s", "ps", "s1")}


def etiquetas_multiples(filas: list[dict]) -> dict:
    """Cuántas obras tienen más de una etiqueta (reales y predichas) y la matriz de coocurrencia de géneros predichos {(a, b): n}: qué géneros se dan juntos."""
    cs = [conjuntos(x) for x in filas]
    co = defaultdict(int)
    for c in cs:
        for a in sorted(c["pg"]):
            for b in sorted(c["pg"]):
                if a < b:
                    co[(a, b)] += 1
    return {"n": len(cs), "reales_multiples": sum(len(c["g"]) > 1 for c in cs), "predichas_multiples": sum(len(c["pg"]) > 1 for c in cs), "coocurrencia": dict(co)}
