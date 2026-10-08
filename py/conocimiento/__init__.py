"""Gestor de conocimiento: un único buscador sobre todo lo que sabes (código del árbol, conceptos, teoría, libros, finanzas, notas).

Índice SQLite FTS5 (BM25, sin acentos, prefijos) en `<árbol>/conocimiento/indice.db`; se actualiza solo con lo que cambió.
Colecciones internas: `codigo` (docstrings de `arbol_estadistica`), `conceptos` (catalogo.json), `teoria` (teoria/*.md).
Colecciones tuyas: `conocimiento/fuentes.json` -> {"libros": ["D:/Libros"], "finanzas": [...], "notas": [...]} (ver fuentes.ejemplo.json).
Formatos de las carpetas de fuentes: .md .txt .pdf (necesita `pip install pypdf`) .epub .docx. El importador admite además código (.py .ipynb .r .sas .sql .js …), datos (.csv .xlsx .json …) y apuntes (.pptx .tex .html …): ver EXT_IMPORTABLE.

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
EXT = {".md", ".txt", ".pdf", ".epub", ".docx"}                          # lo que se busca en las carpetas de fuentes.json (documentos)
CODIGO_EXT = {".py", ".ipynb", ".r", ".rmd", ".qmd", ".sas", ".sql", ".js", ".ts", ".sh", ".bat", ".ps1", ".c", ".cpp", ".h", ".java", ".jl", ".m"}
DATOS_EXT = {".csv", ".tsv", ".xlsx", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml"}
APUNTES_EXT = {".rst", ".tex", ".html", ".htm", ".pptx"}
ENLACE_EXT = {".url"}                                                    # accesos directos a vídeos (YouTube, Vimeo): enlaces.py
EXT_IMPORTABLE = EXT | CODIGO_EXT | DATOS_EXT | APUNTES_EXT | ENLACE_EXT                # lo que acepta el importador y se indexa dentro de biblioteca/


SIN_VENTANA = getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)      # creationflags de los subprocess: en la app (pythonw) evita que parpadee una ventana de consola
PROGRESO = None                                                  # función(texto, fracción 0-1): la pone quien quiera ver el avance (la app, mientras importa un PDF grande)


def _prog(texto: str, frac: float) -> None:
    if PROGRESO:
        try:
            PROGRESO(texto, frac)
        except Exception:
            pass


def _metadatos(carpeta: Path) -> dict:
    f = Path(carpeta) / "biblioteca" / "metadatos.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


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


def _bloques(t: str, titulo: str, tam: int = 60):
    """Trozos de unas `tam` líneas; el título lleva el primer def/class del bloque, la ubicación las líneas."""
    ls = t.splitlines()
    out = []
    for a in range(0, len(ls), tam):
        bloque = "\n".join(ls[a:a + tam])
        if bloque.strip():
            d = re.search(r"(?m)^\s*(?:async\s+)?(?:def|class|function)\s+(\w+)", bloque)
            out.append((f"{titulo} · {d.group(1)}" if d else titulo, bloque, f"líneas {a + 1}–{min(a + tam, len(ls))}"))
    return out


def _codigo_texto(f: Path):
    return _bloques(f.read_text(encoding="utf-8", errors="replace"), f.stem)


def _ipynb(f: Path):
    out = []
    for i, c in enumerate(json.loads(f.read_text(encoding="utf-8", errors="replace")).get("cells", []), 1):
        src = c.get("source", "")
        src = "".join(src) if isinstance(src, list) else str(src)
        if src.strip():
            out += _trocear(src, f.stem, f"celda {i} ({'texto' if c.get('cell_type') == 'markdown' else 'código'})")
    return out


def _datos(f: Path):
    """CSV/TSV/JSON/YAML/XML…: solo el principio (cabecera y primeras filas): lo demás son datos, no texto que buscar."""
    return _trocear("\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[:40]), f.stem, "cabecera y primeras filas")


def _html(f: Path):
    x = _sin_etiquetas(f.read_text(encoding="utf-8", errors="replace"))
    return _trocear(re.sub(r"<[^>]+>", "", x), f.stem, "")


def _pptx(f: Path):
    with zipfile.ZipFile(f) as z:
        lams = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=lambda n: int(re.findall(r"\d+", n)[0]))
        return [x for n in lams for x in _trocear(" ".join(re.findall(r"<a:t>(.*?)</a:t>", z.read(n).decode("utf-8", "replace"))), f.stem, f"diapositiva {re.findall(r'[0-9]+', n)[0]}")]


def _xlsx(f: Path):
    with zipfile.ZipFile(f) as z:
        txt = z.read("xl/sharedStrings.xml").decode("utf-8", "replace") if "xl/sharedStrings.xml" in z.namelist() else ""
    return _trocear("\n".join(re.findall(r"<t[^>]*>(.*?)</t>", txt)[:400]), f.stem, "textos de la hoja")


def _pdf(f: Path):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None                                          # sin pypdf no se marca como indexado: se reintenta al instalarlo
    out = []
    paginas = PdfReader(str(f)).pages
    for i, pag in enumerate(paginas):
        out += _trocear(pag.extract_text() or "", f.stem, f"p. {i + 1}")
        if i % 8 == 0:
            _prog(f"Leyendo «{f.stem[:40]}»: página {i + 1} de {len(paginas)}", (i + 1) / len(paginas))
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
    if col == "codigo" and f.suffix == ".py" and CODIGO in f.parents:           # el código del propio árbol; el código que importas se trata como cualquier archivo de texto
        return _codigo(f)
    if col == "conceptos":
        return _conceptos(f)
    ext = f.suffix.lower()
    if ext in ENLACE_EXT:
        from . import enlaces
        return _trocear(enlaces.texto(f), f.stem, "")
    if ext in CODIGO_EXT and ext != ".ipynb":
        return _codigo_texto(f)
    return {".pdf": _pdf, ".epub": _epub, ".docx": _docx, ".ipynb": _ipynb, ".csv": _datos, ".tsv": _datos, ".json": _datos, ".yaml": _datos, ".yml": _datos, ".toml": _datos,
            ".ini": _datos, ".cfg": _datos, ".xml": _datos, ".html": _html, ".htm": _html, ".pptx": _pptx, ".xlsx": _xlsx}.get(ext, _texto_plano)(f)


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


def _unidades(fuentes: dict, carpeta: Path = CARPETA):
    for f in sorted((CODIGO / "arbol_estadistica").rglob("*.py")):
        yield "codigo", f
    yield "conceptos", RAIZ / "conceptos" / "catalogo.json"
    for f in sorted((RAIZ / "teoria").glob("*.md")):
        yield "teoria", f
    base = Path(carpeta) / "biblioteca"                       # lo importado con el importador: biblioteca/<galaxia>/<subtema>/fichero
    if base.is_dir():
        meta = _metadatos(carpeta)
        for f in sorted(base.rglob("*")):
            if f.is_file() and f.suffix.lower() in EXT_IMPORTABLE and f.relative_to(base).parts[0] != f.name:
                rel = f.relative_to(base)
                yield (meta.get(rel.as_posix(), {}).get("galaxia") or rel.parts[0]), f
    for col, carpetas in fuentes.items():
        for c in carpetas:
            if not Path(c).is_dir():
                print(f"aviso: la carpeta de «{col}» no existe: {c}")
                continue
            for f in sorted(Path(c).rglob("*")):
                if f.is_file() and f.suffix.lower() in EXT:
                    yield col, f


def indexar(db: Path = DB, fuentes: dict | None = None, carpeta: Path = CARPETA) -> dict:
    """Indexa lo nuevo o modificado y borra lo que ya no existe. Devuelve {'nuevos', 'iguales', 'borrados', 'sin_leer'}."""
    fuentes = cargar_fuentes(carpeta) if fuentes is None else fuentes
    con = _abrir(db)
    vistos, r = set(), {"nuevos": 0, "iguales": 0, "borrados": 0, "sin_leer": []}
    for col, f in _unidades(fuentes, carpeta):
        if not f.exists():
            continue
        ruta, st = str(f), f.stat()
        huella = f"{st.st_mtime_ns}:{st.st_size}"
        vistos.add(ruta)
        fila = con.execute("select huella from ficheros where ruta=?", (ruta,)).fetchone()
        if fila and fila[0] == huella:
            r["iguales"] += 1
            continue
        _prog(f"Indexando {f.name[:50]}", 0.0)
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


_PORTADAS: dict = {}


def _portada_cache(base: Path, rel: str) -> str:
    """Portada como data URI (con memoria: la búsqueda la pide en cada pulsación)."""
    if rel not in _PORTADAS:
        f = Path(base) / rel
        _PORTADAS[rel] = "data:image/jpeg;base64," + __import__("base64").b64encode(f.read_bytes()).decode() if f.is_file() else ""
    return _PORTADAS[rel]


def buscar(consulta: str, coleccion: str | None = None, n: int = 10, db: Path = DB, genero: str | None = None, formato: str | None = None) -> list[dict]:
    """Mejores `n` trozos para la consulta, por BM25 (el título pesa 8×); `genero` limita a lo importado con ese género y `formato` (pdf, epub, docx, md, txt) al tipo de archivo. Cada resultado: coleccion, titulo, ubicacion, ruta, fragmento."""
    if not Path(db).exists():
        raise FileNotFoundError("no hay índice: ejecuta primero `python -m conocimiento indexar`")
    con = _abrir(Path(db))
    sql = ("select coleccion, titulo, ubicacion, ruta, snippet(trozos, 1, '«', '»', ' … ', 24) from trozos where trozos match ?"
           + (" and coleccion = ?" if coleccion else "") + " order by bm25(trozos, 8.0, 1.0) limit ?")
    formato = (formato or "").lower().lstrip(".")
    n_sql = n * 8 if genero or formato else n                      # con filtro de género o de formato se piden más y se recorta después
    for expr in _expresiones(con, consulta):
        filas = con.execute(sql, (expr, *([coleccion] if coleccion else []), n_sql)).fetchall()
        if filas:
            break
    else:
        filas = []
    con.close()
    base = Path(db).parent / "biblioteca"
    meta = json.loads((base / "metadatos.json").read_text(encoding="utf-8")) if (base / "metadatos.json").exists() else {}
    out = []
    for f in filas:
        r = dict(zip(("coleccion", "titulo", "ubicacion", "ruta", "fragmento"), f))
        if formato and not r["ruta"].lower().endswith("." + formato):
            continue
        try:
            m = meta.get(Path(r["ruta"]).relative_to(base).as_posix())
        except ValueError:
            m = None
        r.update(subtema=(m or {}).get("subtema", ""), tipo=(m or {}).get("tipo", ""), etiquetas=(m or {}).get("etiquetas", ""))
        if (m or {}).get("portada"):
            r["portada"] = _portada_cache(base, m["portada"])
        if genero and (m or {}).get("genero") != genero:
            continue
        r["interno"] = m is None and (r["coleccion"] in ("codigo", "teoria") or r["ruta"].endswith("catalogo.json"))   # código, teoría y catálogo del propio árbol: no son ficheros que abrir
        out.append(r)
    return out[:n]


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
