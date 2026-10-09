"""Varias etiquetas por obra: varios géneros y varios subgéneros (máximo 3 de cada), con peso; el principal manda sobre la carpeta, las correcciones y el orden."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import etiquetas as et
from conocimiento import importar as im
from conocimiento import llm

ROMA = "Roma antigua: Julio César, la república romana, las legiones, Augusto y el imperio. Alejandro Magno y Grecia clásica. " * 6
ECO = "Economía: mercados, oferta y demanda, inflación, política monetaria, crecimiento, banca central y comercio internacional. " * 6


def test_elegir_pone_primero_al_principal_y_anade_los_que_empatan():
    p = {"historia": .60, "economia": .55, "novela": .20, "otro": .59}
    assert [g for g, _ in et.elegir(p, 1.0, .15)] == ["historia", "economia"]                      # «otro» nunca es secundaria; novela queda lejos
    assert et.elegir(p, 1.0, .15, principal="economia")[0] == ("economia", 1.0)                    # el principal forzado (p. ej. por el LLM) va primero
    assert len(et.elegir({"a": 1, "b": 1, "c": 1, "d": 1}, 1.0, .5)) == et.MAXIMO                  # como mucho tres
    assert et.elegir({"otro": 1.0, "historia": .99}, 1.0, .5) == [("otro", 1.0)]                    # lo que no encaja en nada no lleva otras etiquetas
    pesos = dict(et.elegir({"a": 1.0, "b": 1.0, "c": .86}, 1.0, .15))
    assert pesos["b"] == 1.0 and 0.5 <= pesos["c"] < 1.0                                           # más cerca del primero = más peso


def test_lo_importado_sin_listas_se_lee_como_una_sola_etiqueta():
    m = {"genero": "historia", "subgenero": "antigua"}
    assert et.generos_de(m) == ["historia"] and et.subgeneros_de(m) == [("historia", "antigua")]
    m2 = {"genero": "historia", "generos": [{"id": "economia", "peso": .7}, {"id": "historia", "peso": 1}], "subgenero": "antigua", "subgeneros": [{"genero": "economia", "id": "macro", "peso": .7}]}
    assert et.generos_de(m2) == ["historia", "economia"] and et.subgeneros_de(m2) == [("historia", "antigua"), ("economia", "macro")]    # el principal siempre primero


def test_poner_mantiene_coherentes_las_listas_y_las_etiquetas_principales():
    m = et.poner({}, [("economia", 1), ("historia", .8), "economia", "ciencia", "arte"], [("economia", "macro"), ("ciencia", "fisica"), ("novela", "x"), ("historia", "antigua", .6)])
    assert [e["id"] for e in m["generos"]] == ["economia", "historia", "ciencia"] and m["genero"] == "economia"          # sin repetidos, máximo 3
    assert [(e["genero"], e["id"]) for e in m["subgeneros"]] == [("economia", "macro"), ("ciencia", "fisica"), ("historia", "antigua")] and m["subgenero"] == "macro"   # (novela no es uno de sus géneros)
    assert et.jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3) and et.jaccard([], []) == 1.0


@pytest.fixture
def ollama_multi(monkeypatch):
    """Un Ollama falso que responde con dos géneros y dos subgéneros."""
    def http(url, datos=None, espera=0):
        esquema = (datos or {}).get("format", {}).get("properties", {})
        if "subgeneros" in esquema:
            ids = esquema["subgeneros"]["items"]["enum"]
            return {"message": {"content": json.dumps({"subgeneros": [x for x in ("antigua", "macro") if x in ids][:2] or ids[:1], "motivo": "x"})}}
        return {"message": {"content": json.dumps({"generos": ["historia", "economia", "inventado"], "motivo": "trata de las dos cosas"})}}
    monkeypatch.setattr(llm, "ACTIVO", True)
    monkeypatch.setattr(llm, "disponible", lambda carpeta=None: True)
    monkeypatch.setattr(llm, "_http", http)


def test_llm_devuelve_varios_generos_y_acepta_el_formato_antiguo(ollama_multi, monkeypatch, tmp_path):
    r = llm.clasificar("Historia de la banca", [], "texto", [], im.GENEROS, tmp_path)
    assert r["genero"] == "historia" and r["generos"] == ["historia", "economia"]                  # el que se inventa se ignora
    monkeypatch.setattr(llm, "_http", lambda *a, **k: {"message": {"content": '{"genero": "novela", "motivo": "x"}'}})
    assert llm.clasificar("t", [], "", [], im.GENEROS, tmp_path)["generos"] == ["novela"]          # respuesta con el formato de antes
    monkeypatch.setattr(llm, "_http", lambda *a, **k: {"message": {"content": '{"generos": ["inventado", "novela"], "motivo": "x"}'}})
    assert llm.clasificar("t", [], "", [], im.GENEROS, tmp_path) is None                           # si el principal no vale, no se fía de la respuesta
    subs = [("antigua", "Antigua", "roma", "rome"), ("macro", "Macro", "pib", "gdp"), ("otra", "Otra", "x", "y")]
    monkeypatch.setattr(llm, "_http", lambda *a, **k: {"message": {"content": '{"subgeneros": ["macro", "antigua", "macro"], "motivo": "x"}'}})
    assert llm.subgeneros("t", [], "", "Historia", subs, "", tmp_path) == ["macro", "antigua"] and llm.subgenero("t", [], "", "Historia", subs, "", tmp_path) == "macro"


def test_el_prompt_enseña_que_se_puede_poner_mas_de_un_genero():
    p = llm.prompt_generos("T", [], "texto", [], {"historia": "H", "economia": "E"}, "", [{"titulo": "Otro", "autor": "", "genero": "historia", "generos": ["historia", "economia"]}])
    assert '"generos": ["historia", "economia"]' in p and "máximo 3" in p


def _epub(ruta: Path, texto: str):
    import zipfile
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("mimetype", "application/epub+zip"); z.writestr("c.xhtml", "<p>" + texto + "</p>")


def test_clasificar_con_llm_lleva_varios_generos_y_sus_subgeneros(ollama_multi, tmp_path):
    _epub(tmp_path / "Historia de la banca - Autor Ejemplo.epub", ROMA + ECO)
    a = im.clasificar(tmp_path / "Historia de la banca - Autor Ejemplo.epub", tmp_path)
    assert a["genero"] == "historia" and a["metodo"] == "llm"
    assert [g["id"] for g in a["etiquetas"]["generos"]] == ["historia", "economia"] and a["etiquetas"]["generos"][0]["peso"] == 1.0
    sub = {(s["genero"], s["id"]) for s in a["etiquetas"]["subgeneros"]}
    assert ("historia", "antigua") in sub and ("economia", "macro") in sub and "también" in a["motivo"]


def test_importar_guarda_las_listas_y_la_carpeta_es_la_del_principal(ollama_multi, tmp_path):
    o = tmp_path / "o"; o.mkdir()
    _epub(o / "Historia de la banca - Autor Ejemplo.epub", ROMA + ECO)
    k = tmp_path / "k"
    r = im.importar([o / "Historia de la banca - Autor Ejemplo.epub"], k, db=tmp_path / "i.db")[0]
    assert r["estado"] == "ok" and [g["id"] for g in r["generos"]] == ["historia", "economia"]
    assert "Historia" in Path(r["destino"]).parts and "Economia_y_finanzas" not in Path(r["destino"]).parts       # el archivo vive en la carpeta del género principal
    rel = next(iter(im.leer_metadatos(k)))
    m = im.leer_metadatos(k)[rel]
    assert et.generos_de(m) == ["historia", "economia"] and m["genero"] == "historia" and m["propuesta"]["generos"] == ["historia", "economia"]
    f = im.listar(k)[0]
    assert [g["nombre"] for g in f["generos"]] == [im.GENEROS["historia"], im.GENEROS["economia"]] and f["subgeneros"]


def test_fijar_a_mano_los_generos_manda_sobre_lo_automatico(ollama_multi, tmp_path):
    o = tmp_path / "o"; o.mkdir()
    _epub(o / "Historia de la banca - Autor Ejemplo.epub", ROMA + ECO)
    k = tmp_path / "k"
    im.importar([{"ruta": o / "Historia de la banca - Autor Ejemplo.epub", "generos": ["economia", "politica"]}], k, db=tmp_path / "i.db")
    m = next(iter(im.leer_metadatos(k).values()))
    assert et.generos_de(m)[:2] == ["economia", "politica"] and m["genero"] == "economia"      # lo que eliges tú va primero; lo que no pediste no se queda


def test_editar_cambia_las_etiquetas_y_valida(tmp_path):
    (tmp_path / "biblioteca").mkdir()
    meta = {"libros/a.epub": {"titulo": "A", "galaxia": "libros", "genero": "historia", "subgenero": "antigua", "subtema": "General", "tipo": "libro", "hash": "1",
                              "generos": [{"id": "historia", "peso": 1}, {"id": "economia", "peso": .8}], "subgeneros": [{"genero": "historia", "id": "antigua", "peso": 1}, {"genero": "economia", "id": "macro", "peso": .8}]}}
    (tmp_path / "biblioteca" / "metadatos.json").write_text(json.dumps(meta), encoding="utf-8")
    db = tmp_path / "i.db"
    f = im.editar("libros/a.epub", {"generos": ["economia", "historia", "ciencia"]}, tmp_path, db)
    assert [g["id"] for g in f["generos"]] == ["economia", "historia", "ciencia"] and f["genero"] == "economia" and f["subgenero"] == "macro"     # el principal cambia y su subgénero sale de las listas
    f = im.editar("libros/a.epub", {"subgeneros": ["economia/micro", "historia/antigua", "novela/fantasia"]}, tmp_path, db)
    assert [(s["genero"], s["id"]) for s in f["subgeneros"]] == [("economia", "micro"), ("historia", "antigua")] and f["subgenero"] == "micro"       # novela no es uno de sus géneros
    f = im.editar("libros/a.epub", {"genero": "ciencia"}, tmp_path, db)
    assert f["genero"] == "ciencia" and [g["id"] for g in f["generos"]][0] == "ciencia" and "economia" not in [g["id"] for g in f["generos"]] and "historia" in [g["id"] for g in f["generos"]]    # el principal antiguo se descarta; las demás se quedan
    with pytest.raises(ValueError):
        im.editar("libros/a.epub", {"generos": ["economia", "no_existe"]}, tmp_path, db)
    with pytest.raises(ValueError):
        im.editar("libros/a.epub", {"generos": []}, tmp_path, db)


def test_la_busqueda_por_genero_encuentra_tambien_las_etiquetas_secundarias(tmp_path):
    from conocimiento import indexar, buscar
    (tmp_path / "biblioteca" / "libros").mkdir(parents=True)
    (tmp_path / "biblioteca" / "libros" / "a.md").write_text("# Banca\n\nla banca medieval en Florencia y la economia de los mercados " * 3, encoding="utf-8")
    meta = {"libros/a.md": {"titulo": "Banca", "galaxia": "libros", "genero": "historia", "subgenero": "", "subtema": "General", "tipo": "apuntes", "hash": "1", "generos": [{"id": "historia", "peso": 1}, {"id": "economia", "peso": .9}]}}
    (tmp_path / "biblioteca" / "metadatos.json").write_text(json.dumps(meta), encoding="utf-8")
    db = tmp_path / "i.db"
    indexar(db, {}, carpeta=tmp_path)
    import conocimiento
    conocimiento.CARPETA, antes = tmp_path, conocimiento.CARPETA
    try:
        assert buscar("banca florencia", db=db, genero="historia") and buscar("banca florencia", db=db, genero="economia") and not buscar("banca florencia", db=db, genero="novela")
    finally:
        conocimiento.CARPETA = antes


def test_un_empate_entre_generos_ya_no_es_una_duda_si_los_dos_son_etiquetas():
    empate = {"puntos": {"novela": 0.50, "historia": 0.49}, "confianza": 0.01, "genero": "novela"}
    args = ({"novela": 1, "historia": 1}, empate, None, "novela", None, None, "x" * 500, "libro", False)
    assert any("poco claro" in m for m in im._seguridad(*args)[2])
    assert not any("poco claro" in m for m in im._seguridad(*args, ("historia",))[2])             # pero si «historia» ya es una de sus etiquetas, no hay nada que revisar


def test_las_ramas_del_mapa_llevan_la_obra_en_cada_genero(monkeypatch, tmp_path):
    import construir_visor as cv
    (tmp_path / "biblioteca").mkdir()
    meta = {"libros/a.epub": {"titulo": "Historia de la banca", "galaxia": "libros", "genero": "historia", "subgenero": "antigua", "subtema": "General", "tipo": "libro", "hash": "1", "paginas": 10,
                              "capitulos": [{"titulo": "Uno", "pagina": 1}], "generos": [{"id": "historia", "peso": 1}, {"id": "economia", "peso": .8}]}}
    (tmp_path / "biblioteca" / "metadatos.json").write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setenv("ARBOL_CONOCIMIENTO", str(tmp_path))
    ramas = {r["id"]: r for r in cv.ramas_biblioteca()}
    assert {"gen_historia", "gen_economia"} <= set(ramas)
    assert ramas["gen_economia"]["modulos"][0]["nombre"] == "Historia de la banca" and "también en" in ramas["gen_economia"]["modulos"][0]["desc"]
    assert ramas["gen_economia"]["modulos"][0]["items"][0]["id"] != ramas["gen_historia"]["modulos"][0]["items"][0]["id"]       # ids distintos: cada copia es su propio punto
