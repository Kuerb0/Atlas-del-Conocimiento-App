"""Vuelve a clasificar lo importado en tu biblioteca con las categorías y reglas de hoy y enseña qué cambiaría (género, subgénero, tipo, título). No toca nada salvo con --aplicar.

    python herramientas/estandarizar_biblioteca.py [CARPETA_CONOCIMIENTO] [--desde AAAA-MM-DD] [--sin-llm] [--aplicar] [--json salida.json] [--como criterio.json]

Cada obra se clasifica como si no estuviera importada (sus ejemplos son los demás), así lo que ves es lo que el sistema haría con un archivo nuevo, no una copia de sí mismo.
Con --aplicar, antes hace una copia de metadatos.json, referencias.json y correcciones.json en `biblioteca/_copia_antes_de_estandarizar/` y después cambia lo propuesto
(`importar.editar`, que además lo recuerda como corrección tuya) en las obras que no hayas tocado a mano. Lo que ya habías corregido tú no se modifica nunca.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from conocimiento import clasificador, importar, llm  # noqa: E402


def proponer(carpeta: Path, desde: str = "", con_llm: bool = True, como: dict | None = None) -> list[dict]:
    """`como`: {rel: campos} que se aplican a los ejemplos (los demás documentos) antes de clasificar: mide lo que acertaría el sistema con la biblioteca ya estandarizada."""
    meta, base = importar.leer_metadatos(carpeta), carpeta / "biblioteca"
    clasificador.WEB = False
    llm.ACTIVO = con_llm
    out = []
    for rel, m in sorted(meta.items(), key=lambda kv: kv[1].get("fecha", "")):
        f = base / rel
        if not f.is_file() or (desde and (m.get("fecha") or "")[:10] < desde):
            continue
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "biblioteca").mkdir()
            (tmp / "biblioteca" / "metadatos.json").write_text(json.dumps({r: {**x, **(como or {}).get(r, {})} for r, x in meta.items() if r != rel}, ensure_ascii=False), encoding="utf-8")
            if (base / "vectores.npz").exists():
                shutil.copy(base / "vectores.npz", tmp / "biblioteca" / "vectores.npz")
            for n in ("ajustes.json", "taxonomia.json"):
                if (carpeta / n).exists():
                    shutil.copy(carpeta / n, tmp / n)
            nombre = tmp / (Path(m.get("origen") or rel).stem + f.suffix)
            shutil.copy(f, nombre)
            c = importar.clasificar(nombre, tmp)
        out.append({"rel": rel, "automatico": bool(m.get("automatico")), "antes": {k: m.get(k, "") for k in ("genero", "subgenero", "tipo", "titulo")},
                    "ahora": {k: c.get(k, "") for k in ("genero", "subgenero", "tipo", "titulo")}, "revisar": c.get("revisar"), "motivos": c.get("motivos_revisar", [])})
        if len(out) % 20 == 0:
            print(f"  {len(out)} obras…", flush=True)
    return out


def aplicar(carpeta: Path, props: list[dict]) -> int:
    base = carpeta / "biblioteca"
    copia = base / "_copia_antes_de_estandarizar"
    copia.mkdir(exist_ok=True)
    for n in ("metadatos.json", "referencias.json", "correcciones.json"):
        if (base / n).exists():
            shutil.copy2(base / n, copia / n)
    cambiadas = 0
    for p in props:
        if not p["automatico"] or p["antes"] == p["ahora"]:
            continue
        importar.editar(p["rel"], {k: v for k, v in p["ahora"].items() if v != "" or k == "subgenero"}, carpeta)
        cambiadas += 1
    return cambiadas


if __name__ == "__main__":
    a = sys.argv[1:]
    pos = [x for x in a if not x.startswith("--") and (a.index(x) == 0 or not a[a.index(x) - 1].startswith("--"))]
    carpeta = Path(pos[0]) if pos else Path(importar.carpeta_datos())
    desde = a[a.index("--desde") + 1] if "--desde" in a else ""
    como = json.loads(Path(a[a.index("--como") + 1]).read_text(encoding="utf-8")) if "--como" in a else None
    props = proponer(carpeta, desde, con_llm="--sin-llm" not in a, como=como)
    cambian = [p for p in props if p["antes"] != p["ahora"]]
    print(f"{len(props)} obras · cambiarían {len(cambian)} · géneros nuevos: {Counter(p['ahora']['genero'] for p in cambian).most_common(6)}")
    if "--json" in a:
        Path(a[a.index("--json") + 1]).write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--aplicar" in a:
        print("aplicadas:", aplicar(carpeta, props), "(copia en biblioteca/_copia_antes_de_estandarizar/)")
