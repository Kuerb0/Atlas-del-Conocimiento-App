"""Guardián de RAM para procesos largos (evaluaciones, servidor del modelo): deja siempre un mínimo de memoria libre para que el ordenador no vaya a saltos.

    python herramientas/guarda_ram.py PATRON [PATRON ...] [--libre 1.0] [--sigue 1.8] [--max-gb 3.5] [--matar PATRON]

Cada 2 s mira la RAM disponible y cada 20 s recorta la RAM que los procesos no usan (EmptyWorkingSet: libera varios GB del servidor del modelo, cuyos pesos ya están en la GPU). Si aun así baja de `--libre` GB (por defecto 1), SUSPENDE los procesos de Python cuya línea de comandos contenga algún PATRON (nada se pierde: se reanudan solos
cuando hay más de `--sigue` GB libres). Con `--max-gb` y `--matar PATRON`, un proceso que pase de esa memoria (una fuga) se termina: si lo lanza un bucle de reinicio y guarda el avance
(como `evaluar_corpus.py`), sigue por donde iba con la memoria limpia. Solo toca procesos que coinciden con los patrones.
"""
from __future__ import annotations

import os
import sys
import time

import psutil

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def procesos(patrones: list[str]) -> list[psutil.Process]:
    out = []
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if p.pid != os.getpid() and "guarda_ram" not in " ".join(p.info["cmdline"] or []) and "python" in (p.info["name"] or "").lower() and any(x in " ".join(p.info["cmdline"] or []) for x in patrones):     # (sin tocarse a sí mismo: su línea de comandos lleva los patrones)
                out.append(p)
        except psutil.Error:
            pass
    return out


def recortar(p: psutil.Process) -> None:
    """Devuelve a Windows las páginas de RAM que el proceso no está usando ahora (EmptyWorkingSet): pasan a la caché y se vuelven a traer si hacen falta. Con un modelo ya cargado en la GPU libera varios GB."""
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x0100 | 0x0400, False, p.pid)
        if h:
            ctypes.windll.psapi.EmptyWorkingSet(h)
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:
        pass


def main() -> None:
    a = sys.argv[1:]
    opt = lambda n, d: type(d)(a[a.index(n) + 1]) if n in a else d
    libre, sigue, max_gb = opt("--libre", 1.0), opt("--sigue", 1.8), opt("--max-gb", 0.0)
    matar = [a[i + 1] for i, x in enumerate(a) if x == "--matar"]
    patrones = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--libre", "--sigue", "--max-gb", "--matar"))]
    suspendido, ultimo_recorte = False, 0.0
    print(f"vigilando {patrones}: pausa con menos de {libre} GB libres, sigue con más de {sigue} GB", flush=True)
    while True:
        disp = psutil.virtual_memory().available / 1e9
        if max_gb:
            for p in procesos(matar):
                try:
                    if p.memory_info().rss / 1e9 > max_gb:
                        print(f"{time.strftime('%H:%M:%S')} {p.pid} ocupa {p.memory_info().rss / 1e9:.1f} GB: lo termino para que lo reinicie el vigilante", flush=True)
                        p.kill()
                except psutil.Error:
                    pass
        if not suspendido and time.time() - ultimo_recorte > 20:                      # cada 20 s se recorta lo que no usan (antes de llegar a pausar nada)
            for p in procesos(patrones):
                recortar(p)
            ultimo_recorte, disp = time.time(), psutil.virtual_memory().available / 1e9
        if not suspendido and disp < libre:
            for p in procesos(patrones):
                try:
                    p.suspend()
                except psutil.Error:
                    pass
            suspendido = True
            print(f"{time.strftime('%H:%M:%S')} RAM libre {disp:.2f} GB: procesos en pausa", flush=True)
        elif suspendido and disp > sigue:
            for p in procesos(patrones):
                try:
                    p.resume()
                except psutil.Error:
                    pass
            suspendido = False
            print(f"{time.strftime('%H:%M:%S')} RAM libre {disp:.2f} GB: reanudo", flush=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
