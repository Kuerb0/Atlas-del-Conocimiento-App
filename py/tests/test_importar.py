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


def test_titulo_corto_recorta_los_nombres_largos():
    largo = "3. Regression Modeling Strategies_ With Applications to Linear -- Frank Harrell -- 2015 -- Springer -- isbn13 9783319194257 -- 43944f86 -- Anna’s Archive.pdf"
    assert imp.titulo_corto(largo) == "Regression Modeling Strategies: With Applications to Linear"
    assert len(imp.titulo_corto("palabra " * 40)) <= 61 and imp.titulo_corto("palabra " * 40).endswith("…")
    assert imp.titulo_corto("nota.txt") == "nota"


def test_clasifica_genero_y_da_detalle(tmp_path):
    f = tmp_path / "The_Roman_Empire_-_a_history.txt"
    f.write_text("The history of the Roman empire: the war, the republic and the dynasty of the ancient world. " * 20, encoding="utf-8")
    c = imp.clasificar(f)
    assert c["genero"] == "historia" and c["titulo"] == "The Roman Empire - a history" and c["extension"] == "txt" and c["idioma"] == "en"
    assert c["generos"][0]["id"] == "historia" and "vista_previa" in c and c["tamano"] > 0 and c["capitulos"]


def test_el_importado_aparece_en_el_visor_por_genero_libro_y_capitulo(tmp_path, monkeypatch):
    import construir_visor as cv
    bib = tmp_path / "biblioteca"
    bib.mkdir()
    (bib / "metadatos.json").write_text(json.dumps({
        "libros/General/roma.epub": {"titulo": "The Romans", "galaxia": "libros", "subtema": "General", "genero": "historia", "tipo": "libro", "paginas": 0, "hash": "a",
                                     "capitulos": [{"titulo": "Cover", "pagina": None}, {"titulo": "The Republic", "pagina": 12}], "fecha": "2026-10-06T10:00:00"},
        "notas/General/apunte.md": {"titulo": "Apunte", "galaxia": "notas", "subtema": "Inferencia y contrastes", "genero": "otro", "tipo": "apuntes", "hash": "b", "capitulos": []}}), encoding="utf-8")
    monkeypatch.setenv("ARBOL_CONOCIMIENTO", str(tmp_path))
    ramas = {r["id"]: r for r in cv.construir()["ramas"]}
    g = ramas["gen_historia"]
    assert g["galaxia"] == "libros" and g["biblioteca"] and g["modulos"][0]["nombre"] == "The Romans"
    assert [i["nombre"] for i in g["modulos"][0]["items"]] == ["Cover", "The Republic"] and g["modulos"][0]["items"][1]["pagina"] == 12
    assert {i["tipo"] for i in g["modulos"][0]["items"]} == {"capitulo"}
    nota = next(r for r in ramas.values() if r.get("galaxia") == "notas")
    assert nota["nombre"] == "Inferencia y contrastes" and nota["modulos"][0]["items"][0]["tipo"] == "documento"


def test_conceptos_con_video():
    import construir_visor as cv
    assert cv.es_video({"tipo": "very_normal", "url": "https://www.youtube.com/watch?v=x"}) and cv.es_video({"tipo": "curso", "url": "https://www.3blue1brown.com/?topic=probability"})
    assert not cv.es_video({"tipo": "manual", "url": "https://www.openintro.org/book/os/"}) and not cv.es_video({"tipo": "master", "ref": "x"})
    conceptos = [i for r in cv.construir()["ramas"] for m in r["modulos"] for i in m["items"] if i["tipo"] == "concepto"]
    assert any(c["videos"] for c in conceptos) and all(v["url"] for c in conceptos for v in c["videos"])


def test_el_visor_tiene_el_desplegable_y_las_tarjetas_del_importador():
    import construir_visor as cv
    html = cv.ensamblar(cv.construir())
    for pieza in ("imp-ayuda", "¿Cómo funciona la importación?", "impTarjeta", "detalleDocumento", "actualizar_visor", "esVideo"):
        assert pieza in html


