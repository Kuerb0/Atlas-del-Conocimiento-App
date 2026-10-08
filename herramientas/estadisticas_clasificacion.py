"""Estadísticas de los resultados de evaluar_corpus.py.

    python herramientas/estadisticas_clasificacion.py resultados/A.json [resultados/B.json ...]

Por configuración: acierto de género y de subgénero con intervalo de Wilson al 95 %, acierto por tipo de archivo, F1 macro del género, calibración de la confianza y los
pares de géneros que más se confunden. Con varias: prueba exacta de McNemar (pareada, sobre las mismas obras) de la primera frente a cada otra.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import binomtest

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return c - h, c + h


def f1_macro(filas: list[dict]) -> float:
    fs = []
    for c in {x["g"] for x in filas}:
        tp = sum(x["g"] == c and x["pg"] == c for x in filas)
        fp = sum(x["g"] != c and x["pg"] == c for x in filas)
        fn = sum(x["g"] == c and x["pg"] != c for x in filas)
        fs.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(fs) / len(fs)


def resumen(r: dict) -> None:
    f = r["filas"]
    n, k = len(f), sum(x["g"] == x["pg"] for x in f)
    ls = [x for x in f if x["s"]]
    ks = sum(x["g"] == x["pg"] and x["s"] == x["ps"] for x in ls)
    lo, hi = wilson(k, n)
    lo2, hi2 = wilson(ks, len(ls))
    print(f"\n== {r['nombre']}  (LLM {r['modelo_llm'] if r['llm'] else 'no'}; {', '.join(r['sets']) or 'ajustes por defecto'})")
    print(f"  género    {100 * k / n:5.1f} %  IC95 [{100 * lo:.0f}, {100 * hi:.0f}]   n={n}   F1 macro {100 * f1_macro(f):.0f} %")
    print(f"  subgénero {100 * ks / max(len(ls), 1):5.1f} %  IC95 [{100 * lo2:.0f}, {100 * hi2:.0f}]   n={len(ls)}")
    print("  por tipo: " + "  ".join(f"{t} {100 * sum(x['g'] == x['pg'] for x in f if x['tipo'] == t) / m:.0f} % (n={m})" for t, m in sorted(Counter(x["tipo"] for x in f).items())))
    print(f"  método: {dict(Counter(x['metodo'] for x in f))}   tiempo medio {sum(x['seg'] for x in f) / n:.1f} s/obra")
    bins = defaultdict(lambda: [0, 0])
    for x in f:
        if x["conf"] is not None:
            b = min(int(x["conf"] * 10), 5)
            bins[b][0] += x["g"] == x["pg"]
            bins[b][1] += 1
    if bins:
        print("  calibración (confianza del parecido → acierto): " + "  ".join(f"{b / 10:.1f}+: {100 * v[0] / v[1]:.0f} % (n={v[1]})" for b, v in sorted(bins.items())))
    marc = [x for x in f if x.get("revisar")]
    if any("revisar" in x for x in f):
        err = [x for x in f if x["g"] != x["pg"] or (x["s"] and x["s"] != x["ps"])]       # error de género o de subgénero
        cogidos = [x for x in err if x.get("revisar")]
        libres = [x for x in f if not x.get("revisar")]
        ok_libres = sum(x["g"] == x["pg"] and (not x["s"] or x["s"] == x["ps"]) for x in libres)
        print(f"  cola de revisión: marca {100 * len(marc) / n:.0f} % de las obras y recoge {100 * len(cogidos) / max(len(err), 1):.0f} % de los errores; lo no marcado acierta {100 * ok_libres / max(len(libres), 1):.0f} %")
    print("  confusiones: " + ", ".join(f"{g}→{p} ×{c}" for (g, p), c in Counter((x["g"], x["pg"]) for x in f if x["g"] != x["pg"]).most_common(6)))


def mcnemar(a: dict, b: dict, campo: str) -> str:
    fa, fb = {x["rel"]: x for x in a["filas"]}, {x["rel"]: x for x in b["filas"]}
    ok = (lambda x: x["g"] == x["pg"]) if campo == "g" else (lambda x: x["g"] == x["pg"] and x["s"] == x["ps"])
    sel = [r for r in fa.keys() & fb.keys() if campo == "g" or fa[r]["s"]]
    n10 = sum(ok(fa[r]) and not ok(fb[r]) for r in sel)
    n01 = sum(not ok(fa[r]) and ok(fb[r]) for r in sel)
    p = binomtest(n10, n10 + n01, 0.5).pvalue if n10 + n01 else 1.0
    return f"{'género' if campo == 'g' else 'subgénero'}: {a['nombre']} solo acierta {n10}, {b['nombre']} solo acierta {n01} → p = {p:.3f}" + ("  *" if p < 0.05 else "")


if __name__ == "__main__":
    rs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[1:]]
    for r in rs:
        resumen(r)
    for r in rs[1:]:
        print("\nMcNemar (", rs[0]["nombre"], "vs", r["nombre"], ")  ", mcnemar(rs[0], r, "g"), " | ", mcnemar(rs[0], r, "s"))
