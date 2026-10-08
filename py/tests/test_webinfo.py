"""webinfo: Wikipedia/Wikidata por título y autor, sin red (las respuestas se simulan)."""
import json

from conocimiento import webinfo


def _falso(monkeypatch, paginas, entidades):
    llamadas = []

    def api(que, **p):
        llamadas.append((que, p.get("action")))
        if p.get("action") == "query":
            return {"query": {"pages": paginas}}
        if p.get("action") == "wbgetentities" and p.get("props") == "claims":
            return {"entities": entidades}
        return {"entities": {"Q1": {"labels": {"en": {"value": "literary work"}}}, "Q2": {"labels": {"en": {"value": "fantasy"}}}, "Q9": {"labels": {"en": {"value": "human"}}}}}
    monkeypatch.setattr(webinfo, "_api", api)
    monkeypatch.setattr(webinfo, "_estado", {"ultimo": 0.0, "fallos": 0, "descanso": 0.0, "cache": None})
    return llamadas


def _ent(tipo, genero=None):
    c = {"P31": [{"mainsnak": {"datavalue": {"value": {"id": tipo}}}}]}
    if genero:
        c["P136"] = [{"mainsnak": {"datavalue": {"value": {"id": genero}}}}]
    return {"claims": c}


def test_encuentra_la_obra_por_titulo_y_autor_y_deduce_genero(tmp_path, monkeypatch):
    pag = [{"index": 1, "title": "Mort", "extract": "Mort is a fantasy novel by British writer Terry Pratchett.", "pageprops": {"wikibase_item": "Q5"}}]
    _falso(monkeypatch, pag, {"Q5": _ent("Q1", "Q2")})
    r = webinfo.buscar("Mort", "terry pratchett", ("en",), tmp_path)
    assert r["pagina"] == "Mort" and r["genero"] == "novela" and r["subgenero"] == "fantasia" and r["generos"] == ["fantasy"]


def test_rechaza_la_ficha_del_autor_y_la_que_no_nombra_al_autor(tmp_path, monkeypatch):
    pag = [{"index": 1, "title": "Terry Pratchett", "extract": "Terry Pratchett was an English author. Mort is one of his works.", "pageprops": {"wikibase_item": "Q7"}},
           {"index": 2, "title": "Mort (album)", "extract": "Mort is an album by some band.", "pageprops": {"wikibase_item": "Q8"}}]
    _falso(monkeypatch, pag, {"Q7": _ent("Q9")})
    assert webinfo.buscar("Mort", "terry pratchett", ("en",), tmp_path) is None


def test_la_cache_evita_repetir_peticiones_y_se_guarda_en_disco(tmp_path, monkeypatch):
    pag = [{"index": 1, "title": "Mort", "extract": "Mort is a fantasy novel by Terry Pratchett.", "pageprops": {"wikibase_item": "Q5"}}]
    llamadas = _falso(monkeypatch, pag, {"Q5": _ent("Q1", "Q2")})
    webinfo.buscar("Mort", "Terry Pratchett", ("en",), tmp_path)
    n = len(llamadas)
    webinfo.buscar("Mort", "Terry Pratchett", ("en",), tmp_path)
    assert len(llamadas) == n
    webinfo.guardar(tmp_path)
    assert "mort|terry pratchett" in json.loads((tmp_path / "webinfo_cache.json").read_text(encoding="utf-8"))


def test_sin_red_devuelve_none_y_no_cachea_el_fallo(tmp_path, monkeypatch):
    def roto(*a, **k):
        raise OSError("sin red")
    monkeypatch.setattr(webinfo, "_api", roto)
    monkeypatch.setattr(webinfo, "_estado", {"ultimo": 0.0, "fallos": 0, "descanso": 0.0, "cache": None})
    assert webinfo.buscar("Mort", "Terry Pratchett", ("en",), tmp_path) is None
    assert "mort|terry pratchett" not in (webinfo._estado["cache"] or {})


def test_es_obra_y_subgenero_de_novela():
    assert webinfo.es_obra(["literary work"]) and webinfo.es_obra(["novel"]) and not webinfo.es_obra(["human"]) and not webinfo.es_obra(["film"])
    assert webinfo.subgenero_novela("a science fiction novel") == "scifi" and webinfo.subgenero_novela("una novela histórica") == "historica" and webinfo.subgenero_novela("un ensayo") == ""
    assert webinfo.genero_de(["literary work"], ["fantasy"], "a novel") == "novela" and webinfo.genero_de(["literary work"], ["essay"], "treatise on economics") != "novela"
