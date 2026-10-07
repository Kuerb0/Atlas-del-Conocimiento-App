"""LLM local (Ollama) para los casos dudosos de la clasificación. Opcional: sin Ollama o sin el modelo, `clasificar` devuelve None y todo sigue como antes.

Solo se le pregunta el género (de la lista cerrada de GENEROS) cuando las reglas y el parecido no se ponen de acuerdo. Todo en local: nada sale del ordenador.
Ajustes: variable ARBOL_LLM (nombre del modelo, o «no» para apagarlo) o `conocimiento/ajustes.json` {"llm": {"modelo": "qwen2.5:3b", "url": "http://localhost:11434"}}.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request
from shutil import which
from pathlib import Path

from . import CARPETA

MODELO = "qwen2.5:3b"            # ~1,9 GB; rápido en CPU y obedece bien al formato JSON. En un PC potente: qwen2.5:7b
URL = "http://localhost:11434"
ACTIVO = True                    # False: nunca se consulta (los tests lo apagan)
ESPERA = 180                     # segundos por consulta: en CPU un modelo de 3B tarda 10-40 s por libro
_estado: dict = {}               # "ok": ¿Ollama responde y tiene el modelo?; "t": cuándo se miró. Si estaba apagado se vuelve a mirar cada minuto (por si se abre después que la app)


def ajustes(carpeta: Path | str = CARPETA) -> dict:
    a = {"modelo": MODELO, "url": URL}
    try:
        a.update(json.loads((Path(carpeta) / "ajustes.json").read_text(encoding="utf-8")).get("llm", {}))
    except (OSError, ValueError):
        pass
    if os.environ.get("ARBOL_LLM"):
        a["modelo"] = os.environ["ARBOL_LLM"]
    return a


def _http(url: str, datos: dict | None = None, espera: float = ESPERA) -> dict:
    if not url.startswith(("http://localhost", "http://127.0.0.1")):
        raise ValueError("el LLM solo se consulta en este ordenador (localhost)")
    req = urllib.request.Request(url, data=json.dumps(datos).encode() if datos is not None else None, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=espera) as r:
        return json.loads(r.read().decode("utf-8"))


def _arrancar() -> None:
    """Si Ollama está instalado pero apagado, levanta `ollama serve` sin ventana y espera hasta 12 s a que responda. Una sola vez por sesión."""
    if _estado.get("arrancado"):
        return
    _estado["arrancado"] = True
    exe = which("ollama") or str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe")
    if not Path(exe).exists():
        return
    try:
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        return
    for _ in range(24):
        time.sleep(.5)
        try:
            _http(URL + "/api/tags", espera=1)
            return
        except Exception:
            continue


def disponible(carpeta: Path | str = CARPETA) -> bool:
    """¿Ollama está corriendo y tiene el modelo? Si sí, se mira una sola vez por sesión; si no, cada minuto (la consulta tarda 2 s como mucho)."""
    if not ACTIVO or os.environ.get("ARBOL_LLM", "").lower() in ("no", "0", "off"):
        return False
    if "ok" not in _estado or (not _estado["ok"] and time.time() - _estado["t"] > 60):
        a = ajustes(carpeta)
        try:
            try:
                tags = _http(a["url"] + "/api/tags", espera=5)
            except Exception:
                _arrancar()                                              # instalado pero apagado: se enciende (tarda unos segundos la primera vez)
                tags = _http(a["url"] + "/api/tags", espera=5)
            nombres = [m["name"] for m in tags.get("models", [])]
            _estado["ok"] = any(n == a["modelo"] or n.split(":")[0] == a["modelo"] for n in nombres) or any(n.startswith(a["modelo"]) for n in nombres)
        except Exception:
            _estado["ok"] = False
        _estado["t"] = time.time()
    return _estado["ok"]


EJEMPLOS = [("Orgullo y prejuicio", "Una joven inglesa y un rico caballero superan sus prejuicios y se enamoran.", "novela"),
            ("Breve historia de Roma", "Desde la fundación de la ciudad hasta la caída del Imperio de Occidente.", "historia"),
            ("Estadística para ingenieros", "Probabilidad, estimación e intervalos de confianza con ejemplos.", "estadistica"),
            ("Clean Architecture", "Principios de diseño de software para sistemas mantenibles.", "tecnologia")]      # ejemplos resueltos: con ellos el modelo de 3B pasó del 61 % al 76 % en las pruebas


def _prompt(titulo: str, capitulos: list, vista: str, materias: list, generos: dict) -> str:
    from .clasificador import semillas_todas
    S = semillas_todas()
    lista = "\n".join(f"- {g}: {S[g][0] if g in S else 'no encaja en ninguno de los demás'}" for g in generos)
    ej = "\n".join(f'Libro: «{t}». Sinopsis: {s}\n{{"genero": "{g}", "motivo": "…"}}' for t, s, g in EJEMPLOS)
    caps = "; ".join((c["titulo"] if isinstance(c, dict) else str(c)) for c in capitulos[:8]) or "(sin índice)"
    return (f"Eres bibliotecario. Elige el género que mejor describe el LIBRO (no solo las palabras de su título).\nGéneros:\n{lista}\n\nEjemplos resueltos:\n{ej}\n\n"
            f"Ahora este:\nLibro: «{titulo}». Capítulos o partes: {caps}. Materias según Open Library: {', '.join(materias[:6]) or '(no hay)'}. Principio del texto: {vista[:600]}\n\n"
            'Responde solo con JSON: {"genero": "<id>", "motivo": "<una frase corta>"}.')


def clasificar(titulo: str, capitulos: list, vista: str, materias: list, generos: dict, carpeta: Path | str = CARPETA) -> dict | None:
    """{'genero': id, 'motivo': str} según el LLM, o None si no está disponible o responde algo inválido."""
    if not disponible(carpeta):
        return None
    a = ajustes(carpeta)
    esquema = {"type": "object", "properties": {"genero": {"type": "string", "enum": list(generos)}, "motivo": {"type": "string"}}, "required": ["genero", "motivo"]}
    try:
        r = _http(a["url"] + "/api/chat", {"model": a["modelo"], "stream": False, "format": esquema, "options": {"temperature": 0, "num_predict": 80, "num_ctx": 2048},
                                           "messages": [{"role": "user", "content": _prompt(titulo, capitulos, vista, materias, generos)}]})
        j = json.loads(re.sub(r"^```(?:json)?|```$", "", r["message"]["content"].strip()))
        return {"genero": j["genero"], "motivo": str(j.get("motivo", ""))[:160]} if j.get("genero") in generos else None
    except Exception:
        return None
