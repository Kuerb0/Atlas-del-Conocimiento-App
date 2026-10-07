"""Revisión de lo importado por fecha: se guarda cómo se clasificó cada archivo y el voto de las materias web."""
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import clasificador as c
from conocimiento import importar as im


def _epub(ruta, texto="texto generico sin pistas " * 300):
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("c.xhtml", f"<p>{texto}</p>")


def test_revisar_guarda_metodo_propuesta_y_marca_lo_corregido(tmp_path):
    o = tmp_path / "o"; o.mkdir()
    (o / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (o / "b.md").write_text("# Notas\n\nApuntes de clase.\n", encoding="utf-8")
    k, db = tmp_path / "k", tmp_path / "i.db"
    im.importar([o / "a.py", o / "b.md"], k, db=db)
    filas = {x["titulo"]: x for x in im.revisar(carpeta=k)}
    assert set(filas) == {"a", "b"} and all(x["metodo"] == "reglas" and x["motivo"] and not x["corregido"] for x in filas.values())
    assert filas["a"]["propuesta"]["galaxia"] == "codigo"
    im.editar(filas["b"]["rel"], {"genero": "arte"}, k, db=db)                      # cambias lo que propuso el sistema…
    nuevas = {x["titulo"]: x for x in im.revisar(carpeta=k)}
    assert nuevas["b"]["corregido"] and not nuevas["a"]["corregido"]                # …y queda marcado como corrección
    fecha = nuevas["a"]["fecha"][:10]
    assert len(im.revisar(desde=fecha, hasta=fecha, carpeta=k)) == 2 and im.revisar(desde="2999-01-01", carpeta=k) == []
    assert im.listar(k)[0]["fecha_hora"] and "metodo" in im.listar(k)[0]


def test_voto_de_las_materias_web(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "WEB", True)
    monkeypatch.setattr(im, "_materias_web", lambda t: ["Statistics", "Regression analysis"])
    f = tmp_path / "Zorrotz Quimbaya.epub"; _epub(f)
    r = im.clasificar(f, tmp_path)
    assert r["genero"] == "estadistica" and r["metodo"] == "web" and "materias web" in r["motivo"]
    monkeypatch.setattr(c, "WEB", False)
    assert im.clasificar(f, tmp_path)["metodo"] == "reglas"                         # sin red (o desactivado) se clasifica como siempre


def test_la_forma_de_la_obra_manda_sobre_el_tema(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "WEB", True)
    f = tmp_path / "The Reluctant Spy.epub"; _epub(f, "la CIA el gobierno el Estado politica democracia " * 300)
    monkeypatch.setattr(im, "_materias_web", lambda t: ["Nonfiction", "Politics", "Spies", "Personal narratives", "Biography"])
    r = im.clasificar(f, tmp_path)
    assert r["genero"] == "biografia" and r["metodo"] == "web" and "Biography" in r["motivo"]       # habla de política pero es una memoria
    monkeypatch.setattr(im, "_materias_web", lambda t: ["Fiction", "History", "Kings and rulers"])
    g = tmp_path / "Roma soy yo.epub"; _epub(g, "el imperio romano las guerras y los reyes historia " * 300)
    assert im.clasificar(g, tmp_path)["genero"] == "novela"                                         # habla de historia pero es una novela
    assert im._forma_materias(["Economics", "Finance"]) is None


def test_decidir_con_voto_web_desempata():
    p = {"puntos": {"historia": .40, "ciencia": .38}}
    assert c.decidir({}, "otro", p)[0] == "historia" and c.decidir({}, "otro", p, web="ciencia")[0] == "ciencia"
