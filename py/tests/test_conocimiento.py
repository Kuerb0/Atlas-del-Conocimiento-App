"""Gestor de conocimiento: índice incremental, acentos, filtros, sinónimos del catálogo y formatos."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conocimiento as k


def _montar(tmp_path):
    notas = tmp_path / "notas"; notas.mkdir()
    (notas / "tfm.md").write_text("# Cartera\n\nLa frontera eficiente de Markowitz minimiza la varianza.\n\n# Otro\n\nTexto sin relación.", encoding="utf-8")
    with zipfile.ZipFile(notas / "apunte.docx", "w") as z:
        z.writestr("word/document.xml", "<w:p><w:t>Duración modificada de un bono</w:t></w:p>")
    return {"finanzas": [str(notas)]}, tmp_path / "i.db"


def test_indexa_busca_y_es_incremental(tmp_path):
    fuentes, db = _montar(tmp_path)
    r = k.indexar(db, fuentes)
    assert r["nuevos"] > 100 and r["borrados"] == 0
    assert k.indexar(db, fuentes)["nuevos"] == 0                       # segunda pasada: nada que hacer
    h = k.buscar("frontera eficiente", "finanzas", db=db)[0]
    assert h["coleccion"] == "finanzas" and h["ubicacion"] == "Cartera"
    assert k.buscar("duracion modificada", coleccion="finanzas", db=db)[0]["ruta"].endswith("apunte.docx")   # sin acentos y desde .docx
    assert k.buscar("duracion", coleccion="codigo", db=db) == [] or all(x["coleccion"] == "codigo" for x in k.buscar("duracion", "codigo", db=db))


def test_codigo_conceptos_y_sinonimos(tmp_path):
    db = tmp_path / "i.db"; k.indexar(db, {})
    assert any(x["titulo"] == "tabla_odds_ratios" for x in k.buscar("odds ratios tabla", "codigo", 5, db))
    con = k._abrir(db)
    g = con.execute("select frase from grupos where grupo in (select grupo from grupos where frase = 'vif')").fetchall()
    con.close()
    assert len(g) > 1                                                  # el catálogo da sinónimos de «VIF»
    assert k.buscar("palabrainexistentexyz", db=db) == []
    assert k.buscar("odds zzzzinexistente", db=db)                      # relajada: cualquier palabra


def test_borrado_y_sin_indice(tmp_path):
    fuentes, db = _montar(tmp_path)
    k.indexar(db, fuentes)
    (tmp_path / "notas" / "tfm.md").unlink()
    assert k.indexar(db, fuentes)["borrados"] == 1 and not k.buscar("Markowitz", "finanzas", db=db)
    try:
        k.buscar("x", db=tmp_path / "no.db"); assert False
    except FileNotFoundError:
        pass


def test_visor_incluye_cerebro_e_icono():
    import construir_visor as cv
    html = cv.ensamblar(cv.construir())
    assert "window.crearCerebro" in html and 'id="cerebro"' in html
    assert "__ICONO__" not in html and "CEREBRO_JS" not in html and 'href="data:image/png;base64,' in html


def test_cerebro_reparte_el_arbol_en_galaxias():
    import construir_visor as cv
    html = cv.ensamblar(cv.construir())
    for g in ("codigo", "conceptos", "demos", "finanzas", "libros", "notas"):
        assert f"{{id: '{g}'" in html                                   # una galaxia por parte del árbol y por colección
    assert "volar: function" in html and "cerebro.volar(" in html        # animación de vuelo antes de entrar
