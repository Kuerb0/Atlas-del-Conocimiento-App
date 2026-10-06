"""Compresión sin pérdida de la biblioteca: el libro queda idéntico y solo se sustituye si es menor."""
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import importar as im


def _pdf(ruta, paginas=30):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    w = PdfWriter()
    for i in range(paginas):
        p = w.add_blank_page(300, 300)
        s = DecodedStreamObject()
        s.set_data(f"BT /F1 12 Tf 20 200 Td (Pagina {i} " .encode() + b"texto repetido " * 200 + b") Tj ET")
        p[NameObject("/Contents")] = w._add_object(s)
        p[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})})})
    with open(ruta, "wb") as fh:
        w.write(fh)


def _biblioteca(tmp_path):
    b = tmp_path / "biblioteca" / "libros" / "x"; b.mkdir(parents=True)
    _pdf(b / "a.pdf")
    with zipfile.ZipFile(b / "b.epub", "w") as z:
        z.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)
        z.writestr("c.xhtml", "<p>" + "hola " * 5000 + "</p>", zipfile.ZIP_STORED)          # sin comprimir: hay ganancia
    meta = {"libros/x/a.pdf": {}, "libros/x/b.epub": {}}
    (tmp_path / "biblioteca" / "metadatos.json").write_text(json.dumps(meta))
    return b


def test_comprime_sin_perdida(tmp_path):
    b = _biblioteca(tmp_path)
    antes = {n: (b / n).stat().st_size for n in ("a.pdf", "b.epub")}
    from pypdf import PdfReader
    textos = [p.extract_text() for p in PdfReader(str(b / "a.pdf")).pages]
    r = im.comprimir_todo(tmp_path)
    assert r["errores"] == [] and r["n"] == 2 and r["ahorrado"] > 0
    assert (b / "b.epub").stat().st_size < antes["b.epub"]
    with zipfile.ZipFile(b / "b.epub") as z:
        assert z.namelist()[0] == "mimetype" and z.read("c.xhtml").startswith(b"<p>hola")
    if (b / "a.pdf").stat().st_size < antes["a.pdf"]:
        assert [p.extract_text() for p in PdfReader(str(b / "a.pdf")).pages] == textos           # mismo texto, mismas páginas
    assert not list(b.glob("*.tmp"))
    assert im.comprimir("libros/x/b.epub", tmp_path)["estado"] == "sin_ganancia"                 # segunda pasada: nada que ganar


def test_no_sustituye_si_no_coincide(tmp_path, monkeypatch):
    b = _biblioteca(tmp_path); antes = (b / "b.epub").read_bytes()
    monkeypatch.setattr(im, "_igual", lambda a, c: False)
    r = im.comprimir("libros/x/b.epub", tmp_path)
    assert r["estado"] == "error" and (b / "b.epub").read_bytes() == antes and not list(b.glob("*.tmp"))
