"""Mide el clasificador con TU biblioteca (dejando uno fuera): cada libro se clasifica como si no estuviera importado ni corregido, y se compara con la etiqueta que tiene ahora.

    python herramientas/evaluar_biblioteca.py [carpeta_conocimiento] [--sin-llm] [--web] [--wiki] [-q]

Las etiquetas son las de `biblioteca/metadatos.json` (las que corregiste). Sin --web no se consulta Open Library (resultados repetibles).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from conocimiento import clasificador, importar, llm  # noqa: E402


def evaluar(carpeta: Path, con_llm: bool = True, con_web: bool = False, verbose: bool = True, wiki: bool = False) -> dict:
    clasificador.WEB, llm.ACTIVO, clasificador.WIKI = con_web, con_llm, wiki
    from conocimiento import webinfo
    webinfo._estado["cache"] = None
    webinfo._cargar(carpeta)                                   # la caché de Wikipedia vive en la carpeta real, no en la temporal de cada obra
    meta = importar.leer_metadatos(carpeta)
    base = carpeta / "biblioteca"
    obra = {r: m for r, m in meta.items() if m.get("tipo") in ("libro", "articulo") and (base / r).is_file()}
    g_ok = s_ok = s_n = 0
    fallos = []
    for rel, m in obra.items():
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "biblioteca").mkdir()
            (tmp / "biblioteca" / "metadatos.json").write_text(json.dumps({r: x for r, x in meta.items() if r != rel}, ensure_ascii=False), encoding="utf-8")
            for f in ("ajustes.json", "taxonomia.json"):
                if (carpeta / f).exists():
                    shutil.copy(carpeta / f, tmp / f)
            f = tmp / (Path(m.get("origen") or rel).stem + Path(rel).suffix)       # con el nombre original (lleva el autor)
            shutil.copy(base / rel, f)
            c = importar.clasificar(f, tmp)
        ok_g = c["genero"] == m["genero"]
        g_ok += ok_g
        if m.get("subgenero"):
            s_n += 1
            s_ok += ok_g and c["subgenero"] == m["subgenero"]
        if not ok_g or (m.get("subgenero") and c["subgenero"] != m["subgenero"]):
            fallos.append((m["titulo"][:42], f"{m['genero']}/{m.get('subgenero') or '-'}", f"{c['genero']}/{c['subgenero'] or '-'}", c["metodo"]))
    webinfo.guardar(carpeta)
    n = len(obra)
    r = {"n": n, "genero": g_ok / max(n, 1), "subgenero": s_ok / max(s_n, 1), "n_sub": s_n, "fallos": fallos}
    if verbose:
        print(f"{n} obras: género {100 * r['genero']:.0f} % · subgénero {100 * r['subgenero']:.0f} % (de {s_n} con subgénero)")
        for f in fallos:
            print("  ✗", " | ".join(f))
    return r


if __name__ == "__main__":
    a = sys.argv[1:]
    pos = [x for x in a if not x.startswith('-')]
    evaluar(Path(pos[0] if pos else importar.carpeta_datos()), con_llm="--sin-llm" not in a, con_web="--web" in a, verbose="-q" not in a, wiki="--wiki" in a)
