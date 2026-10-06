"""CLI del gestor de conocimiento: python -m conocimiento indexar | buscar <consulta> [-c colección] [-n 10] | estado"""
import argparse
import sys

from . import CARPETA, buscar, estado, indexar

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ap = argparse.ArgumentParser(prog="conocimiento")
sub = ap.add_subparsers(dest="orden", required=True)
sub.add_parser("indexar", help="indexa lo nuevo o modificado")
sub.add_parser("estado", help="qué hay indexado")
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
else:
    for i, x in enumerate(buscar(" ".join(a.consulta), a.coleccion, a.n), 1):
        print(f"{i:2}. [{x['coleccion']}] {x['titulo']}  {x['ubicacion']}\n    {x['fragmento'].replace(chr(10), ' ')}")
