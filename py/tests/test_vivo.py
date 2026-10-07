"""Clasificación en vivo: clasificar() emite sus etapas con barras parciales y la app las publica mientras trabaja en segundo plano."""
import importlib.machinery
import importlib.util
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import clasificador as c
from conocimiento import importar as im

ROMA = "# Roma\n\n" + "Roma antigua: Julio César, la república romana, las legiones, Augusto y el imperio. " * 8


def test_clasificar_emite_todas_las_etapas_en_orden(tmp_path):
    f = tmp_path / "apuntes_roma.md"; f.write_text(ROMA, encoding="utf-8")
    eventos = []
    r = im.clasificar(f, tmp_path, etapa=lambda n, d: eventos.append((n, d)))
    nombres = [n for n, d in eventos]
    assert nombres[0] == "leer" and nombres[-1] == "decision"
    assert [n for n in dict.fromkeys(nombres)] == list(im.ETAPAS)                          # salen todas, siempre en el mismo orden
    fin = {n: d for n, d in eventos if d["estado"] == "fin"}
    assert set(fin) == set(im.ETAPAS)
    b = fin["reglas"]["barras"]
    assert b and b[0]["id"] == "historia" and b[0]["valor"] == 100 and all(0 < x["valor"] <= 100 for x in b)      # barras relativas a la mejor
    assert fin["web"]["omitido"] and fin["llm"]["omitido"]                                  # en los tests no hay red ni LLM: se dice por qué
    assert fin["subgenero"]["id"] == r["subgenero"] == "antigua" and fin["subgenero"]["barras"][0]["valor"] == 100
    d = fin["decision"]
    assert d["genero"] == r["genero"] and d["galaxia"] == r["galaxia"] and d["metodo"] == r["metodo"] and d["motivo"] == r["motivo"]
    assert im.clasificar(f, tmp_path)["genero"] == r["genero"]                              # sin callback devuelve lo mismo


def test_una_funcion_de_eventos_que_falla_no_rompe_la_clasificacion(tmp_path):
    f = tmp_path / "apuntes_roma.md"; f.write_text(ROMA, encoding="utf-8")
    def mala(n, d):
        raise RuntimeError("fallo en la interfaz")
    assert im.clasificar(f, tmp_path, etapa=mala)["genero"] == "historia"


def test_barras_normalizadas_y_voto_decisivo():
    b = im._barras({"historia": 10, "economia": 5, "arte": 0, "xxx": 3})
    assert [x["id"] for x in b] == ["historia", "economia"] and b[0]["valor"] == 100 and b[1]["valor"] == 50      # sin ceros ni géneros que no existen
    assert im._barras({"historia": 10, "economia": 5}, forzar="economia")[0]["id"] == "economia"
    assert im._barras({}) == []


def test_la_app_clasifica_en_segundo_plano_y_publica_el_estado(tmp_path, monkeypatch):
    monkeypatch.setenv("ARBOL_CONOCIMIENTO", str(tmp_path / "k"))
    (tmp_path / "a.md").write_text(ROMA, encoding="utf-8")
    (tmp_path / "b.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    ruta = Path(__file__).resolve().parents[1] / "arbol_app.pyw"
    spec = importlib.util.spec_from_loader("arbol_app_test", importlib.machinery.SourceFileLoader("arbol_app_test", str(ruta)))
    app = importlib.util.module_from_spec(spec); spec.loader.exec_module(app)
    api = app.Api()
    assert api.estado_clasificacion()["fase"] == "fin"                                     # antes de empezar no hay nada en curso
    assert api.clasificar_en_vivo([tmp_path / "a.md", tmp_path / "b.py"]) == {"ok": True}
    t0 = time.time()
    while api.estado_clasificacion()["fase"] != "fin" and time.time() - t0 < 60:
        time.sleep(.1)
    st = api.estado_clasificacion()
    assert [a["estado"] for a in st["archivos"]] == ["listo", "listo"] and st["fase"] == "fin"
    assert st["archivos"][0]["resultado"]["genero"] == "historia" and st["archivos"][1]["resultado"]["galaxia"] == "codigo"
    assert "decision" in st["archivos"][0]["etapas"] and st["archivos"][0]["etapas"]["decision"]["estado"] == "fin"
