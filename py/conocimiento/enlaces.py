"""Enlaces a vídeos (YouTube, Vimeo): el título y el canal salen del oEmbed oficial de cada plataforma (sin clave y sin rascar la página).

Un enlace entra al importador como un acceso directo `.url` (lo que crea el navegador al arrastrar una dirección al escritorio o a una carpeta). No se descarga el vídeo ni su
transcripción: con el título, el canal y, si la obra tiene ficha en Wikipedia (documentales), su descripción, se clasifica como cualquier otro documento.
Solo sale la dirección del vídeo hacia YouTube/Vimeo. Sin red: el nombre del acceso directo hace de título.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

UA = "arbol-estadistica/1.0 (biblioteca personal) python-urllib"
OEMBED = {"youtube": "https://www.youtube.com/oembed?format=json&url=", "vimeo": "https://vimeo.com/api/oembed.json?url="}
_memo: dict = {}


def url_de(f: Path | str) -> str:
    """La dirección de un acceso directo `.url` (línea `URL=…` del formato INI de Windows); "" si no la tiene."""
    try:
        t = Path(f).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.search(r"(?im)^\s*URL\s*=\s*(\S+)", t)
    return m.group(1).strip() if m else ""


def plataforma(url: str) -> str:
    """'youtube' | 'vimeo' | '' según la dirección."""
    h = (urllib.parse.urlparse(url).hostname or "").lower()
    if h in ("youtu.be", "youtube.com") or h.endswith(".youtube.com"):
        return "youtube"
    if h == "vimeo.com" or h.endswith(".vimeo.com"):
        return "vimeo"
    return ""


def info(f: Path | str) -> dict | None:
    """{'url', 'plataforma', 'titulo', 'canal', 'miniatura'} del vídeo de un acceso directo (o de una dirección), o None si no es de una plataforma conocida o no responde."""
    url = str(f) if str(f).startswith("http") else url_de(f)
    p = plataforma(url)
    if not p:
        return None
    if url not in _memo:
        try:
            req = urllib.request.Request(OEMBED[p] + urllib.parse.quote(url, safe=""), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.loads(r.read().decode("utf-8"))
            _memo[url] = {"url": url, "plataforma": p, "titulo": re.sub(r"\s+", " ", d.get("title", "")).strip(), "canal": d.get("author_name", "").strip(), "miniatura": d.get("thumbnail_url", "")}
        except Exception:
            _memo[url] = {"url": url, "plataforma": p, "titulo": "", "canal": "", "miniatura": ""}          # sin red o vídeo no disponible: se clasifica por el nombre del acceso directo
    return _memo[url]


def miniatura(url: str, limite: int = 2_000_000) -> bytes | None:
    """La imagen de portada del vídeo (https, hasta 2 MB), o None."""
    if not url.startswith("https://"):
        return None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=8) as r:
            datos = r.read(limite + 1)
        return datos if 0 < len(datos) <= limite and datos[:3] in (b"\xff\xd8\xff", b"\x89PN", b"RIF") else None
    except Exception:
        return None


def texto(f: Path | str) -> str:
    """Lo que se lee de un vídeo para clasificarlo e indexarlo: título, canal y plataforma."""
    i = info(f)
    nombre = Path(str(f)).stem
    if not i:
        return nombre
    return "\n".join(x for x in (i["titulo"] or nombre, f"Canal: {i['canal']}" if i["canal"] else "", f"Vídeo de {i['plataforma'].capitalize()}", i["url"]) if x)
