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
GB = {"items": [
    {"id": "g1", "volumeInfo": {"title": "Historia", "subtitle": "de la estadística", "authors": ["X"], "publishedDate": "1890-01", "categories": ["History"], "infoLink": "http://books.google.com/g1"},
     "accessInfo": {"publicDomain": True, "epub": {"isAvailable": True, "downloadLink": "https://books.google.com/g1.epub"}}},
    {"id": "g2", "volumeInfo": {"title": "Moderno", "infoLink": "http://books.google.com/g2"},
     "accessInfo": {"publicDomain": False, "pdf": {"isAvailable": True, "downloadLink": "https://books.google.com/g2.pdf"}}}]}
RESP = {
    "googleapis.com/books": GB,
    "gutenberg.org/ebooks/search.opds": '<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>https://www.gutenberg.org/ebooks/subjects/search.opds/?query=x</id><title>Subjects</title></entry>'
                                        '<entry><id>https://www.gutenberg.org/ebooks/7.opds</id><title>Essai</title><content>Laplace</content></entry></feed>',
    "openlibrary.org/search.json": {"docs": [{"key": "/works/OL1W", "title": "Abierto", "ebook_access": "public", "ia": ["abierto00x"], "subject": ["Statistics"]},
                                             {"key": "/works/OL2W", "title": "Prestado", "ebook_access": "borrowable", "ia": ["p"]}, {"key": "/works/OL3W", "title": "Sin ebook", "ebook_access": "no_ebook"}]},
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
    gb = {x["id"]: x for x in r["resultados"] if x["fuente"] == "googlebooks"}
    assert gb["g1"]["url"].endswith(".epub") and gb["g1"]["enlace"].startswith("https://")      # dominio público: descargable
    assert gb["g2"]["url"] == "" and gb["g2"]["enlace"]                                        # con copyright: solo la ficha, aunque Google dé un PDF
    assert por["gutenberg"] == ["7"]                                      # la entrada «Subjects» del catálogo, fuera
    ol = {x["id"]: x for x in r["resultados"] if x["fuente"] in ("openlibrary", "archive") and x["enlace"].startswith("https://openlibrary.org")}
    assert ol["abierto00x"]["fuente"] == "archive" and ol["/works/OL2W"]["url"] == "" and ol["/works/OL3W"]["fuente"] == "openlibrary"   # solo la lectura abierta se puede traer
    assert por["openalex"] == ["W2"]                                      # sin PDF abierto, fuera
    assert sorted(i for i in por["archive"] if i != "abierto00x") == ["cc", "viejo"]                      # solo licencia abierta o ≤ 1929
    assert por["arxiv"] and next(x for x in r["resultados"] if x["fuente"] == "arxiv")["url"].startswith("https://")
    assert r["errores"] == {} and "zzz" in t.buscar("x", fuentes=("zzz",))["errores"]       # una fuente que falla no tira las demás


def test_titulo_autor_tipo_y_formato(monkeypatch):
    vistas = []
    monkeypatch.setattr(t, "_get", lambda url, *a, **k: (vistas.append(url), falso(url))[1])
    r = t.buscar(titulo="Essai", autor="laplace", tipo="libro")
    assert {x["fuente"] for x in r["resultados"]} <= set(t.LIBROS) and not any("arxiv" in u or "openalex" in u for u in vistas)
    assert [x["id"] for x in r["resultados"] if x["fuente"] == "gutenberg"] == ["7"]            # el autor coincide («Laplace»)
    assert t.buscar(titulo="Essai", autor="Newton", tipo="libro", fuentes=("gutenberg",))["resultados"] == []   # otro autor: fuera
    assert any("intitle" in u and "inauthor" in u for u in vistas) and any("title=Essai" in u and "author=laplace" in u for u in vistas)
    assert {x["formato"] for x in t.buscar("probability", formato="epub")["resultados"]} == {"epub"}
    assert t.buscar("probability", tipo="articulo")["resultados"] and {x["fuente"] for x in t.buscar("probability", tipo="articulo")["resultados"]} <= set(t.ARTICULOS)
    assert t.buscar() == {"resultados": [], "errores": {}}                                          # sin nada que buscar no se llama a la red


def test_genero_desde_materias():
    assert t.genero_desde_materias(["Bayesian statistics", "Regression analysis"]) == "estadistica"
    assert t.genero_desde_materias(["Rome -- History", "Ancient history"]) == "historia"
    assert t.genero_desde_materias(["zzz qqq"]) == "otro"


def test_traer_no_descarga_lo_que_solo_tiene_ficha(tmp_path):
    with pytest.raises(ValueError, match="solo se puede ver"):
        t.traer({"fuente": "googlebooks", "id": "g2", "url": "", "titulo": "T"}, tmp_path)


def test_get_solo_https():
    with pytest.raises(ValueError):
        t._get("http://ejemplo.com/a.pdf")


def test_traer_rechaza_lo_que_no_es_pdf_ni_epub(monkeypatch, tmp_path):
    monkeypatch.setattr(t, "_get", lambda *a, **k: b"<html>pago</html>")
    with pytest.raises(ValueError, match="ni un EPUB"):
        t.traer({"fuente": "arxiv", "id": "1", "url": "https://x/a.pdf", "titulo": "T"}, tmp_path)
