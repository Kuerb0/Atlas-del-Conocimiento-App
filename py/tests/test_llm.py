"""LLM local (Ollama) para los casos dudosos, con un Ollama falso: se prueba cuándo se pregunta y cómo se usa la respuesta."""
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import clasificador as c
from conocimiento import importar as im
from conocimiento import llm


@pytest.fixture
def ollama_falso(monkeypatch):
    llamadas = []

    def http(url, datos=None, espera=0):
        llamadas.append(url)
        if url.endswith("/api/tags"):
            return {"models": [{"name": "qwen2.5:3b"}]}
        return {"message": {"content": json.dumps({"genero": "novela", "motivo": "narra una historia con personajes"})}}
    monkeypatch.setattr(llm, "_http", http)
    monkeypatch.setattr(llm, "ACTIVO", True)
    monkeypatch.delenv("ARBOL_LLM", raising=False)
    llm._estado.clear()
    yield llamadas
    llm._estado.clear()


def test_disponible_y_respuesta(ollama_falso, tmp_path):
    assert llm.disponible(tmp_path) and llm.disponible(tmp_path)
    assert ollama_falso.count("http://localhost:11434/api/tags") == 1                       # si está disponible, se comprueba una sola vez por sesión
    r = llm.clasificar("Titulo", [{"titulo": "Cap 1"}], "texto", ["Fiction"], im.GENEROS, tmp_path)
    assert r["genero"] == "novela" and "personajes" in r["motivo"]


def test_sin_ollama_o_sin_modelo_no_pasa_nada(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "ACTIVO", True); llm._estado.clear()
    monkeypatch.setattr(llm, "_arrancar", lambda: None)                                     # que el test no encienda un Ollama de verdad
    monkeypatch.setattr(llm, "_http", lambda *a, **k: (_ for _ in ()).throw(OSError("conexión rechazada")))
    assert llm.disponible(tmp_path) is False and llm.clasificar("t", [], "", [], im.GENEROS, tmp_path) is None
    llm._estado.clear()
    monkeypatch.setattr(llm, "_http", lambda *a, **k: {"models": [{"name": "otro:7b"}]})
    assert llm.disponible(tmp_path) is False                                                # Ollama responde pero no tiene el modelo
    llm._estado.clear()
    monkeypatch.setenv("ARBOL_LLM", "no")
    assert llm.disponible(tmp_path) is False


def test_si_esta_apagado_intenta_arrancarlo_una_sola_vez(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "ACTIVO", True); llm._estado.clear()
    arranques = []
    monkeypatch.setattr(llm, "_arrancar", lambda: arranques.append(1))
    monkeypatch.setattr(llm, "_http", lambda *a, **k: (_ for _ in ()).throw(OSError("apagado")))
    assert llm.disponible(tmp_path) is False and arranques == [1]
    llm._estado.clear()


def test_respuesta_invalida_y_solo_localhost(monkeypatch, ollama_falso, tmp_path):
    monkeypatch.setattr(llm, "_http", lambda url, datos=None, espera=0: ({"models": [{"name": "qwen2.5:3b"}]} if url.endswith("tags") else {"message": {"content": '{"genero": "inventado"}'}}))
    assert llm.clasificar("t", [], "", [], im.GENEROS, tmp_path) is None                    # género fuera de la lista: se ignora
    monkeypatch.undo()
    with pytest.raises(ValueError):
        llm._http("https://api.ejemplo.com/chat", {})


def test_dudoso():
    claro = {"puntos": {"historia": .60, "ciencia": .30}}
    justo = {"puntos": {"historia": .40, "ciencia": .38}}
    assert not c.dudoso({"historia": 25}, claro) and c.dudoso({}, justo) and c.dudoso({}, {"puntos": {"historia": .1}})
    assert c.dudoso({"historia": 3}, None) and not c.dudoso({"historia": 30}, None)


def test_clasificar_pregunta_al_llm_solo_si_es_dudoso(ollama_falso, monkeypatch, tmp_path):
    f = tmp_path / "Zorrotz Quimbaya.epub"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("mimetype", "application/epub+zip"); z.writestr("c.xhtml", "<p>" + "texto generico sin pistas " * 300 + "</p>")
    r = im.clasificar(f, tmp_path)                                                           # reglas flojas, sin parecido: dudoso -> LLM
    assert r["genero"] == "novela" and r["metodo"] == "llm" and "LLM" in r["motivo"]
    monkeypatch.setattr(c, "dudoso", lambda *a, **k: False)
    assert im.clasificar(f, tmp_path)["metodo"] == "reglas"                                  # si no es dudoso no se pregunta
