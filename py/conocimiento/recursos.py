"""Límites de GPU, VRAM y RAM para el entrenamiento y para el LLM (pestaña «🧠 IA» › Configuración) y lectura del uso real de la máquina.

Se guardan en `conocimiento/ajustes.json` → {"recursos": {"vram": 85, "ram": 80, "gpu": 100}} (porcentajes; 100 = sin límite). Qué se puede limitar de verdad:
  · VRAM: entrenamiento → tope real (`torch.cuda.set_per_process_memory_fraction`, lo lee entrenar.py de ARBOL_VRAM_PCT); Ollama → aproximado: se reparten las capas
    del modelo entre GPU y CPU (`num_gpu`), así que con menos VRAM el modelo sigue cabiendo pero va más lento.
  · RAM: tope real al proceso que lanzamos (un Job Object de Windows con límite de memoria comprometida); el servidor de Ollama lo arranca él solo y no lo controlamos.
  · GPU: Windows no deja capar el % de cómputo de una tarjeta de consumo. En el entrenamiento se aproxima con pausas entre ejemplos (50 % ≈ el doble de tiempo; ARBOL_GPU_PCT);
    en Ollama no se puede.
"""
from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import CARPETA

DEFECTO = {"vram": 100, "ram": 100, "gpu": 100}
MINIMO = 10
_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_capas: dict = {}                         # modelo -> nº de capas (se pregunta una vez a Ollama)


def _limpiar(v: dict) -> dict:
    out = dict(DEFECTO)
    for k in DEFECTO:
        try:
            out[k] = max(MINIMO, min(100, int(round(float(v[k])))))
        except (KeyError, TypeError, ValueError):
            pass
    return out


def ajustes(carpeta: Path | str = CARPETA) -> dict:
    try:
        return _limpiar(json.loads((Path(carpeta) / "ajustes.json").read_text(encoding="utf-8")).get("recursos", {}))
    except (OSError, ValueError):
        return dict(DEFECTO)


def guardar(valores: dict, carpeta: Path | str = CARPETA) -> dict:
    """Guarda los límites sin tocar el resto de ajustes.json y devuelve lo guardado (ya recortado a 10-100)."""
    f = Path(carpeta) / "ajustes.json"
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        j = {}
    j["recursos"] = _limpiar({**ajustes(carpeta), **valores})
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    return j["recursos"]


def entorno(carpeta: Path | str = CARPETA) -> dict:
    """Variables de entorno con las que entrena entrenar.py (solo las que limitan algo)."""
    a = ajustes(carpeta)
    return {**({"ARBOL_VRAM_PCT": str(a["vram"])} if a["vram"] < 100 else {}), **({"ARBOL_GPU_PCT": str(a["gpu"])} if a["gpu"] < 100 else {})}


