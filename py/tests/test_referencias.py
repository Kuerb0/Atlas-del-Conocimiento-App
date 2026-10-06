"""Las referencias viajan por GitHub aunque los PDF/EPUB no: otro equipo ve el libro como referencia vacía y puede restaurarlo."""
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import importar as im


def _epub(ruta):
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("c.xhtml", "<p>" + "probabilidad de una variable aleatoria " * 400 + "</p>")


def test_referencia_sin_archivo_y_restauracion(tmp_path):
    orig = tmp_path / "Mi libro privado.epub"; _epub(orig)
    k = tmp_path / "conocimiento"
    r = im.importar([{"ruta": orig, "galaxia": "libros"}], k, db=tmp_path / "i.db")[0]
    assert r["estado"] == "ok"
    ref = k / "biblioteca" / "referencias.json"
    assert "Mi libro privado" not in ref.read_text(encoding="utf-8") or str(tmp_path) not in ref.read_text(encoding="utf-8")   # sin rutas del equipo
    assert "origen" not in next(iter(json.loads(ref.read_text(encoding="utf-8")).values()))

    # «otro equipo»: llegan solo referencias.json (y no el epub ni metadatos.json)
    Path(r["destino"]).unlink(); (k / "biblioteca" / "metadatos.json").unlink()
    meta = im.leer_metadatos(k)
    assert len(meta) == 1
    ficha = im.listar(k)[0]
    assert ficha["existe"] is False and ficha["galaxia"] == "libros"
    assert im.comprimir_todo(k)["n"] == 0                                    # lo que no está no se comprime ni da error

    # al importar el mismo archivo se restaura en su sitio, sin duplicado
    r2 = im.importar([orig], k, db=tmp_path / "i.db")[0]
    assert r2["estado"] == "ok" and "restaurado" in r2["mensaje"] and Path(r2["destino"]).is_file()
    assert len(im.leer_metadatos(k)) == 1 and im.listar(k)[0]["existe"] is True
