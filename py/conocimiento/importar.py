"""Importador: copia ficheros a `conocimiento/biblioteca/<galaxia>/<subtema>/`, los clasifica (galaxia, subtema, tipo) y los indexa para el buscador.

Por defecto lo decide solo (`clasificar`); cualquier dato que pases (galaxia, subtema, tipo, etiquetas) manda sobre lo automático.
Galaxia automática: finanzas si domina el vocabulario financiero; si no, libros (PDF/EPUB largos) o notas. Subtema automático: el tema del catálogo de conceptos
(«Inferencia y contrastes», «Regresión y GLM»…) con más coincidencias. Los metadatos van en `biblioteca/metadatos.json` (ruta relativa -> datos).

Uso: `python -m conocimiento importar f1.pdf f2.docx [-g libros] [-s "Inferencia y contrastes"] [-t libro]`.
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import math
import os
import re
import shutil
import unicodedata
import posixpath
import zipfile
from datetime import datetime
from pathlib import Path

from . import CARPETA, CODIGO_EXT, DATOS_EXT, DB, EXT_IMPORTABLE, RAIZ, SIN_VENTANA, _abrir, _extraer, _norm, _prog, clasificador, indexar, llm

GALAXIAS = {"codigo": "Código", "conceptos": "Conceptos", "demos": "Demos y guías", "finanzas": "Finanzas", "libros": "Libros", "notas": "Notas y enlaces"}
TIPOS = {"libro": "Libro", "articulo": "Artículo", "apuntes": "Apuntes", "nota": "Nota", "codigo": "Código", "datos": "Datos", "otro": "Otro"}
GENEROS = {"historia": "Historia", "economia": "Economía y finanzas", "ensayo": "Ensayo y filosofía", "estadistica": "Estadística y matemáticas", "ciencia": "Ciencia y divulgación",
           "novela": "Novela y ficción", "biografia": "Biografía y memorias", "politica": "Política y sociedad", "tecnologia": "Tecnología e informática",
           "psicologia": "Psicología y salud", "arte": "Arte, música y cultura", "otro": "Otros"}
_GEN_PALABRAS = {
    "historia": r"history|historia|empire|imperio|war|guerra|century|siglo|ancient|antigu|medieval|revolution|revolucion|dynasty|dinastia|republic|republica|romans?|romanos?|civilization|civilizacion|kingdom|reino|conquest|conquista",
    "economia": r"economics|economy|economia|economist|market|mercado|capitalism|capitalismo|trade|comercio|inflation|inflacion|monetary|monetaria|fiscal|growth|crecimiento|bank|banco|poverty|pobreza|wealth|riqueza|gdp|pib|labor|empresa|business|inversion|invest|finanzas|finance",
    "estadistica": r"statistic\w*|estadistic\w*|regression|regresion|probability|probabilidad|estimat\w*|hypothesis|hipotesis|bayes\w*|variance|varianza|econometric\w*|machine learning|theorem|teorema|calculus|algebra|matrix|matriz|likelihood|verosimilitud",
    "ciencia": r"physics|fisica|biology|biologia|chemistry|quimica|universe|universo|evolution|evolucion|neuroscience|neurociencia|quantum|cuantic\w*|genome|genoma|climate|clima|cosmos|astronomy|astronomia|scientific|cientific\w*|science|ciencia",
    "novela": r"novel|novela|cuento|thriller|mystery|misterio|detective|fantasy|fantasia|romance|once upon|chapter one|capitulo uno|he said|she said|dijo",
    "ensayo": r"philosoph\w*|filosof\w*|essay|ensayo|ethic\w*|etic\w*|metaphysic\w*|stoic\w*|estoic\w*|reason|razon|liberty|libertad|freedom|truth|verdad|meaning|sentido|virtue|virtud|moral\w*",
    "biografia": r"biograph\w*|memoir\w*|memorias|autobiograph\w*|life of|vida de|my life|mi vida",
    "politica": r"politic\w*|democracy|democracia|government|gobierno|election|eleccion\w*|geopolit\w*|society|sociedad|social|state|estado|policy|nationalism|nacionalismo",
    "tecnologia": r"software|programming|programacion|python|algorithm\w*|algoritmo\w*|computer|ordenador|internet|artificial intelligence|inteligencia artificial|data science|linux|codigo|developer",
    "psicologia": r"psycholog\w*|psicolog\w*|behavior|conducta|cognitive|cognitiv\w*|therapy|terapia|emotion\w*|emocion\w*|health|salud|mental",
    "arte": r"art|arte|music|musica|painting|pintura|film|cine|literature|literatura|architecture|arquitectura|poetry|poesia|theatre|teatro|museum|museo"}
_GEN_RE = {g: re.compile(r"\b(?:" + p + r")\b") for g, p in _GEN_PALABRAS.items()}
_ES = set("el la de que y en los las un una por con para es se del al lo como mas pero sus le ya o este si porque esta entre cuando muy sin sobre tambien me hasta hay donde quien desde todo nos durante".split())
_EN = set("the of and to in is that for with as on by it this are was be at from or an which have has not but they their its been were all more can will one also".split())
_TEMA_PALABRAS = {
    "t_prob": r"probabilit\w*|probabilidad|random variables?|variables? aleatorias?|distributions?|distribuci\w+|expectation|expected value|esperanza|bayes\w*|markov|poisson|binomial|gaussian|central limit|limit theorem|moment generating",
    "t_inf": r"estimat\w+|estimad\w+|hypothesis|hipotesis|confidence intervals?|intervalos? de confianza|p-?values?|significan\w+|likelihood|verosimilitud|t-?tests?|chi-?squared?|chi-?cuadrado|nonparametric|sampling distributions?|contrastes?",
    "t_mod": r"regression|regresion|linear models?|modelos? lineales?|generalized linear|glm|logistic|logit|anova|residuals?|residuos|multicollinearity|colinealidad|least squares|minimos cuadrados|covariates?|predictors?",
    "t_ml": r"machine learning|aprendizaje automatico|classification|clasificacion|cross-?validation|validacion cruzada|random forests?|boosting|neural networks?|redes neuronales|overfitting|sobreajuste|tuning|resampling|bootstrap|support vector|decision trees?|arboles de decision|predictive|lasso|ridge|regulariz\w+|supervised|unsupervised|clustering",
    "t_sim": r"simulation|simulacion|monte carlo|mcmc|bayesian|bayesiano|posterior|prior|experimental design|diseno de experimentos|factorial|randomi[sz]ation|aleatorizacion",
    "t_pob": r"survival analysis|analisis de supervivencia|kaplan|hazard|censoring|censura|demograph\w+|demografi\w+|mortality|mortalidad|life tables?|tablas de vida|cohort|epidemiolog\w+",
    "t_seg": r"insurance|seguros?|actuarial|claims?|siniestros?|premium|reserves?|reservas|ruin|credibility|credibilidad|risk theory|reinsurance",
    "t_fin": r"portfolio|cartera|bonds?|bonos|derivatives?|derivados|interest rates?|tipos de interes|volatility|volatilidad|capm|markowitz|black-?scholes|value at risk|solvency|solvencia|basel"}
_TEMA_RE = {k: re.compile(r"\b(?:" + v + r")\b") for k, v in _TEMA_PALABRAS.items()}
GENEROS_CON_TEMA = {"estadistica", "economia", "tecnologia"}          # solo a estos se les asigna un tema del catálogo de estadística: a un libro de historia no le corresponde ninguno


def _puntos_temas(t: str, nombre: str) -> dict:
    """{(id, nombre): puntos}. Palabras clave en inglés y español (cada una cuenta 1 + log(veces), así no manda una sola palabra repetida) más las frases del catálogo."""
    out = {}
    for tid, tnombre, frases in _temas_con_frases():
        palabras = _TEMA_RE.get(tid)
        veces = {}
        for m in (palabras.findall(t) if palabras else []):
            veces[m] = veces.get(m, 0) + 1
        clave = sum(1 + math.log(n) for n in veces.values())
        cat = sum(1 for fr in frases if len(fr) >= 7 and fr in t) + 3 * sum(1 for fr in frases if len(fr) >= 7 and fr in nombre)
        titulo = 8 * len(palabras.findall(nombre)) if palabras else 0          # lo que dice el título pesa mucho
        p = int(round(2 * clave + cat / 2 + titulo))
        if p:
            out[(tid, tnombre)] = p
    return out


FINANZAS = re.compile(r"\b(bonos?|carteras?|rentabilidad|volatilidad|derivados?|opcion(?:es)?|futuros?|tipos? de interes|capm|markowitz|renta fija|renta variable|tesoreria|"
                      r"solvencia|var|valoracion|acciones|mercados?|activos?|pasivos?|riesgo de credito|fiscalidad|impuestos?|bancari[oa]s?|swaps?|duracion|rating)\b")


def carpeta_datos() -> Path:
    """Carpeta de datos del usuario (`conocimiento/`; ARBOL_CONOCIMIENTO la cambia), leída al llamar."""
    return Path(os.environ.get("ARBOL_CONOCIMIENTO", RAIZ / "conocimiento"))


def capitulos(ruta: str | Path) -> tuple[list[dict], int]:
    """([{titulo, pagina}], nº de páginas). PDF: el índice (marcadores) del libro, o tramos de 25 páginas si no lo tiene; EPUB: su tabla de contenidos;
    DOCX/MD: los títulos. Siempre devuelve al menos una entrada."""
    f = Path(ruta); ext = f.suffix.lower(); caps: list[dict] = []; paginas = 0
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            r = PdfReader(str(f)); paginas = len(r.pages); planos: list = []

            def rec(lista, nivel):
                for it in lista:
                    if isinstance(it, list):
                        rec(it, nivel + 1)
                    else:
                        try:
                            pg = r.get_destination_page_number(it) + 1
                        except Exception:
                            pg = None
                        planos.append((nivel, str(it.title).strip(), pg))
            rec(r.outline, 0)
            top = [p for p in planos if p[0] == 0]
            usar = top if len(top) >= 4 else [p for p in planos if p[0] <= 1]
            caps = [{"titulo": tt, "pagina": pg} for _, tt, pg in usar if tt][:80]
            if not caps and paginas:
                caps = [{"titulo": f"Páginas {a}–{min(a + 24, paginas)}", "pagina": a} for a in range(1, paginas + 1, 25)][:60]
        elif ext == ".epub":
            with zipfile.ZipFile(f) as z:
                nombres = z.namelist(); titulos: list = []
                ncx = next((n for n in nombres if n.endswith(".ncx")), None)
                nav = next((n for n in nombres if re.search(r"(nav|toc)[^/]*\.x?html?$", n, re.I)), None)
                if ncx:
                    titulos = re.findall(r"<navLabel>\s*<text>(.*?)</text>", z.read(ncx).decode("utf-8", "replace"), re.S)
                elif nav:
                    titulos = [re.sub(r"<[^>]+>", "", x) for x in re.findall(r"<a[^>]*>(.*?)</a>", z.read(nav).decode("utf-8", "replace"), re.S)]
                caps = [{"titulo": re.sub(r"\s+", " ", html.unescape(x)).strip(), "pagina": None} for x in titulos if x.strip()][:80]
        elif ext == ".docx":
            with zipfile.ZipFile(f) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            for par in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
                if re.search(r'w:pStyle w:val="(Heading|Ttulo|Título)\d', par):
                    tt = html.unescape(re.sub(r"<[^>]+>", "", par)).strip()
                    if tt:
                        caps.append({"titulo": tt, "pagina": None})
            caps = caps[:80]
        elif ext in (".md", ".txt", ".rmd", ".qmd", ".rst"):
            caps = [{"titulo": m.strip(), "pagina": None} for m in re.findall(r"(?m)^#{1,3}\s+(.+)$", f.read_text(encoding="utf-8", errors="replace"))][:80]
        elif ext == ".ipynb":                                          # títulos de las celdas de texto
            for c in json.loads(f.read_text(encoding="utf-8", errors="replace")).get("cells", []):
                if c.get("cell_type") == "markdown":
                    caps += [{"titulo": m.strip(), "pagina": None} for m in re.findall(r"(?m)^#{1,3}\s+(.+)$", "".join(c.get("source", [])))]
            caps = caps[:80]
        elif ext in CODIGO_EXT:                                        # funciones y clases de primer nivel
            caps = [{"titulo": m, "pagina": None} for m in re.findall(r"(?m)^(?:async\s+)?(?:def|class|function)\s+(\w+)", f.read_text(encoding="utf-8", errors="replace"))][:80]
    except Exception:
        caps = []
    return (caps or [{"titulo": f.stem, "pagina": 1 if ext == ".pdf" else None}]), paginas


def titulo_corto(nombre: str, n: int = 60) -> str:
    """Recorta nombres largos de fichero («3. Regression Modeling Strategies_ With Applications -- Autor -- 2016 -- Springer -- isbn… -- Anna's Archive»):
    primer tramo antes de « -- », sin numeración inicial, sin guiones bajos y como mucho `n` caracteres (corta en una palabra y añade «…»)."""
    s = re.sub(r"[.]\w{2,4}$", "", str(nombre)).split(" -- ")[0]
    s = re.sub(r"^\s*\d+[.)]\s+", "", s).replace(";_", ";").replace("_ ", ": ").replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip(" -;,")
    if len(s) > n:
        s = s[:n].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return s or str(nombre)[:n]


_COLOR_GENERO = {"historia": (150, 90, 50), "economia": (40, 120, 80), "ensayo": (110, 80, 150), "estadistica": (40, 90, 170), "ciencia": (30, 130, 150), "novela": (160, 60, 90),
                 "biografia": (140, 110, 40), "politica": (150, 60, 50), "tecnologia": (60, 70, 90), "psicologia": (130, 70, 130), "arte": (170, 90, 120), "otro": (80, 90, 110)}


def _imagen_epub(f: Path) -> bytes | None:
    with zipfile.ZipFile(f) as z:
        nombres = z.namelist()
        opf = next((n for n in nombres if n.endswith(".opf")), None)
        if opf:
            x = z.read(opf).decode("utf-8", "replace")
            ident = re.search(r'<meta[^>]+name="cover"[^>]+content="([^"]+)"', x) or re.search(r'<meta[^>]+content="([^"]+)"[^>]+name="cover"', x)
            href = None
            if ident:
                m = re.search(r'<item[^>]+id="' + re.escape(ident.group(1)) + r'"[^>]*>', x)
                href = re.search(r'href="([^"]+)"', m.group(0)).group(1) if m else None
            if not href:
                m = re.search(r'<item[^>]+properties="[^"]*cover-image[^"]*"[^>]*>', x)
                href = re.search(r'href="([^"]+)"', m.group(0)).group(1) if m else None
            if href:
                ruta = posixpath.normpath(posixpath.join(posixpath.dirname(opf), html.unescape(href)))
                if ruta in nombres:
                    return z.read(ruta)
        imgs = [n for n in nombres if re.search(r"\.(jpe?g|png)$", n, re.I)]
        cub = [n for n in imgs if "cover" in n.lower() or "portada" in n.lower()]
        elegido = (cub or sorted(imgs, key=lambda n: -z.getinfo(n).file_size))[:1]
        return z.read(elegido[0]) if elegido else None


def _imagen_pdf(f: Path) -> bytes | None:
    """La primera página del PDF como imagen: con `pdftoppm` (Poppler) si está instalado; si no, una imagen JPEG incrustada en las dos primeras páginas (las demás
    codificaciones salen mal sin un motor de PDF)."""
    exe = shutil.which("pdftoppm")
    if exe:
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            try:
                subprocess.run([exe, "-f", "1", "-l", "1", "-jpeg", "-scale-to", "260", str(f), str(Path(td) / "p")], check=True, capture_output=True, timeout=60, creationflags=SIN_VENTANA)
                sal = sorted(Path(td).glob("p*.jpg"))
                if sal:
                    return sal[0].read_bytes()
            except Exception:
                pass
    try:
        from pypdf import PdfReader
        for pag in PdfReader(str(f)).pages[:2]:
            for im in pag.images:
                if im.data[:2] == bytes([255, 216]) and len(im.data) > 8000:
                    return im.data
    except Exception:
        pass
    return None


def portada(f: str | Path, destino: Path, titulo: str = "", genero: str = "otro") -> bool:
    """Guarda en `destino` (JPG de unos 120×170 px) la portada del libro: la imagen del EPUB o del PDF si la tiene; si no, una portada de color según el género con el título.
    Devuelve True si pudo escribirla."""
    from PIL import Image, ImageDraw, ImageFont
    f = Path(f)
    try:
        datos = _imagen_epub(f) if f.suffix.lower() == ".epub" else _imagen_pdf(f) if f.suffix.lower() == ".pdf" else None
    except Exception:
        datos = None
    try:
        if datos:
            im = Image.open(io.BytesIO(datos)).convert("RGB")
            im.thumbnail((150, 215))
        else:                                                      # portada generada: color del género, título a mano
            c = _COLOR_GENERO.get(genero, _COLOR_GENERO["otro"])
            im = Image.new("RGB", (120, 170), c)
            d = ImageDraw.Draw(im)
            for y in range(170):
                d.line([(0, y), (120, y)], fill=tuple(int(v * (1.15 - .45 * y / 170)) % 256 if v * 1.15 < 256 else min(255, int(v * (1.15 - .45 * y / 170))) for v in c))
            d.rectangle((6, 6, 113, 163), outline=(255, 255, 255), width=1)
            try:
                fuente = ImageFont.load_default(size=13)
            except TypeError:
                fuente = ImageFont.load_default()
            lineas, actual = [], ""
            for w in (titulo or f.stem).split():
                if len(actual) + len(w) + 1 > 13 and actual:
                    lineas.append(actual); actual = w
                else:
                    actual = (actual + " " + w).strip()
            lineas.append(actual)
            for i, ln in enumerate(lineas[:7]):
                d.text((12, 14 + i * 18), ln[:14], fill=(255, 255, 255), font=fuente)
        destino.parent.mkdir(parents=True, exist_ok=True)
        im.save(destino, "JPEG", quality=78)
        return True
    except Exception:
        return False


def portada_datauri(carpeta: Path, rel: str) -> str:
    """La portada guardada (`rel`, relativa a biblioteca/) como data URI, o ''."""
    f = Path(carpeta) / "biblioteca" / rel
    return "data:image/jpeg;base64," + base64.b64encode(f.read_bytes()).decode() if rel and f.is_file() else ""


_STOP = set("with from that this their about which edition third second first fourth volume and for the los las del una por con para como mas pero sus book books libro libros".split())


def _tokens(texto: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", _norm(str(texto))) if w not in _STOP}


def _ruta_correcciones(carpeta: Path | None = None) -> Path:
    return Path(carpeta or carpeta_datos()) / "biblioteca" / "correcciones.json"


def recordar_correccion(m: dict, carpeta: Path | None = None) -> None:
    """Guarda lo que el usuario fijó a mano (género y subtema) con las palabras del nombre original: una obra parecida que se importe después se clasifica igual."""
    f = _ruta_correcciones(carpeta)
    lista = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    nombre = Path(m.get("origen", "")).stem or m.get("titulo", "")
    nueva = {"titulo": m.get("titulo", ""), "tokens": sorted(_tokens(nombre)), "genero": m.get("genero"), "subtema": m.get("subtema"), "hash": m.get("hash", "")}
    lista = [c for c in lista if c.get("hash") != nueva["hash"] or not nueva["hash"]] + [nueva]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")


def por_correcciones(nombre: str, carpeta: Path | None = None) -> dict | None:
    """La corrección guardada cuyo nombre se parece al de `nombre` (al menos 2 palabras y la mitad en común), o None."""
    f = _ruta_correcciones(carpeta)
    if not f.exists():
        return None
    tk = _tokens(nombre)
    mejor, mj = None, 0.0
    for c in json.loads(f.read_text(encoding="utf-8")):
        ct = set(c.get("tokens", []))
        com = len(tk & ct)
        j = com / max(len(tk | ct), 1)
        if com >= 2 and j >= .5 and j > mj:
            mejor, mj = c, j
    return mejor


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


def filtros_dialogo() -> tuple[str, str]:
    """Filtros del explorador de archivos de pywebview. Su formato es estricto: el texto solo admite letras, números y espacios (sin comas ni signos)."""
    return ("Documentos codigo y datos (" + ";".join("*" + e for e in sorted(EXT_IMPORTABLE)) + ")", "Todos los archivos (*.*)")


def opciones() -> dict:
    """Lo que ofrecen los desplegables: galaxias, tipos y subtemas (los temas del catálogo, las ramas de código y 'General')."""
    ramas = sorted(p.name for p in (RAIZ / "py" / "arbol_estadistica").iterdir() if p.is_dir() and not p.name.startswith("_")) if (RAIZ / "py" / "arbol_estadistica").is_dir() else []
    temas = [t["nombre"] for t in _catalogo()["temas"]]
    return {"generos": [{"id": k, "nombre": v} for k, v in GENEROS.items()],
            "galaxias": [{"id": k, "nombre": v} for k, v in GALAXIAS.items()], "tipos": [{"id": k, "nombre": v} for k, v in TIPOS.items()],
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


_WEB = {"fallo": False, "memo": {}}


def _materias_web(titulo: str) -> list[str]:
    """Materias de un título según Open Library (apoyo para clasificar). Si falla la red, no se vuelve a intentar en esta sesión."""
    if _WEB["fallo"]:
        return []
    if titulo not in _WEB["memo"]:
        try:
            from . import telescopio
            _WEB["memo"][titulo] = telescopio.materias_de(titulo)
        except Exception:
            _WEB["fallo"] = True
            return []
    return _WEB["memo"][titulo]


def _genero_materias(materias: list[str]) -> str | None:
    if not materias:
        return None
    t = " " + _norm(" ; ".join(materias)) + " "
    p = {g: len(r.findall(t)) for g, r in _GEN_RE.items()}
    g = max(p, key=p.get)
    return g if p[g] >= 2 else None


def clasificar(ruta: str | Path, carpeta: Path | None = None) -> dict:
    """Propone galaxia, subtema, tipo y título de un fichero, con el motivo. {'galaxia','subtema','tipo','titulo','motivo','paginas'}"""
    f = Path(ruta)
    carpeta = Path(carpeta or carpeta_datos())
    texto, paginas = _muestra(f)
    t = " " + _norm(texto[:40000]) + " "
    nombre = _norm(re.sub(r"[_\-.]+", " ", f.stem))
    puntos = _puntos_temas(t, nombre)
    (tid, tnombre), p = max(puntos.items(), key=lambda kv: kv[1]) if puntos else ((None, "General"), 0)
    fin = len(FINANZAS.findall(t)) + 4 * len(FINANZAS.findall(nombre))
    ext = f.suffix.lower()
    if ext in CODIGO_EXT:
        tipo = "codigo"
    elif ext in DATOS_EXT:
        tipo = "datos"
    elif ext == ".epub" or (ext == ".pdf" and paginas >= 60):
        tipo = "libro"
    elif ext == ".pdf":
        tipo = "articulo"
    elif ext in (".docx", ".md", ".pptx", ".rst", ".tex", ".html", ".htm"):
        tipo = "apuntes"
    else:
        tipo = "nota"
    gp = {g: len(r.findall(t)) + 6 * len(r.findall(nombre)) for g, r in _GEN_RE.items()}
    if p >= 6:
        gp["economia" if tid == "t_fin" else "estadistica"] += p        # lo que casa con los temas de estadística/finanzas también cuenta como ese género
    gp["economia"] += fin // 2
    genero = max(gp, key=gp.get) if max(gp.values()) >= 4 else "otro"
    if tipo == "codigo":
        genero = "tecnologia"
    subtema = tnombre if p >= 6 and genero in GENEROS_CON_TEMA else "General"
    if tipo == "codigo":
        galaxia, motivo = "codigo", f"archivo de código ({ext})"
    elif tipo == "libro":                                                # un libro va a Libros, sea de lo que sea; Finanzas y Notas son para documentos más cortos
        galaxia, motivo = "libros", f"{'EPUB' if ext == '.epub' else str(paginas) + ' páginas'}"
    elif fin >= 8 or (tid == "t_fin" and p >= 6):
        galaxia, motivo = "finanzas", f"vocabulario financiero ({fin} términos)"
    else:
        galaxia, motivo = "notas", "documento corto o de apuntes"
    if subtema != "General":
        motivo += f"; el tema «{subtema}» puntúa {p}"
    corr = por_correcciones(f.stem, carpeta)
    if corr:                                                              # algo parecido que corregiste a mano antes: se clasifica igual
        genero, subtema = corr["genero"] or genero, corr["subtema"] or subtema
        motivo += f"; como «{corr['titulo'][:30]}», que corregiste"
    caps, _ = capitulos(f)
    metodo, materias, s = "reglas", [], None
    web = None
    if not corr and tipo in ("libro", "articulo") and clasificador.WEB and len(f.stem.split()) >= 2:    # materias reales de la obra según Open Library (si hay red)
        materias = _materias_web(titulo_corto(f.stem))
        web = _genero_materias(materias)
    if not corr and tipo != "codigo" and clasificador.ACTIVO:                                  # parecido con ejemplos (embeddings locales) mezclado con las reglas; sin modelo, solo reglas
        s = clasificador.sugerir(clasificador.texto_libro(titulo_corto(f.stem), caps, re.sub(r"\s+", " ", texto[:1500])), carpeta)
        if s:
            nuevo, cambia = clasificador.decidir(gp, genero, s, web)
            if cambia:
                genero, metodo = nuevo, "parecido"
                subtema = tnombre if p >= 6 and genero in GENEROS_CON_TEMA else "General"
                motivo += f"; género «{GENEROS[genero]}» por parecido con ejemplos (margen {s['confianza']:.2f})"
        elif web and genero == "otro":
            genero, metodo = web, "web"
    elif web and genero == "otro" and not corr:
        genero, metodo = web, "web"
    if not corr and tipo != "codigo" and llm.ACTIVO and clasificador.dudoso(gp, s, web) and llm.disponible(carpeta):      # caso dudoso: se pregunta al LLM local (Ollama)
        r = llm.clasificar(titulo_corto(f.stem), caps, re.sub(r"\s+", " ", texto[:1500]), materias, {k: v for k, v in GENEROS.items()}, carpeta)
        if r:
            genero, metodo = r["genero"], "llm"
            subtema = tnombre if p >= 6 and genero in GENEROS_CON_TEMA else "General"
            motivo += f"; el LLM propone «{GENEROS[genero]}»: {r['motivo']}"
    if materias and metodo not in ("reglas", "llm"):
        motivo += f"; materias web: {', '.join(materias[:4])}"
    palabras = re.findall(r"[a-z]+", t[:20000])
    es, en = sum(w in _ES for w in palabras), sum(w in _EN for w in palabras)
    h = _sha1(f)
    dup = next((rel for rel, m in leer_metadatos(carpeta).items() if m.get("hash") == h), "")
    return {"galaxia": galaxia, "subtema": subtema, "genero": genero, "tipo": tipo, "titulo": titulo_corto(f.stem), "titulo_largo": f.stem, "motivo": motivo, "metodo": metodo, "materias_web": materias[:8], "paginas": paginas,
            "tamano": f.stat().st_size, "extension": ext.lstrip("."), "idioma": "es" if es > en else "en" if en else "", "duplicado": dup,
            "vista_previa": re.sub(r"\s+", " ", texto[:1500]).strip()[:380],
            "temas": [{"tema": nombre_t, "puntos": pt} for (_, nombre_t), pt in sorted(puntos.items(), key=lambda kv: -kv[1])[:4] if pt >= 3] if genero in GENEROS_CON_TEMA else [],
            "generos": [{"id": g, "nombre": GENEROS[g], "puntos": pt} for g, pt in sorted(gp.items(), key=lambda kv: -kv[1])[:4] if pt],
            "n_capitulos": len(caps), "capitulos": [c["titulo"] for c in caps[:6]]}


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
    """Metadatos de la biblioteca: los de este equipo (metadatos.json) más las referencias que llegaron por GitHub (referencias.json) de libros que aquí aún no están."""
    b = Path(carpeta) / "biblioteca"
    leer = lambda n: json.loads((b / n).read_text(encoding="utf-8")) if (b / n).exists() else {}
    return {**leer("referencias.json"), **leer("metadatos.json")}


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
            if f.suffix.lower() not in EXT_IMPORTABLE:
                raise ValueError(f"formato no admitido ({f.suffix or 'sin extensión'}); sirven {', '.join(sorted(EXT_IMPORTABLE))}")
            _prog(f"Analizando «{f.name[:40]}»", .02)
            h = _sha1(f)
            if h in hashes and not (base / hashes[h]).exists() and (base / hashes[h]).suffix.lower() == f.suffix.lower():     # la referencia llegó por GitHub y ahora tienes el libro: se restaura en su sitio
                rel0 = hashes[h]; (base / rel0).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, base / rel0)
                m0 = meta[rel0]
                salida.append({**r, "movido": False, "estado": "ok", "titulo": m0.get("titulo", ""), "galaxia": m0.get("galaxia", ""), "subtema": m0.get("subtema", ""), "genero": m0.get("genero", "otro"),
                               "tipo": m0.get("tipo", ""), "destino": str(base / rel0), "mensaje": "restaurado: ya estaba en tus referencias"})
                continue
            if h in hashes:
                salida.append({**r, "estado": "duplicado", "mensaje": f"ya estaba importado ({hashes[h]})"})
                continue
            auto = clasificar(f, carpeta)
            galaxia = d.get("galaxia") if d.get("galaxia") in GALAXIAS else auto["galaxia"]
            subtema = (d.get("subtema") or "").strip() or auto["subtema"]
            tipo = d.get("tipo") if d.get("tipo") in TIPOS else auto["tipo"]
            genero = d.get("genero") if d.get("genero") in GENEROS else auto["genero"]
            titulo = (d.get("titulo") or "").strip() or auto["titulo"]
            destino = base / galaxia / _slug(GENEROS[genero] if galaxia == "libros" else subtema)      # Libros: una carpeta por género
            destino.mkdir(parents=True, exist_ok=True)
            nombre = _slug(titulo)[:80] or "documento"                          # nombre corto: evita rutas larguísimas (límite de Windows) y es legible
            fin, n = destino / f"{nombre}{f.suffix}", 1
            while fin.exists():
                n += 1; fin = destino / f"{nombre}_{n}{f.suffix}"
            _prog(f"Copiando «{f.name[:40]}»", .06)
            shutil.copy2(f, fin)
            rel = fin.relative_to(base).as_posix()
            caps, pags = capitulos(fin)
            meta[rel] = {"capitulos": caps, "paginas": pags, "titulo": titulo, "galaxia": galaxia, "subtema": subtema, "genero": genero, "tipo": tipo, "etiquetas": (d.get("etiquetas") or "").strip(), "origen": str(f), "hash": h,
                         "fecha": datetime.now().isoformat(timespec="seconds"), "automatico": not (d.get("galaxia") or d.get("subtema") or d.get("tipo") or d.get("genero")) and (d.get("titulo") or auto["titulo"]).strip() == auto["titulo"],
                         "metodo": auto["metodo"], "motivo": auto["motivo"], "materias_web": auto.get("materias_web", []),
                         "propuesta": {"galaxia": auto["galaxia"], "subtema": auto["subtema"], "genero": auto["genero"], "tipo": auto["tipo"]}}
            hashes[h] = rel
            if tipo == "libro":
                nom = "portadas/" + h[:10] + ".jpg"
                if portada(fin, base / nom, titulo, genero):
                    meta[rel]["portada"] = nom
            movido = False
            if d.get("modo") == "mover" and fin.stat().st_size == f.stat().st_size:     # «mover»: el original desaparece de su carpeta (la copia queda en la biblioteca)
                try:
                    f.unlink()
                    movido = True
                except OSError:
                    pass
            salida.append({**r, "movido": movido, "estado": "ok", "titulo": titulo, "galaxia": galaxia, "subtema": subtema, "genero": genero, "tipo": tipo, "destino": str(fin), "mensaje": auto["motivo"]})
        except Exception as e:
            salida.append({**r, "estado": "error", "mensaje": str(e)})
    if any(s["estado"] == "ok" for s in salida):
        base.mkdir(parents=True, exist_ok=True)
        _guardar(carpeta, meta)
        if indexar_ahora:
            _prog("Indexando el texto…", .1)
            ind = indexar(db or carpeta / "indice.db", {}, carpeta=carpeta)
            sin = set(ind["sin_leer"])
            for s in salida:
                if s["estado"] == "ok" and s["destino"] in sin:
                    s["mensaje"] += " · sin indexar (¿falta `pip install pypdf`?)"
    return salida


def enriquecer(carpeta: Path | None = None) -> int:
    """Completa lo ya importado a lo que le falte (capítulos, nº de páginas, género): sirve para lo importado con versiones anteriores. Devuelve cuántos tocó."""
    carpeta = Path(carpeta or carpeta_datos()); meta = leer_metadatos(carpeta); n = 0
    for rel, m in meta.items():
        f = carpeta / "biblioteca" / rel
        if not f.is_file():
            continue
        if "capitulos" not in m:
            m["capitulos"], m["paginas"] = capitulos(f); n += 1
        if m.get("tipo") == "libro" and not m.get("portada"):
            nom = "portadas/" + m.get("hash", rel)[:10] + ".jpg"
            if portada(f, carpeta / "biblioteca" / nom, m.get("titulo", ""), m.get("genero", "otro")):
                m["portada"] = nom; n += 1
        if len(m.get("titulo", "")) > 60 or " -- " in m.get("titulo", ""):
            m["titulo"] = titulo_corto(m["titulo"]); n += 1
        if "genero" not in m:
            m["genero"] = clasificar(f, carpeta)["genero"]; n += 1
    if n:
        _guardar(carpeta, meta)
    return n


def reclasificar(carpeta: Path | None = None) -> list[tuple]:
    """Vuelve a clasificar (galaxia aparte: los ficheros no se mueven) el género y el subtema de lo importado con todo en «Automático»; lo que tú fijaste no se toca.
    Devuelve [(título, subtema antes, subtema ahora, género antes, género ahora)] de lo que cambió."""
    carpeta = Path(carpeta or carpeta_datos()); meta = leer_metadatos(carpeta); cambios = []
    for rel, m in meta.items():
        f = carpeta / "biblioteca" / rel
        if not f.is_file() or not m.get("automatico", False):
            continue
        c = clasificar(f, carpeta)
        if (c["subtema"], c["genero"]) != (m.get("subtema"), m.get("genero")):
            cambios.append((m.get("titulo", rel)[:40], m.get("subtema"), c["subtema"], m.get("genero"), c["genero"]))
            m["subtema"], m["genero"] = c["subtema"], c["genero"]
    if cambios:
        _guardar(carpeta, meta)
    return cambios


# ---------- gestionar lo importado (pestaña «Observatorio») ----------
CAMPOS = ("titulo", "galaxia", "genero", "subtema", "tipo", "etiquetas")


def _guardar(carpeta: Path, meta: dict) -> None:
    """Escribe metadatos.json (lo de este equipo) y referencias.json (lo mismo sin rutas del equipo: es lo que viaja por GitHub, aunque los PDF/EPUB no)."""
    base = Path(carpeta) / "biblioteca"
    base.mkdir(parents=True, exist_ok=True)
    esc = lambda d: json.dumps(d, ensure_ascii=False, indent=1)
    (base / "metadatos.json").write_text(esc(meta), encoding="utf-8")
    (base / "referencias.json").write_text(esc({rel: {k: v for k, v in m.items() if k != "origen"} for rel, m in sorted(meta.items())}), encoding="utf-8")


def _ficha(carpeta: Path, rel: str, m: dict, con_portada: bool = True) -> dict:
    f = Path(carpeta) / "biblioteca" / rel
    return {"rel": rel, "existe": f.is_file(), "titulo": m.get("titulo", ""), "titulo_largo": Path(m.get("origen", "")).stem or m.get("titulo", ""), "galaxia": m.get("galaxia", ""),
            "genero": m.get("genero", "otro"), "subtema": m.get("subtema", ""), "tipo": m.get("tipo", ""), "etiquetas": m.get("etiquetas", ""), "paginas": m.get("paginas", 0),
            "capitulos": len(m.get("capitulos", [])), "fecha": m.get("fecha", "")[:10], "automatico": bool(m.get("automatico")), "fecha_hora": m.get("fecha", ""), "metodo": m.get("metodo", ""), "motivo": m.get("motivo", ""), "extension": f.suffix.lstrip(".").lower(),
            "tamano": f.stat().st_size if f.is_file() else 0, "ruta": str(f), "portada": portada_datauri(carpeta, m.get("portada", "")) if con_portada else ""}


def listar(carpeta: Path | None = None) -> list[dict]:
    """Todo lo importado, ordenado por galaxia y título."""
    carpeta = Path(carpeta or carpeta_datos())
    return sorted((_ficha(carpeta, rel, m) for rel, m in leer_metadatos(carpeta).items()), key=lambda x: (x["galaxia"], x["titulo"].lower()))


def _galaxia_en_indice(db: Path, ruta: str, galaxia: str) -> None:
    con = _abrir(Path(db))
    con.execute("update trozos set coleccion = ? where ruta = ?", (galaxia, ruta))
    con.execute("update ficheros set coleccion = ? where ruta = ?", (galaxia, ruta))
    con.commit(); con.close()


def editar(rel: str, cambios: dict, carpeta: Path | None = None, db: Path | None = None) -> dict:
    """Cambia título, galaxia, género, subtema, tipo o etiquetas de un documento importado. El fichero no se mueve; el índice se pone al día y la corrección se recuerda
    (algo parecido que importes después se clasificará igual). Devuelve la ficha."""
    carpeta = Path(carpeta or carpeta_datos()); meta = leer_metadatos(carpeta)
    if rel not in meta:
        raise KeyError(f"no está en el observatorio: {rel}")
    m, antes = meta[rel], meta[rel].get("galaxia")
    for k, v in cambios.items():
        if k not in CAMPOS:
            continue
        v = str(v).strip()
        if (k == "galaxia" and v not in GALAXIAS) or (k == "genero" and v not in GENEROS) or (k == "tipo" and v not in TIPOS):
            raise ValueError(f"valor no válido para {k}: {v}")
        if k == "titulo" and not v:
            continue
        m[k] = v
    m["automatico"] = False
    _guardar(carpeta, meta)
    if m.get("galaxia") != antes:
        _galaxia_en_indice(db or carpeta / "indice.db", str(carpeta / "biblioteca" / rel), m["galaxia"])
    if {"genero", "subtema"} & set(cambios):
        recordar_correccion(m, carpeta)
    return _ficha(carpeta, rel, m)


def revisar(desde: str = "", hasta: str = "", carpeta: Path | None = None) -> list[dict]:
    """Lo importado entre dos fechas (AAAA-MM-DD, ambas opcionales), de más reciente a más antiguo, para revisar cómo se clasificó.
    Cada fila: fecha, título, galaxia, género, subtema, tipo, método (reglas|parecido|web), motivo, materias_web, propuesta y `corregido` (distinto de lo que propuso el sistema)."""
    carpeta = Path(carpeta or carpeta_datos()); filas = []
    for rel, m in leer_metadatos(carpeta).items():
        f = (m.get("fecha") or "")[:10]
        if (desde and f < desde) or (hasta and f > hasta):
            continue
        prop = m.get("propuesta") or {}
        filas.append({"rel": rel, "fecha": m.get("fecha", ""), "titulo": m.get("titulo", ""), "galaxia": m.get("galaxia"), "genero": m.get("genero"), "subtema": m.get("subtema"), "tipo": m.get("tipo"),
                      "metodo": m.get("metodo", ""), "motivo": m.get("motivo", ""), "materias_web": m.get("materias_web", []), "propuesta": prop,
                      "corregido": bool(prop) and any(prop.get(k) != m.get(k) for k in ("galaxia", "genero", "subtema", "tipo"))})
    return sorted(filas, key=lambda x: x["fecha"], reverse=True)


def reclasificar_uno(rel: str, carpeta: Path | None = None, db: Path | None = None) -> dict:
    """Vuelve a poner en «automático» la galaxia, el género y el subtema de un documento (según el contenido y tus correcciones guardadas). Devuelve la ficha."""
    carpeta = Path(carpeta or carpeta_datos()); meta = leer_metadatos(carpeta)
    m, f = meta[rel], carpeta / "biblioteca" / rel
    c = clasificar(f, carpeta)
    antes = m.get("galaxia")
    m["galaxia"], m["genero"], m["subtema"], m["automatico"] = c["galaxia"], c["genero"], c["subtema"], True
    _guardar(carpeta, meta)
    if m["galaxia"] != antes:
        _galaxia_en_indice(db or carpeta / "indice.db", str(f), m["galaxia"])
    return _ficha(carpeta, rel, m)


def borrar(rel: str, carpeta: Path | None = None, db: Path | None = None) -> bool:
    """Quita un documento del observatorio: borra SU COPIA (en biblioteca/), su portada, sus metadatos y su texto del índice. El original (de donde se importó) no se toca."""
    carpeta = Path(carpeta or carpeta_datos()); meta = leer_metadatos(carpeta)
    m = meta.pop(rel, None)
    if m is None:
        return False
    base = carpeta / "biblioteca"
    f = base / rel
    for x in (f, base / m["portada"] if m.get("portada") else None):
        if x is not None:
            try:
                x.unlink()
            except OSError:
                pass
    _guardar(carpeta, meta)
    con = _abrir(Path(db or carpeta / "indice.db"))
    con.execute("delete from trozos where ruta = ?", (str(f),))
    con.execute("delete from ficheros where ruta = ?", (str(f),))
    con.commit(); con.close()
    return True
