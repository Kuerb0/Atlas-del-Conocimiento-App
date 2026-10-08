"""Clasificador por parecido (embeddings): sugiere el género de un libro comparándolo con ejemplos, sin palabras clave.

Los ejemplos son (1) unas frases semilla por género y (2) lo que ya hay en tu biblioteca, contando más lo que corregiste a mano.
El modelo corre en local con `fastembed` (ONNX, sin PyTorch) y se descarga una vez a `conocimiento/modelos/`.
Si falta fastembed o el modelo, `sugerir` devuelve None y el importador sigue con las reglas de siempre.
Modelo: variable ARBOL_MODELO o `conocimiento/ajustes.json` {"modelo_embeddings": "..."}; ver `herramientas/comparar_clasificadores.py`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import threading

import numpy as np

from . import CARPETA, _norm

MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
ACTIVO = True            # False: solo reglas (los tests y el script de comparación lo usan)
WEB = True               # consultar Open Library por el título para sacar las materias de la obra (False: sin red)
PESO_WEB = 0.15          # lo que suma al género que dicen las materias web
MARGEN_DUDA = 0.05       # si el mejor género saca menos que esto al segundo, el caso es dudoso (y se pregunta al LLM si hay uno)
PESO_REGLAS = 1.0        # cuánto pesa lo que opinan las reglas (parte de los puntos que se llevaría cada género) frente al parecido
SATURA = 20              # con tantos puntos las reglas ya se consideran seguras
PESO_AUTOR = 0.3         # lo que suma el género (o subgénero) que ya tienen los otros libros del mismo autor, según cuántos haya (n / (n + 1))
PESO_CABEZA = 2.0        # lo que suma la probabilidad de un clasificador supervisado (regresión logística sobre los embeddings de TODOS los ejemplos); 0 = apagado. Validado: 53 → 68 % de acierto de género (evaluar_corpus.py)
PESO_CABEZA_SUB = 2.0    # lo mismo para el subgénero (un clasificador por género, con las frases de la taxonomía y tus libros de ese género)
LIBROS_CABEZA = (100, 400)   # la cabeza supervisada pesa 0 con 100 libros tuyos como ejemplos o menos y su peso completo con 400 o más: con pocos ejemplos EMPEORA (79 → 75 % con 73 obras), con cientos mejora 15 puntos
LIBROS_CABEZA_SUB = (20, 120)   # lo mismo para el subgénero, contando solo los libros de ese género
MARGEN_REVISAR = 0.15    # distancia entre el género ganador y el segundo, dividida entre la escala máxima de puntos (1 + PESO_CABEZA + PESO_REGLAS); por debajo se pide revisión manual.
                         # Calibrado con 232 obras de validación y el LLM: marca ~44 % de las obras y recoge ~67 % de los errores de género (lo no marcado acierta ~85 %). Más alto = más avisos
MARGEN_SUB_REVISAR = 0.03  # lo mismo para el subgénero (escala 1 + PESO_CABEZA_SUB)
WIKI = "auto"            # Wikipedia/Wikidata (webinfo.py) por título y autor: "auto" = solo si el LLM no está disponible (con LLM no suma: 86/66 frente a 86/68 en 73 obras; sin él sube 75/49 → 79/56); True = siempre; False = nunca (sin red)
PESO_WIKI = 0.6          # lo que suma el género que dice Wikidata de la obra (y 0,6 · el subgénero)
MIN_PARECIDO = 0.25      # por debajo, el libro no se parece a ningún género: se queda como lo dejaron las reglas (p. ej. «otro»)
_cache: dict = {}        # nombre del modelo -> función(textos) -> matriz normalizada; también guarda los vectores de las semillas

SEMILLAS = {
    "historia": ["Historia de imperios, guerras, reyes y civilizaciones antiguas y medievales", "History of empires, wars, revolutions and kingdoms through the centuries",
                 "Crónica de un periodo histórico, sus batallas, dinastías y consecuencias políticas"],
    "economia": ["Economía: mercados, oferta y demanda, inflación, crecimiento y política monetaria", "Finance and investing: stocks, bonds, portfolios, banks and business valuation",
                 "Riqueza, pobreza, comercio y desigualdad en la economía de los países"],
    "ensayo": ["Ensayo filosófico sobre la ética, la libertad, la verdad y el sentido de la vida", "Philosophy essay on reason, virtue, morality, metaphysics and human knowledge",
               "Reflexiones personales y pensamiento crítico sobre la condición humana"],
    "estadistica": ["Estadística y probabilidad: estimación, contrastes de hipótesis, regresión y modelos", "Mathematics: linear algebra, calculus, theorems, matrices and proofs",
                    "Statistical learning, Bayesian inference, random variables and data analysis"],
    "ciencia": ["Divulgación científica: física, química, biología, evolución y el universo", "Popular science on cosmology, genes, ecology, quantum physics and nature",
                "Ciencias naturales y experimentos: átomos, células, planetas y clima"],
    "novela": ["Novela de ficción con personajes, una trama, misterio, aventura o romance", "A novel: fiction story with characters, a detective, a quest or a family saga",
               "Cuento y narrativa literaria: protagonistas, crimen, amor y destino"],
    "biografia": ["Biografía de una persona: su infancia, su vida, su carrera y su muerte", "Memoir and autobiography: the life story of a famous person told in his own words",
                  "Memorias de un personaje histórico, su familia, sus años y su legado"],
    "politica": ["Política y sociedad: el Estado, el poder, la democracia, las elecciones y los gobiernos", "Political theory, nationalism, international relations, ideology and public policy",
                 "Análisis del poder, los partidos, las instituciones y los conflictos internacionales"],
    "tecnologia": ["Programación y software: código, algoritmos, lenguajes, bases de datos y desarrollo", "Computer science and technology: networks, operating systems, internet and artificial intelligence",
                   "Manual técnico de informática, ingeniería de software y sistemas"],
    "psicologia": ["Psicología y salud mental: emociones, conducta, terapia, trastornos y cerebro", "Psychology of thinking, habits, therapy, anxiety, behavior and wellbeing",
                   "Cómo piensan y sienten las personas: sesgos cognitivos, personalidad y bienestar"],
    "arte": ["Arte, música, pintura, cine, arquitectura, poesía y literatura", "Art history and culture: painters, composers, film, theatre, poems and design",
             "Historia del arte y la música: movimientos, estilos, artistas y obras"],
}


def semillas_todas(carpeta: Path | str | None = None) -> dict:
    """SEMILLAS de los 12 géneros de siempre + las de los géneros nuevos, sacadas de las frases de sus subgéneros (3 semillas por género)."""
    from . import taxonomia
    s = {g: list(v) for g, v in SEMILLAS.items()}
    for g, subs in taxonomia.cargar(carpeta or CARPETA)[1].items():
        if g not in s and subs:
            s[g] = ["; ".join(x[2] for x in subs[:2]), "; ".join(x[3] for x in subs[:2]), "; ".join(x[2] for x in subs[2:4]) or subs[0][2]]
    return s


def modelo(carpeta: Path | str = CARPETA) -> str:
    if os.environ.get("ARBOL_MODELO"):
        return os.environ["ARBOL_MODELO"]
    f = Path(carpeta) / "ajustes.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("modelo_embeddings") or MODELO
    except (OSError, ValueError):
        return MODELO


_candado = threading.RLock()        # cargar el modelo y entrenar la cabeza una sola vez aunque varios hilos clasifiquen a la vez (evaluar_corpus.py usa hilos)


def _embedder(nombre: str, carpeta: Path | str = None):  # los modelos son de todos los proyectos: siempre en CARPETA/modelos
    with _candado:
        return _embedder_(nombre)


def _embedder_(nombre: str):
    if nombre not in _cache:
        from fastembed import TextEmbedding
        m = TextEmbedding(model_name=nombre, cache_dir=str(Path(CARPETA) / "modelos"))

        memo: dict = {}                                          # texto -> vector: los ejemplos de la biblioteca no se vuelven a calcular en cada archivo

        def emb(textos):
            with _candado:
                nuevos = [t for t in dict.fromkeys(textos) if t not in memo]
                if nuevos:
                    v = np.array(list(m.embed(nuevos)), dtype=float)
                    memo.update(zip(nuevos, v / np.linalg.norm(v, axis=1, keepdims=True)))
                return np.array([memo[t] for t in textos])
        _cache[nombre] = emb
    return _cache[nombre]


def preparar(carpeta: Path | str | None = None) -> str:
    """Descarga (si falta) el modelo de embeddings y comprueba que funciona. Lo usa el instalador (`python -m conocimiento modelos`). Devuelve un mensaje; lanza excepción si no se pudo."""
    carpeta = Path(carpeta or CARPETA)
    nombre = modelo(carpeta)
    v = _embedder(nombre, carpeta)(["prueba del modelo"])
    return f"modelo {nombre} listo ({v.shape[1]} dimensiones) en {Path(CARPETA) / 'modelos'}"


_CAP_VACIO = __import__("re").compile(r"^\W*(?:chapter|cap[ií]tulo|cap\.?|part|parte|book|libro|section)?\W*(?:m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})|\d+)?\W*$", __import__("re").I)


def texto_libro(titulo: str, capitulos: list, vista: str = "") -> str:
    """Lo que se compara de un libro: título, los primeros capítulos y el principio del texto."""
    caps = "; ".join(x for x in ((c["titulo"] if isinstance(c, dict) else str(c)) for c in capitulos[:12]) if not _CAP_VACIO.match(x))[:400]       # «Chapter II.», «III» o «Parte 2» no dicen nada
    return f"{titulo}. {caps}. {vista[:700]}".strip()


def autor_de(nombre: str) -> str:
    """Autor según el nombre del archivo («Título - Autor»): el último tramo tras « - », normalizado; "" si no parece un nombre."""
    partes = [x.strip() for x in str(nombre).split(" - ")]
    a = _norm(partes[-1]).strip() if len(partes) > 1 else ""
    return a if 1 <= len(a.split()) <= 5 and not any(c.isdigit() for c in a) else ""


def _del_autor(autor: str, carpeta: Path | str) -> list[dict]:
    """Metadatos de los libros de la biblioteca cuyo archivo original tenía ese autor."""
    if not autor:
        return []
    try:
        from .importar import leer_metadatos
        return [m for m in leer_metadatos(Path(carpeta)).values() if autor_de(Path(m.get("origen", "")).stem or m.get("titulo", "")) == autor]
    except Exception:
        return []


def _sesgo_autor(autor: str, clave: str, carpeta: Path | str, filtro=lambda m: True) -> dict:
    """{valor de `clave`: bonus} según lo que ya tienen los otros libros de ese autor (los que cumplen `filtro`)."""
    ms = [m for m in _del_autor(autor, carpeta) if filtro(m) and m.get(clave)]
    return {v: PESO_AUTOR * sum(m[clave] == v for m in ms) / (len(ms) + 1) for v in {m[clave] for m in ms}}


def _ejemplos(carpeta: Path | str) -> list[tuple[str, str, float]]:
    """(texto, género, peso): las semillas (peso 1) y lo importado (1,5; 2,5 si lo corregiste a mano)."""
    ej = [(t, g, 1.0) for g, ts in semillas_todas(carpeta).items() for t in ts]
    try:
        from .importar import GENEROS, leer_metadatos
        for m in leer_metadatos(Path(carpeta)).values():
            if m.get("genero") in GENEROS and m.get("genero") != "otro":
                ej.append((texto_libro(m.get("titulo", ""), m.get("capitulos", []), extra_ejemplo(m)), m["genero"], 1.5 if m.get("automatico") else 2.5))
    except Exception:
        pass
    return ej


def vecinos(texto: str, carpeta: Path | str, k: int = 6) -> list[dict]:
    """Los k libros ya clasificados de tu biblioteca más parecidos al texto: [{'titulo','autor','genero','subgenero'}]. Son los ejemplos que se le enseñan al LLM."""
    if not ACTIVO or _cache.get("fallo") or k <= 0:
        return []
    try:
        from .importar import GENEROS, leer_metadatos
        ms = [m for m in leer_metadatos(Path(carpeta)).values() if m.get("genero") in GENEROS and m["genero"] != "otro"]
        if not ms:
            return []
        emb = _embedder(modelo(carpeta), carpeta)
        X = emb([texto_libro(m.get("titulo", ""), m.get("capitulos", []), extra_ejemplo(m)) for m in ms])
        orden = np.argsort(-(X @ emb([texto])[0]))[:k]
        return [{"titulo": ms[i].get("titulo", ""), "autor": autor_de(Path(ms[i].get("origen", "")).stem), "genero": ms[i]["genero"], "subgenero": ms[i].get("subgenero", "")} for i in orden]
    except Exception:
        return []


_cabezas: dict = {}


def _cabeza(ej: list, X):
    """Regresión logística multinomial entrenada con los ejemplos (semillas + biblioteca). Se guarda por contenido: con los mismos ejemplos no se vuelve a entrenar."""
    clave = hash(tuple(e[0] for e in ej))
    with _candado:
        return _cabeza_(clave, ej, X)


def _cabeza_(clave, ej, X):
    if clave not in _cabezas:
        from sklearn.linear_model import LogisticRegression
        y = [e[1] for e in ej]
        if len(set(y)) < 2:
            _cabezas[clave] = None
        else:
            _cabezas[clave] = LogisticRegression(C=10.0, max_iter=500, class_weight="balanced").fit(X, y, sample_weight=[e[2] for e in ej])
    return _cabezas[clave]


def extra_ejemplo(m: dict) -> str:
    """El texto que se suma al título y los capítulos de un libro de la biblioteca cuando hace de ejemplo: sus etiquetas y su descripción de Wikipedia (si la tuvo al importarse)."""
    return " ".join(x for x in (m.get("web_resumen", ""), m.get("etiquetas", "")) if x).strip()


def fuerza(n: int, rango: tuple) -> float:
    """0 si hay `rango[0]` ejemplos o menos, 1 con `rango[1]` o más, lineal entre medias: cuánto fiarse de un clasificador supervisado según los ejemplos propios que tiene."""
    return min(1.0, max(0.0, (n - rango[0]) / (rango[1] - rango[0])))


def sugerir(texto: str, carpeta: Path | str | None = None, autor: str = "", pistas: dict | None = None) -> dict | None:
    """{'genero', 'confianza' (margen sobre el segundo), 'puntos': {género: parecido}} o None si no hay modelo."""
    if not ACTIVO or _cache.get("fallo"):
        return None
    carpeta = Path(carpeta or CARPETA)
    try:
        emb = _embedder(modelo(carpeta), carpeta)
        ej = _ejemplos(carpeta)
        X = emb([e[0] for e in ej])
        q = emb([texto])[0]
    except Exception:
        _cache["fallo"] = True                                   # sin fastembed o sin modelo (p. ej. sin internet la primera vez): no se reintenta en cada archivo
        return None
    sims = X @ q
    puntos = {}
    for g in {e[1] for e in ej}:
        v = sorted((s + .04 * (e[2] - 1) for s, e in zip(sims, ej) if e[1] == g), reverse=True)[:2]
        puntos[g] = float(np.mean(v))
    peso = PESO_CABEZA * fuerza(sum(e[2] > 1 for e in ej), LIBROS_CABEZA)
    if peso:
        clf = _cabeza(ej, X)
        if clf is not None:
            for g, pr in zip(clf.classes_, clf.predict_proba(q.reshape(1, -1))[0]):
                if g in puntos:
                    puntos[g] += peso * float(pr)
    for g, b in _sesgo_autor(autor, "genero", carpeta).items():
        if g in puntos:
            puntos[g] += b
    for g, w in (pistas or {}).items():                                   # lo que dice Wikidata de la obra
        if g in puntos:
            puntos[g] += PESO_WIKI * w
    orden = sorted(puntos, key=puntos.get, reverse=True)
    return {"genero": orden[0], "confianza": puntos[orden[0]] - puntos[orden[1]], "puntos": {g: round(puntos[g], 3) for g in orden}}


_PARADA = set("para como pero sobre entre desde hasta este esta estos estas the and for with from that this their about which sus los las del una por con".split())


def _palabras(t: str) -> set:
    return {w for w in __import__("re").findall(r"[a-z]{4,}", _norm(t)) if w not in _PARADA}


def subgenero(texto: str, genero: str, carpeta: Path | str | None = None, autor: str = "", pistas: dict | None = None) -> dict | None:
    """Subgénero (de la taxonomía del género) que mejor describe el texto: {'id','nombre','confianza','puntos': {id: 0-100}} o None si el género no tiene subgéneros.
    Con modelo de embeddings compara con las frases del subgénero y con lo que ya tienes en esa categoría; sin modelo, por palabras en común."""
    from . import taxonomia
    carpeta = Path(carpeta or CARPETA)
    subs = taxonomia.subgeneros(genero, carpeta)
    if not subs:
        return None
    puntos = None
    if ACTIVO and not _cache.get("fallo"):
        try:
            emb = _embedder(modelo(carpeta), carpeta)
            ej = [(s[2], s[0], 1.0) for s in subs] + [(s[3], s[0], 1.0) for s in subs]
            try:
                from .importar import leer_metadatos
                ids = {s[0] for s in subs}
                for m in leer_metadatos(carpeta).values():
                    if m.get("genero") == genero and m.get("subgenero") in ids:
                        ej.append((texto_libro(m.get("titulo", ""), m.get("capitulos", []), extra_ejemplo(m)), m["subgenero"], 1.5 if m.get("automatico") else 2.5))
            except Exception:
                pass
            X, q = emb([e[0] for e in ej]), emb([texto])[0]
            sims = X @ q
            puntos = {}
            for sid in ids:
                v = sorted((s + .04 * (e[2] - 1) for s, e in zip(sims, ej) if e[1] == sid), reverse=True)[:2]
                puntos[sid] = float(np.mean(v))
            peso = PESO_CABEZA_SUB * fuerza(sum(e[2] > 1 for e in ej), LIBROS_CABEZA_SUB)
            if peso:
                clf = _cabeza(ej, X)
                if clf is not None:
                    for sid, pr in zip(clf.classes_, clf.predict_proba(q.reshape(1, -1))[0]):
                        if sid in puntos:
                            puntos[sid] += peso * float(pr)
            for sid, b in _sesgo_autor(autor, "subgenero", carpeta, lambda m: m.get("genero") == genero).items():
                if sid in puntos:
                    puntos[sid] += b
            for sid, w in (pistas or {}).items():
                if sid in puntos:
                    puntos[sid] += PESO_WIKI * w
        except Exception:
            _cache["fallo"] = True
            puntos = None
    if puntos is None:                                                   # sin modelo: palabras en común con las frases del subgénero
        pt = _palabras(texto)
        puntos = {s[0]: len(pt & _palabras(s[2] + " " + s[3])) / (len(_palabras(s[2] + " " + s[3])) ** .5 or 1) for s in subs}
        if not any(puntos.values()):
            return None
    orden = sorted(puntos, key=puntos.get, reverse=True)
    segundo = puntos[orden[1]] if len(orden) > 1 else 0.0
    return {"id": orden[0], "nombre": taxonomia.nombre_sub(genero, orden[0], carpeta), "confianza": puntos[orden[0]] - segundo,
            "puntos": {sid: round(100 * puntos[sid], 1) for sid in orden[:4]}}


def decidir(reglas: dict, genero_reglas: str, parecido: dict, web: str | None = None) -> tuple[str, bool]:
    """Mezcla lo que opinan las reglas ({género: puntos}) con el parecido: gana el género con más (parecido + peso · cuota de las reglas · su seguridad).
    `web` es el género que sugieren las materias de Open Library (voto pequeño). Devuelve (género, ¿cambia lo que decían las reglas?). Si nada se parece (MIN_PARECIDO) se respeta a las reglas."""
    p = parecido["puntos"]
    if max(p.values()) < MIN_PARECIDO:
        return genero_reglas, False
    sc = puntuar(reglas, parecido, web)
    g = max(sc, key=sc.get)
    return g, g != genero_reglas


def puntuar(reglas: dict, parecido: dict, web: str | None = None) -> dict:
    """Puntos finales por género: parecido + peso · cuota de las reglas · su seguridad (+ voto web)."""
    p = parecido["puntos"]
    tot, fuerza = sum(reglas.values()) or 1, max(reglas.values(), default=0)
    return {g: p[g] + PESO_REGLAS * reglas.get(g, 0) / tot * min(1, fuerza / SATURA) + (PESO_WEB if g == web else 0) for g in p}


def dudoso(reglas: dict, parecido: dict | None, web: str | None = None) -> bool:
    """¿Está poco claro el género? Sin parecido: reglas flojas. Con parecido: nada se le parece (MIN_PARECIDO) o el mejor apenas gana al segundo (MARGEN_DUDA)."""
    if not parecido:
        return max(reglas.values(), default=0) < 10
    if max(parecido["puntos"].values()) < MIN_PARECIDO:
        return True
    v = sorted(puntuar(reglas, parecido, web).values(), reverse=True)
    return v[0] - v[1] < MARGEN_DUDA
