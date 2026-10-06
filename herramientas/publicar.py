"""Publica una versión: genera los instaladores, comprueba que no hay datos privados, hace commit y push.

Uso (desde la carpeta principal):
    python herramientas/publicar.py "qué ha cambiado"            # instaladores + commit + push
    python herramientas/publicar.py "qué ha cambiado" --tests    # antes pasa los tests (unos 3 min)
    python herramientas/publicar.py "qué ha cambiado" --sin-push # solo commit local

Antes de usarlo, sube la versión en py/VERSION.txt, py/pyproject.toml y __version__ (ver CLAUDE.md).
En instaladores/ solo queda la versión actual: las anteriores se apartan a anteriores/ (que git ignora).
"""
from __future__ import annotations

import base64
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# Palabras que no deben llegar a un repositorio público (escritas por trozos para que este fichero no las contenga).
PRIVADO = re.compile("|".join(["N" + "TT", r"\bAu" + "di\\b", "Mu" + "tua", "Mi" + "guel", "Ant" + "[oó]n", "cu" + "erv", "mespi" + "nosa"]))


def ejecutar(*orden: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(orden, cwd=RAIZ, check=True, **kw)


def texto(orden: list[str]) -> str:
    return subprocess.run(orden, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8").stdout


def revisar_privado() -> list[str]:
    """Busca palabras privadas en los ficheros rastreados y dentro de los instaladores (texto y bloques base64)."""
    malos = []
    for rel in texto(["git", "ls-files", "-z"]).split("\0"):
        p = RAIZ / rel
        if not rel or rel == "herramientas/publicar.py" or not p.is_file() or p.suffix.lower() in {".ico", ".png", ".webp"}:
            continue
        try:
            contenido = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in PRIVADO.finditer(contenido):
            malos.append(f"{rel}: «{m.group(0)}»")
            break
    for bat in (RAIZ / "instaladores").glob("*.bat"):
        t = bat.read_text(encoding="utf-8")
        sin_b64 = re.sub(r":::BEGIN ([^|\n]+)\|b64\n.*?\n:::END", "", t, flags=re.S)   # el texto base64 de un binario puede contener una palabra por azar: se comprueba abajo, ya decodificado
        for m in PRIVADO.finditer(sin_b64):
            malos.append(f"{bat.name}: «{m.group(0)}»")
            break
        for b in re.finditer(r":::BEGIN ([^|\n]+)\|b64\n(.*?)\n:::END", t, re.S):
            try:
                d = base64.b64decode(b.group(2).replace("\n", "")).decode("utf-8", "ignore")
            except ValueError:
                continue
            m = PRIVADO.search(d)
            if m:
                malos.append(f"{bat.name} → {b.group(1)}: «{m.group(0)}»")
    return malos


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    mensaje = args[0]
    version = (RAIZ / "py" / "VERSION.txt").read_text(encoding="utf-8").strip()

    if "--tests" in sys.argv:
        print("Pasando los tests...")
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=RAIZ / "py", check=True)

    print("Regenerando el visor...")
    ejecutar(sys.executable, "py/construir_visor.py")

    carpeta = RAIZ / "instaladores"
    apartados = RAIZ / "anteriores" / "instaladores_antiguos"
    apartados.mkdir(parents=True, exist_ok=True)
    for viejo in carpeta.glob("*.bat"):
        if version not in viejo.name:
            shutil.move(str(viejo), str(apartados / viejo.name))

    print(f"Generando los instaladores de la {version}...")
    ejecutar(sys.executable, "herramientas/generar_instaladores.py")

    malos = revisar_privado()
    if malos:
        print("\nPARO: hay datos privados que no deben publicarse:")
        for m in malos:
            print("  -", m)
        return 1

    for rel in texto(["git", "ls-files", "--others", "--exclude-standard", "-z"]).split("\0"):      # basura de 1-2 bytes que crea el entorno (ver .gitignore)
        f = RAIZ / rel
        if rel and f.is_file() and not f.suffix and f.stat().st_size <= 8:
            f.unlink()
            print("Borrado fichero basura:", rel)
    ejecutar("git", "add", "-A")
    if not texto(["git", "status", "--porcelain"]).strip():
        print("No hay cambios que publicar.")
        return 0
    ejecutar("git", "commit", "-q", "-m", f"v{version}: {mensaje}")
    print(texto(["git", "log", "--oneline", "-1"]).strip())
    if "--sin-push" in sys.argv:
        print("Commit hecho (sin push).")
        return 0
    ejecutar("git", "push", "origin", "HEAD")
    print(f"Publicado: v{version}. Tus amigos lo reciben con «Fetch / Pull» en GitHub Desktop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
