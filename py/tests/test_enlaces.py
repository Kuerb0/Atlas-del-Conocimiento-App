"""Vídeos de YouTube/Vimeo como accesos directos .url: título y canal por oEmbed (simulado), clasificación e importación sin red."""
from conocimiento import enlaces, importar


def _atajo(tmp_path, url="https://www.youtube.com/watch?v=abc123", nombre="atajo"):
    f = tmp_path / f"{nombre}.url"
    f.write_text(f"[InternetShortcut]\nURL={url}\n", encoding="utf-8")
    return f


def _oembed(monkeypatch, titulo="La caída del Imperio romano: documental", canal="Historia en Vídeo"):
    monkeypatch.setattr(enlaces, "_memo", {})
    monkeypatch.setattr(enlaces.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("sin red")))
    enlaces._memo["https://www.youtube.com/watch?v=abc123"] = {"url": "https://www.youtube.com/watch?v=abc123", "plataforma": "youtube", "titulo": titulo, "canal": canal, "miniatura": ""}


def test_url_y_plataforma(tmp_path):
    assert enlaces.url_de(_atajo(tmp_path)) == "https://www.youtube.com/watch?v=abc123"
    assert enlaces.plataforma("https://youtu.be/xyz") == "youtube" and enlaces.plataforma("https://vimeo.com/123") == "vimeo" and enlaces.plataforma("https://ejemplo.com/v") == ""
    assert enlaces.url_de(tmp_path / "no_existe.url") == ""


def test_sin_red_el_nombre_del_atajo_hace_de_titulo(tmp_path, monkeypatch):
    monkeypatch.setattr(enlaces, "_memo", {})
    monkeypatch.setattr(enlaces.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("sin red")))
    f = _atajo(tmp_path, nombre="Documental Roma")
    assert enlaces.texto(f).startswith("Documental Roma") and enlaces.info(tmp_path / "otro.url") is None


def test_clasifica_un_video_como_tipo_video_en_libros(tmp_path, monkeypatch):
    _oembed(monkeypatch)
    f = _atajo(tmp_path)
    c = importar.clasificar(f, tmp_path)
    assert c["tipo"] == "video" and c["galaxia"] == "libros" and c["titulo"].startswith("La caída del Imperio romano") and c["url"].startswith("https://www.youtube.com")
    assert c["genero"] == "historia"                                          # «imperio romano» lo dice el título


def test_importa_el_video_y_guarda_la_url(tmp_path, monkeypatch):
    _oembed(monkeypatch)
    r = importar.importar([_atajo(tmp_path)], tmp_path, indexar_ahora=False)[0]
    assert r["estado"] == "ok" and r["tipo"] == "video"
    meta = importar.leer_metadatos(tmp_path)
    assert list(meta.values())[0]["url"].startswith("https://www.youtube.com")
