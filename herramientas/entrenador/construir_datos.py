"""Datos para reentrenar el LLM que clasifica (géneros y subgéneros, varias etiquetas por obra).

    python herramientas/entrenador/construir_datos.py CARPETA_CORPUS [--biblioteca RUTA/conocimiento] [--salida DIR] [--val 0.1] [--vecinos 8] [--max N]

CARPETA_CORPUS es la carpeta con `enes/corpus/biblioteca/metadatos.json` (etiquetas buenas) y `enes/split.json`: SOLO las obras de entrenamiento entran (las de prueba no se tocan, para poder
medir de verdad). Con --biblioteca se añade tu propia biblioteca (lo que corregiste tú pesa el doble: sale repetido). Por cada obra salen ejemplos de dos tareas, con EXACTAMENTE el
prompt con el que luego se pregunta al modelo (`llm.prompt_generos` y `llm.prompt_subgeneros`), incluidos los 8 libros más parecidos como ejemplos resueltos (calculados sin contar la propia obra):
  · género:    {"generos": ["historia", "economia"], "motivo": "…"}
  · subgénero: {"subgeneros": ["antigua"], "motivo": "…"}   (uno por cada género de la obra)
Escribe en DIR (por defecto CARPETA_CORPUS/enes/entrenamiento/datos): train.jsonl, val.jsonl (la validación se parte por obra, no por ejemplo) y resumen.json con lo que hay (para el panel).
Cada línea: {"messages": [{"role": "user", ...}, {"role": "assistant", ...}], "tarea", "rel", "generos"}.
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "py"))
sys.path.insert(0, str(RAIZ / "herramientas"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402

from conocimiento import clasificador, etiquetas, importar, llm, taxonomia  # noqa: E402

clasificador.WEB = False
clasificador.WIKI = False


def motivo(ids: list[str], nombres: dict) -> str:
    """Frase corta y fija para el campo «motivo» (el modelo solo necesita aprender la forma; lo que importa son las etiquetas)."""
    n = [nombres.get(i, i) for i in ids]
    return "Trata de " + (n[0] if len(n) == 1 else ", ".join(n[:-1]) + " y " + n[-1])


def leer_obra(f: Path) -> tuple[str, str]:
    texto, _ = importar._muestra(f)
    texto = importar.sin_licencia(texto)
    return texto, re.sub(r"\s+", " ", texto[:1500])


def vecinos_de(i: int, X: np.ndarray, fichas: list[dict], k: int) -> list[dict]:
    """Los k libros más parecidos a la obra i sin contarla a ella ni a sus copias (mismo título)."""
    sim = X @ X[i]
    orden = [j for j in np.argsort(-sim) if j != i and fichas[j]["titulo"] != fichas[i]["titulo"]][:k]
    return [{k2: fichas[j][k2] for k2 in ("titulo", "autor", "genero", "subgenero", "generos", "subgeneros")} for j in orden]


def main() -> None:
    a = sys.argv[1:]
    corpus = Path(a[0])
    opt = lambda n, d: a[a.index(n) + 1] if n in a else d
    salida = Path(opt("--salida", corpus / "enes" / "entrenamiento" / "datos"))
    frac_val, k, tope = float(opt("--val", 0.1)), int(opt("--vecinos", 8)), int(opt("--max", 0))
    carpeta = corpus / "enes" / "corpus"
    meta = importar.leer_metadatos(carpeta)
    sp = json.loads((corpus / "enes" / "split.json").read_text(encoding="utf-8"))
    ent = set(sp["entrenamiento"])
    obras = [(carpeta, rel, m, 1) for rel, m in sorted(meta.items()) if rel in ent and (carpeta / "biblioteca" / rel).is_file() and m.get("tipo") in ("libro", "articulo", "video", "apuntes")]
    if "--biblioteca" in a:
        mia = Path(opt("--biblioteca", ""))
        for rel, m in sorted(importar.leer_metadatos(mia).items()):
            if (mia / "biblioteca" / rel).is_file() and m.get("tipo") in ("libro", "articulo", "video", "apuntes"):
                obras.append((mia, rel, m, 1 if m.get("automatico") else 2))        # lo que corregiste tú vale doble
    if tope:
        random.Random(1).shuffle(obras)
        obras = obras[:tope]
    print(f"{len(obras)} obras de entrenamiento", flush=True)

    t0, fichas, textos = time.time(), [], []
    for n, (base, rel, m, peso) in enumerate(obras):
        try:
            texto, vista = leer_obra(base / "biblioteca" / rel)
        except Exception as e:                                                                   # un fichero ilegible no frena a los demás
            print("  no se pudo leer", rel, type(e).__name__, flush=True)
            continue
        origen = Path(m.get("origen", "")).stem or m.get("titulo", "")
        fichas.append({"rel": rel, "titulo": m.get("titulo", ""), "autor": clasificador.autor_de(origen), "genero": m["genero"], "subgenero": m.get("subgenero", ""),
                       "generos": etiquetas.generos_de(m), "subgeneros": [s for _, s in etiquetas.subgeneros_de(m)], "pares": etiquetas.subgeneros_de(m),
                       "caps": m.get("capitulos", []), "vista": vista, "materias": m.get("materias_web", []), "peso": peso, "base": base})
        textos.append(clasificador.texto_libro(m.get("titulo", ""), m.get("capitulos", []), vista))
        if (n + 1) % 100 == 0:
            print(f"  leídas {n + 1}/{len(obras)}  ({time.time() - t0:.0f} s)", flush=True)
    emb = clasificador._embedder(clasificador.modelo(carpeta), carpeta)
    X = emb(textos)
    print(f"{len(fichas)} obras leídas y vectorizadas ({time.time() - t0:.0f} s)", flush=True)

    nombres = importar.GENEROS
    rng = random.Random(42)
    val_rel = {f["rel"] for f in rng.sample(fichas, max(1, round(len(fichas) * frac_val)))}
    train, val = [], []
    for i, f in enumerate(fichas):
        vec = vecinos_de(i, X, fichas, k)
        ejemplos = [{"tarea": "genero", "prompt": llm.prompt_generos(f["titulo"], f["caps"], f["vista"][:600], f["materias"], nombres, f["autor"], vec),
                     "respuesta": json.dumps({"generos": f["generos"], "motivo": motivo(f["generos"], nombres)}, ensure_ascii=False)}]
        for g in f["generos"]:                                                                     # un ejemplo de subgénero por cada género de la obra
            subs = taxonomia.subgeneros(g, carpeta)
            ids = [s for gg, s in f["pares"] if gg == g]
            if subs and ids:
                ejemplos.append({"tarea": "subgenero", "prompt": llm.prompt_subgeneros(f["titulo"], f["caps"], f["vista"][:600], nombres[g], subs, f["autor"], vec),
                                 "respuesta": json.dumps({"subgeneros": ids, "motivo": motivo(ids, {s[0]: s[1] for s in subs})}, ensure_ascii=False)})
        for e in ejemplos:
            fila = {"messages": [{"role": "user", "content": e["prompt"]}, {"role": "assistant", "content": e["respuesta"]}], "tarea": e["tarea"], "rel": f["rel"], "generos": f["generos"]}
            (val if f["rel"] in val_rel else train).extend([fila] * (f["peso"] if f["rel"] not in val_rel else 1))
    rng.shuffle(train)
    salida.mkdir(parents=True, exist_ok=True)
    for nombre, filas in (("train", train), ("val", val)):
        (salida / f"{nombre}.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in filas) + "\n", encoding="utf-8")
    largo = [len(x["messages"][0]["content"]) + len(x["messages"][1]["content"]) for x in train]
    resumen = {"hora": time.strftime("%Y-%m-%d %H:%M"), "obras": len(fichas), "obras_val": len(val_rel), "ejemplos_train": len(train), "ejemplos_val": len(val),
               "por_tarea": dict(Counter(x["tarea"] for x in train)), "generos": dict(Counter(g for f in fichas for g in f["generos"])),
               "etiquetas_por_obra": dict(Counter(len(f["generos"]) for f in fichas)), "con_varias_etiquetas": sum(len(f["generos"]) > 1 for f in fichas),
               "caracteres_medios": round(sum(largo) / max(len(largo), 1)), "caracteres_max": max(largo, default=0), "vecinos": k, "tokens_aprox": round(sum(largo) / 3.4)}
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    print(f"-> {salida}  ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
