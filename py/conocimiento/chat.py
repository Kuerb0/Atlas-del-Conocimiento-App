"""Chat con el LLM local (Ollama) para la pestaña «🧠 IA» › Chat.

La app (pywebview) no puede recibir texto a trozos, así que la respuesta se genera en un hilo y la página pregunta cada poco con `estado()` (igual que la importación).
Con `biblioteca=True` se buscan en tu conocimiento (`conocimiento.buscar`) los trozos más parecidos a la última pregunta y se le pasan como contexto, con su número para citarlos.
Todo en localhost. Los modelos entrenados para clasificar contestan JSON aunque les hables: para charlar usa el modelo base (qwen2.5:7b).
"""
from __future__ import annotations

import json
import threading
import urllib.request

from . import llm, recursos

SISTEMA = ("Eres el asistente del Atlas del conocimiento, la biblioteca personal de estadística y conocimiento de Mario. Respondes en español, claro y sin rodeos. "
           "Si no sabes algo o los fragmentos no lo cubren, lo dices en vez de inventarlo.")
_t: dict = {"fase": "libre", "texto": "", "fuentes": [], "error": "", "n": 0}
_parar = threading.Event()
_lock = threading.Lock()


def modelos() -> dict:
    """{modelos: [nombres instalados en Ollama], por_defecto, error}; por defecto el base más grande (no el afinado para clasificar)."""
    try:
        nombres = [m["name"] for m in recursos._http(llm.URL + "/api/tags").get("models", [])]
    except Exception as e:
        return {"modelos": [], "por_defecto": "", "error": f"No hay Ollama en este equipo ({type(e).__name__})."}
    base = [n for n in nombres if not any(k in n.lower() for k in ("arbol", "atlas", "clasific"))]
    pref = next((n for n in ("qwen2.5:7b", "qwen2.5:3b") if n in base), base[0] if base else (nombres[0] if nombres else ""))
    return {"modelos": nombres, "por_defecto": pref, "error": ""}


def _contexto(pregunta: str) -> tuple[str, list]:
    try:
        from . import buscar
        res = buscar(pregunta, n=6)
    except Exception:
        return "", []
    fuentes = [{"n": i + 1, "titulo": r["titulo"], "ubicacion": r.get("ubicacion", ""), "coleccion": r["coleccion"], "ruta": r.get("ruta", "")} for i, r in enumerate(res)]
    texto = "\n".join(f"[{i + 1}] {r['titulo']} ({r.get('ubicacion', '')}): {r['fragmento']}" for i, r in enumerate(res))
    return (f"\n\nFragmentos de la biblioteca de Mario que pueden servir (cítalos como [n]):\n{texto}" if texto else ""), fuentes


def _correr(mensajes: list, modelo: str, biblioteca: bool, n: int) -> None:
    try:
        pregunta = next((m["content"] for m in reversed(mensajes) if m["role"] == "user"), "")
        extra, fuentes = _contexto(pregunta) if biblioteca else ("", [])
        with _lock:
            _t.update(fuentes=fuentes)
        url = llm.ajustes()["url"]
        op = {"num_ctx": 4096, **recursos.opciones_ollama(modelo, url)}
        cuerpo = {"model": modelo, "stream": True, "options": op, "messages": [{"role": "system", "content": SISTEMA + extra}, *[{"role": m["role"], "content": m["content"]} for m in mensajes]]}
        req = urllib.request.Request(url + "/api/chat", json.dumps(cuerpo).encode(), {"Content-Type": "application/json"})
        if not url.startswith(("http://localhost", "http://127.0.0.1")):
            raise ValueError("solo se habla con Ollama en este equipo")
        with urllib.request.urlopen(req, timeout=300) as r:
            for linea in r:
                if _parar.is_set():
                    break
                if not linea.strip():
                    continue
                j = json.loads(linea)
                with _lock:
                    if _t["n"] != n:
                        return
                    _t["texto"] += j.get("message", {}).get("content", "")
                if j.get("done"):
                    break
    except Exception as e:
        with _lock:
            if _t["n"] == n:
                _t["error"] = f"{type(e).__name__}: {e}"
    finally:
        with _lock:
            if _t["n"] == n:
                _t["fase"] = "fin"


def iniciar(mensajes: list, modelo: str, biblioteca: bool = False) -> dict:
    """Empieza a generar la respuesta a `mensajes` ([{role: user|assistant, content}]) en segundo plano."""
    with _lock:
        if _t["fase"] == "trabajando":
            return {"error": "ya se está generando una respuesta"}
        if not mensajes or mensajes[-1].get("role") != "user":
            return {"error": "falta la pregunta"}
        _parar.clear()
        _t.update(fase="trabajando", texto="", fuentes=[], error="", n=_t["n"] + 1)
        n = _t["n"]
    threading.Thread(target=_correr, args=([dict(m) for m in mensajes], str(modelo), bool(biblioteca), n), daemon=True).start()
    return {"ok": True}


def estado() -> dict:
    with _lock:
        return dict(_t)


def parar() -> dict:
    _parar.set()
    return {"ok": True}
