"""Clasificador por parecido, con un modelo falso (bolsa de palabras) para no descargar nada: se prueba la mecánica, no la calidad del modelo real
(esa se mide con herramientas/comparar_clasificadores.py)."""
import json
import re
import sys
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import clasificador as c
from conocimiento import importar as im


def _falso(textos):
    v = np.zeros((len(textos), 256))
    for i, t in enumerate(textos):
        for w in re.findall(r"[a-záéíóúñ]{4,}", t.lower()):
            v[i, zlib.crc32(w.encode()) % 256] += 1
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)


def _con_modelo_falso(monkeypatch):
    monkeypatch.setenv("ARBOL_MODELO", "falso")
    monkeypatch.setitem(c._cache, "falso", _falso)
    monkeypatch.setattr(c, "ACTIVO", True)
    c._cache.pop("fallo", None)


def test_sugiere_por_semillas_y_por_tu_biblioteca(monkeypatch, tmp_path):
    _con_modelo_falso(monkeypatch)
    s = c.sugerir("Historia de imperios, guerras, reyes y civilizaciones antiguas", tmp_path)
    assert s["genero"] == "historia" and s["confianza"] > 0 and set(s["puntos"]) == set(c.SEMILLAS)
    # un libro tuyo con una palabra rara arrastra a los parecidos hacia el género que fijaste
    b = tmp_path / "biblioteca"; b.mkdir()
    (b / "metadatos.json").write_text(json.dumps({"libros/x/a.pdf": {"titulo": "Zorrotz quimbaya tuxtla", "genero": "arte", "automatico": False}}), encoding="utf-8")
    assert c.sugerir("zorrotz quimbaya tuxtla", tmp_path)["genero"] == "arte"


def test_sin_modelo_devuelve_none_y_no_reintenta(monkeypatch, tmp_path):
    monkeypatch.setenv("ARBOL_MODELO", "no-existe/modelo")
    monkeypatch.setattr(c, "_embedder", lambda *a, **k: (_ for _ in ()).throw(OSError("sin red")))
    c._cache.pop("fallo", None)
    assert c.sugerir("lo que sea", tmp_path) is None and c._cache["fallo"] is True
    assert c.sugerir("otra vez", tmp_path) is None
    c._cache.pop("fallo", None)


def test_decidir_mezcla_reglas_y_parecido():
    parecido = {"puntos": {"historia": .40, "ciencia": .38, "novela": .10}}
    assert c.decidir({"historia": 6}, "historia", parecido) == ("historia", False)              # reglas flojas coinciden
    assert c.decidir({"ciencia": 30, "historia": 2}, "ciencia", parecido) == ("ciencia", False)  # reglas seguras deciden el empate
    assert c.decidir({}, "otro", parecido) == ("historia", True)                                 # reglas sin opinión: manda el parecido
    assert c.decidir({}, "otro", {"puntos": {"historia": .1}}) == ("otro", False)                # nada se parece: se respeta a las reglas


def test_clasificar_usa_el_parecido_cuando_las_reglas_no_saben(monkeypatch, tmp_path):
    _con_modelo_falso(monkeypatch)
    f = tmp_path / "xyzzy.txt"
    f.write_text("Historia de imperios, guerras, reyes y civilizaciones antiguas y medievales " * 3, encoding="utf-8")
    monkeypatch.setattr(c, "ACTIVO", False)
    solo_reglas = im.clasificar(f, tmp_path)
    monkeypatch.setattr(c, "ACTIVO", True)
    r = im.clasificar(f, tmp_path)
    assert r["genero"] == "historia" and r["metodo"] in ("reglas", "parecido") and solo_reglas["metodo"] == "reglas"
