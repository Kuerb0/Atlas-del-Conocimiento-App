"""Cola de revisión: lo que el clasificador no ve claro se marca para que lo revise una persona."""
import json

from conocimiento import clasificador, importar


def test_seguridad_sin_modelo_marca_pocas_pistas():
    margen, msub, motivos = importar._seguridad({"historia": 2, "novela": 1}, None, None, "historia", None, None, "x" * 500, "libro", False)
    assert any("pocas pistas" in m for m in motivos) and msub is None


def test_seguridad_con_parecido_claro_no_marca_y_con_empate_si():
    claro = {"puntos": {"novela": 0.9, "historia": 0.2}, "confianza": 0.7, "genero": "novela"}
    _, _, ninguno = importar._seguridad({"novela": 30}, claro, None, "novela", None, None, "x" * 500, "libro", False)
    assert ninguno == []
    empate = {"puntos": {"novela": 0.50, "historia": 0.49}, "confianza": 0.01, "genero": "novela"}
    _, _, motivos = importar._seguridad({"novela": 1, "historia": 1}, empate, None, "novela", None, None, "x" * 500, "libro", False)
    assert any("poco claro" in m for m in motivos)


def test_seguridad_avisa_de_poco_texto_discrepancia_del_llm_y_lo_corregido_por_ti():
    p = {"puntos": {"novela": 0.9, "historia": 0.1}, "confianza": 0.8, "genero": "novela"}
    assert any("casi no hay texto" in m for m in importar._seguridad({"novela": 30}, p, None, "novela", None, None, "corto", "libro", False)[2])
    sg = {"id": "fantasia", "puntos": {"fantasia": 1.0, "negra": 0.2}, "confianza": 0.8, "nombre": "Fantasía"}
    assert any("LLM y el parecido" in m for m in importar._seguridad({"novela": 30}, p, None, "novela", sg, "negra", "x" * 500, "libro", False)[2])
    assert importar._seguridad({"novela": 1}, None, None, "otro", None, None, "x" * 500, "libro", True)[2] == []          # ya lo corregiste: se respeta
    assert importar._seguridad({}, None, None, "otro", None, None, "x" * 500, "codigo", False)[2] == []                   # el «género» de un código no es lo importante


def _biblioteca(tmp_path):
    m = {"libros/a.epub": {"titulo": "Libro A", "galaxia": "libros", "genero": "novela", "subtema": "General", "subgenero": "", "tipo": "libro", "hash": "1", "revisar": True, "margen": 0.1, "motivos_revisar": ["género poco claro"]},
         "libros/b.epub": {"titulo": "Libro B", "galaxia": "libros", "genero": "historia", "subtema": "General", "subgenero": "", "tipo": "libro", "hash": "2", "revisar": True, "margen": 0.5, "motivos_revisar": ["subgénero poco claro"]},
         "libros/c.epub": {"titulo": "Libro C", "galaxia": "libros", "genero": "ensayo", "subtema": "General", "subgenero": "", "tipo": "libro", "hash": "3"}}
    (tmp_path / "biblioteca").mkdir()
    (tmp_path / "biblioteca" / "metadatos.json").write_text(json.dumps(m), encoding="utf-8")


def test_por_revisar_ordena_por_lo_menos_claro_y_confirmar_lo_quita(tmp_path):
    _biblioteca(tmp_path)
    cola = importar.por_revisar(tmp_path)
    assert [x["titulo"] for x in cola] == ["Libro A", "Libro B"] and cola[0]["motivos"] == ["género poco claro"]
    ficha = importar.confirmar("libros/a.epub", tmp_path)
    assert ficha["revisar"] is False and [x["titulo"] for x in importar.por_revisar(tmp_path)] == ["Libro B"]
    assert (tmp_path / "biblioteca" / "correcciones.json").exists()               # confirmar = corrección tuya: lo parecido se clasificará igual


def test_editar_cuenta_como_revisado(tmp_path):
    _biblioteca(tmp_path)
    importar.editar("libros/b.epub", {"genero": "politica"}, tmp_path, db=tmp_path / "i.db")
    assert importar.por_revisar(tmp_path) != [] and all(x["titulo"] != "Libro B" for x in importar.por_revisar(tmp_path))


def test_umbrales_por_defecto_son_positivos():
    assert clasificador.MARGEN_REVISAR > 0 and clasificador.MARGEN_SUB_REVISAR > 0


def test_si_el_parecido_dudaba_y_el_llm_decidio_no_hay_aviso_de_discrepancia():
    p = {"puntos": {"novela": 0.9, "historia": 0.1}, "confianza": 0.8, "genero": "novela"}
    dudoso = {"id": "fantasia", "puntos": {"fantasia": 1.0, "negra": 0.99}, "confianza": 0.01, "nombre": "Fantasía"}
    assert not any("LLM y el parecido" in m for m in importar._seguridad({"novela": 30}, p, None, "novela", dudoso, "negra", "x" * 500, "libro", False)[2])
