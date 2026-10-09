"""Varias etiquetas por obra: uno o más géneros y uno o más subgéneros (máximo MAXIMO de cada), con un peso 0-1.

En los metadatos (`biblioteca/metadatos.json`) cada obra sigue teniendo `genero` y `subgenero` (la etiqueta PRINCIPAL: de ella dependen la carpeta donde vive el archivo,
las correcciones y el orden) y además `generos` = [{"id", "peso"}] y `subgeneros` = [{"genero", "id", "peso"}], con la principal siempre la primera. Lo importado con versiones
anteriores no tiene esas listas: `generos_de`/`subgeneros_de` las deducen de la etiqueta única.

Una etiqueta secundaria entra cuando puntúa a menos de `DELTA` (género) o `DELTA_SUB` (subgénero) del primero, medido en fracción de la escala máxima de puntos: es la misma
distancia que antes hacía saltar el aviso «género poco claro» (MARGEN_REVISAR); ahora, en vez de dudar, la obra lleva las dos etiquetas. Se ajusta con `evaluar_corpus.py --val`.
Módulo sin dependencias del paquete para que lo puedan importar todos.
"""
from __future__ import annotations

MAXIMO = 3          # etiquetas de género (y de subgénero) como mucho por obra
DELTA = 0.15        # una etiqueta secundaria de género puntúa a menos de DELTA · escala del primero (= clasificador.MARGEN_REVISAR); la escala es lo que puede valer una diferencia de puntos ahora (1 + el peso con que cuenta la cabeza supervisada)
DELTA_SUB = 0.03    # lo mismo para los subgéneros. Medido en 247 obras de validación sin LLM: F1 de subgénero 31 (0,00 y 0,03) frente a 29 (0,08); con 0,03 la real está entre las predichas el 40 %
PESO_MIN = 0.3      # peso mínimo de una etiqueta secundaria que viene del LLM


def peso_relativo(puntos: dict, id_: str, escala: float, delta: float) -> float:
    """Peso 0-1 de una etiqueta según lo cerca que está del primero: 1,0 con empate, 0,5 en el límite de `delta`, nunca menos de PESO_MIN."""
    top = max(puntos.values())
    lim = delta * escala or 1.0
    return round(max(PESO_MIN, min(1.0, 1 - 0.5 * (top - puntos.get(id_, top)) / lim)), 2)


def elegir(puntos: dict, escala: float, delta: float | None = None, maximo: int | None = None, principal: str | None = None, excluir: tuple = ("otro",)) -> list[tuple[str, float]]:
    """[(id, peso)] con la etiqueta principal primero (peso 1) y las que puntúan a menos de `delta · escala` del mejor, hasta `maximo`.
    `principal` fuerza cuál va primero (p. ej. la que decidió el LLM aunque no puntúe más). Con principal «otro» no hay secundarias."""
    if not puntos:
        return []
    delta, maximo = DELTA if delta is None else delta, maximo or MAXIMO               # (se leen al llamar, no al definir: evaluar_corpus.py los cambia con --set)
    orden = sorted(puntos, key=puntos.get, reverse=True)
    principal = principal if principal in puntos else orden[0]
    salida = [(principal, 1.0)]
    if principal in excluir:
        return salida
    top, lim = puntos[orden[0]], delta * escala
    for k in orden:
        if len(salida) >= maximo:
            break
        if k != principal and k not in excluir and puntos[k] > 0 and top - puntos[k] <= lim:
            salida.append((k, peso_relativo(puntos, k, escala, delta)))
    return salida


def generos_de(m: dict) -> list[str]:
    """Ids de género de una obra, la principal primero. Sin lista guardada: solo `genero`."""
    v = [e["id"] if isinstance(e, dict) else e for e in m.get("generos") or []]
    g = m.get("genero")
    return list(dict.fromkeys(([g] if g else []) + v))


def subgeneros_de(m: dict) -> list[tuple[str, str]]:
    """[(género, subgénero)] de una obra, la principal primero. Sin lista guardada: solo `genero`/`subgenero`."""
    v = [(e["genero"], e["id"]) for e in m.get("subgeneros") or [] if isinstance(e, dict)]
    p = (m.get("genero"), m.get("subgenero"))
    return list(dict.fromkeys(([p] if p[0] and p[1] else []) + v))


def pesos_genero(m: dict) -> dict:
    return {(e["id"] if isinstance(e, dict) else e): (e.get("peso", 1.0) if isinstance(e, dict) else 1.0) for e in m.get("generos") or []}


def _g(e) -> tuple:
    if isinstance(e, dict):
        return e["id"], e.get("peso", 1.0)
    return (e, 1.0) if isinstance(e, str) else (e[0], e[1] if len(e) > 1 else 1.0)


def _s(e) -> tuple:
    if isinstance(e, dict):
        return e["genero"], e["id"], e.get("peso", 1.0)
    return e[0], e[1], (e[2] if len(e) > 2 else 1.0)


def poner(m: dict, generos: list, subgeneros: list | None = None) -> dict:
    """Escribe en `m` las listas de etiquetas y deja `genero`/`subgenero` igual a la primera de cada lista.
    `generos`: [id | (id, peso) | {"id", "peso"}]; `subgeneros`: [(género, id) | (género, id, peso) | {"genero", "id", "peso"}]. Devuelve `m`."""
    gs = list({i: {"id": i, "peso": round(float(w), 2)} for i, w in map(_g, generos) if i}.values())[:MAXIMO]     # (el primero de cada id manda: el dict conserva el orden de inserción)
    m["generos"] = gs
    if gs:
        m["genero"] = gs[0]["id"]
    if subgeneros is not None:
        validos = {x["id"] for x in gs}
        ss = list({(g, i): {"genero": g, "id": i, "peso": round(float(w), 2)} for g, i, w in map(_s, subgeneros) if g in validos and i}.values())[:MAXIMO]
        m["subgeneros"] = ss
        m["subgenero"] = next((x["id"] for x in ss if x["genero"] == m.get("genero")), "")
    return m


def jaccard(a, b) -> float:
    """Parecido entre dos conjuntos de etiquetas (1 = iguales). Dos conjuntos vacíos cuentan como iguales."""
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 1.0
