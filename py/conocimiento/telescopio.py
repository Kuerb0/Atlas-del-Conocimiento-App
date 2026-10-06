"""Telescopio: busca obras de acceso abierto o dominio público, las trae a la biblioteca y las clasifica con los metadatos reales (materias).

Fuentes (solo legales): Project Gutenberg (Gutendex), arXiv, OpenAlex (artículos en abierto con PDF) e Internet Archive
(solo obras con licencia abierta o publicadas hasta 1929). Open Library aporta las materias para clasificar un título.
Solo lectura de la web con la biblioteca estándar; lo descargado pasa por `importar.importar` como cualquier otro archivo.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from . import CARPETA, _norm
from .importar import _GEN_RE, GENEROS, importar

AGENTE = "ArbolEstadistica/1.0 (biblioteca personal; telescopio)"
MAX_BYTES = 200 << 20                       # no se descarga nada de más de 200 MB
FUENTES = ("gutenberg", "arxiv", "openalex", "archive")
_ATOM = "{http://www.w3.org/2005/Atom}"


def _get(url: str, binario: bool = False, limite: int = MAX_BYTES):
    """GET por https con tope de tamaño. Es el único punto de red (los tests lo sustituyen)."""
    if not url.startswith("https://"):
        raise ValueError(f"solo https: {url[:60]}")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}), timeout=30) as r:
        datos = r.read(limite + 1)
    if len(datos) > limite:
        raise ValueError(f"más de {limite >> 20} MB: no se descarga")
    return datos if binario else datos.decode("utf-8", "replace")


def _q(**kw) -> str:
    return urllib.parse.urlencode(kw)


def genero_desde_materias(materias: list[str]) -> str:
    """Género (clave de GENEROS) que mejor casa con las materias de la obra; 'otro' si ninguna puntúa."""
    t = " " + _norm(" ; ".join(materias)) + " "
    p = {g: len(r.findall(t)) for g, r in _GEN_RE.items()}
    g = max(p, key=p.get)
    return g if p[g] else "otro"


def _item(fuente, id_, titulo, autores, anio, url, formato, licencia, materias, resumen=""):
    materias = [m for m in dict.fromkeys(materias) if m][:12]
    return {"fuente": fuente, "id": str(id_), "titulo": re.sub(r"\s+", " ", titulo or "").strip(), "autores": [a for a in autores if a][:4], "anio": anio, "url": url,
            "formato": formato, "licencia": licencia, "materias": materias, "genero": genero_desde_materias(materias + [titulo or ""]), "resumen": resumen[:300]}


def _gutenberg(q, n):
    for b in json.loads(_get("https://gutendex.com/books?" + _q(search=q)))["results"][:n]:
        f = b.get("formats", {})
        url = next((f[k] for k in f if k.startswith("application/epub+zip")), None)
        if url and not b.get("copyright"):
            yield _item("gutenberg", b["id"], b["title"], [a["name"] for a in b.get("authors", [])], None, url, "epub", "Dominio público", b.get("subjects", []) + b.get("bookshelves", []))


def _arxiv(q, n):
    raiz = ET.fromstring(_get("https://export.arxiv.org/api/query?" + _q(search_query="all:" + q, max_results=n)))
    for e in raiz.findall(_ATOM + "entry"):
        pdf = next((l.get("href") for l in e.findall(_ATOM + "link") if l.get("title") == "pdf"), None)
        if pdf:
            yield _item("arxiv", e.findtext(_ATOM + "id", ""), e.findtext(_ATOM + "title", ""), [a.findtext(_ATOM + "name") for a in e.findall(_ATOM + "author")],
                        int((e.findtext(_ATOM + "published") or "0")[:4]) or None, pdf.replace("http://", "https://"), "pdf", "arXiv (descarga personal)",
                        [c.get("term") for c in e.findall(_ATOM + "category")], e.findtext(_ATOM + "summary", ""))


def _openalex(q, n):
    r = json.loads(_get("https://api.openalex.org/works?" + _q(search=q, filter="open_access.is_oa:true", **{"per-page": n * 2})))
    for w in r["results"]:
        loc = w.get("best_oa_location") or {}
        if loc.get("pdf_url"):
            yield _item("openalex", w["id"], w.get("display_name"), [a["author"]["display_name"] for a in w.get("authorships", [])], w.get("publication_year"), loc["pdf_url"], "pdf",
                        loc.get("license") or "acceso abierto", [c["display_name"] for c in w.get("concepts", [])][:8])


def _archive(q, n):
    r = json.loads(_get("https://archive.org/advancedsearch.php?" + _q(q=f"({q}) AND mediatype:texts AND NOT access-restricted-item:true", fl="identifier,title,creator,year,subject,licenseurl", rows=n * 3, output="json")))
    for d in r["response"]["docs"]:
        anio = int(str(d.get("year") or 0)[:4] or 0)
        lic = str(d.get("licenseurl") or "")
        if re.search(r"creativecommons|publicdomain", lic) or 0 < anio <= 1929:     # licencia abierta (CC / dominio público) o publicada hasta 1929
            sub = d.get("subject", [])
            yield _item("archive", d["identifier"], d.get("title", ""), [d["creator"]] if isinstance(d.get("creator"), str) else d.get("creator", []), anio or None, "", "pdf",
                        lic or "Dominio público (≤ 1929)", [sub] if isinstance(sub, str) else sub)


_BUSCADORES = {"gutenberg": _gutenberg, "arxiv": _arxiv, "openalex": _openalex, "archive": _archive}


def buscar(consulta: str, n: int = 6, fuentes=FUENTES) -> dict:
    """{'resultados': [item…], 'errores': {fuente: motivo}}: n por fuente; una fuente caída no impide las demás."""
    res, err = [], {}
    for f in fuentes:
        try:
            res += list(_BUSCADORES[f](consulta, n))[:n]
        except Exception as e:
            err[f] = f"{type(e).__name__}: {e}"
    return {"resultados": res, "errores": err}


def materias_de(titulo: str, autor: str = "") -> list[str]:
    """Materias de un título según Open Library (para clasificar algo que ya tienes). [] si no lo encuentra."""
    r = json.loads(_get("https://openlibrary.org/search.json?" + _q(title=titulo, author=autor, limit=3, fields="title,subject")))
    return [s for d in r.get("docs", [])[:3] for s in d.get("subject", [])[:15]]


def _url_archive(identificador: str) -> str:
    """Archivo PDF/EPUB abierto de una obra de Internet Archive."""
    files = json.loads(_get(f"https://archive.org/metadata/{urllib.parse.quote(identificador)}"))["files"]
    for ext in ("epub", "pdf"):
        for f in files:
            if f["name"].lower().endswith("." + ext) and "ncrypted" not in f.get("format", ""):      # fuera los PDF cifrados (préstamo)
                return f"https://archive.org/download/{urllib.parse.quote(identificador)}/{urllib.parse.quote(f['name'])}"
    raise ValueError("la obra no tiene PDF ni EPUB descargable")


def traer(item: dict, carpeta: Path = CARPETA) -> dict:
    """Descarga la obra, comprueba que es un PDF/EPUB de verdad y la importa clasificada con el género de sus materias. Devuelve el resultado de importar()."""
    url = item["url"] or _url_archive(item["id"])
    datos = _get(url, binario=True)
    ext = "pdf" if datos[:5] == b"%PDF-" else "epub" if datos[:2] == b"PK" else ""
    if not ext:
        raise ValueError("lo descargado no es un PDF ni un EPUB")
    tmp = Path(carpeta) / "telescopio"
    tmp.mkdir(parents=True, exist_ok=True)
    f = tmp / (re.sub(r"[^A-Za-z0-9._-]+", "_", f"{item['fuente']}_{item['id'].rsplit('/', 1)[-1]}")[:60] + "." + ext)
    f.write_bytes(datos)
    gen = item.get("genero") if item.get("genero") in GENEROS else None
    r = importar([{"ruta": f, "titulo": item["titulo"][:80], "genero": gen, "tipo": "articulo" if item["fuente"] in ("arxiv", "openalex") else "libro",
                   "etiquetas": ", ".join(item.get("materias", [])[:6] + [item["fuente"]])}], Path(carpeta))[0]
    f.unlink(missing_ok=True)                                              # la copia buena ya está en biblioteca/
    return r