def _ram() -> tuple[float, float]:
    """(usada, total) en GB; (0, 0) si no se sabe."""
    class _Mem(ctypes.Structure):
        _fields_ = [("l", ctypes.c_ulong), ("c", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("libre", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong),
                    ("lp", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("lv", ctypes.c_ulonglong), ("ext", ctypes.c_ulonglong)]
    try:
        m = _Mem(); m.l = ctypes.sizeof(_Mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return (m.total - m.libre) / 1e9, m.total / 1e9
    except Exception:
        return 0.0, 0.0


def maquina() -> dict:
    """Uso real ahora mismo: {gpu, vram_usada, vram_total (GB), vram_pct, ram_usada, ram_total (GB), ram_pct, gpu_nombre} (None donde no se pueda medir)."""
    usada, total = _ram()
    out = {"ram_usada": round(usada, 1), "ram_total": round(total, 1), "ram_pct": round(100 * usada / total) if total else None, "gpu": None, "vram_usada": None, "vram_total": None, "vram_pct": None, "gpu_nombre": ""}
    try:
        s = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,name", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4,
                           creationflags=_SIN_VENTANA).stdout.strip().splitlines()[0].split(", ")
        u, mu, mt = float(s[0]), float(s[1]) / 1024, float(s[2]) / 1024
        out.update(gpu=round(u), vram_usada=round(mu, 1), vram_total=round(mt, 1), vram_pct=round(100 * mu / mt), gpu_nombre=s[3])
    except Exception:
        pass
    return out


def limitar_ram(pid: int, pct: int) -> bool:
    """Mete el proceso (y lo que lance) en un Job Object con tope de memoria = pct % de la RAM. False si pct = 100, no es Windows o no se pudo."""
    _, total = _ram()
    if pct >= 100 or not total or sys.platform != "win32":
        return False

    class _Basica(ctypes.Structure):
        _fields_ = [("t1", ctypes.c_int64), ("t2", ctypes.c_int64), ("flags", ctypes.c_uint32), ("ws_min", ctypes.c_size_t), ("ws_max", ctypes.c_size_t), ("activos", ctypes.c_uint32),
                    ("afinidad", ctypes.c_size_t), ("prioridad", ctypes.c_uint32), ("sched", ctypes.c_uint32)]

    class _Extendida(ctypes.Structure):
        _fields_ = [("basica", _Basica), ("io", ctypes.c_uint64 * 6), ("proceso", ctypes.c_size_t), ("trabajo", ctypes.c_size_t), ("pico_p", ctypes.c_size_t), ("pico_t", ctypes.c_size_t)]
    try:
        k = ctypes.windll.kernel32
        k.CreateJobObjectW.restype = ctypes.c_void_p
        k.OpenProcess.restype = ctypes.c_void_p
        job = k.CreateJobObjectW(None, None)
        info = _Extendida()
        info.basica.flags = 0x200                                      # JOB_OBJECT_LIMIT_JOB_MEMORY
        info.trabajo = int(total * 1e9 * pct / 100)
        if not k.SetInformationJobObject(ctypes.c_void_p(job), 9, ctypes.byref(info), ctypes.sizeof(info)):
            return False
        h = k.OpenProcess(0x0101, False, int(pid))                     # PROCESS_SET_QUOTA | PROCESS_TERMINATE
        return bool(h and k.AssignProcessToJobObject(ctypes.c_void_p(job), ctypes.c_void_p(h)))
    except Exception:
        return False


def _http(url: str, datos: dict | None = None) -> dict:
    if not url.startswith(("http://localhost", "http://127.0.0.1")):
        raise ValueError("solo se habla con Ollama en este equipo")
    req = urllib.request.Request(url, json.dumps(datos).encode() if datos is not None else None, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)


def capas(modelo: str, url: str) -> int:
    """Nº de bloques del modelo (de /api/show); 0 si no se puede saber."""
    if modelo not in _capas:
        try:
            info = _http(url + "/api/show", {"model": modelo}).get("model_info", {})
            _capas[modelo] = next((int(v) for k, v in info.items() if k.endswith(".block_count")), 0)
        except Exception:
            return 0
    return _capas[modelo]


def opciones_ollama(modelo: str, url: str, carpeta: Path | str = CARPETA) -> dict:
    """Opciones de Ollama que aplican el límite de VRAM: {'num_gpu': capas en GPU} o {} sin límite. (num_gpu cuenta las capas de bloques más la de salida.)"""
    pct = ajustes(carpeta)["vram"]
    if pct >= 100:
        return {}
    n = capas(modelo, url)
    return {"num_gpu": max(0, round((n + 1) * pct / 100))} if n else {}


def fijar_modelo_llm(modelo: str, carpeta: Path | str = CARPETA) -> None:
    """Modelo de Ollama con el que clasifica la app (ajustes.json → llm.modelo), sin tocar el resto."""
    f = Path(carpeta) / "ajustes.json"
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        j = {}
    j.setdefault("llm", {})["modelo"] = modelo
    f.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
