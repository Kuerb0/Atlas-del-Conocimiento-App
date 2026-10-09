"""Evalúa el clasificador con un corpus grande etiquetado, separando entrenamiento y prueba.

    python herramientas/evaluar_corpus.py CARPETA NOMBRE [--sin-llm] [--web] [--set modulo.ATRIBUTO=valor ...] [--prueba 0.25] [--val] [--n 100] [--hilos 6]

CARPETA es una carpeta de conocimiento con `biblioteca/metadatos.json` (etiquetas buenas). Un 25 % de las obras (estratificado por género y tipo, semilla fija, guardado en
`CARPETA/../split.json`) es de PRUEBA: se clasifica como si no estuviera importado, y sus ejemplos son solo los de entrenamiento. Guarda las predicciones en
`CARPETA/../resultados/NOMBRE.json`; `herramientas/estadisticas_clasificacion.py` calcula intervalos, F1, calibración y las comparaciones entre configuraciones.
"""
from __future__ import annotations

import json
import random
import shutil
import sys
import tempfile
import threading
import time
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
import os
sys.path.insert(0, os.environ.get("ARBOL_PY") or str(RAIZ / "py"))      # ARBOL_PY=otra carpeta py: mide otra versión del código (p. ej. la publicada)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from conocimiento import clasificador, importar, llm  # noqa: E402
try:
    from conocimiento import etiquetas  # noqa: E402
except ImportError:                       # versiones anteriores a la 1.13 (ARBOL_PY): una sola etiqueta
    etiquetas = None

def _multi(m: dict, c: dict) -> dict:
    """Las etiquetas reales (`gs`, `ss`) y las predichas (`pgs`, `pss`) de una obra, para metricas_etiquetas.py; vacío con versiones del código anteriores a la 1.13 (ARBOL_PY)."""
    if etiquetas is None or "etiquetas" not in c:
        return {}
    return {"gs": etiquetas.generos_de(m), "ss": [list(p) for p in etiquetas.subgeneros_de(m)],
            "pgs": [e["id"] for e in c["etiquetas"]["generos"]], "pss": [[e["genero"], e["id"]] for e in c["etiquetas"]["subgeneros"]]}


TIPOS_EVAL = ("libro", "articulo", "codigo", "datos")


def partir(carpeta: Path, frac: float = 0.25, semilla: int = 42, val: bool = False) -> dict:
    """Prueba/entrenamiento. Con val=True se vuelve a partir SOLO el entrenamiento (validación para ajustar parámetros sin mirar la prueba)."""
    f = carpeta.parent / ("split_val.json" if val else "split.json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    meta = importar.leer_metadatos(carpeta)
    if val:
        meta = {r: meta[r] for r in partir(carpeta, frac)["entrenamiento"]}
    por = defaultdict(list)
    for rel, m in sorted(meta.items()):
        if m.get("tipo") in TIPOS_EVAL and (carpeta / "biblioteca" / rel).is_file():
            por[(m["genero"], m["tipo"])].append(rel)
    rng, prueba = random.Random(semilla), []
    for grupo in por.values():
        rng.shuffle(grupo)
        prueba += grupo[: max(1, round(len(grupo) * frac))] if len(grupo) >= 4 else []
    r = {"prueba": sorted(prueba), "entrenamiento": sorted(set(meta) - set(prueba))}
    f.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return r


def aplicar(sets: list[str]) -> None:
    for s in sets:
        k, v = s.split("=", 1)
        mod, attr = k.rsplit(".", 1)
        obj = {"clasificador": clasificador, "llm": llm, "importar": importar, "etiquetas": etiquetas}[mod]       # etiquetas.DELTA, etiquetas.DELTA_SUB, etiquetas.MAXIMO: los mandos de las varias etiquetas
        setattr(obj, attr, json.loads(v))


def recursos() -> dict:
    """RAM libre (GB), uso de la GPU (%) y VRAM libre (MB); lo que no se pueda medir queda en None (entonces no se sube la carga por ese motivo)."""
    r = {"ram_gb": None, "gpu": None, "vram_mb": None}
    try:
        import psutil
        r["ram_gb"] = psutil.virtual_memory().available / 1e9
    except Exception:
        pass
    try:
        import subprocess
        o = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4).stdout.strip().split(", ")
        r["gpu"], r["vram_mb"] = int(o[0]), int(o[2]) - int(o[1])
    except Exception:
        pass
    return r


