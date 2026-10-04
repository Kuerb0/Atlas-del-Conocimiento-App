import ast
import importlib
import json
import re
import sys
from pathlib import Path

CODIGO = Path(__file__).resolve().parents[1]      # .../py
RAIZ = CODIGO.parent                              # carpeta principal (conceptos/, INDEX.md...)
sys.path.insert(0, str(CODIGO))
construir_visor = importlib.import_module("construir_visor")


def _publicas():
    nombres = set()
    for py in (CODIGO / "arbol_estadistica").rglob("*.py"):
        if py.name == "__init__.py":
            continue
        for n in ast.parse(py.read_text(encoding="utf-8")).body:
            if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"):
                nombres.add(n.name)
    return nombres


def test_el_visor_contiene_todas_las_funciones_publicas_con_descripcion():
    datos = construir_visor.construir()
    items = [i for r in datos["ramas"] for m in r["modulos"] for i in m["items"] if i["tipo"] == "funcion"]
    assert {i["nombre"] for i in items} == _publicas()
    sin_desc = [i["nombre"] for i in items if not i["desc"]]
    assert not sin_desc, f"Funciones sin descripción (docstring o fila en INDEX.md): {sin_desc}"
    assert all(i["codigo"].lstrip().startswith(("def ", "@")) and i["linea"] > 0 for i in items)


def test_las_funciones_documentadas_en_index_llevan_sas_u_origen():
    datos = construir_visor.construir()
    por_nombre = {i["nombre"]: i for r in datos["ramas"] for m in r["modulos"] for i in m["items"]}
    assert "ODDSRATIO" in por_nombre["tabla_odds_ratios"]["sas"]
    assert "multinomial_logit_sas_like" in por_nombre["logit_multinomial_sas"]["origen"]
    assert por_nombre["logit_multinomial_sas"]["importar"] == "from arbol_estadistica.modelos import logit_multinomial_sas"


def test_el_html_es_autocontenido_y_los_datos_son_json_valido():
    html = construir_visor.ensamblar(construir_visor.construir())
    assert not re.findall(r'(?:src|href)="https?://', html)           # sin recursos externos
    bruto = re.search(r'id="datos">(.*?)</script>', html, re.S).group(1).replace("<\\/", "</")
    assert json.loads(bruto)["ramas"]


# ---------- capa de conceptos (temario del máster + Very Normal) ----------
def _catalogo():
    return json.loads((RAIZ / "conceptos" / "catalogo.json").read_text(encoding="utf-8"))


def test_catalogo_de_conceptos_es_coherente():
    cat = _catalogo()
    areas = {a["id"] for a in cat["areas"]}
    ids = [k["id"] for k in cat["conceptos"]]
    assert len(ids) == len(set(ids)), "ids de concepto duplicados"
    temas = {t["id"] for t in cat["temas"]}
    assert temas and len(temas) == len(cat["temas"]), "temas vacíos o duplicados"
    assert len(areas) == len(cat["areas"]), "ids de área duplicados"
    for t in cat["temas"]:
        assert t["nombre"] and set(t["color"]) == {"claro", "oscuro"}
        assert not t["id"] in {"preprocesado", "seleccion", "modelos", "diagnostico", "clustering", "contrastes", "graficos", "demos", "guias"}, "el id del tema choca con una rama de código"
    for a in cat["areas"]:
        assert a["tema"] in temas, a["id"]
        assert a["ambito"] in ("metodologico", "actuarial", "financiero", "normativo"), a["id"]
    assert all(any(a["tema"] == t for a in cat["areas"]) for t in temas), "tema sin áreas"
    assert all(any(k["area"] == a["id"] for k in cat["conceptos"]) for a in cat["areas"]), "área sin conceptos"
    for k in cat["conceptos"]:
        assert k.get("prioridad", "alta") == "alta"
        assert k["area"] in areas, k["nombre"]
        assert k["desc"] and k["fuentes"], f"«{k['nombre']}» necesita descripción y al menos una fuente"
        for f in k["fuentes"]:
            assert f["tipo"] in ("master", "very_normal", "arbol", "manual", "curso") and f["ref"]
            if f["tipo"] == "curso":
                assert f["url"].startswith("https://") and f["base"], f
            if f["tipo"] == "very_normal":
                assert f["url"].startswith(("https://verynormal.substack.com/", "https://www.youtube.com/watch?v=")), f["url"]


