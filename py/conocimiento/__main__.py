"""CLI del gestor de conocimiento: python -m conocimiento indexar | buscar <consulta> [-c colección] [-n 10] | estado"""
import argparse
import sys

from . import CARPETA, buscar, estado, indexar

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ap = argparse.ArgumentParser(prog="conocimiento")
sub = ap.add_subparsers(dest="orden", required=True)
sub.add_parser("indexar", help="indexa lo nuevo o modificado")
sub.add_parser("estado", help="qué hay indexado")
i = sub.add_parser("importar", help="copia ficheros al observatorio, los clasifica y los indexa")
i.add_argument("ficheros", nargs="+")
i.add_argument("-g", "--galaxia", help="codigo | conceptos | demos | finanzas | libros | notas (por defecto, automática)")
i.add_argument("-s", "--subtema", help="p. ej. «Inferencia y contrastes» (por defecto, automático)")
i.add_argument("-t", "--tipo", help="libro | articulo | apuntes | nota | otro (por defecto, automático)")
i.add_argument("-G", "--genero", help="historia | economia | ensayo | estadistica | ciencia | novela | biografia | politica | tecnologia | psicologia | arte | otro (por defecto, automático)")
t = sub.add_parser("telescopio", help="busca obras de acceso abierto (Gutenberg, arXiv, OpenAlex, Internet Archive); con --traer N descarga e importa la N-ésima")
t.add_argument("consulta", nargs="+")
t.add_argument("--traer", type=int, metavar="N", help="trae a la biblioteca el resultado número N")
b = sub.add_parser("buscar", help="busca en todas las colecciones")
b.add_argument("consulta", nargs="+")
b.add_argument("-c", "--coleccion", help="codigo | conceptos | teoria | libros | finanzas | notas …")
b.add_argument("-n", type=int, default=10)
a = ap.parse_args()

if a.orden == "indexar":
    r = indexar()
    print(f"{r['nuevos']} ficheros indexados, {r['iguales']} sin cambios, {r['borrados']} borrados")
    if r["sin_leer"]:
        print(f"{len(r['sin_leer'])} sin leer (¿falta `pip install pypdf`?), p. ej. {r['sin_leer'][0]}")
elif a.orden == "estado":
    for col, nf, nt in estado():
        print(f"{col:12} {nf:5} ficheros {nt:8} trozos")
    print(f"fuentes propias: {CARPETA / 'fuentes.json'}")
elif a.orden == "importar":
    from .importar import importar
    for r in importar([{"ruta": f, "galaxia": a.galaxia, "subtema": a.subtema, "tipo": a.tipo, "genero": a.genero} for f in a.ficheros]):
        print(f"{r['estado']:10} {r['nombre']}  ->  {r.get('galaxia', '')} › {r.get('subtema', '')} ({r.get('tipo', '')})  {r['mensaje']}")
elif a.orden == "telescopio":
    from . import telescopio
    r = telescopio.buscar(" ".join(a.consulta))
    for i, x in enumerate(r["resultados"], 1):
        print(f"{i:2}. [{x['fuente']}] {x['titulo'][:80]} — {', '.join(x['autores'][:2])} ({x['anio'] or '?'}) · {x['formato']} · {x['licencia']} · género: {x['genero']}")
    for f, e in r["errores"].items():
        print(f"   ✗ {f}: {e}")
    if a.traer:
        print(telescopio.traer(r["resultados"][a.traer - 1]))
else:
    for i, x in enumerate(buscar(" ".join(a.consulta), a.coleccion, a.n), 1):
        print(f"{i:2}. [{x['coleccion']}] {x['titulo']}  {x['ubicacion']}\n    {x['fragmento'].replace(chr(10), ' ')}")
