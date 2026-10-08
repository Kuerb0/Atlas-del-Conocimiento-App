"""Publica la rama de un worktree en main SIN arrastrar los datos personales del usuario (su biblioteca).

    python herramientas/publicar_seguro.py "qué cambió" --rama claude/mi-rama [--ensayo]

Por qué existe: `publicar.py` hace `git add -A` y construye el visor leyendo `conocimiento/`; si en main hay datos tuyos sin commitear (`conocimiento/biblioteca/referencias.json` modificado,
portadas nuevas) los publicaría, y su comprobación de datos privados se negaría a seguir (nombres de autores). Aquí:
  1. los ficheros de `conocimiento/` sin commitear se apartan a una carpeta temporal y se devuelven al acabar (aunque falle);
  2. la rama se trae a main con `git merge --squash` (un solo commit por entrega, como pide el CLAUDE.md);
  3. `publicar.py` corre con ARBOL_CONOCIMIENTO apuntando a una carpeta vacía: el visor y los instaladores salen sin tu biblioteca.
`--ensayo`: lo hace todo en un clon temporal de main y sin push (ensayo general). Después hay que volver a construir tu visor local: `python py/construir_visor.py` en main.
Antes: subir la versión en py/VERSION.txt, py/pyproject.toml y py/arbol_estadistica/__init__.py, pasar los tests y dejar la rama con todo commiteado.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")        # la consola de Windows (cp1252) no sabe imprimir todo lo que dice publicar.py
args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args or "--rama" not in sys.argv:
    print(__doc__)
    raise SystemExit(2)
mensaje, RAMA, ensayo = args[0], sys.argv[sys.argv.index("--rama") + 1], "--ensayo" in sys.argv
if mensaje == RAMA:
    mensaje = args[1]
MAIN = Path(subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, text=True, cwd=Path(__file__).parent).stdout.strip()).parent


def sh(*a, cwd, check=True, env=None):
    r = subprocess.run(a, cwd=cwd, check=check, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.stdout.strip():
        print(r.stdout.strip()[-1500:])
    if r.stderr.strip() and r.returncode != 0:
        print(r.stderr.strip()[-1500:])
    return r


if ensayo:
    raiz = Path(tempfile.mkdtemp(prefix="ensayo_publicar_")) / "repo"
    sh("git", "clone", "-q", str(MAIN), str(raiz), cwd=MAIN)
    sh("git", "fetch", "-q", str(MAIN), f"{RAMA}:{RAMA}", cwd=raiz)
else:
    raiz = MAIN
apartados, backup = [], Path(tempfile.mkdtemp(prefix="datos_usuario_"))
try:
    if not ensayo:
        for linea in sh("git", "status", "--porcelain", "--", "conocimiento", cwd=raiz).stdout.splitlines():
            rel = linea[3:].strip().strip('"')
            f = raiz / rel
            if f.is_dir():
                continue
            (backup / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, backup / rel)
            apartados.append((rel, linea[:2]))
        print(f"apartados {len(apartados)} ficheros de datos del usuario en {backup}")
        for rel, estado in apartados:
            if estado.strip() == "??":
                (raiz / rel).unlink()
            else:
                sh("git", "checkout", "--", rel, cwd=raiz)
    sh("git", "merge", "--squash", RAMA, cwd=raiz)
    env = {**os.environ, "ARBOL_CONOCIMIENTO": tempfile.mkdtemp(prefix="conocimiento_vacio_"), "PYTHONIOENCODING": "utf-8"}
    r = sh(sys.executable, "herramientas/publicar.py", mensaje, *(["--sin-push"] if ensayo else []), cwd=raiz, check=False, env=env)
    print("publicar.py terminó con código", r.returncode)
    if r.returncode != 0:
        raise SystemExit(r.returncode)
finally:
    if not ensayo:
        for rel, estado in apartados:
            if (backup / rel).exists():
                (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup / rel, raiz / rel)
        print(f"restaurados {len(apartados)} ficheros del usuario")
