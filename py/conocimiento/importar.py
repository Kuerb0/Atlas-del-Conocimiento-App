"""Importador: copia ficheros a `conocimiento/biblioteca/<galaxia>/<subtema>/`, los clasifica (galaxia, subtema, tipo) y los indexa para el buscador.

Por defecto lo decide solo (`clasificar`); cualquier dato que pases (galaxia, subtema, tipo, etiquetas) manda sobre lo automático.
Galaxia automática: finanzas si domina el vocabulario financiero; si no, libros (PDF/EPUB largos) o notas. Subtema automático: el tema del catálogo de conceptos
(«Inferencia y contrastes», «Regresión y GLM»…) con más coincidencias. Los metadatos van en `biblioteca/metadatos.json` (ruta relativa -> datos).

Uso: `python -m conocimiento importar f1.pdf f2.docx [-g libros] [-s "Inferencia y contrastes"] [-t libro]`.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import shutil
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

from . import CARPETA, DB, EXT, RAIZ, _extraer, _norm, indexar

GALAXIAS = {"codigo": "Código", "conceptos": "Conceptos", "demos": "Demos y guías", "finanzas": "Finanzas", "libros": "Libros", "notas": "Notas y enlaces"}
TIPOS = {"libro": "Libro", "articulo": "Artículo", "apuntes": "Apuntes", "nota": "Nota", "otro": "Otro"}
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
        elif ext in (".md", ".txt"):
            caps = [{"titulo": m.strip(), "pagina": None} for m in re.findall(r"(?m)^#{1,3}\s+(.+)$", f.read_text(encoding="utf-8", errors="replace"))][:80]
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


def clasificar(ruta: str | Path) -> dict:
    """Propone galaxia, subtema, tipo y título de un fichero, con el motivo. {'galaxia','subtema','tipo','titulo','motivo','paginas'}"""
    f = Path(ruta)
    texto, paginas = _muestra(f)
    t = " " + _norm(texto[:40000]) + " "
    nombre = _norm(re.sub(r"[_\-.]+", " ", f.stem))
    puntos = _puntos_temas(t, nombre)
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
    gp = {g: len(r.findall(t)) + 6 * len(r.findall(nombre)) for g, r in _GEN_RE.items()}
    if p >= 6:
        gp["economia" if tid == "t_fin" else "estadistica"] += p        # lo que casa con los temas de estadística/finanzas también cuenta como ese género
    gp["economia"] += fin // 2
    genero = max(gp, key=gp.get) if max(gp.values()) >= 4 else "otro"
    subtema = tnombre if p >= 6 and genero in GENEROS_CON_TEMA else "General"
    if tipo == "libro":                                                  # un libro va a Libros, sea de lo que sea; Finanzas y Notas son para documentos más cortos
        galaxia, motivo = "libros", f"{'EPUB' if ext == '.epub' else str(paginas) + ' páginas'}"
    elif fin >= 8 or (tid == "t_fin" and p >= 6):
        galaxia, motivo = "finanzas", f"vocabulario financiero ({fin} términos)"
    else:
        galaxia, motivo = "notas", "documento corto o de apuntes"
    if subtema != "General":
        motivo += f"; el tema «{subtema}» puntúa {p}"
    caps, _ = capitulos(f)
    palabras = re.findall(r"[a-z]+", t[:20000])
    es, en = sum(w in _ES for w in palabras), sum(w in _EN for w in palabras)
    h = _sha1(f)
    dup = next((rel for rel, m in leer_metadatos(carpeta_datos()).items() if m.get("hash") == h), "")
    return {"galaxia": galaxia, "subtema": subtema, "genero": genero, "tipo": tipo, "titulo": titulo_corto(f.stem), "titulo_largo": f.stem, "motivo": motivo, "paginas": paginas,
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
            genero = d.get("genero") if d.get("genero") in GENEROS else auto["genero"]
            titulo = (d.get("titulo") or "").strip() or auto["titulo"]
            destino = base / galaxia / _slug(GENEROS[genero] if galaxia == "libros" else subtema)      # Libros: una carpeta por género
            destino.mkdir(parents=True, exist_ok=True)
            nombre = _slug(titulo)[:80] or "documento"                          # nombre corto: evita rutas larguísimas (límite de Windows) y es legible
            fin, n = destino / f"{nombre}{f.suffix}", 1
            while fin.exists():
                n += 1; fin = destino / f"{nombre}_{n}{f.suffix}"
            shutil.copy2(f, fin)
            rel = fin.relative_to(base).as_posix()
            caps, pags = capitulos(fin)
            meta[rel] = {"capitulos": caps, "paginas": pags, "titulo": titulo, "galaxia": galaxia, "subtema": subtema, "genero": genero, "tipo": tipo, "etiquetas": (d.get("etiquetas") or "").strip(), "origen": str(f), "hash": h,
                         "fecha": datetime.now().isoformat(timespec="seconds"), "automatico": not (d.get("galaxia") or d.get("subtema") or d.get("tipo") or d.get("genero")) and (d.get("titulo") or auto["titulo"]).strip() == auto["titulo"]}
            hashes[h] = rel
            salida.append({**r, "estado": "ok", "titulo": titulo, "galaxia": galaxia, "subtema": subtema, "genero": genero, "tipo": tipo, "destino": str(fin), "mensaje": auto["motivo"]})
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


def enriquecer(carpeta: Path | None = None) -> int:
    """Completa lo ya importado a lo que le falte (capítulos, nº de páginas, género): sirve para lo importado con versiones anteriores. Devuelve cuántos tocó."""
    carpeta = Path(carpeta or carpeta_datos()); meta = leer_metadatos(carpeta); n = 0
    for rel, m in meta.items():
        f = carpeta / "biblioteca" / rel
        if not f.is_file():
            continue
        if "capitulos" not in m:
            m["capitulos"], m["paginas"] = capitulos(f); n += 1
        if len(m.get("titulo", "")) > 60 or " -- " in m.get("titulo", ""):
            m["titulo"] = titulo_corto(m["titulo"]); n += 1
        if "genero" not in m:
            m["genero"] = clasificar(f)["genero"]; n += 1
    if n:
        (carpeta / "biblioteca" / "metadatos.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return n


def reclasificar(carpeta: Path | None = None) -> list[tuple]:
    """Vuelve a clasificar (galaxia aparte: los ficheros no se mueven) el género y el subtema de lo importado con todo en «Automático»; lo que tú fijaste no se toca.
    Devuelve [(título, subtema antes, subtema ahora, género antes, género ahora)] de lo que cambió."""
    carpeta = Path(carpeta or carpeta_datos()); meta = leer_metadatos(carpeta); cambios = []
    for rel, m in meta.items():
        f = carpeta / "biblioteca" / rel
        if not f.is_file() or not m.get("automatico", False):
            continue
        c = clasificar(f)
        if (c["subtema"], c["genero"]) != (m.get("subtema"), m.get("genero")):
            cambios.append((m.get("titulo", rel)[:40], m.get("subtema"), c["subtema"], m.get("genero"), c["genero"]))
            m["subtema"], m["genero"] = c["subtema"], c["genero"]
    if cambios:
        (carpeta / "biblioteca" / "metadatos.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return cambios
