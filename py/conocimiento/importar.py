"""Importador: copia ficheros a `conocimiento/biblioteca/<galaxia>/<subtema>/`, los clasifica (galaxia, subtema, tipo) y los indexa para el buscador.

Por defecto lo decide solo (`clasificar`); cualquier dato que pases (galaxia, subtema, tipo, etiquetas) manda sobre lo automático.
Galaxia automática: finanzas si domina el vocabulario financiero; si no, libros (PDF/EPUB largos) o notas. Subtema automático: el tema del catálogo de conceptos
(«Inferencia y contrastes», «Regresión y GLM»…) con más coincidencias. Los metadatos van en `biblioteca/metadatos.json` (ruta relativa -> datos).

Uso: `python -m conocimiento importar f1.pdf f2.docx [-g libros] [-s "Inferencia y contrastes"] [-t libro]`.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

from . import CARPETA, DB, EXT, RAIZ, _extraer, _norm, indexar

GALAXIAS = {"codigo": "Código", "conceptos": "Conceptos", "demos": "Demos y guías", "finanzas": "Finanzas", "libros": "Libros", "notas": "Notas y enlaces"}
TIPOS = {"libro": "Libro", "articulo": "Artículo", "apuntes": "Apuntes", "nota": "Nota", "otro": "Otro"}
FINANZAS = re.compile(r"\b(bonos?|carteras?|rentabilidad|volatilidad|derivados?|opcion(?:es)?|futuros?|tipos? de interes|capm|markowitz|renta fija|renta variable|tesoreria|"
                      r"solvencia|var|valoracion|acciones|mercados?|activos?|pasivos?|riesgo de credito|fiscalidad|impuestos?|bancari[oa]s?|swaps?|duracion|rating)\b")


def _catalogo() -> dict:
    return json.loads((RAIZ / "conceptos" / "catalogo.json").read_text(encoding="utf-8"))


def _temas_con_frases() -> list[tuple[str, str, list[str]]]:
    """[(id_tema, nombre_tema, frases normalizadas)] con el nombre y los sinónimos de cada concepto."""
    cat = _catalogo()
    area_tema = {a["id"]: a["tema"] for a in cat["areas"]}
    frases: dict[str, set] = {}
    for c in cat["conceptos"]:
        tema = area_tema.get(c.get("area"))
        if tema:
            frases.setdefault(tema, set()).update(f for f in (_norm(x) for x in [c["nombre"], *c.get("sinonimos", [])]) if len(f) >= 5)
    return [(t["id"], t["nombre"], sorted(frases.get(t["id"], []))) for t in cat["temas"]]


def opciones() -> dict:
    """Lo que ofrecen los desplegables: galaxias, tipos y subtemas (los temas del catálogo, las ramas de código y 'General')."""
    ramas = sorted(p.name for p in (RAIZ / "py" / "arbol_estadistica").iterdir() if p.is_dir() and not p.name.startswith("_")) if (RAIZ / "py" / "arbol_estadistica").is_dir() else []
    temas = [t["nombre"] for t in _catalogo()["temas"]]
    return {"galaxias": [{"id": k, "nombre": v} for k, v in GALAXIAS.items()], "tipos": [{"id": k, "nombre": v} for k, v in TIPOS.items()],
            "subtemas": {"codigo": ramas + ["General"], "conceptos": temas + ["General"], "demos": ["Demos", "Guías", "General"],
                         "finanzas": ["Carteras y riesgo", "Renta fija", "Derivados", "Actuarial y seguros", "General"] + [t for t in temas if "inanz" in t],
                         "libros": temas + ["General"], "notas": temas + ["General"]}}


def _muestra(f: Path, max_pag: int = 12) -> tuple[str, int]:
    """(texto del principio, nº de páginas o 0). Para un PDF solo lee las primeras páginas."""
    if f.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            r = PdfReader(str(f))
            return "\n".join((p.extract_text() or "") for p in r.pages[:max_pag]), len(r.pages)
        except Exception:
            return "", 0
    try:
        trozos = _extraer("importar", f) or []
    except Exception:
        return "", 0
    return "\n".join(x for _, x, _ in trozos[:30])[:30000], 0


def clasificar(ruta: str | Path) -> dict:
    """Propone galaxia, subtema, tipo y título de un fichero, con el motivo. {'galaxia','subtema','tipo','titulo','motivo','paginas'}"""
    f = Path(ruta)
    texto, paginas = _muestra(f)
    t = " " + _norm(texto[:40000]) + " "
    nombre = _norm(re.sub(r"[_\-.]+", " ", f.stem))
    puntos = {}
    for tid, tnombre, frases in _temas_con_frases():
        p = sum(t.count(fr) for fr in frases) + 4 * sum(1 for fr in frases if fr in nombre)
        if p:
            puntos[(tid, tnombre)] = p
    (tid, tnombre), p = max(puntos.items(), key=lambda kv: kv[1]) if puntos else ((None, "General"), 0)
    fin = len(FINANZAS.findall(t)) + 4 * len(FINANZAS.findall(nombre))
    ext = f.suffix.lower()
    if ext == ".epub" or (ext == ".pdf" and paginas >= 60):
        tipo = "libro"
    elif ext == ".pdf":
        tipo = "articulo"
    elif ext in (".docx", ".md"):
        tipo = "apuntes"
    else:
        tipo = "nota"
    if fin >= 8 or tid == "t_fin" and p >= 3:
        galaxia, motivo = "finanzas", f"vocabulario financiero ({fin} términos)"
    elif tipo == "libro":
        galaxia, motivo = "libros", f"{'EPUB' if ext == '.epub' else str(paginas) + ' páginas'}"
    else:
        galaxia, motivo = "notas", "documento corto o de apuntes"
    subtema = tnombre if p >= 3 else "General"
    if subtema != "General":
        motivo += f"; el tema «{subtema}» sale {p} veces"
    return {"galaxia": galaxia, "subtema": subtema, "tipo": tipo, "titulo": re.sub(r"\s+", " ", re.sub(r"[_]+", " ", f.stem)).strip(), "motivo": motivo, "paginas": paginas}


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")[:60] or "General"


def _sha1(f: Path) -> str:
    h = hashlib.sha1()
    with open(f, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def leer_metadatos(carpeta: Path = CARPETA) -> dict:
    f = Path(carpeta) / "biblioteca" / "metadatos.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def resumen(carpeta: Path = CARPETA) -> dict:
    """{galaxia: nº de documentos importados}."""
    r: dict = {}
    for m in leer_metadatos(carpeta).values():
        r[m["galaxia"]] = r.get(m["galaxia"], 0) + 1
    return r


def importar(items: list, carpeta: Path = CARPETA, db: Path | None = None, indexar_ahora: bool = True) -> list[dict]:
    """Importa ficheros. Cada item es una ruta o un dict {ruta, galaxia?, subtema?, tipo?, etiquetas?}; lo que falte se clasifica solo.
    Devuelve por fichero {ruta, estado: 'ok'|'duplicado'|'error', galaxia, subtema, tipo, destino, mensaje}."""
    carpeta = Path(carpeta)
    base = carpeta / "biblioteca"
    meta = leer_metadatos(carpeta)
    hashes = {m["hash"]: rel for rel, m in meta.items()}
    salida = []
    for it in items:
        d = {"ruta": it} if isinstance(it, (str, Path)) else dict(it)
        f = Path(d["ruta"])
        r = {"ruta": str(f), "nombre": f.name}
        try:
            if not f.is_file():
                raise ValueError("no existe el fichero")
            if f.suffix.lower() not in EXT:
                raise ValueError(f"formato no admitido ({f.suffix or 'sin extensión'}); sirven {', '.join(sorted(EXT))}")
            h = _sha1(f)
            if h in hashes:
                salida.append({**r, "estado": "duplicado", "mensaje": f"ya estaba importado ({hashes[h]})"})
                continue
            auto = clasificar(f)
            galaxia = d.get("galaxia") if d.get("galaxia") in GALAXIAS else auto["galaxia"]
            subtema = (d.get("subtema") or "").strip() or auto["subtema"]
            tipo = d.get("tipo") if d.get("tipo") in TIPOS else auto["tipo"]
            destino = base / galaxia / _slug(subtema)
            destino.mkdir(parents=True, exist_ok=True)
            fin, n = destino / f.name, 1
            while fin.exists():
                n += 1; fin = destino / f"{f.stem}_{n}{f.suffix}"
            shutil.copy2(f, fin)
            rel = fin.relative_to(base).as_posix()
            meta[rel] = {"titulo": auto["titulo"], "galaxia": galaxia, "subtema": subtema, "tipo": tipo, "etiquetas": (d.get("etiquetas") or "").strip(), "origen": str(f), "hash": h,
                         "fecha": datetime.now().isoformat(timespec="seconds"), "automatico": not (d.get("galaxia") or d.get("subtema") or d.get("tipo"))}
            hashes[h] = rel
            salida.append({**r, "estado": "ok", "galaxia": galaxia, "subtema": subtema, "tipo": tipo, "destino": str(fin), "mensaje": auto["motivo"]})
        except Exception as e:
            salida.append({**r, "estado": "error", "mensaje": str(e)})
    if any(s["estado"] == "ok" for s in salida):
        base.mkdir(parents=True, exist_ok=True)
        (base / "metadatos.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        if indexar_ahora:
            ind = indexar(db or carpeta / "indice.db", {}, carpeta=carpeta)
            sin = set(ind["sin_leer"])
            for s in salida:
                if s["estado"] == "ok" and s["destino"] in sin:
                    s["mensaje"] += " · sin indexar (¿falta `pip install pypdf`?)"
    return salida
