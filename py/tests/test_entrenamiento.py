"""Pestaña «Entrenamiento»: localizar corpus y entorno, lanzar (con subprocess falso) y parar."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import entrenamiento as ent


def _preparar(tmp_path, monkeypatch, venv=True):
    c = tmp_path / "corpus"
    (c / "enes" / "entrenamiento" / "datos").mkdir(parents=True)
    (c / "enes" / "entrenamiento" / "datos" / "train.jsonl").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("ARBOL_CORPUS", str(c))
    monkeypatch.delenv("ARBOL_VENV", raising=False)
    monkeypatch.setattr(ent, "venv_python", lambda: tmp_path / "v" / "Scripts" / "python.exe" if venv else None)
    monkeypatch.setattr(ent, "_soltar_gpu", lambda: None)
    return c


def test_estado_sin_entorno_avisa_y_no_lanza(tmp_path, monkeypatch):
    _preparar(tmp_path, monkeypatch, venv=False)
    e = ent.estado()
    assert e["disponible"] and not e["entorno"] and "preparar" in e["motivo"]
    assert "error" in ent.lanzar("ft2")


def test_lanzar_escribe_lote_y_marca_y_no_duplica(tmp_path, monkeypatch):
    c = _preparar(tmp_path, monkeypatch)

    class P:
        pid = 4242
    llamadas = []
    monkeypatch.setattr(ent.subprocess, "Popen", lambda *a, **k: llamadas.append(a) or P())
    monkeypatch.setattr(ent, "_vivo", lambda pid: True)
    r = ent.lanzar("mi ft/../3", "Qwen/Qwen2.5-3B-Instruct", biblioteca=False)
    assert r["ok"] and r["pid"] == 4242 and len(llamadas) == 1
    lote = (c / "enes" / "entrenamiento" / "_lanzar.bat").read_text(encoding="utf-8")
    assert "ARBOL_VENV" in lote and "entrenar" in lote and " datos " not in lote       # los datos ya existen y no se pidió sumar la biblioteca
    assert "mift3" in lote                                                               # el nombre se limpia (nada de rutas)
    assert json.loads((c / "enes" / "entrenamiento" / "_lanzado.json").read_text(encoding="utf-8"))["pid"] == 4242
    assert ent.estado()["entrenando"]["nombre"] == "mift3"
    assert "ya hay" in ent.lanzar("otro")["error"] and len(llamadas) == 1


def test_biblioteca_reconstruye_datos_y_modelo_desconocido_se_rechaza(tmp_path, monkeypatch):
    c = _preparar(tmp_path, monkeypatch)
    monkeypatch.setattr(ent.subprocess, "Popen", lambda *a, **k: type("P", (), {"pid": 1})())
    assert "modelo" in ent.lanzar("x", "evil/modelo")["error"]
    assert ent.lanzar("x", "Qwen/Qwen2.5-3B-Instruct", biblioteca=True)["ok"]
    assert " datos " in (c / "enes" / "entrenamiento" / "_lanzar.bat").read_text(encoding="utf-8")


def test_parar_sin_entrenamiento(tmp_path, monkeypatch):
    _preparar(tmp_path, monkeypatch)
    assert "error" in ent.parar()
