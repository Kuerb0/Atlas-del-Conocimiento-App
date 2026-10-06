"""Abre el Árbol de la estadística en su propia ventana, como una aplicación.

Uso: doble clic en el acceso directo del Escritorio (lo crean el instalador y el actualizador),
o desde una consola:  pythonw py/arbol_app.pyw

Cómo abre, por orden de preferencia:
  1. pywebview: ventana nativa de Windows con el motor de Edge (WebView2). Sin barras de navegador.
     Solo así funciona «Probar» (ejecutar el código de ejemplo por celdas): el visor habla con Python.
  2. Edge o Chrome en modo aplicación (--app), si pywebview no está instalado.
  3. El navegador predeterminado, como último recurso.
Si visor_arbol.html no existe todavía, lo genera antes con py/construir_visor.py.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

CODIGO = Path(__file__).resolve().parent
RAIZ = CODIGO.parent
if str(CODIGO) not in sys.path:          # arbol_estadistica y el cuaderno, aunque no esté registrado el paquete
    sys.path.insert(0, str(CODIGO))
VISOR = RAIZ / "visor_arbol.html"
FOCO = RAIZ / ".foco"                  # modo vivo: dónde debe colocarse la app (ver vigilar)
VIVO = "--vivo" in sys.argv
TITULO = "Árbol de la estadística"


def asegurar_visor() -> None:
    if not VISOR.exists():
        python = Path(sys.executable)
        if python.name.lower() == "pythonw.exe" and (python.parent / "python.exe").exists():
            python = python.parent / "python.exe"
        subprocess.run([str(python), str(CODIGO / "construir_visor.py")], cwd=str(RAIZ),
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    if not VISOR.exists():
        raise FileNotFoundError(f"No existe {VISOR}. Ejecuta regenerar_visor.bat.")


class Api:
    """Lo que el visor puede pedir a Python (window.pywebview.api.*): ejecutar las celdas de «Probar» y buscar en el gestor de conocimiento."""

    def __init__(self) -> None:
        self._cuaderno = None

    def _c(self):
        if self._cuaderno is None:
            from cuaderno.ejecutor import Cuaderno
            self._cuaderno = Cuaderno()
        return self._cuaderno

    def ejecutar(self, sesion, codigo):
        try:
            return self._c().ejecutar(str(sesion), str(codigo))
        except Exception as e:
            return {"salida": "", "html": "", "texto": "", "imagenes": [], "error": f"{type(e).__name__}: {e}"}

    def reiniciar(self, sesion):
        return self._c().reiniciar(str(sesion))

    def estado_conocimiento(self):
        """{colección: nº de ficheros indexados}, para rotular las galaxias del cerebro."""
        try:
            import conocimiento
            return {c: nf for c, nf, _ in conocimiento.estado()}
        except Exception:
            return {}

    def buscar_conocimiento(self, consulta, n=12, coleccion=None):
        """Gestor de conocimiento (py/conocimiento): los mejores trozos de código, conceptos, teoría, libros, finanzas y notas."""
        try:
            import conocimiento
            return {"resultados": conocimiento.buscar(str(consulta), coleccion or None, int(n))}
        except FileNotFoundError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def abrir_fuente(self, ruta, ubicacion=""):
        """Abre un fichero del índice. Un PDF se abre en el navegador, en la página del resultado (p. 248 -> #page=248)."""
        import conocimiento
        if not (conocimiento.es_fuente(str(ruta)) and Path(ruta).exists()):
            return False
        m = re.match(r"p\. (\d+)$", str(ubicacion))
        if str(ruta).lower().endswith(".pdf") and m:
            webbrowser.open(Path(ruta).as_uri() + "#page=" + m.group(1))
        else:
            os.startfile(str(ruta))
        return True


def abrir_con_pywebview() -> bool:
    try:
        import webview  # pywebview
    except ImportError:
        return False
    try:
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True     # YouTube, Substack... en el navegador
    except Exception:
        pass
    opciones = dict(width=1400, height=900, min_size=(800, 500), text_select=True, js_api=Api())
    try:
        ventana = webview.create_window(TITULO, VISOR.as_uri(), maximized=True, **opciones)
    except TypeError:                                                   # pywebview antiguo, sin `maximized`
        ventana = webview.create_window(TITULO, VISOR.as_uri(), **opciones)
    extra = (vigilar, ventana) if VIVO else ()
    try:   # private_mode=False: recuerda tema, ancho del panel, etc. entre sesiones
        webview.start(*extra, private_mode=False, storage_path=str(RAIZ / ".ventana"))
    except TypeError:
        webview.start(*extra)
    return True


def leer_foco() -> str:
    try:
        return FOCO.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def vigilar(ventana) -> None:
    """Modo vivo (acceso directo con --vivo): si se regenera visor_arbol.html la ventana se recarga sola, y si cambia el fichero
    .foco (una línea: nombre de función/concepto/demo, `galaxia:codigo` o `cerebro`) la app se coloca ahí. Lo escribe herramientas/ver.py."""
    def aplicar():
        destino = leer_foco()
        if destino:
            ventana.evaluate_js("window.irDestino && window.irDestino(%s)" % json.dumps(destino))
    ventana.events.loaded += aplicar                                     # tras cada recarga, vuelve al sitio del foco
    visto, foco = _marca(), leer_foco()
    while True:
        time.sleep(.7)
        marca, f = _marca(), leer_foco()
        if marca != visto:
            visto, foco = marca, f
            ventana.evaluate_js("location.reload()")
        elif f != foco:
            foco = f
            aplicar()


def _marca() -> int:
    try:
        return VISOR.stat().st_mtime_ns
    except OSError:
        return 0


def navegadores() -> list[Path]:
    pf86, pf, local = (os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"))
    rutas = [Path(pf86, "Microsoft/Edge/Application/msedge.exe"), Path(pf, "Microsoft/Edge/Application/msedge.exe"),
             Path(pf, "Google/Chrome/Application/chrome.exe"), Path(pf86, "Google/Chrome/Application/chrome.exe"),
             Path(local, "Google/Chrome/Application/chrome.exe")]
    return [r for r in rutas if r.drive and r.exists()]


def abrir_en_modo_app() -> bool:
    for nav in navegadores():
        try:   # la URL va como file:///…%C3%AD… (bien codificada): con la ruta cruda salía una ventana vacía
            subprocess.Popen([str(nav), f"--app={VISOR.as_uri()}", "--start-maximized"])
            return True
        except OSError:
            continue
    return False


def avisar(mensaje: str) -> None:
    try:
        import tkinter
        from tkinter import messagebox
        raiz = tkinter.Tk(); raiz.withdraw()
        messagebox.showerror(TITULO, mensaje)
        raiz.destroy()
    except Exception:
        print(mensaje, file=sys.stderr)


def main() -> int:
    try:
        asegurar_visor()
    except Exception as e:
        avisar(str(e))
        return 1
    if abrir_con_pywebview() or abrir_en_modo_app():
        return 0
    webbrowser.open(VISOR.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
