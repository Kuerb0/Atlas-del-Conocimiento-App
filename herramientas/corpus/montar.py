"""Corpus de pruebas del clasificador. Orden:
1) python herramientas/corpus/libros_gutenberg.py CARPETA   (necesita CARPETA/pg_catalog.csv: https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv; baja EPUB en/es con la etiqueta de su estantería oficial)
2) python herramientas/corpus/articulos_arxiv.py CARPETA [N]  (artículos de arXiv con el género de su categoría)
3) python herramientas/corpus/codigo_y_datos.py CARPETA        (código y datos de los paquetes instalados, etiquetados por paquete)
4) python herramientas/corpus/montar.py CARPETA               (junta todo en CARPETA/enes/corpus con las etiquetas buenas; luego herramientas/evaluar_corpus.py)
Todo de fuentes legales (dominio público, acceso abierto, licencias BSD/PSF). El corpus no se publica: pesa GB.
"""

import json, re, shutil, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "py")); sys.stdout.reconfigure(encoding="utf-8")
from conocimiento import importar, clasificador, llm
clasificador.WEB = False; llm.ACTIVO = False; clasificador.ACTIVO = False
D = pathlib.Path(sys.argv[1]); (D / "enes").mkdir(exist_ok=True); C = D / "enes" / "corpus"; ST = D / "staging"; ST.mkdir(exist_ok=True)
if not C.exists():
    shutil.copytree(importar.carpeta_datos() / "biblioteca", C / "biblioteca")        # tu biblioteca real entra como ejemplos (y como objetivo de la medición)
seg = lambda s: re.sub(r'[^\w ,.()-]+', ' ', s)[:70].strip()
items = []
libros = [b for n in ("libros_etiquetas.json", "libros2_etiquetas.json") if (D / n).exists() for b in json.loads((D / n).read_text(encoding="utf-8"))]
libros = [b for b in libros if b.get("idioma", "en") in ("en", "es")]
print(len(libros), "libros en inglés y español")
for b in libros:
    f = ST / f"{seg(b['titulo'])} - {seg(b['autor'])}.epub"
    if not f.exists(): shutil.copy(D / "raw" / f"{b['id']}.epub", f)
    items.append({"ruta": f, "galaxia": "libros", "genero": b["genero"], "subgenero": b["subgenero"], "titulo": b["titulo"][:80]})
if (D / "arxiv_etiquetas.json").exists():
    for b in json.loads((D / "arxiv_etiquetas.json").read_text(encoding="utf-8")):
        f = ST / f"{seg(b['titulo'])} - {seg(b['autor'])}.pdf"
        if not f.exists(): shutil.copy(D / "raw_arxiv" / b["archivo"], f)
        items.append({"ruta": f, "genero": b["genero"], "subgenero": b["subgenero"], "titulo": b["titulo"][:80], "tipo": "articulo", "galaxia": "notas"})
if (D / "codigo_etiquetas.json").exists():
    for b in json.loads((D / "codigo_etiquetas.json").read_text(encoding="utf-8")):
        items.append({"ruta": D / "raw_codigo" / b["archivo"], "genero": b["genero"], "tipo": b["tipo"], "galaxia": "codigo" if b["tipo"] == "codigo" else "notas", "titulo": b["archivo"][:70]})
out = importar.importar(items, C, indexar_ahora=False)
from collections import Counter
print(Counter(o["estado"] for o in out), [o["mensaje"][:80] for o in out if o["estado"] == "error"][:5])
print(len(importar.leer_metadatos(C)), "obras en el corpus")
