"""Gestor de conocimiento: un único buscador sobre todo lo que sabes (código del árbol, conceptos, teoría, libros, finanzas, notas).

Índice SQLite FTS5 (BM25, sin acentos, prefijos) en `<árbol>/conocimiento/indice.db`; se actualiza solo con lo que cambió.
Colecciones internas: `codigo` (docstrings de `arbol_estadistica`), `conceptos` (catalogo.json), `teoria` (teoria/*.md).
Colecciones tuyas: `conocimiento/fuentes.json` -> {"libros": ["D:/Libros"], "finanzas": [...], "notas": [...]} (ver fuentes.ejemplo.json).
Formatos: .md .txt .pdf (necesita `pip install pypdf`) .epub .docx.

Uso: `python -m conocimiento indexar` · `python -m conocimiento buscar "odds ratio" [-c libros] [-n 10]` · `python -m conocimiento estado`.
Los sinónimos del catálogo amplían la consulta (buscar «VIF» encuentra también su nombre largo). Si la consulta exacta no da nada, se relaja a «cualquiera de las palabras».
"""
from __future__ import annotations

import ast
import json
import os
import re
import sqlite3
import unicodedata
import zipfile
from pathlib import Path

CODIGO = Path(__file__).resolve().parents[1]
RAIZ = CODIGO.parent
CARPETA = Path(os.environ.get("ARBOL_CONOCIMIENTO", RAIZ / "conocimiento"))   # datos del usuario: no se publican (.gitignore)
DB = CARPETA / "indice.db"
EXT = {".md", ".txt", ".pdf", ".epub", ".docx"}


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def _palabras(s: str) -> list[str]:
    return re.findall(r"\w+", _norm(s))


# ---------- extracción: cada función devuelve [(titulo, texto, ubicacion)] o None si no se puede leer ----------
def _trocear(texto: str, titulo: str, ubic: str, max_car: int = 1200) -> list[tuple]:
    out, buf = [], ""
    for p in re.split(r"\n\s*\n", texto):
        p = p.strip()
        if not p:
            continue
        if buf and len(buf) + len(p) > max_car:
            out.append((titulo, buf, ubic)); buf = ""
        buf = f"{buf}\n\n{p}" if buf else p
        while len(buf) > 2 * max_car:
            out.append((titulo, buf[:max_car], ubic)); buf = buf[max_car:]
    return out + [(titulo, buf, ubic)] if buf else out


def _texto_plano(f: Path):
    t = f.read_text(encoding="utf-8", errors="replace")
    if f.suffix != ".md":
        return _trocear(t, f.stem, "")
    partes = re.split(r"(?m)^(#{1,6} .*)$", t)              # [intro, '# titulo', cuerpo, ...]
    out = _trocear(partes[0], f.stem, "")
    for i in range(1, len(partes), 2):
        out += _trocear(partes[i + 1], f.stem, partes[i].lstrip("# ").strip())
    return out


def _pdf(f: Path):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None                                          # sin pypdf no se marca como indexado: se reintenta al instalarlo
    out = []
    for i, pag in enumerate(PdfReader(str(f)).pages):
        out += _trocear(pag.extract_text() or "", f.stem, f"p. {i + 1}")
    return out


def _sin_etiquetas(x: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"</(p|div|h\d|li|tr)>|<br\s*/?>", "\n\n", x).replace("\r", ""))


def _epub(f: Path):
    out = []
    with zipfile.ZipFile(f) as z:
        for n in sorted(z.namelist()):
            if n.lower().endswith((".xhtml", ".html", ".htm")):
                x = _sin_etiquetas(z.read(n).decode("utf-8", "replace"))
                out += _trocear(re.sub(r"<[^>]+>", "", x), f.stem, Path(n).name)
    return out


def _docx(f: Path):
    with zipfile.ZipFile(f) as z:
        x = _sin_etiquetas(z.read("word/document.xml").decode("utf-8", "replace"))
    return _trocear(re.sub(r"<[^>]+>", "", x), f.stem, "")


def _codigo(f: Path):
    rama = f.parent.name
    out = []
    for n in ast.parse(f.read_text(encoding="utf-8")).body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
            doc = ast.get_docstring(n) or ""
            out.append((n.name, f"{n.name}({ast.unparse(n.args)})\n{doc}", f"{rama}/{f.name}:{n.lineno}"))
    return out


def _conceptos(f: Path):
    out = []
    for c in json.loads(f.read_text(encoding="utf-8"))["conceptos"]:
        fuentes = "; ".join(f"{x.get('ref', '')} ({x.get('base', '')})" for x in c.get("fuentes", []))
        txt = (f"{c.get('desc', '')}\nSinónimos: {', '.join(c.get('sinonimos', []))}\n"
               f"Funciones: {', '.join(c.get('funciones', []))}\nFuentes: {fuentes}")
        out.append((c["nombre"], txt, c.get("area", "")))
    return out


def _grupos(con: sqlite3.Connection, f: Path) -> None:
    """Sinónimos del catálogo: cada concepto es un grupo de frases equivalentes (nombre + sinónimos)."""
    con.execute("delete from grupos")
    for c in json.loads(f.read_text(encoding="utf-8"))["conceptos"]:
        for frase in [c["nombre"], *c.get("sinonimos", [])]:
            if _palabras(frase):
                con.execute("insert into grupos values (?, ?)", (" ".join(_palabras(frase)), c["id"]))


def _extraer(col: str, f: Path):
    if col == "codigo":
        return _codigo(f)
    if col == "conceptos":
        return _conceptos(f)
    return {".pdf": _pdf, ".epub": _epub, ".docx": _docx}.get(f.suffix.lower(), _texto_plano)(f)


