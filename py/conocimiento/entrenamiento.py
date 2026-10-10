"""Reentrenar el LLM desde la app (pestaña «🧠 Entrenamiento»): lanzarlo, pararlo y enseñar el panel de progreso.

El entrenamiento corre en un proceso APARTE (`herramientas/entrenador/entrenar_llm.bat`), sin ventana y sin colgar de la app: se puede cerrar y
volver a abrir la app mientras entrena, y el panel (`herramientas/panel_progreso.py`, en localhost) sigue leyendo los ficheros que va escribiendo.
Solo existe en la carpeta de desarrollo (necesita `herramientas/` y el corpus `corpus/enes`); en una instalación normal `estado()` dice por qué no está.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import CARPETA, RAIZ

PUERTO = 8765
MODELOS = {"Qwen/Qwen2.5-3B-Instruct": "3B (cabe con 12 GB de VRAM)", "Qwen/Qwen2.5-7B-Instruct": "7B (cierra todo lo demás: necesita casi toda la VRAM)"}
_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def _subiendo(inicio: Path):
    """La carpeta, y las de arriba (los worktrees de Claude viven dentro de la carpeta principal)."""
    yield inicio
    yield from inicio.parents


def corpus() -> Path | None:
    """Carpeta con `enes/` (el corpus): ARBOL_CORPUS, o `corpus/` en esta carpeta o en alguna de arriba."""
    if os.environ.get("ARBOL_CORPUS"):
        return Path(os.environ["ARBOL_CORPUS"])
    return next((d / "corpus" for d in _subiendo(RAIZ) if (d / "corpus" / "enes").is_dir()), None)


def venv_python() -> Path | None:
    """El Python del entorno de entrenamiento (torch, peft…): ARBOL_VENV, el de esta carpeta o el de algún worktree hermano (es gitignored y pesa 5 GB: no se duplica)."""
    rel = Path("herramientas/entrenador/.venv/Scripts/python.exe")
    if os.environ.get("ARBOL_VENV"):
        p = Path(os.environ["ARBOL_VENV"]) / "Scripts" / "python.exe"
        return p if p.exists() else None
    for d in _subiendo(RAIZ):
        for p in [d / rel, *sorted((d / ".claude" / "worktrees").glob(f"*/{rel.as_posix()}"))]:
            if p.exists():
                return p
    return None


def _marca(c: Path) -> Path:
    return c / "enes" / "entrenamiento" / "_lanzado.json"


def _vivo(pid: int) -> bool:
    try:
        salida = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, timeout=10, creationflags=_SIN_VENTANA).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return str(pid) in salida


def _lanzado(c: Path) -> dict | None:
    try:
        m = json.loads(_marca(c).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return m if _vivo(int(m.get("pid", 0))) else None


def _escucha() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}/", timeout=1.5):
            return True
    except OSError:
        return False


def estado() -> dict:
    """{disponible, motivo, panel, entrenando: {nombre, modelo, pid, desde} | None, modelos, ultimo}."""
    c, v = corpus(), venv_python()
    if not (RAIZ / "herramientas" / "panel_progreso.py").exists():
        return {"disponible": False, "motivo": "Esta pestaña solo está en la carpeta de desarrollo (falta herramientas/)."}
    if c is None:
        return {"disponible": False, "motivo": "No encuentro el corpus (corpus/enes). Móntalo con herramientas/corpus/ o define ARBOL_CORPUS."}
    ult = sorted((c / "enes" / "entrenamiento").glob("*/resultado.json"), key=lambda p: p.stat().st_mtime)
    return {"disponible": True, "motivo": "" if v else "Falta el entorno de entrenamiento: ejecuta entrenar_llm.bat preparar (unos 5 GB).", "entorno": bool(v), "panel": f"http://localhost:{PUERTO}",
            "entrenando": _lanzado(c), "modelos": MODELOS, "ultimo": ult[-1].parent.name if ult else ""}


def abrir_panel() -> dict:
    """Arranca el panel de progreso si no está escuchando y devuelve su URL."""
    e = estado()
    if not e["disponible"]:
        return {"error": e["motivo"]}
    if not _escucha():
        py = Path(sys.executable)
        if py.name.lower() == "pythonw.exe" and (py.parent / "python.exe").exists():
            py = py.parent / "python.exe"
        subprocess.Popen([str(py), str(RAIZ / "herramientas" / "panel_progreso.py"), str(corpus()), "--puerto", str(PUERTO)], cwd=str(RAIZ), creationflags=_SIN_VENTANA,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        for _ in range(30):
            time.sleep(.3)
            if _escucha():
                break
    return {"url": e["panel"]}


def _soltar_gpu() -> None:
    """Descarga de la VRAM los modelos que Ollama tenga cargados (el entrenamiento los necesita; ya se recargarán solos al usarlos)."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=2) as x:
            nombres = [m["name"] for m in json.load(x).get("models", [])]
        for n in nombres:
            urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/generate", json.dumps({"model": n, "keep_alive": 0}).encode(), {"Content-Type": "application/json"}), timeout=10).close()
    except (OSError, ValueError):
        pass


def lanzar(nombre: str, modelo: str = "Qwen/Qwen2.5-3B-Instruct", biblioteca: bool = False) -> dict:
    """Lanza datos (si faltan o si `biblioteca`: suma tu biblioteca) + entrenamiento, ambos en segundo plano. Un nombre ya usado se reanuda, no se pisa."""
    e = estado()
    if not e["disponible"] or not e["entorno"]:
        return {"error": e["motivo"]}
    if e["entrenando"]:
        return {"error": f"ya hay un entrenamiento en marcha ({e['entrenando']['nombre']})"}
    nombre = "".join(ch for ch in str(nombre) if ch.isalnum() or ch in "-_") or "ft2"
    if modelo not in MODELOS:
        return {"error": "modelo no permitido: " + modelo}
    c, bat = corpus(), RAIZ / "herramientas" / "entrenador" / "entrenar_llm.bat"
    datos = c / "enes" / "entrenamiento" / "datos" / "train.jsonl"
    pasos = []
    if biblioteca or not datos.exists():
        pasos.append(f'call "{bat}" datos "{c}"' + (f' --biblioteca "{CARPETA}"' if biblioteca else ""))
    pasos.append(f'call "{bat}" entrenar "{c}" {modelo} {nombre}')
    (c / "enes" / "entrenamiento").mkdir(parents=True, exist_ok=True)
    lote = c / "enes" / "entrenamiento" / "_lanzar.bat"
    lote.write_text("@echo off\nset \"ARBOL_VENV=%s\"\n%s\n" % (venv_python().parent.parent, " && ".join(pasos)), encoding="utf-8")
    _soltar_gpu()
    p = subprocess.Popen(["cmd", "/c", str(lote)], cwd=str(RAIZ), creationflags=_SIN_VENTANA, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    _marca(c).write_text(json.dumps({"pid": p.pid, "nombre": nombre, "modelo": modelo, "desde": time.strftime("%Y-%m-%d %H:%M:%S")}), encoding="utf-8")
    return {"ok": True, "pid": p.pid}


def parar() -> dict:
    """Corta el entrenamiento y todo lo que cuelga de él. El último adaptador guardado queda: lanzar con el mismo nombre lo reanuda."""
    c = corpus()
    m = _lanzado(c) if c else None
    if not m:
        return {"error": "no hay ningún entrenamiento en marcha"}
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(m["pid"])], capture_output=True, creationflags=_SIN_VENTANA)
    return {"ok": True}
