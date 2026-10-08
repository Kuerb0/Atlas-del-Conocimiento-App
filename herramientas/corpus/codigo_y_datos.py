"""Corpus de pruebas del clasificador. Orden:
1) python herramientas/corpus/libros_gutenberg.py CARPETA   (necesita CARPETA/pg_catalog.csv: https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv; baja EPUB en/es con la etiqueta de su estantería oficial)
2) python herramientas/corpus/articulos_arxiv.py CARPETA [N]  (artículos de arXiv con el género de su categoría)
3) python herramientas/corpus/codigo_y_datos.py CARPETA        (código y datos de los paquetes instalados, etiquetados por paquete)
4) python herramientas/corpus/montar.py CARPETA               (junta todo en CARPETA/enes/corpus con las etiquetas buenas; luego herramientas/evaluar_corpus.py)
Todo de fuentes legales (dominio público, acceso abierto, licencias BSD/PSF). El corpus no se publica: pesa GB.
"""

import json, random, sys, sysconfig, shutil, pathlib
sys.stdout.reconfigure(encoding="utf-8")
D = pathlib.Path(sys.argv[1]); R = D / "raw_codigo"; R.mkdir(exist_ok=True)
sp = pathlib.Path(sysconfig.get_paths()["purelib"]); std = pathlib.Path(sysconfig.get_paths()["stdlib"])
random.seed(42); out = []
def tomar(carpeta, patron, n, genero, etiqueta, tipo="codigo", minimo=1500, maximo=200000):
    fs = [f for f in carpeta.rglob(patron) if f.is_file() and minimo < f.stat().st_size < maximo and "test" not in f.name.lower() and "__" not in f.name]
    random.shuffle(fs)
    for f in fs[:n]:
        destino = R / f"{etiqueta}_{f.parent.name}_{f.name}"
        shutil.copy(f, destino)
        out.append({"archivo": destino.name, "genero": genero, "tipo": tipo, "origen": etiqueta})
tomar(sp / "statsmodels", "*.py", 25, "estadistica", "statsmodels")
tomar(sp / "scipy" / "stats", "*.py", 15, "estadistica", "scipy_stats")
tomar(sp / "sklearn", "*.py", 20, "estadistica", "sklearn")
for paq, n in (("asyncio", 8), ("http", 6), ("email", 8), ("json", 3), ("sqlite3", 3), ("urllib", 4), ("logging", 3), ("xml", 6), ("unittest", 4)):
    tomar(std / paq, "*.py", n, "tecnologia", "stdlib")
tomar(sp / "sklearn" / "datasets" / "data", "*.csv", 12, "estadistica", "sklearn_datos", "datos", 500, 400000)
tomar(sp / "statsmodels" / "datasets", "*.csv", 14, "estadistica", "statsmodels_datos", "datos", 500, 400000)
(D / "codigo_etiquetas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
import collections; print(len(out), collections.Counter((o["tipo"], o["origen"]) for o in out))
