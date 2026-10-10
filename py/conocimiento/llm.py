"""LLM local (Ollama) que opina sobre el género y el subgénero de cada obra. Opcional: sin Ollama o sin el modelo, `clasificar` devuelve None y todo sigue como antes.

Se le pregunta por todas las obras (`siempre`), con los libros más parecidos de tu biblioteca como ejemplos resueltos (`VECINOS`): medido con 232 obras de validación sube el acierto de género
de 68 % a 75 % (McNemar p = 0,005). Lista cerrada de GENEROS y de subgéneros; todo en local: nada sale del ordenador.
Modelo por defecto según la RAM: qwen2.5:7b (4,7 GB) con 12 GB o más, qwen2.5:3b (1,9 GB) con menos; si falta el elegido se usa el otro.
Ajustes: variable ARBOL_LLM (nombre del modelo, o «no» para apagarlo) o `conocimiento/ajustes.json` {"llm": {"modelo": "qwen2.5:3b", "url": "http://localhost:11434", "siempre": true}}
("siempre": false = solo para los casos dudosos).
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

from . import CARPETA, recursos
from .etiquetas import MAXIMO

def ram_gb() -> float:
    """RAM total del equipo en GB (0 si no se sabe)."""
    try:
        import ctypes

        class _Mem(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("c", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("libre", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("lp", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("lv", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
        m = _Mem(); m.l = ctypes.sizeof(_Mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.total / 1e9
    except Exception:
        try:
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
        except Exception:
            return 0.0


MODELO_GRANDE, MODELO_PEQUENO = "qwen2.5:7b", "qwen2.5:3b"      # 4,7 GB y 1,9 GB; los dos obedecen bien al formato JSON
MODELO = MODELO_GRANDE if ram_gb() >= 12 else MODELO_PEQUENO     # el que mejor rinde si el equipo lo aguanta
URL = "http://localhost:11434"
ACTIVO = True                    # False: nunca se consulta (los tests lo apagan)
PASAJES = 0                      # cuántos pasajes del cuerpo del documento ve el LLM además del principio (0 = solo el principio, lo medido en 1.11.0); sin medir con LLM: probar con --set llm.PASAJES=3
VECINOS = 8                      # cuántos libros parecidos de tu biblioteca se le enseñan al LLM como ejemplos resueltos (0 = solo los 4 fijos); ver clasificador.vecinos
ESPERA = 180                    # segundos por consulta: en CPU un modelo de 3B tarda 10-40 s por libro
_estado: dict = {}               # "ok": ¿Ollama responde y tiene el modelo?; "t": cuándo se miró. Si estaba apagado se vuelve a mirar cada minuto (por si se abre después que la app)


def ajustes(carpeta: Path | str = CARPETA) -> dict:
    a, explicito = {"modelo": MODELO, "url": URL, "siempre": True}, False
    try:
        j = json.loads((Path(carpeta) / "ajustes.json").read_text(encoding="utf-8")).get("llm", {})
        a.update(j)
        explicito = "modelo" in j
    except (OSError, ValueError):
        pass
    if os.environ.get("ARBOL_LLM"):
        a["modelo"], explicito = os.environ["ARBOL_LLM"], True
    if not explicito and _estado.get("modelo"):                            # el elegido por defecto no está instalado: se usa el otro
        a["modelo"] = _estado["modelo"]
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

            def tiene(mod):
                return any(n == mod or n.split(":")[0] == mod for n in nombres) or any(n.startswith(mod) for n in nombres)
            _estado["ok"] = tiene(a["modelo"])
            if not _estado["ok"] and a["modelo"] in (MODELO_GRANDE, MODELO_PEQUENO) and "modelo" not in _estado:
                for alt in (MODELO_GRANDE, MODELO_PEQUENO):          # lo que haya: antes preferir el que mejor rinda
                    if alt != a["modelo"] and tiene(alt):
                        _estado["modelo"], _estado["ok"] = alt, True
                        break
        except Exception:
            _estado["ok"] = False
        _estado["t"] = time.time()
    return _estado["ok"]


EJEMPLOS = [("Orgullo y prejuicio", "Una joven inglesa y un rico caballero superan sus prejuicios y se enamoran.", ["novela"]),
            ("Breve historia de Roma", "Desde la fundación de la ciudad hasta la caída del Imperio de Occidente.", ["historia"]),
            ("Estadística para ingenieros", "Probabilidad, estimación e intervalos de confianza con ejemplos.", ["estadistica"]),
            ("Clean Architecture", "Principios de diseño de software para sistemas mantenibles.", ["tecnologia"]),
            ("Los orígenes del capitalismo moderno", "Cómo cambiaron el comercio, la banca y las finanzas a lo largo de la historia de Europa.", ["economia", "historia"])]      # ejemplos resueltos (con ellos el modelo de 3B pasó del 61 % al 76 %); el último enseña que una obra puede llevar dos géneros


def _lista(etiquetas) -> str:
    return json.dumps(list(etiquetas), ensure_ascii=False)


def prompt_generos(titulo: str, capitulos: list, vista: str, materias: list, generos: dict, autor: str = "", vecinos: list | None = None) -> str:
    from .clasificador import semillas_todas
    S = semillas_todas()
    lista = "\n".join(f"- {g}: {S[g][0] if g in S else 'no encaja en ninguno de los demás'}" for g in generos)
    ej = "\n".join(f'Libro: «{t}». Sinopsis: {s}\n{{"generos": {_lista(g)}, "motivo": "…"}}' for t, s, g in EJEMPLOS)
    if vecinos:        # ejemplos reales: libros parecidos que el usuario ya tiene, con sus géneros
        ej = "\n".join(f'Libro: «{v["titulo"]}»{" de " + v["autor"] if v["autor"] else ""}.\n{{"generos": {_lista(v.get("generos") or [v["genero"]])}, "motivo": "…"}}' for v in vecinos)
    caps = "; ".join((c["titulo"] if isinstance(c, dict) else str(c)) for c in capitulos[:8]) or "(sin índice)"
    return (f"Eres bibliotecario. Elige el género que mejor describe el LIBRO (no solo las palabras de su título). Pon primero el principal y añade otro u otros dos (máximo {MAXIMO}) "
            f"SOLO si el libro trata de verdad de esos temas a la vez.\nGéneros:\n{lista}\n\nEjemplos resueltos:\n{ej}\n\n"
            f"Ahora este:\nLibro: «{titulo}»{' de ' + autor if autor else ''}. Capítulos o partes: {caps}. Materias según Open Library: {', '.join(materias[:6]) or '(no hay)'}. Texto: {vista[:1300]}\n\n"
            'Responde solo con JSON: {"generos": ["<id principal>", "<id opcional>"], "motivo": "<una frase corta>"}.')


def _pedir(a: dict, prompt: str, esquema: dict) -> dict | None:
    """Una consulta a Ollama con salida JSON forzada por `esquema`; None si falla o la respuesta no es JSON."""
    try:
        r = _http(a["url"] + "/api/chat", {"model": a["modelo"], "stream": False, "format": esquema, "options": {"temperature": 0, "num_predict": 100, "num_ctx": 2048, **recursos.opciones_ollama(a["modelo"], a["url"])},
                                           "messages": [{"role": "user", "content": prompt}]})
        _estado["fallo_red"] = False
        return json.loads(re.sub(r"^```(?:json)?|```$", "", r["message"]["content"].strip()))
    except Exception as e:
        if isinstance(e, OSError) or "HTTP Error" in str(e):          # no se pudo hablar con Ollama (servidor caído, conexión cortada, error 5xx): se vuelve a comprobar en un minuto
            _estado.update(fallo_red=True, ok=False, t=time.time())
        return None


def _ids(j: dict, plural: str, singular: str, validos) -> list[str]:
    """Ids válidos de la respuesta (lista `plural`, o el valor único `singular` de las respuestas con el formato antiguo), sin repetir y como mucho MAXIMO. Si el primero no es válido, [] (el principal manda)."""
    v = j.get(plural)
    v = [v] if isinstance(v, str) else v if isinstance(v, list) else [j.get(singular)]
    v = list(dict.fromkeys(x for x in v if isinstance(x, str)))
    return [x for x in v if x in validos][:MAXIMO] if v and v[0] in validos else []


def clasificar(titulo: str, capitulos: list, vista: str, materias: list, generos: dict, carpeta: Path | str = CARPETA, autor: str = "", vecinos: list | None = None) -> dict | None:
    """{'genero': id principal, 'generos': [ids, el principal primero], 'motivo': str} según el LLM, o None si no está disponible o responde algo inválido."""
    if not disponible(carpeta):
        return None
    esquema = {"type": "object", "properties": {"generos": {"type": "array", "items": {"type": "string", "enum": list(generos)}, "minItems": 1, "maxItems": MAXIMO}, "motivo": {"type": "string"}}, "required": ["generos", "motivo"]}
    j = _pedir(ajustes(carpeta), prompt_generos(titulo, capitulos, vista, materias, generos, autor, vecinos), esquema)
    ids = _ids(j, "generos", "genero", generos) if j else []
    return {"genero": ids[0], "generos": ids, "motivo": str(j.get("motivo", ""))[:160]} if ids else None


def prompt_subgeneros(titulo: str, capitulos: list, vista: str, genero: str, subs: list, autor: str = "", vecinos: list | None = None) -> str:
    """El prompt con el que se pregunta el subgénero (o los subgéneros) de un libro ya clasificado en `genero`; `subs` = [(id, nombre, frase_es, frase_en)]."""
    ids = [x[0] for x in subs]
    lista = "\n".join(f"- {x[0]}: {x[1]} ({x[2]})" for x in subs)
    caps = "; ".join((c["titulo"] if isinstance(c, dict) else str(c)) for c in capitulos[:8]) or "(sin índice)"
    ej = "".join(f'- «{v["titulo"]}»{" de " + v["autor"] if v["autor"] else ""} → {", ".join([v["subgenero"]] + [x for x in v.get("subgeneros", []) if x in ids and x != v["subgenero"]])}\n' for v in (vecinos or []) if v.get("subgenero") in ids)
    ej = f"Libros parecidos que el usuario ya clasificó:\n{ej}\n" if ej else ""
    return (f"Eres bibliotecario. El libro es de género «{genero}». Elige el subgénero que mejor lo describe y, solo si de verdad encaja en otro más, añade uno o dos (máximo {MAXIMO}, el principal primero).\n"
            f"Subgéneros:\n{lista}\n\n{ej}Libro: «{titulo}»{' de ' + autor if autor else ''}. Capítulos o partes: {caps}. Texto: {vista[:1100]}\n\n"
            'Responde solo con JSON: {"subgeneros": ["<id principal>", "<id opcional>"], "motivo": "<una frase corta>"}.')


def subgeneros(titulo: str, capitulos: list, vista: str, genero: str, subs: list, autor: str = "", carpeta: Path | str = CARPETA, vecinos: list | None = None) -> list[str]:
    """Ids de subgénero (de `subs` = [(id, nombre, frase_es, frase_en)]) que elige el LLM para un libro ya clasificado en `genero`, el principal primero y hasta MAXIMO; [] si no está disponible o responde algo inválido."""
    if not disponible(carpeta):
        return []
    ids = [x[0] for x in subs]
    esquema = {"type": "object", "properties": {"subgeneros": {"type": "array", "items": {"type": "string", "enum": ids}, "minItems": 1, "maxItems": MAXIMO}, "motivo": {"type": "string"}}, "required": ["subgeneros", "motivo"]}
    j = _pedir(ajustes(carpeta), prompt_subgeneros(titulo, capitulos, vista, genero, subs, autor, vecinos), esquema)
    return _ids(j, "subgeneros", "subgenero", ids) if j else []


def subgenero(titulo: str, capitulos: list, vista: str, genero: str, subs: list, autor: str = "", carpeta: Path | str = CARPETA, vecinos: list | None = None) -> str | None:
    """Id del subgénero principal que elige el LLM (el primero de `subgeneros`), o None."""
    return next(iter(subgeneros(titulo, capitulos, vista, genero, subs, autor, carpeta, vecinos)), None)
