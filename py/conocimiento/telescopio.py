"""Telescopio: busca obras de acceso abierto o dominio público, las trae a la biblioteca y las clasifica con los metadatos reales (materias).

Fuentes (solo legales): Google Books y Open Library (catálogo: ficha y enlace; descarga solo si es dominio público o préstamo abierto), Project Gutenberg (catálogo OPDS), arXiv, OpenAlex (artículos en abierto con PDF) e Internet Archive
(solo obras con licencia abierta o publicadas hasta 1929). Open Library aporta las materias para clasificar un título.
Solo lectura de la web con la biblioteca estándar; lo descargado pasa por `importar.importar` como cualquier otro archivo.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import namedtuple
from pathlib import Path

from . import CARPETA, _norm
from .importar import _GEN_RE, GENEROS, importar

AGENTE = "ArbolEstadistica/1.0 (biblioteca personal; telescopio)"
MAX_BYTES = 200 << 20                       # no se descarga nada de más de 200 MB
FUENTES = ("googlebooks", "openlibrary", "gutenberg", "arxiv", "openalex", "archive")
_ATOM = "{http://www.w3.org/2005/Atom}"
LIBROS = ("googlebooks", "openlibrary", "gutenberg", "archive")
ARTICULOS = ("arxiv", "openalex")
Consulta = namedtuple("Consulta", "texto titulo autor")             # lo que se busca: palabras sueltas, título y autor (cualquiera puede ir vacío)


def _get(url: str, binario: bool = False, limite: int = MAX_BYTES):
    """GET por https con tope de tamaño. Es el único punto de red (los tests lo sustituyen)."""
    if not url.startswith("https://"):
        raise ValueError(f"solo https: {url[:60]}")
    for intento in (1, 2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}), timeout=20) as r:
                datos = r.read(limite + 1)
            break
        except urllib.error.HTTPError as e:
            if intento == 2 or e.code not in (500, 502, 503, 504):          # un fallo del servidor suele ser pasajero: se reintenta una vez
                raise
            time.sleep(1.5)
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


def _item(fuente, id_, titulo, autores, anio, url, formato, licencia, materias, resumen="", enlace=""):
    materias = [m for m in dict.fromkeys(materias) if m][:12]
    return {"fuente": fuente, "id": str(id_), "titulo": re.sub(r"\s+", " ", titulo or "").strip(), "autores": [a for a in autores if a][:4], "anio": anio, "url": url,
            "formato": formato, "licencia": licencia, "materias": materias, "genero": genero_desde_materias(materias + [titulo or ""]), "resumen": resumen[:300], "enlace": enlace}


def _libre(c) -> str:
    return " ".join(x for x in (c.texto, c.titulo, c.autor) if x)


def _gutenberg(c, n):
    """Catálogo OPDS oficial de Project Gutenberg (todo es dominio público). Gutendex se descartó: tardaba más de 30 s."""
    raiz = ET.fromstring(_get("https://www.gutenberg.org/ebooks/search.opds/?" + _q(query=_libre(c))).encode("utf-8"))
    hay = 0
    for e in raiz.findall(_ATOM + "entry"):
        m = re.search(r"/ebooks/(\d+)\.opds$", e.findtext(_ATOM + "id", ""))
        if m and hay < n:
            hay += 1
            yield _item("gutenberg", m.group(1), e.findtext(_ATOM + "title", ""), [e.findtext(_ATOM + "content", "")], None, f"https://www.gutenberg.org/ebooks/{m.group(1)}.epub3.images", "epub",
                        "Dominio público", [], enlace=f"https://www.gutenberg.org/ebooks/{m.group(1)}")


def _arxiv(c, n):
    raiz = ET.fromstring(_get("https://export.arxiv.org/api/query?" + _q(search_query=" AND ".join(p for p in (f'all:"{c.texto}"' if c.texto else "", f'ti:"{c.titulo}"' if c.titulo else "", f'au:"{c.autor}"' if c.autor else "") if p), max_results=n)))
    for e in raiz.findall(_ATOM + "entry"):
        pdf = next((l.get("href") for l in e.findall(_ATOM + "link") if l.get("title") == "pdf"), None)
        if pdf:
            yield _item("arxiv", e.findtext(_ATOM + "id", ""), e.findtext(_ATOM + "title", ""), [a.findtext(_ATOM + "name") for a in e.findall(_ATOM + "author")],
                        int((e.findtext(_ATOM + "published") or "0")[:4]) or None, pdf.replace("http://", "https://"), "pdf", "arXiv (descarga personal)",
                        [c.get("term") for c in e.findall(_ATOM + "category")], e.findtext(_ATOM + "summary", ""), e.findtext(_ATOM + "id", "").replace("http://", "https://"))


def _openalex(c, n):
    r = json.loads(_get("https://api.openalex.org/works?" + _q(search=_libre(c), filter="open_access.is_oa:true", **{"per-page": n * 2})))
    for w in r["results"]:
        loc = w.get("best_oa_location") or {}
        if loc.get("pdf_url"):
            yield _item("openalex", w["id"], w.get("display_name"), [a["author"]["display_name"] for a in w.get("authorships", [])], w.get("publication_year"), loc["pdf_url"], "pdf",
                        loc.get("license") or "acceso abierto", [c["display_name"] for c in w.get("concepts", [])][:8], enlace=w["id"])


def _archive(c, n):
    r = json.loads(_get("https://archive.org/advancedsearch.php?" + _q(q="(" + " AND ".join(p for p in (c.texto, f"title:({c.titulo})" if c.titulo else "", f"creator:({c.autor})" if c.autor else "") if p) + ") AND mediatype:texts AND NOT access-restricted-item:true", fl="identifier,title,creator,year,subject,licenseurl", rows=n * 3, output="json")))
    for d in r["response"]["docs"]:
        anio = int(str(d.get("year") or 0)[:4] or 0)
        lic = str(d.get("licenseurl") or "")
        if re.search(r"creativecommons|publicdomain", lic) or 0 < anio <= 1929:     # licencia abierta (CC / dominio público) o publicada hasta 1929
            sub = d.get("subject", [])
            yield _item("archive", d["identifier"], d.get("title", ""), [d["creator"]] if isinstance(d.get("creator"), str) else d.get("creator", []), anio or None, "", "pdf",
                        lic or "Dominio público (≤ 1929)", [sub] if isinstance(sub, str) else sub, enlace="https://archive.org/details/" + d["identifier"])


def _clave_google() -> str:
    """Clave de la API de Google Books (opcional; sin ella la cuota diaria compartida suele estar agotada): variable GOOGLE_BOOKS_KEY o fichero conocimiento/google_books.key."""
    f = Path(CARPETA) / "google_books.key"
    return os.environ.get("GOOGLE_BOOKS_KEY") or (f.read_text(encoding="utf-8").strip() if f.exists() else "")


def _openlibrary(c, n):
    """Open Library (sin clave): ficha con materias; si es de lectura abierta en Internet Archive se puede traer."""
    r = json.loads(_get("https://openlibrary.org/search.json?" + _q(**{k: v for k, v in (("q", c.texto), ("title", c.titulo), ("author", c.autor)) if v}, limit=n, fields="key,title,author_name,first_publish_year,subject,ebook_access,ia")))
    for d in r.get("docs", []):
        enlace = "https://openlibrary.org" + d["key"]
        args = (d.get("title", ""), d.get("author_name", []), d.get("first_publish_year"))
        if d.get("ebook_access") == "public" and d.get("ia"):                      # lectura abierta: se descarga por Internet Archive
            yield _item("archive", d["ia"][0], *args, "", "pdf", "Lectura abierta (Open Library)", d.get("subject", []), enlace=enlace)
        else:
            yield _item("openlibrary", d["key"], *args, "", "web", "Solo ficha / préstamo", d.get("subject", []), enlace=enlace)


def _googlebooks(c, n):
    """Catálogo de Google Books: ficha, categorías y enlace para verlo. Solo es descargable si Google lo marca como dominio público y da enlace de PDF/EPUB."""
    r = json.loads(_get("https://www.googleapis.com/books/v1/volumes?" + _q(q=_libre(c), maxResults=n, printType="books", **({"key": _clave_google()} if _clave_google() else {}))))
    for v in r.get("items", []):
        i, a = v.get("volumeInfo", {}), v.get("accessInfo", {})
        url, formato = "", "web"
        if a.get("publicDomain"):
            for ext in ("epub", "pdf"):
                if a.get(ext, {}).get("isAvailable") and a[ext].get("downloadLink", "").startswith("https://"):
                    url, formato = a[ext]["downloadLink"], ext
                    break
        yield _item("googlebooks", v["id"], i.get("title", "") + (": " + i["subtitle"] if i.get("subtitle") else ""), i.get("authors", []), int(str(i.get("publishedDate") or 0)[:4]) or None,
                    url, formato, "Dominio público" if url else "Solo vista previa / compra", i.get("categories", []), i.get("description", ""), i.get("infoLink", "").replace("http://", "https://"))


_BUSCADORES = {"googlebooks": _googlebooks, "openlibrary": _openlibrary, "gutenberg": _gutenberg, "arxiv": _arxiv, "openalex": _openalex, "archive": _archive}


def buscar(consulta: str = "", n: int = 6, fuentes=None, titulo: str = "", autor: str = "", tipo: str = "todo", formato: str = "") -> dict:
    """{'resultados': [item…], 'errores': {fuente: motivo}}: n por fuente; una fuente caída no impide las demás.
    `titulo` y `autor` afinan la búsqueda (y el autor se comprueba en cada resultado); `tipo` = todo | libro | articulo elige las fuentes; `formato` = pdf | epub deja solo lo descargable en ese formato."""
    c = Consulta(consulta.strip(), titulo.strip(), autor.strip())
    if not _libre(c):
        return {"resultados": [], "errores": {}}
    fuentes = fuentes or {"libro": LIBROS, "articulo": ARTICULOS}.get(tipo, FUENTES)
    toks = _norm(c.autor).split()
    res, err = [], {}
    for f in fuentes:
        try:
            for it in list(_BUSCADORES[f](c, n))[:n]:
                quien = _norm(" ".join(it["autores"]))
                if (not toks or all(t in quien for t in toks)) and (not formato or it["formato"] == formato.lower()):
                    res.append(it)
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
    if not item["url"] and item["fuente"] != "archive":
        raise ValueError("esta obra solo se puede ver en la web (no es de dominio público): abre el enlace")
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
