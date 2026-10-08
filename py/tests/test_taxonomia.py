"""Taxonomía género › subgénero: datos coherentes, ampliable por el usuario, y el subgénero se calcula, se guarda, se corrige y se revisa."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import clasificador as c
from conocimiento import importar as im
from conocimiento import taxonomia as tx

ROMA = "Roma antigua: Julio César, la república romana, las legiones, Augusto y el imperio. Alejandro Magno y Grecia clásica. " * 6


def test_los_datos_de_la_taxonomia_son_coherentes():
    assert sum(len(v) for v in tx.TAXONOMIA.values()) >= 100 and len(tx.GENEROS_NUEVOS) == 10
    for g, subs in tx.TAXONOMIA.items():
        assert g in im.GENEROS and subs, g
        ids = [s[0] for s in subs]
        assert len(ids) == len(set(ids)), f"ids repetidos en {g}"
        assert all(len(s) == 4 and all(str(x).strip() for x in s) for s in subs), g          # id, nombre, frase en español, frase en inglés
    assert set(tx.GENEROS_NUEVOS) <= set(tx.TAXONOMIA) and set(tx.GENEROS_NUEVOS) <= set(im.GENEROS)
    assert list(im.GENEROS)[-1] == "otro"


def test_el_usuario_amplia_la_taxonomia_sin_tocar_el_codigo(tmp_path):
    (tmp_path / "taxonomia.json").write_text(json.dumps({
        "generos": {"astrologia": "Astrología"},
        "sub": {"historia": [{"id": "vikingos", "nombre": "Vikingos", "frases": ["Vikingos, drakkars y sagas nórdicas", "Vikings, longships and Norse sagas"]},
                             {"id": "antigua", "nombre": "Mundo antiguo (mío)", "frases": ["a", "b"]}],
                "astrologia": [{"id": "signos", "nombre": "Signos", "frases": ["Signos del zodiaco"]}]}}), encoding="utf-8")
    generos, tax = tx.cargar(tmp_path)
    assert generos["astrologia"] == "Astrología" and "derecho" in generos
    ids = {s[0]: s for s in tax["historia"]}
    assert "vikingos" in ids and ids["antigua"][1] == "Mundo antiguo (mío)" and len(tax["historia"]) == len(tx.TAXONOMIA["historia"]) + 1   # suma, y mismo id = sustituye
    assert tx.nombre_sub("astrologia", "signos", tmp_path) == "Signos" and tx.subgeneros("no_existe", tmp_path) == []


def test_subgenero_sin_modelo_por_palabras(monkeypatch, tmp_path):
    monkeypatch.setattr(c, "ACTIVO", False)
    r = c.subgenero(ROMA, "historia", tmp_path)
    assert r["id"] == "antigua" and r["nombre"].startswith("Roma") and set(r["puntos"]) <= {s[0] for s in tx.TAXONOMIA["historia"]}
    assert c.subgenero("zzz qqq", "historia", tmp_path) is None            # nada en común: no inventa
    assert c.subgenero(ROMA, "otro", tmp_path) is None                      # «otro» no tiene subgéneros
    sem = c.semillas_todas(tmp_path)
    assert set(tx.GENEROS_NUEVOS) <= set(sem) and all(len(v) >= 2 for v in sem.values())


def test_importar_guarda_el_subgenero_lo_valida_y_se_puede_corregir(tmp_path):
    o = tmp_path / "o"; o.mkdir()
    (o / "apuntes_roma.md").write_text("# Roma\n\n" + ROMA, encoding="utf-8")
    (o / "otros.md").write_text("# Roma\n\n" + ROMA + " diferente", encoding="utf-8")
    k, db = tmp_path / "k", tmp_path / "i.db"
    auto = im.clasificar(o / "apuntes_roma.md", k)
    assert auto["genero"] == "historia" and auto["subgenero"] == "antigua" and auto["subgeneros"] and "subgénero" in auto["motivo"]
    r = im.importar([o / "apuntes_roma.md", {"ruta": o / "otros.md", "subgenero": "no_vale"}], k, db=db)
    assert all(x["estado"] == "ok" and x["subgenero"] == "antigua" for x in r)                   # un subgénero inválido se ignora y manda el automático
    rel = next(iter(im.leer_metadatos(k)))
    assert im.leer_metadatos(k)[rel]["subgenero"] == "antigua" and im.leer_metadatos(k)[rel]["propuesta"]["subgenero"] == "antigua"
    f = im.editar(rel, {"subgenero": "medieval"}, k, db=db)
    assert f["subgenero"] == "medieval" and f["subgenero_nombre"] == "Edad Media"
    with pytest.raises(ValueError):
        im.editar(rel, {"subgenero": "fisica"}, k, db=db)                                         # un subgénero de otro género no vale
    g = im.editar(rel, {"genero": "ciencia"}, k, db=db)
    assert g["subgenero"] == ""                                                                  # al cambiar de género se limpia el subgénero que ya no corresponde
    fila = next(x for x in im.revisar(carpeta=k) if x["rel"] == rel)
    assert fila["corregido"] and fila["propuesta"]["subgenero"] == "antigua"
    assert im.opciones()["subgeneros"]["historia"][0]["id"] == "antigua" and "cocina" in {x["id"] for x in im.opciones()["generos"]}


def test_libros_van_a_carpeta_de_genero_y_subgenero(tmp_path):
    import zipfile
    f = tmp_path / "SPQR historia.epub"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("mimetype", "application/epub+zip"); z.writestr("c.xhtml", "<p>" + ROMA + "</p>")
    r = im.importar([{"ruta": f, "galaxia": "libros", "genero": "historia"}], tmp_path / "k", db=tmp_path / "i.db")[0]
    assert r["estado"] == "ok" and r["subgenero"] == "antigua"
    partes = Path(r["destino"]).parts
    assert partes[-3:-1] == ("Historia", "Roma_Grecia_y_mundo_antiguo"), partes
