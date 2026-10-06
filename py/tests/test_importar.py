"""Importador: clasificación automática, copia a la biblioteca, metadatos, índice y búsqueda."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conocimiento as k
from conocimiento import importar as imp


def _frases_de_tema(nombre_tema, n=6):
    cat = imp._catalogo()
    tid = next(t["id"] for t in cat["temas"] if t["nombre"] == nombre_tema)
    areas = {a["id"] for a in cat["areas"] if a["tema"] == tid}
    return [c["nombre"] for c in cat["conceptos"] if c.get("area") in areas][:n]


def test_clasifica_por_el_tema_del_catalogo(tmp_path):
    f = tmp_path / "apuntes_contrastes.md"
    f.write_text("# Apuntes\n\n" + "\n\n".join(f"Hoy repasamos {x}. " * 3 for x in _frases_de_tema("Inferencia y contrastes")), encoding="utf-8")
    c = imp.clasificar(f)
    assert c["subtema"] == "Inferencia y contrastes" and c["galaxia"] == "notas" and c["tipo"] == "apuntes"
    g = tmp_path / "carteras.txt"
    g.write_text("La cartera de bonos tiene volatilidad y rentabilidad; el riesgo de mercado y los derivados se cubren con opciones y futuros. " * 5, encoding="utf-8")
    assert imp.clasificar(g)["galaxia"] == "finanzas"


def test_importa_copia_indexa_y_no_duplica(tmp_path):
    carpeta, db = tmp_path / "datos", tmp_path / "datos" / "i.db"
    f = tmp_path / "mis_apuntes.md"
    f.write_text("# Notas\n\nEl estimador de Kaplan-Meier estima la supervivenciaxyz con censura. " * 4, encoding="utf-8")
    r = imp.importar([f], carpeta=carpeta, db=db)[0]
    assert r["estado"] == "ok" and Path(r["destino"]).is_file() and "biblioteca" in r["destino"]
    meta = json.loads((carpeta / "biblioteca" / "metadatos.json").read_text(encoding="utf-8"))
    assert list(meta.values())[0]["galaxia"] == r["galaxia"] and imp.resumen(carpeta) == {r["galaxia"]: 1}
    h = k.buscar("supervivenciaxyz", db=db)[0]                                  # ya se encuentra, con su galaxia y subtema
    assert h["coleccion"] == r["galaxia"] and h["subtema"] == r["subtema"] and h["interno"] is False
    assert imp.importar([f], carpeta=carpeta, db=db)[0]["estado"] == "duplicado"


def test_lo_indicado_manda_sobre_lo_automatico_y_los_errores_no_paran(tmp_path):
    carpeta, db = tmp_path / "datos", tmp_path / "datos" / "i.db"
    f = tmp_path / "algo.txt"
    f.write_text("texto cualquiera sobre nada en concreto " * 5, encoding="utf-8")
    malo = tmp_path / "foto.jpg"
    malo.write_bytes(b"\xff\xd8\xff")
    r = imp.importar([{"ruta": f, "galaxia": "finanzas", "subtema": "Renta fija", "tipo": "libro", "etiquetas": "bonos"}, malo, tmp_path / "noexiste.pdf"], carpeta=carpeta, db=db)
    assert (r[0]["estado"], r[0]["galaxia"], r[0]["subtema"], r[0]["tipo"]) == ("ok", "finanzas", "Renta fija", "libro")
    assert r[0]["destino"].replace("\\", "/").endswith("biblioteca/finanzas/Renta_fija/algo.txt")
    assert r[1]["estado"] == "error" and "formato" in r[1]["mensaje"] and r[2]["estado"] == "error"


def test_opciones_para_los_desplegables():
    o = imp.opciones()
    assert {g["id"] for g in o["galaxias"]} == set(imp.GALAXIAS) and "General" in o["subtemas"]["conceptos"] and "Inferencia y contrastes" in o["subtemas"]["libros"]


def test_el_visor_tiene_la_pestana_del_agujero_negro():
    import construir_visor as cv
    html = cv.ensamblar(cv.construir())
    for pieza in ("window.crearAgujero", 'id="pestImportar"', 'id="impPanel"', "elegir_archivos", "clasificar_archivos", "importar_archivos", "modo-importar"):
        assert pieza in html
    assert "/*__AGUJERO_JS__*/" not in html and 'id="pestUniverso"' in html
