"""Telescopio sin red: las respuestas de las fuentes se simulan sustituyendo telescopio._get."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import telescopio as t

ARXIV = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1</id><title>Bayesian regression</title><summary>x</summary>
<published>2020-01-02T00:00:00Z</published><author><name>A. Gauss</name></author><category term="stat.ME"/>
<link title="pdf" href="http://arxiv.org/pdf/1"/></entry></feed>"""
RESP = {
    "gutendex": {"results": [{"id": 7, "title": "Essai", "authors": [{"name": "Laplace"}], "subjects": ["Probabilities"], "formats": {"application/epub+zip": "https://g/7.epub"}, "copyright": False},
                             {"id": 8, "title": "Con copyright", "formats": {"application/epub+zip": "https://g/8.epub"}, "copyright": True}]},
    "arxiv": ARXIV,
    "openalex": {"results": [{"id": "W1", "display_name": "Sin pdf", "best_oa_location": {}}, {"id": "W2", "display_name": "Con pdf", "publication_year": 2019,
                 "best_oa_location": {"pdf_url": "https://x/a.pdf", "license": "cc-by"}, "concepts": [{"display_name": "Statistics"}], "authorships": []}]},
    "archive.org/advancedsearch": {"response": {"docs": [{"identifier": "viejo", "title": "Old", "year": 1900}, {"identifier": "moderno", "title": "Prestado", "year": 2005},
                                                           {"identifier": "cc", "title": "Abierto", "year": 2015, "licenseurl": "https://creativecommons.org/x"}]}},
}


def falso(url, binario=False, limite=0):
    for k, v in RESP.items():
        if k in url:
            return v if isinstance(v, str) else json.dumps(v)
    raise OSError("sin red")


def test_buscar_filtra_lo_no_legal_y_tolera_fuentes_caidas(monkeypatch):
    monkeypatch.setattr(t, "_get", falso)
    r = t.buscar("probability")
    por = {x["fuente"]: [y["id"] for y in r["resultados"] if y["fuente"] == x["fuente"]] for x in r["resultados"]}
    assert por["gutenberg"] == ["7"]                                      # el de copyright, fuera
    assert por["openalex"] == ["W2"]                                      # sin PDF abierto, fuera
    assert sorted(por["archive"]) == ["cc", "viejo"]                      # solo licencia abierta o ≤ 1929
    assert por["arxiv"] and next(x for x in r["resultados"] if x["fuente"] == "arxiv")["url"].startswith("https://")
    assert r["errores"] == {} and "zzz" in t.buscar("x", fuentes=("zzz",))["errores"]       # una fuente que falla no tira las demás


def test_genero_desde_materias():
    assert t.genero_desde_materias(["Bayesian statistics", "Regression analysis"]) == "estadistica"
    assert t.genero_desde_materias(["Rome -- History", "Ancient history"]) == "historia"
    assert t.genero_desde_materias(["zzz qqq"]) == "otro"


def test_get_solo_https():
    with pytest.raises(ValueError):
        t._get("http://ejemplo.com/a.pdf")


def test_traer_rechaza_lo_que_no_es_pdf_ni_epub(monkeypatch, tmp_path):
    monkeypatch.setattr(t, "_get", lambda *a, **k: b"<html>pago</html>")
    with pytest.raises(ValueError, match="ni un EPUB"):
        t.traer({"fuente": "arxiv", "id": "1", "url": "https://x/a.pdf", "titulo": "T"}, tmp_path)
