"""Almacenaje: reparto por galaxia y tipo, y diferencia entre Â«discoÂ» y Â«githubÂ» (.gitignore)."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conocimiento import almacenaje as a


def test_grupo_por_ruta():
    assert a.grupo("conocimiento/biblioteca/libros/historia/x.pdf") == "libros"
    assert a.grupo("conocimiento/biblioteca/raro/x.pdf") == "otros"
    assert a.grupo("conocimiento/modelos/models--x/blobs/a") == "modelos"
    assert a.grupo("py/arbol_estadistica/modelos/glm.py") == "codigo"
    assert a.grupo("py/visor/demos.js") == "demos" and a.grupo("teoria/glm.md") == "conceptos"
    assert a.grupo("visor_arbol.html") == "visor" and a.grupo("LEEME.txt") == "otros"


def test_medir_disco_y_github(tmp_path):
    (tmp_path / "py").mkdir(); (tmp_path / "py" / "a.py").write_bytes(b"x" * 100)
    (tmp_path / "libro.pdf").write_bytes(b"y" * 1000)
    (tmp_path / ".gitignore").write_bytes(b"*.pdf\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    r = a.medir(tmp_path)
    d = {g["id"]: g["bytes"] for g in r["disco"]["grupos"]}
    assert d["codigo"] == 100 and d["otros"] == 1000 + len("*.pdf\n")
    assert {t["id"] for t in r["disco"]["tipos"]} >= {"py", "pdf"}
    assert r["github"]["total"] == 100 + len("*.pdf\n")                # el pdf ignorado no sube
    assert r["github"]["total"] < r["disco"]["total"] and r["limite"] == 1 << 30
