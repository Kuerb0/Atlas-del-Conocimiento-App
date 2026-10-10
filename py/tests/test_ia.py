"""Pestaña «IA»: límites de recursos (ajustes, entorno, num_gpu de Ollama) y chat con Ollama (falso)."""
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import chat, recursos


def test_ajustes_por_defecto_recortan_y_conservan_lo_demas(tmp_path):
    assert recursos.ajustes(tmp_path) == {"vram": 100, "ram": 100, "gpu": 100}
    (tmp_path / "ajustes.json").write_text(json.dumps({"llm": {"modelo": "qwen2.5:7b"}}), encoding="utf-8")
    assert recursos.guardar({"vram": 5, "gpu": 250, "ram": "70"}, tmp_path) == {"vram": 10, "ram": 70, "gpu": 100}       # 10-100 %, y acepta números como texto
    j = json.loads((tmp_path / "ajustes.json").read_text(encoding="utf-8"))
    assert j["llm"] == {"modelo": "qwen2.5:7b"} and j["recursos"]["ram"] == 70
    recursos.fijar_modelo_llm("arbol-ft2", tmp_path)
    assert json.loads((tmp_path / "ajustes.json").read_text(encoding="utf-8"))["llm"]["modelo"] == "arbol-ft2"
    assert recursos.ajustes(tmp_path)["ram"] == 70                                                                         # fijar el modelo no pisa los límites


def test_entorno_solo_lleva_lo_que_limita(tmp_path):
    assert recursos.entorno(tmp_path) == {}
    recursos.guardar({"vram": 60, "gpu": 50}, tmp_path)
    assert recursos.entorno(tmp_path) == {"ARBOL_VRAM_PCT": "60", "ARBOL_GPU_PCT": "50"}


def test_num_gpu_reparte_las_capas_segun_la_vram(tmp_path, monkeypatch):
    monkeypatch.setattr(recursos, "capas", lambda m, u: 28)
    assert recursos.opciones_ollama("qwen2.5:7b", "http://localhost:11434", tmp_path) == {}                                # 100 %: sin límite (y ni pregunta a Ollama)
    recursos.guardar({"vram": 50}, tmp_path)
    assert recursos.opciones_ollama("qwen2.5:7b", "http://localhost:11434", tmp_path) == {"num_gpu": 14}                  # (28 + 1) · 0,5 redondeado
    monkeypatch.setattr(recursos, "capas", lambda m, u: 0)                                                                   # no se sabe cuántas capas tiene: no se toca
    assert recursos.opciones_ollama("raro", "http://localhost:11434", tmp_path) == {}


def test_recursos_solo_habla_con_localhost():
    try:
        recursos._http("http://ejemplo.com/api/tags")
    except ValueError:
        return
    raise AssertionError("debía rechazar una URL que no es local")


def test_maquina_devuelve_las_claves():
    m = recursos.maquina()
    assert {"gpu", "vram_pct", "ram_pct", "ram_total"} <= set(m)


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ollama_falso(trozos):
    cuerpo = b"".join(json.dumps({"message": {"content": t}, "done": False}).encode() + b"\n" for t in trozos) + b'{"done": true}\n'
    pedidos = []

    def urlopen(req, timeout=0):
        pedidos.append(json.loads(req.data))
        return _Resp(cuerpo)
    return urlopen, pedidos


def _esperar():
    for _ in range(100):
        if chat.estado()["fase"] == "fin":
            return chat.estado()
        time.sleep(.05)
    raise AssertionError("el chat no terminó")


def test_chat_acumula_el_texto_y_manda_el_historial(monkeypatch):
    urlopen, pedidos = _ollama_falso(["Hola", ", ", "Mario"])
    monkeypatch.setattr(chat.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(chat.recursos, "opciones_ollama", lambda *a, **k: {})
    r = chat.iniciar([{"role": "user", "content": "¿Qué tal?"}], "qwen2.5:7b", biblioteca=False)
    assert r == {"ok": True}
    e = _esperar()
    assert e["texto"] == "Hola, Mario" and not e["error"] and e["fuentes"] == []
    assert pedidos[0]["model"] == "qwen2.5:7b" and pedidos[0]["messages"][0]["role"] == "system" and pedidos[0]["messages"][-1]["content"] == "¿Qué tal?"


def test_chat_con_biblioteca_cita_fuentes(monkeypatch):
    urlopen, pedidos = _ollama_falso(["Ok"])
    monkeypatch.setattr(chat.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(chat.recursos, "opciones_ollama", lambda *a, **k: {})
    import conocimiento
    monkeypatch.setattr(conocimiento, "buscar", lambda q, n=6, **k: [{"coleccion": "libros", "titulo": "Libro X", "ubicacion": "p. 3", "ruta": "x.pdf", "fragmento": "texto «clave»"}])
    chat.iniciar([{"role": "user", "content": "clave"}], "m", biblioteca=True)
    e = _esperar()
    assert e["fuentes"][0]["titulo"] == "Libro X" and "[1] Libro X" in pedidos[0]["messages"][0]["content"]


def test_chat_rechaza_preguntas_vacias_y_errores_llegan_a_la_pagina(monkeypatch):
    assert "error" in chat.iniciar([], "m")
    monkeypatch.setattr(chat.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("sin servidor")))
    monkeypatch.setattr(chat.recursos, "opciones_ollama", lambda *a, **k: {})
    chat.iniciar([{"role": "user", "content": "hola"}], "m")
    assert "sin servidor" in _esperar()["error"]
