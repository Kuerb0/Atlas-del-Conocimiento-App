"""Las demos del visor (visor/demos.js) se ejecutan sin navegador con un DOM mínimo: sin excepciones ni NaN."""
import shutil
import subprocess
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent


@pytest.mark.skipif(shutil.which("node") is None, reason="hace falta Node.js")
def test_demos_se_ejecutan_sin_errores():
    r = subprocess.run(["node", str(AQUI / "demos_stub.js"), str(AQUI.parent / "visor" / "demos.js")],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