class Regulador:
    """Cuántas obras se clasifican a la vez. Empieza con 1 y cada 5 segundos sube o baja según lo que le quede libre al equipo:
    sube si hay RAM y VRAM de sobra y la GPU no está saturada; baja si la RAM o la VRAM se acaban."""
    RAM_MIN, RAM_SOBRA, VRAM_MIN, VRAM_SOBRA, GPU_TOPE = 1.2, 2.5, 300, 900, 85

    def __init__(self, maximo: int):
        self.maximo, self.limite, self.activos, self.cv, self.fin, self.ultimo = maximo, 1, 0, threading.Condition(), False, {}

    def entrar(self) -> None:
        with self.cv:
            while self.activos >= self.limite:
                self.cv.wait(1.0)
            self.activos += 1

    def salir(self) -> None:
        with self.cv:
            self.activos -= 1
            self.cv.notify_all()

    def vigilar(self) -> None:
        while not self.fin:
            r = recursos()
            self.ultimo = r
            ram, gpu, vram = r["ram_gb"], r["gpu"], r["vram_mb"]
            with self.cv:
                if (ram is not None and ram < self.RAM_MIN) or (vram is not None and vram < self.VRAM_MIN):
                    self.limite = max(1, self.limite - 1)
                elif self.activos >= self.limite and self.limite < self.maximo and (ram is None or ram > self.RAM_SOBRA) and (vram is None or vram > self.VRAM_SOBRA) and (gpu is None or gpu < self.GPU_TOPE):
                    self.limite += 1
                self.cv.notify_all()
            time.sleep(5)


