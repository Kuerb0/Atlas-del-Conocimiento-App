"""Información de una obra desde Wikipedia y Wikidata, con sus APIs oficiales (no se rascan páginas): descripción corta, tipo («novela», «obra literaria») y género
(«fantasía», «ciencia ficción»…). Sirve de apoyo a la clasificación: un libro moderno que el texto no deja claro casi siempre tiene su ficha.

Es optativo (`clasificador.WIKI`, o `ARBOL_WIKI=no`): sin red o con la red apagada todo sigue como antes. Respeta a los servidores: una petición cada `INTERVALO` s,
reintentos con espera si responden 429, descanso de 2 minutos tras varios fallos seguidos y caché en disco (`conocimiento/webinfo_cache.json`), así que cada obra se pregunta una sola vez.
Solo sale el título y el autor.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import CARPETA, _norm

INTERVALO = 1.0                  # segundos mínimos entre dos peticiones (todas las de este módulo)
ESPERA = 10                      # segundos de espera por petición
UA = "ArbolEstadistica/1.11 (https://github.com/Kuerb0/Arbol_de_la_estadistica; biblioteca personal que clasifica libros) python-urllib"      # Wikimedia pide nombre de la herramienta y un contacto
_cerrojo, _cache_lock = threading.Lock(), threading.Lock()
_estado: dict = {"ultimo": 0.0, "fallos": 0, "descanso": 0.0, "cache": None, "nuevos": 0}
_etiq: dict = {}                    # Q-id -> nombre (se repiten mucho: «literary work», «novel»…)

# Tipo/género según Wikidata o el resumen → subgénero de novela (id de taxonomia.py). El primero que case gana.
SUB_NOVELA = [("historica", r"historical (?:novel|fiction)|novela historica"), ("negra", r"detective|crime|mystery|noir|novela negra|policiaca"), ("thriller", r"thriller|espionage|spy"),
              ("scifi", r"science fiction|ciencia ficcion|dystopi|space opera|cyberpunk"), ("fantasia", r"fantasy|fantasia|sword and sorcery"), ("terror", r"horror|gothic|terror|vampire"),
              ("romance", r"romance|romantic|romantica"), ("juvenil", r"children|young adult|juvenil|infantil|bildungsroman")]


def _ruta(carpeta: Path | str | None = None) -> Path:
    return Path(carpeta or CARPETA) / "webinfo_cache.json"


def _cargar(carpeta: Path | str | None) -> dict:
    if _estado["cache"] is None:
        try:
            _estado["cache"] = json.loads(_ruta(carpeta).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _estado["cache"] = {}
    return _estado["cache"]


def guardar(carpeta: Path | str | None = None) -> None:        # (los tests sustituyen _estado y no llevan «nuevos»: por eso .get)
    """Escribe la caché en disco (se llama al acabar una tanda; guardar en cada obra sería lento)."""
    with _cache_lock:
        if _estado["cache"] is None:                                  # no se ha leído ni usado: no hay nada que escribir (y no se pisa la caché que hay en disco)
            return
        try:
            _ruta(carpeta).write_text(json.dumps(_estado["cache"], ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass


def activo() -> bool:
    return os.environ.get("ARBOL_WIKI", "").lower() not in ("no", "0", "off") and time.time() >= _estado["descanso"]


def _get(url: str) -> dict:
    """GET con ritmo máximo, reintentos ante 429/5xx y descanso tras fallos seguidos. Lanza la excepción si no hay forma."""
    ultimo_error = None
    for intento in range(4):
        with _cerrojo:
            time.sleep(max(0.0, _estado["ultimo"] + INTERVALO - time.time()))
            _estado["ultimo"] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=ESPERA) as r:
                _estado["fallos"] = 0
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            ultimo_error = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(30.0, float(e.headers.get("Retry-After") or 0) or 2.0 ** (intento + 1)))
                continue
            break
        except Exception as e:                                       # sin red, DNS…
            ultimo_error = e
            time.sleep(1.5)
    _estado["fallos"] += 1
    if _estado["fallos"] >= 3:
        _estado["descanso"], _estado["fallos"] = time.time() + 120, 0
    raise ultimo_error or RuntimeError("sin respuesta")


def _api(lang_o_host: str, **params) -> dict:
    host = "www.wikidata.org" if lang_o_host == "wikidata" else f"{lang_o_host}.wikipedia.org"
    return _get(f"https://{host}/w/api.php?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2}))


def _apellido(autor: str) -> str:
    partes = [p for p in _norm(autor).replace(",", " ").split() if len(p) > 2]
    return partes[-1] if partes else ""


def _etiquetas(ids: list[str]) -> dict:
    if not ids:
        return {}
    nuevos = [i for i in ids if i not in _etiq]
    if nuevos:
        d = _api("wikidata", action="wbgetentities", ids="|".join(nuevos[:50]), props="labels", languages="en|es")["entities"]
        _etiq.update({k: (v.get("labels", {}).get("en") or v.get("labels", {}).get("es") or {}).get("value", "") for k, v in d.items()})
    return {i: _etiq.get(i, "") for i in ids}


def _de_wikidata(qids: list[str]) -> dict:
    """{qid: (tipos, géneros)} de varias entidades de Wikidata a la vez (2 peticiones en total), con los nombres en inglés (o español)."""
    if not qids:
        return {}
    ents = _api("wikidata", action="wbgetentities", ids="|".join(qids), props="claims")["entities"]

    def ids(e, p):
        return [x["mainsnak"]["datavalue"]["value"]["id"] for x in e.get("claims", {}).get(p, []) if x.get("mainsnak", {}).get("datavalue")]
    crudo = {q: (ids(e, "P31"), ids(e, "P136")) for q, e in ents.items()}
    lab = _etiquetas(sorted({i for t, g in crudo.values() for i in t + g}))
    return {q: ([lab[i] for i in t if lab.get(i)], [lab[i] for i in g if lab.get(i)]) for q, (t, g) in crudo.items()}


def es_obra(tipos: list[str]) -> bool:
    """¿Wikidata dice que es una obra escrita (novela, ensayo, libro…) y no una persona, una película o un personaje?"""
    t = " ".join(tipos).lower()
    return bool(re.search(r"literary work|novel|book|essay|treatise|short story|written work|publication|poem|play\b|writing|text\b|non-fiction|scholarly|monograph", t)) and not re.search(r"\bhuman\b|film|fictional|television|taxon|album|musical", t)


def genero_de(tipos: list[str], generos: list[str], resumen: str) -> str:
    """Género (clave de GENEROS) que sugieren el tipo, el género y la descripción de una obra; "" si no dice nada. Las obras de ficción son «novela»."""
    from .telescopio import genero_desde_materias
    t = _norm(" ".join(tipos + generos) + " " + resumen[:200])
    if re.search(r"\bnovel|\bfiction\b|\bnovela|\bcuento|short story|\bfantasy|\bnovella", t):
        return "novela"
    g = genero_desde_materias(tipos + generos + [resumen[:200]])
    return "" if g == "otro" else g


def subgenero_novela(texto: str) -> str:
    """Subgénero de novela que sugiere un texto («novela de fantasía de 1990…»); "" si no dice nada."""
    t = _norm(texto)
    for sid, patron in SUB_NOVELA:
        if re.search(patron, t):
            return sid
    return ""


def buscar(titulo: str, autor: str = "", idiomas: tuple = ("en", "es"), carpeta: Path | str | None = None) -> dict | None:
    """{'pagina', 'lang', 'resumen', 'tipos', 'generos', 'subgenero'} de la obra en Wikipedia/Wikidata, o None si no la encuentra (o no hay red).
    Se busca «título autor» y se acepta la página cuya introducción nombra al autor (así «Niebla» no se confunde con un hongo)."""
    if not activo() or not titulo.strip():
        return None
    clave = _norm(titulo).strip() + "|" + _norm(autor).strip()
    with _cache_lock:
        cache = _cargar(carpeta)
        if clave in cache:
            return cache[clave] or None
    ap, res = _apellido(autor), None
    try:
        for lang in idiomas:
            d = _api(lang, action="query", generator="search", gsrsearch=f"{titulo} {autor}".strip(), gsrlimit=5, gsrnamespace=0, prop="extracts|pageprops", exintro=1, explaintext=1,
                     exsentences=4, exlimit="max", ppprop="wikibase_item")
            paginas = sorted(d.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99))
            cands = []
            for p in paginas:
                ext = p.get("extract") or ""
                if not ext or re.search(r"may refer to|puede referirse|disambiguation|desambiguaci", ext[:200], re.I):
                    continue
                if ap and ap not in _norm(ext):                      # sin el autor en la introducción no es esa obra
                    continue
                if not ap and _norm(titulo) not in _norm(p.get("title", "")):
                    continue
                cands.append(p)
            wd = _de_wikidata([p["pageprops"]["wikibase_item"] for p in cands if p.get("pageprops", {}).get("wikibase_item")])
            for p in cands:
                tipos, gens = wd.get(p.get("pageprops", {}).get("wikibase_item"), ([], []))
                if tipos and not es_obra(tipos):                     # su ficha, la de una película o la de un personaje: no es el libro
                    continue
                ext = p["extract"]
                res = {"pagina": p["title"], "lang": lang, "resumen": re.sub(r"\s+", " ", ext).strip()[:500], "tipos": tipos, "generos": gens,
                       "subgenero": subgenero_novela(" ".join(gens + [ext[:240]])), "genero": genero_de(tipos, gens, ext)}
                break
            if res:
                break
    except Exception:
        return None                                                  # sin red o caído: no se guarda (se volverá a intentar)
    with _cache_lock:
        _cargar(carpeta)[clave] = res or {}
        _estado["nuevos"] = _estado.get("nuevos", 0) + 1
        guardar_ya = _estado["nuevos"] % 10 == 0
    if guardar_ya:
        guardar(carpeta)
    return res
