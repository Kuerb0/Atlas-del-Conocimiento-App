"""Guía de aprendizaje (py/aprender/*.json): estructura y enlaces válidos. El visor la muestra en la pestaña «Aprender»."""
import importlib
import json
import sys
from pathlib import Path

CODIGO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODIGO))
construir_visor = importlib.import_module("construir_visor")
RUTAS = [r for f in sorted((CODIGO / "aprender").glob("*.json")) for r in json.loads(f.read_text(encoding="utf-8"))["rutas"]]
PASO = {"id", "titulo", "idea", "prueba", "pregunta"}
PREGUNTA = {"texto", "opciones", "correcta", "pista", "explicacion"}


def test_estructura_de_las_rutas():
    assert RUTAS and len({r["id"] for r in RUTAS}) == len(RUTAS)
    for r in RUTAS:
        assert {"id", "titulo", "para", "nivel", "duracion", "desc", "pasos"} <= set(r)
        assert len({p["id"] for p in r["pasos"]}) == len(r["pasos"]), f"pasos repetidos en {r['id']}"
        for p in r["pasos"]:
            assert PASO <= set(p), f"{r['id']}/{p.get('id')}: faltan {PASO - set(p)}"
            q = p["pregunta"]
            assert PREGUNTA <= set(q) and len(q["opciones"]) >= 2 and 0 <= q["correcta"] < len(q["opciones"])


def test_los_enlaces_de_las_rutas_existen():
    datos = construir_visor.construir()          # imprime AVISO y quita lo que no exista; aquí exigimos que no se quite nada
    nombres_fn = {i["nombre"] for r in datos["ramas"] for m in r["modulos"] for i in m["items"] if i["tipo"] == "funcion"}
    conceptos = {k["id"] for k in json.loads(construir_visor.CATALOGO.read_text(encoding="utf-8"))["conceptos"]}
    demos = {d["id"] for _, _, ds in construir_visor.DEMOS for d in ds}
    for r in RUTAS:
        for p in r["pasos"]:
            assert not p.get("demo") or p["demo"] in demos, f"{p['id']}: demo inexistente"
            assert set(p.get("funciones", [])) <= nombres_fn, f"{p['id']}: funciones inexistentes"
            assert set(p.get("conceptos", [])) <= conceptos, f"{p['id']}: conceptos inexistentes"
    assert [len(r["pasos"]) for r in datos["rutas"]] == [len(r["pasos"]) for r in RUTAS]