# ---------- índice ----------
def _abrir(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.executescript("""
        create virtual table if not exists trozos using fts5(titulo, texto, coleccion unindexed, ruta unindexed,
            ubicacion unindexed, tokenize = 'unicode61 remove_diacritics 2');
        create table if not exists ficheros (ruta text primary key, huella text, coleccion text);
        create table if not exists grupos (frase text, grupo text);
        create index if not exists grupos_frase on grupos(frase);""")
    return con


def cargar_fuentes(carpeta: Path = CARPETA) -> dict:
    f = carpeta / "fuentes.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _unidades(fuentes: dict):
    for f in sorted((CODIGO / "arbol_estadistica").rglob("*.py")):
        yield "codigo", f
    yield "conceptos", RAIZ / "conceptos" / "catalogo.json"
    for f in sorted((RAIZ / "teoria").glob("*.md")):
        yield "teoria", f
    for col, carpetas in fuentes.items():
        for c in carpetas:
            if not Path(c).is_dir():
                print(f"aviso: la carpeta de «{col}» no existe: {c}")
                continue
            for f in sorted(Path(c).rglob("*")):
                if f.is_file() and f.suffix.lower() in EXT:
                    yield col, f


def indexar(db: Path = DB, fuentes: dict | None = None) -> dict:
    """Indexa lo nuevo o modificado y borra lo que ya no existe. Devuelve {'nuevos', 'iguales', 'borrados', 'sin_leer'}."""
    fuentes = cargar_fuentes() if fuentes is None else fuentes
    con = _abrir(db)
    vistos, r = set(), {"nuevos": 0, "iguales": 0, "borrados": 0, "sin_leer": []}
    for col, f in _unidades(fuentes):
        if not f.exists():
            continue
        ruta, st = str(f), f.stat()
        huella = f"{st.st_mtime_ns}:{st.st_size}"
        vistos.add(ruta)
        fila = con.execute("select huella from ficheros where ruta=?", (ruta,)).fetchone()
        if fila and fila[0] == huella:
            r["iguales"] += 1
            continue
        try:
            trozos = _extraer(col, f)
        except Exception as e:                               # un PDF cifrado o un .py roto no debe parar el resto
            print(f"aviso: no se pudo leer {f.name}: {e}")
            trozos = None
        if trozos is None:
            r["sin_leer"].append(ruta)
            continue
        con.execute("delete from trozos where ruta=?", (ruta,))      # ponytail: borrado por barrido; con >1M de trozos, tabla auxiliar con rowid
        con.executemany("insert into trozos(titulo, texto, coleccion, ruta, ubicacion) values (?,?,?,?,?)",
                        [(t, x, col, ruta, u) for t, x, u in trozos])
        con.execute("insert or replace into ficheros values (?,?,?)", (ruta, huella, col))
        if col == "conceptos":
            _grupos(con, f)
        con.commit(); r["nuevos"] += 1
    for (ruta,) in con.execute("select ruta from ficheros").fetchall():
        if ruta not in vistos:
            con.execute("delete from trozos where ruta=?", (ruta,)); con.execute("delete from ficheros where ruta=?", (ruta,)); r["borrados"] += 1
    con.commit(); con.close()
    return r


# ---------- búsqueda ----------
def _expresiones(con: sqlite3.Connection, consulta: str) -> list[str]:
    toks = _palabras(consulta)
    if not toks:
        return []
    exacta = " AND ".join(f'"{t}"*' for t in toks)
    sin = [f for (f,) in con.execute("select g2.frase from grupos g1 join grupos g2 on g1.grupo = g2.grupo where g1.frase = ?", (" ".join(toks),))]
    expr = " OR ".join([f"({exacta})"] + [f'"{f}"' for f in dict.fromkeys(sin) if f != " ".join(toks)])
    return [expr, " OR ".join(f'"{t}"*' for t in toks)]      # si la primera no da nada, vale cualquier palabra


def buscar(consulta: str, coleccion: str | None = None, n: int = 10, db: Path = DB) -> list[dict]:
    """Mejores `n` trozos para la consulta, por BM25 (el título pesa 8×). Cada resultado: coleccion, titulo, ubicacion, ruta, fragmento."""
    if not Path(db).exists():
        raise FileNotFoundError("no hay índice: ejecuta primero `python -m conocimiento indexar`")
    con = _abrir(Path(db))
    sql = ("select coleccion, titulo, ubicacion, ruta, snippet(trozos, 1, '«', '»', ' … ', 24) from trozos where trozos match ?"
           + (" and coleccion = ?" if coleccion else "") + " order by bm25(trozos, 8.0, 1.0) limit ?")
    for expr in _expresiones(con, consulta):
        filas = con.execute(sql, (expr, *([coleccion] if coleccion else []), n)).fetchall()
        if filas:
            break
    else:
        filas = []
    con.close()
    return [dict(zip(("coleccion", "titulo", "ubicacion", "ruta", "fragmento"), f)) for f in filas]


def estado(db: Path = DB) -> list[tuple]:
    """(colección, ficheros, trozos) de lo indexado."""
    con = _abrir(Path(db))
    filas = con.execute("select coleccion, count(distinct ruta), count(*) from trozos group by 1 order by 1").fetchall()
    con.close()
    return filas


def es_fuente(ruta: str, db: Path = DB) -> bool:
    """True si `ruta` es un fichero indexado (la app solo abre lo que está en el índice)."""
    con = _abrir(Path(db))
    ok = con.execute("select 1 from ficheros where ruta = ?", (str(ruta),)).fetchone() is not None
    con.close()
    return ok