def test_solo_se_asignan_temas_de_estadistica_a_lo_que_lo_es(tmp_path):
    historia = tmp_path / "Rise_of_Empire_a_history.txt"
    historia.write_text("The history of the empire: the war, the republic, the dynasty. The generals tested every model of validation and cross-validation of their armies' prediction. " * 12, encoding="utf-8")
    c = imp.clasificar(historia)
    assert c["genero"] == "historia" and c["subtema"] == "General" and c["temas"] == []          # un libro de historia no recibe un tema de estadística
    estad = tmp_path / "Regression_Modeling.txt"
    estad.write_text("Linear regression, logistic regression, residuals, least squares and generalized linear models with covariates and predictors. " * 15, encoding="utf-8")
    e = imp.clasificar(estad)
    assert e["genero"] == "estadistica" and e["subtema"] == "Regresión y GLM"


def test_importar_desde_la_interfaz_sigue_siendo_automatico_y_los_libros_van_por_genero(tmp_path):
    f = tmp_path / "libro_de_roma.epub"
    import zipfile
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("OEBPS/c1.xhtml", "<html><body><h1>The Republic</h1><p>" + "The history of the Roman empire and its wars. " * 80 + "</p></body></html>")
    auto = imp.clasificar(f)
    r = imp.importar([{"ruta": f, "titulo": auto["titulo"]}], carpeta=tmp_path / "datos", db=tmp_path / "datos" / "i.db")[0]      # la interfaz siempre manda el título
    assert r["estado"] == "ok" and r["galaxia"] == "libros" and r["genero"] == "historia" and "Historia" in r["destino"]
    assert imp.leer_metadatos(tmp_path / "datos")[next(iter(imp.leer_metadatos(tmp_path / "datos")))]["automatico"] is True


def test_el_visor_no_tiene_los_filtros_de_arriba_y_el_libro_muestra_sus_capitulos_al_pulsarlo():
    import construir_visor as cv
    html = cv.ensamblar(cv.construir())
    assert 'id="chips"' not in html and 'class="filtros"' not in html and 'id="soloSas"' not in html
    assert "detalleLibro" in html and "esLibro" in html and "n.tipo === 'capitulo'" in html     # capítulos ocultos hasta enfocar el libro (mapa3d.js)


def _epub_con_portada(ruta):
    import io
    import zipfile
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (300, 440), (200, 30, 40)).save(buf, "JPEG")
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("OEBPS/content.opf", '<package><metadata><meta name="cover" content="cov"/></metadata><manifest><item id="cov" href="img/tapa.jpg" media-type="image/jpeg"/></manifest></package>')
        z.writestr("OEBPS/img/tapa.jpg", buf.getvalue())
        z.writestr("OEBPS/c1.xhtml", "<html><body><h1>Uno</h1><p>" + "history of the empire " * 60 + "</p></body></html>")


def test_portadas_la_del_epub_si_la_tiene_y_una_generada_si_no(tmp_path):
    from PIL import Image
    e = tmp_path / "con_portada.epub"
    _epub_con_portada(e)
    assert imp.portada(e, tmp_path / "p" / "a.jpg", "Con portada", "historia")
    px = Image.open(tmp_path / "p" / "a.jpg").convert("RGB").getpixel((50, 50))
    assert px[0] > 150 and px[1] < 90                               # la imagen rojiza del propio EPUB, no una generada
    t = tmp_path / "apunte.txt"
    t.write_text("nada", encoding="utf-8")
    assert imp.portada(t, tmp_path / "p" / "b.jpg", "Apunte sin portada propia", "estadistica") and Image.open(tmp_path / "p" / "b.jpg").size == (120, 170)


def test_la_portada_viaja_con_la_importacion_y_con_la_busqueda_y_el_visor(tmp_path, monkeypatch):
    import construir_visor as cv
    e = tmp_path / "roma.epub"
    _epub_con_portada(e)
    carpeta = tmp_path / "datos"
    r = imp.importar([e], carpeta=carpeta, db=carpeta / "i.db")[0]
    meta = next(iter(imp.leer_metadatos(carpeta).values()))
    assert r["estado"] == "ok" and meta["portada"].startswith("portadas/") and (carpeta / "biblioteca" / meta["portada"]).is_file()
    assert k.buscar("empire", db=carpeta / "i.db")[0]["portada"].startswith("data:image/jpeg;base64,")
    monkeypatch.setenv("ARBOL_CONOCIMIENTO", str(carpeta))
    d = cv.construir()
    assert d["portadas"][meta["portada"]].startswith("data:image/jpeg") and any(i.get("portada") == meta["portada"] for r_ in d["ramas"] for m in r_["modulos"] for i in m["items"])