def test_las_fuentes_de_manuales_citan_libro_y_capitulo():
    cat = _catalogo()
    manuales = [f for k in cat["conceptos"] for f in k["fuentes"] if f["tipo"] == "manual"]
    assert len(manuales) > 100
    for f in manuales:
        siglas, _, capitulo = f["ref"].partition(" · ")
        assert siglas in ("ALSM", "JW", "HS", "ISLR", "APM", "RMS", "MSDA", "PSDS", "ESL", "DSUS") and capitulo, f["ref"]
        assert f["base"].startswith(("Applied", "An Introduction", "Practical", "The Elements", "Discovering", "Regression", "Mathematical")), f["base"]


def test_los_conceptos_enlazan_funciones_reales_y_todas_las_funciones_tienen_concepto():
    cat = _catalogo()
    publicas = _publicas()
    enlazadas = {f for k in cat["conceptos"] for f in k["funciones"]}
    assert enlazadas <= publicas, f"funciones inexistentes: {enlazadas - publicas}"
    assert publicas <= enlazadas, f"funciones sin ningún concepto (añádelas al catálogo): {publicas - enlazadas}"


def test_el_visor_incluye_una_rama_por_tema_con_huecos_y_fuentes():
    datos = construir_visor.construir()
    cat = _catalogo()
    ramas = [r for r in datos["ramas"] if r.get("grupo") == "conceptos"]
    assert [r["id"] for r in ramas] == [t["id"] for t in cat["temas"]]
    assert all(r["color"]["oscuro"].startswith("#") for r in ramas)
    items = [i for r in ramas for m in r["modulos"] for i in m["items"]]
    assert len(items) == len(cat["conceptos"]) and all(i["tipo"] == "concepto" for i in items)
    assert len({i["id"] for i in items}) == len(items)
    assert any(not i["funciones"] for i in items) and any(i["funciones"] for i in items)   # huecos y cubiertos
    assert any("Very Normal" in i["origen"] for i in items) and any("Máster" in i["origen"] for i in items)
    assert any(i["ambito"] == "normativo" for i in items) and any(i["prioridad"] == "alta" for i in items)
    ajenos = {i["id"] for r in datos["ramas"] if r.get("grupo") != "conceptos" for m in r["modulos"] for i in m["items"]}
    assert not {i["id"] for i in items} & ajenos


def test_los_ids_de_concepto_no_cambian_con_la_reorganizacion():
    """Los ids son estables: las demos, los enlaces y tu catálogo dependen de ellos."""
    cat = _catalogo()
    ids = {k["id"] for k in cat["conceptos"]}
    usados = {c for _, _, demos in construir_visor.DEMOS for d in demos for c in d["conceptos"]}
    assert usados <= ids, f"demos que enlazan conceptos inexistentes: {usados - ids}"


def test_un_concepto_con_funcion_inexistente_avisa_sin_romper_el_visor(monkeypatch, tmp_path):
    malo = {"areas": [{"id": "a", "nombre": "A", "desc": "d"}],
            "conceptos": [{"id": "c_x", "nombre": "X", "area": "a", "desc": "d", "funciones": ["no_existe"], "sinonimos": [], "fuentes": []}]}
    ruta = tmp_path / "catalogo.json"
    ruta.write_text(json.dumps(malo), encoding="utf-8")
    monkeypatch.setattr(construir_visor, "CATALOGO", ruta)
    monkeypatch.setattr(construir_visor, "RAIZ", tmp_path)
    ramas = construir_visor.ramas_conceptos({"ajustar_logit"})      # catálogo sin temas: una sola rama; avisa y quita el enlace
    assert [r["id"] for r in ramas] == ["conceptos"]
    assert ramas[0]["modulos"][0]["items"][0]["funciones"] == []


# ---------- mapa 3D (py/visor/mapa3d.js) ----------
def test_el_mapa_3d_esta_incrustado_y_sin_marcadores_sin_sustituir():
    html = construir_visor.ensamblar(construir_visor.construir())
    assert "crearMapa3D" in html and '<canvas id="mapa"' in html
    assert "/*__MAPA3D_JS__*/" not in html and "/*__DEMOS_JS__*/" not in html and "__DATOS__" not in html
    assert "<svg id=\"mapa\"" not in html                                    # ya no es el mapa de burbujas en SVG


def test_el_javascript_del_mapa_3d_es_sintacticamente_valido():
    import shutil
    import subprocess
    import pytest
    if not shutil.which("node"):
        pytest.skip("node no está instalado: no se puede comprobar la sintaxis del JS")
    r = subprocess.run(["node", "--check", str(CODIGO / "visor" / "mapa3d.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
