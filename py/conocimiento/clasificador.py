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

import numpy as np

from . import CARPETA

MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
ACTIVO = True            # False: solo reglas (los tests y el script de comparación lo usan)
PESO_REGLAS = 1.0        # cuánto pesa lo que opinan las reglas (parte de los puntos que se llevaría cada género) frente al parecido
SATURA = 20              # con tantos puntos las reglas ya se consideran seguras
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


def modelo(carpeta: Path | str = CARPETA) -> str:
    if os.environ.get("ARBOL_MODELO"):
        return os.environ["ARBOL_MODELO"]
    f = Path(carpeta) / "ajustes.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("modelo_embeddings") or MODELO
    except (OSError, ValueError):
        return MODELO


def _embedder(nombre: str, carpeta: Path | str = None):  # los modelos son de todos los proyectos: siempre en CARPETA/modelos
    if nombre not in _cache:
        from fastembed import TextEmbedding
        m = TextEmbedding(model_name=nombre, cache_dir=str(Path(CARPETA) / "modelos"))

        memo: dict = {}                                          # texto -> vector: los ejemplos de la biblioteca no se vuelven a calcular en cada archivo

        def emb(textos):
            nuevos = [t for t in dict.fromkeys(textos) if t not in memo]
            if nuevos:
                v = np.array(list(m.embed(nuevos)), dtype=float)
                memo.update(zip(nuevos, v / np.linalg.norm(v, axis=1, keepdims=True)))
            return np.array([memo[t] for t in textos])
        _cache[nombre] = emb
    return _cache[nombre]


def texto_libro(titulo: str, capitulos: list, vista: str = "") -> str:
    """Lo que se compara de un libro: título, los primeros capítulos y el principio del texto."""
    caps = "; ".join((c["titulo"] if isinstance(c, dict) else str(c)) for c in capitulos[:8])
    return f"{titulo}. {caps}. {vista[:700]}".strip()


def _ejemplos(carpeta: Path | str) -> list[tuple[str, str, float]]:
    """(texto, género, peso): las semillas (peso 1) y lo importado (1,5; 2,5 si lo corregiste a mano)."""
    ej = [(t, g, 1.0) for g, ts in SEMILLAS.items() for t in ts]
    try:
        from .importar import GENEROS, leer_metadatos
        for m in leer_metadatos(Path(carpeta)).values():
            if m.get("genero") in GENEROS and m.get("genero") != "otro":
                ej.append((texto_libro(m.get("titulo", ""), m.get("capitulos", []), m.get("etiquetas", "")), m["genero"], 1.5 if m.get("automatico") else 2.5))
    except Exception:
        pass
    return ej


def sugerir(texto: str, carpeta: Path | str | None = None) -> dict | None:
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
    orden = sorted(puntos, key=puntos.get, reverse=True)
    return {"genero": orden[0], "confianza": puntos[orden[0]] - puntos[orden[1]], "puntos": {g: round(puntos[g], 3) for g in orden}}


def decidir(reglas: dict, genero_reglas: str, parecido: dict) -> tuple[str, bool]:
    """Mezcla lo que opinan las reglas ({género: puntos}) con el parecido: gana el género con más (parecido + peso · cuota de las reglas · su seguridad).
    Devuelve (género, ¿cambia lo que decían las reglas?). Si nada se parece (MIN_PARECIDO) se respeta a las reglas."""
    p = parecido["puntos"]
    if max(p.values()) < MIN_PARECIDO:
        return genero_reglas, False
    tot, fuerza = sum(reglas.values()) or 1, max(reglas.values(), default=0)
    sc = {g: p[g] + PESO_REGLAS * reglas.get(g, 0) / tot * min(1, fuerza / SATURA) for g in p}
    g = max(sc, key=sc.get)
    return g, g != genero_reglas