def test_el_visor_tiene_iconos_en_el_buscador_y_animaciones_al_buscar():
    import construir_visor as cv
    html = cv.ensamblar(cv.construir())
    for pieza in ("iconoNodo", "iconoRes", "SVG_PY", 'class="ico-t sig"', "enfocar: function", "cerebro.enfocar(", "flex:1 1 480px"):
        assert pieza in html


def _nota(tmp_path, nombre, texto):
    f = tmp_path / nombre
    f.write_text(texto, encoding="utf-8")
    return f


def test_biblioteca_editar_cambia_la_galaxia_en_el_indice_y_recuerda_la_correccion(tmp_path):
    c, db = tmp_path / "datos", tmp_path / "datos" / "i.db"
    f = _nota(tmp_path, "Ancient_Rome_Collapse_Empire.txt", "history of the roman empire and its wars. " * 40)
    r = imp.importar([f], carpeta=c, db=db)[0]
    rel = next(iter(imp.leer_metadatos(c)))
    ficha = imp.editar(rel, {"galaxia": "finanzas", "genero": "economia", "subtema": "Historia económica", "titulo": "Roma y su economía"}, carpeta=c, db=db)
    assert ficha["galaxia"] == "finanzas" and ficha["genero"] == "economia" and ficha["titulo"] == "Roma y su economía" and ficha["automatico"] is False
    assert k.buscar("roman empire", coleccion="finanzas", db=db) and not k.buscar("roman empire", coleccion=r["galaxia"], db=db)    # el índice sigue a la galaxia
    assert k.buscar("roman empire", genero="economia", db=db) and not k.buscar("roman empire", genero="historia", db=db)         # y el filtro por género
    g = _nota(tmp_path, "Ancient_Rome_Collapse_Empire_segunda_parte.txt", "otra cosa distinta " * 40)
    assert imp.clasificar(g, c)["genero"] == "economia" and "corregiste" in imp.clasificar(g, c)["motivo"]                              # algo parecido se clasifica como corregiste
    try:
        imp.editar(rel, {"galaxia": "marte"}, carpeta=c, db=db); assert False
    except ValueError:
        pass


def test_biblioteca_borrar_quita_la_copia_pero_no_el_original(tmp_path):
    c, db = tmp_path / "datos", tmp_path / "datos" / "i.db"
    f = _nota(tmp_path, "apunte_borrable.txt", "texto sobre el unicornio morado " * 30)
    imp.importar([f], carpeta=c, db=db)
    rel = next(iter(imp.leer_metadatos(c)))
    copia = c / "biblioteca" / rel
    assert copia.is_file() and k.buscar("unicornio", db=db) and imp.listar(c)[0]["rel"] == rel
    assert imp.borrar(rel, carpeta=c, db=db) is True
    assert not copia.exists() and f.exists() and not imp.leer_metadatos(c) and not k.buscar("unicornio", db=db)
    assert imp.borrar(rel, carpeta=c, db=db) is False


def test_importar_mover_quita_el_original_y_avisa_del_progreso(tmp_path):
    c, db = tmp_path / "datos", tmp_path / "datos" / "i.db"
    f = _nota(tmp_path, "para_mover.txt", "contenido movible " * 30)
    g = _nota(tmp_path, "para_copiar.txt", "contenido copiable " * 30)
    avisos = []
    k.PROGRESO = lambda txt, fr: avisos.append((txt, fr))
    try:
        r = imp.importar([{"ruta": f, "modo": "mover"}, {"ruta": g}], carpeta=c, db=db)
    finally:
        k.PROGRESO = None
    assert r[0]["movido"] is True and not f.exists() and r[1]["movido"] is False and g.exists()
    assert any("Copiando" in a for a, _ in avisos) and any("Indexando" in a for a, _ in avisos)


def test_el_visor_tiene_biblioteca_ambitos_de_busqueda_y_progreso():
    import construir_visor as cv
    html = cv.ensamblar(cv.construir())
    for pieza in ('id="pestBiblioteca"', "bibTarjeta", "biblioteca_borrar", "parseAmbito", "mostrarAtajos", "Buscando en tu conocimiento", "estado_trabajo", 'id="gModo"'[:0] + "gModo", "li._accion"[:0] + "_accion"):
        assert pieza in html


def test_la_pestana_se_llama_observatorio():
    import construir_visor as cv
    html = cv.ensamblar(cv.construir())
    assert "🔭 Observatorio" in html and "<h2>Observatorio</h2>" in html and "📚 Biblioteca" not in html
