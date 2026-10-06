"""Almacenaje: cuánto ocupa cada galaxia y cada tipo de archivo frente al límite de GitHub (pestaña «Eclipses»).

Dos escenarios: «disco» (todo lo que hay en la carpeta) y «github» (lo que subiría un `git add`: respeta .gitignore).
GitHub: se recomienda no pasar de 1 GB por repositorio (tope duro ~5 GB) y rechaza archivos de más de 100 MB.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import RAIZ

LIMITE = 1 << 30            # 1 GB recomendado por repositorio
LIMITE_DURO = 5 << 30       # a partir de aquí GitHub puede bloquear el repo
LIMITE_ARCHIVO = 100 << 20  # GitHub rechaza archivos de más de 100 MB

GRUPOS = {"codigo": "Código", "conceptos": "Conceptos", "demos": "Demos y guías", "finanzas": "Finanzas", "libros": "Libros",
          "notas": "Notas y enlaces", "visor": "Visor generado", "instaladores": "Instaladores", "copias": "Copias anteriores", "otros": "Otros"}
_SALTAR = {".git", "__pycache__", ".pytest_cache"}


def grupo(rel: str) -> str:
    """Galaxia (o cubo) al que pertenece un archivo según su ruta relativa."""
    p = rel.replace("\\", "/").split("/")
    if p[0] == "conocimiento" and len(p) > 2 and p[1] == "biblioteca":
        return p[2] if p[2] in GRUPOS else "otros"
    if p[0] in ("conceptos", "teoria"):
        return "conceptos"
    if p[0] in ("ejemplos",) or p[:2] in (["py", "aprender"], ["py", "cuaderno"]) or rel.endswith("demos.js"):
        return "demos"
    if p[0] in ("py", "herramientas"):
        return "codigo"
    if p[0] == "instaladores":
        return "instaladores"
    if p[0] == "anteriores":
        return "copias"
    if p[0] == "visor_arbol.html":
        return "visor"
    return "otros"


def _lista_disco(raiz: Path):
    for d, ds, fs in os.walk(raiz):
        ds[:] = [x for x in ds if x not in _SALTAR]
        for f in fs:
            yield str((Path(d) / f).relative_to(raiz))


def _lista_github(raiz: Path):
    """Archivos que subiría git (versionados + nuevos no ignorados). Sin git: None."""
    try:
        r = subprocess.run(["git", "-C", str(raiz), "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True, timeout=60, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return [x.decode("utf-8", "replace") for x in r.stdout.split(b"\0") if x]


def _escenario(rels, raiz: Path) -> dict:
    por_g, por_t, grandes, total = {}, {}, [], 0
    for rel in rels:
        try:
            n = (raiz / rel).stat().st_size
        except OSError:
            continue
        total += n
        por_g[grupo(rel)] = por_g.get(grupo(rel), 0) + n
        t = (Path(rel).suffix.lower().lstrip(".") or "sin ext.")
        por_t[t] = por_t.get(t, 0) + n
        if n > LIMITE_ARCHIVO:
            grandes.append({"ruta": rel, "bytes": n})
    ordenar = lambda d, nombres=None: [{"id": k, "nombre": (nombres or {}).get(k, k), "bytes": v}
                                       for k, v in sorted(d.items(), key=lambda kv: -kv[1]) if v > 0]
    return {"total": total, "grupos": ordenar(por_g, GRUPOS), "tipos": ordenar(por_t), "grandes": grandes}


def medir(raiz: Path | str = RAIZ) -> dict:
    """{'limite','limite_duro','limite_archivo','disco':{…},'github':{…}|None}; cada escenario trae total, grupos, tipos y archivos de >100 MB."""
    raiz = Path(raiz)
    gh = _lista_github(raiz)
    return {"limite": LIMITE, "limite_duro": LIMITE_DURO, "limite_archivo": LIMITE_ARCHIVO,
            "disco": _escenario(_lista_disco(raiz), raiz), "github": _escenario(gh, raiz) if gh is not None else None}
