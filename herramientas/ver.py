"""Regenera el visor y, si la app está en modo vivo (acceso directo con --vivo), la recarga y la coloca en `destino`.

Uso (desde la carpeta principal):
    python herramientas/ver.py                      # solo regenera: la app se recarga sola
    python herramientas/ver.py cerebro              # ...y vuelve al cerebro
    python herramientas/ver.py galaxia:codigo       # ...y entra en una galaxia (codigo, conceptos, demos, finanzas)
    python herramientas/ver.py ajustar_logit        # ...y muestra una función, concepto o demo por su nombre
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if len(sys.argv) > 1:
    (RAIZ / ".foco").write_text(" ".join(sys.argv[1:]) + "\n", encoding="utf-8")      # primero el foco: la recarga lo lee al terminar de cargar
subprocess.run([sys.executable, str(RAIZ / "py" / "construir_visor.py")], cwd=RAIZ, check=True)