def evaluar(carpeta: Path, nombre: str, con_llm: bool = True, con_web: bool = False, frac: float = 0.25, sets: list[str] | None = None, val: bool = False, n_max: int = 0, hilos: int = 1) -> list[dict]:
    """`hilos` > 1: clasifica varias obras a la vez con un Regulador que sube o baja la carga según la RAM, la VRAM y la GPU libres (hilos = tope)."""
    clasificador.WEB, llm.ACTIVO = con_web, con_llm
    aplicar(sets or [])
    meta, sp = importar.leer_metadatos(carpeta), partir(carpeta, frac, val=val)
    base, filas = carpeta / "biblioteca", []
    parcial = carpeta.parent / "resultados" / f"_parcial_{nombre}.json"      # lo ya clasificado: si se corta (reinicio del PC, GPU sin memoria…) al repetir se sigue por donde iba
    if parcial.exists():
        try:
            previo = json.loads(parcial.read_text(encoding="utf-8"))
            if previo.get("sets") == (sets or []) and previo.get("llm") == con_llm:
                filas.extend(previo["filas"])
                print(f"  reanudo: {len(filas)} obras ya clasificadas", flush=True)
        except (OSError, ValueError):
            pass
    hechas = {x["rel"] for x in filas}
    pendientes = [r for r in sp["prueba"] if r not in hechas]
    if n_max and n_max < len(sp["prueba"]):
        sp = {**sp, "prueba": sorted(random.Random(1).sample(sp["prueba"], n_max))}      # misma muestra siempre: las configuraciones se comparan sobre las mismas obras
    train = {r: m for r, m in meta.items() if r in set(sp["entrenamiento"])}      # (con val=True, la prueba real queda fuera: ni como ejemplo)
    reg, t0, cerrojo = Regulador(max(hilos, 1)), time.time(), threading.Lock()
    try:
        from conocimiento import webinfo                      # (las versiones anteriores a la 1.11 no lo tienen: se puede medir con ARBOL_PY)
    except ImportError:
        webinfo = None
    if webinfo:
        webinfo._estado["cache"] = None
        webinfo._cargar(carpeta)                                   # la caché de Wikipedia vive en la carpeta del corpus (no en la temporal de cada obra)
    if hilos > 1:
        threading.Thread(target=reg.vigilar, daemon=True).start()

    def clasificar_con_llm(f, tmp):
        """Clasifica; si el LLM tenía que contestar y no pudo (servidor caído, GPU sin memoria…) espera 30 s y repite (hasta 8 veces). Devuelve (resultado, ¿sigue sin LLM?)."""
        for _ in range(8):
            caido = []
            c = importar.clasificar(f, tmp, etapa=lambda fase, d: caido.append(1) if fase == "llm" and "no está disponible" in str(d.get("omitido", "")) else None)
            if not caido or not (con_llm and llm.ACTIVO):
                return c, False
            llm._estado.clear()                                              # que vuelva a comprobar si está disponible
            time.sleep(30)
        return c, True

    def una(rel: str) -> dict:
        m = meta[rel]
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "biblioteca").mkdir()
            (tmp / "biblioteca" / "metadatos.json").write_text(json.dumps(train, ensure_ascii=False), encoding="utf-8")
            if (base / "vectores.npz").exists():                           # los vectores del cuerpo de los ejemplos (no se recalculan por obra)
                shutil.copy(base / "vectores.npz", tmp / "biblioteca" / "vectores.npz")
            for f in ("ajustes.json", "taxonomia.json"):
                if (carpeta / f).exists():
                    shutil.copy(carpeta / f, tmp / f)
            f = tmp / (Path(m.get("origen") or rel).stem + Path(rel).suffix)
            shutil.copy(base / rel, f)
            t1 = time.time()
            c, sin_llm = clasificar_con_llm(f, tmp)
        return {"rel": rel, "titulo": m["titulo"][:60], "tipo": m["tipo"], "g": m["genero"], "s": m.get("subgenero") or "", "pg": c["genero"], "ps": c["subgenero"] or "",
                "metodo": c["metodo"], "conf": c.get("confianza"), "margen": c.get("margen"), "msub": c.get("margen_sub"), "revisar": c.get("revisar"), "seg": round(time.time() - t1, 2), "sin_llm": sin_llm, **_multi(m, c)}

    def hecha(fila: dict) -> None:
        with cerrojo:
            filas.append(fila)
            if len(filas) % 10 == 0:
                try:
                    parcial.parent.mkdir(exist_ok=True)
                    parcial.write_text(json.dumps({"sets": sets or [], "llm": con_llm, "filas": filas}, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
            i, ok = len(filas), sum(x["g"] == x["pg"] for x in filas)
            if i % 20 == 0:
                print(f"  {i}/{len(sp['prueba'])}  género {100 * ok / i:.0f} %  ({time.time() - t0:.0f} s)  hilos {reg.limite}", flush=True)
            try:        # para el panel de progreso (herramientas/panel_progreso.py)
                (carpeta.parent / "resultados").mkdir(exist_ok=True)
                vivo = {"nombre": nombre, "i": i, "n": len(sp["prueba"]), "aciertos": ok, "seg": round(time.time() - t0, 1), "t": time.time(), "llm": con_llm,
                        "hilos": {"limite": reg.limite, "activos": reg.activos, "maximo": reg.maximo}, "recursos": reg.ultimo, "ultimas": filas[-8:]}
                (carpeta.parent / "resultados" / "_vivo.json").write_text(json.dumps(vivo, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass

    def tarea(rel: str) -> None:
        reg.entrar()
        try:
            hecha(una(rel))
        finally:
            reg.salir()

    if hilos > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(hilos) as ex:
            list(ex.map(tarea, pendientes))
        reg.fin = True
        filas.sort(key=lambda x: x["rel"])
    else:
        for rel in pendientes:
            hecha(una(rel))
    if webinfo:
        webinfo.guardar(carpeta)
    out = carpeta.parent / "resultados"
    out.mkdir(exist_ok=True)
    (out / f"{nombre}.json").write_text(json.dumps({"nombre": nombre, "sets": sets or [], "llm": con_llm, "modelo_llm": llm.ajustes(carpeta)["modelo"], "filas": filas, "hilos": hilos, "llm_fallos": sum(bool(x.get("sin_llm")) for x in filas), "version": (Path(importar.__file__).resolve().parent.parent / "VERSION.txt").read_text(encoding="utf-8").strip() if (Path(importar.__file__).resolve().parent.parent / "VERSION.txt").exists() else ""}, ensure_ascii=False, indent=1), encoding="utf-8")
    return filas


if __name__ == "__main__":
    a = sys.argv[1:]
    sets = [a[i + 1] for i, x in enumerate(a) if x == "--set"]
    frac = float(a[a.index("--prueba") + 1]) if "--prueba" in a else 0.25
    pos = [x for x in a if not x.startswith("--") and x not in sets and x != str(frac) and not ("--n" in a and x == a[a.index("--n") + 1]) and not ("--hilos" in a and x == a[a.index("--hilos") + 1])]
    f = evaluar(Path(pos[0]), pos[1], con_llm="--sin-llm" not in a, con_web="--web" in a, frac=frac, sets=sets, val="--val" in a, n_max=int(a[a.index("--n") + 1]) if "--n" in a else 0, hilos=int(a[a.index("--hilos") + 1]) if "--hilos" in a else 1)
    print(f"{len(f)} obras de prueba: género {100 * sum(x['g'] == x['pg'] for x in f) / len(f):.1f} %")
