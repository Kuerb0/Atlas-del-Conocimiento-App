"""El importador acepta código, cuadernos, datos y apuntes además de libros: se clasifican, se indexan y se encuentran."""
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conocimiento as k
from conocimiento import importar as im


def _archivos(tmp_path):
    d = tmp_path / "origen"; d.mkdir()
    (d / "limpieza.py").write_text("import pandas as pd\n\n\ndef depurar_quimbaya(df):\n    return df.dropna()\n\n\nclass Tuxtla:\n    pass\n", encoding="utf-8")
    (d / "analisis.ipynb").write_text(json.dumps({"cells": [
        {"cell_type": "markdown", "source": ["# Regresión zorrotz\n", "Texto de la sección"]},
        {"cell_type": "code", "source": ["import statsmodels.api as sm\n", "modelo_zorrotz = sm.OLS(y, X)"], "outputs": []}]}), encoding="utf-8")
    (d / "notas.md").write_text("# Mis notas\n\nApuntes sobre la frontera eficiente de Markowitz.\n", encoding="utf-8")
    (d / "ventas.csv").write_text("fecha,importe\n2026-01-01,10\n2026-01-02,12\n", encoding="utf-8")
    with zipfile.ZipFile(d / "clase.pptx", "w") as z:
        z.writestr("ppt/slides/slide1.xml", "<p:sld><a:t>Diapositiva sobre cópulas</a:t></p:sld>")
    (d / "programa.exe").write_bytes(b"MZ\x00\x00")
    return d


def test_importa_codigo_cuadernos_datos_y_apuntes(tmp_path):
    d = _archivos(tmp_path)
    k_dir, db = tmp_path / "conocimiento", tmp_path / "i.db"
    res = {Path(r["ruta"]).name: r for r in im.importar([d / n for n in ("limpieza.py", "analisis.ipynb", "notas.md", "ventas.csv", "clase.pptx", "programa.exe")], k_dir, db=db)}
    assert res["programa.exe"]["estado"] == "error" and "no admitido" in res["programa.exe"]["mensaje"]
    assert all(res[n]["estado"] == "ok" for n in ("limpieza.py", "analisis.ipynb", "notas.md", "ventas.csv", "clase.pptx"))
    assert res["limpieza.py"]["galaxia"] == "codigo" and res["limpieza.py"]["tipo"] == "codigo" and res["limpieza.py"]["genero"] == "tecnologia"
    assert res["analisis.ipynb"]["galaxia"] == "codigo" and res["ventas.csv"]["tipo"] == "datos" and res["notas.md"]["tipo"] == "apuntes"
    assert [c["titulo"] for c in im.capitulos(Path(res["limpieza.py"]["destino"]))[0]] == ["depurar_quimbaya", "Tuxtla"]
    assert [c["titulo"] for c in im.capitulos(Path(res["analisis.ipynb"]["destino"]))[0]] == ["Regresión zorrotz"]

    # se encuentran por su contenido, con el formato como filtro
    def buscar(q, **kw):
        return k.buscar(q, db=db, **kw)
    assert Path(buscar("depurar_quimbaya", formato="py")[0]["ruta"]).name == "limpieza.py"            # el código importado no se confunde con el del árbol
    assert Path(buscar("modelo_zorrotz")[0]["ruta"]).name == "analisis.ipynb"                         # texto de una celda de código
    assert buscar("zorrotz", formato="ipynb") and not buscar("zorrotz", formato="py")
    assert Path(buscar("copulas", formato="pptx")[0]["ruta"]).name == "clase.pptx"
    assert buscar("importe", formato="csv")                                                           # cabecera del CSV


def test_las_carpetas_de_fuentes_siguen_siendo_solo_documentos():
    assert ".py" not in k.EXT and ".md" in k.EXT and {".py", ".ipynb", ".csv", ".pptx"} <= k.EXT_IMPORTABLE


def test_filtros_del_explorador_los_acepta_pywebview():
    """El explorador de archivos de la app falló una vez por una coma en el texto del filtro: se valida con el propio validador de pywebview."""
    util = pytest.importorskip("webview.util")
    filtros = im.filtros_dialogo()
    assert len(filtros) == 2 and all(util.parse_file_type(f) for f in filtros)
    assert ".py" in util.parse_file_type(filtros[0])[1] and ".ipynb" in util.parse_file_type(filtros[0])[1]
