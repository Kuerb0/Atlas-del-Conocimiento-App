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

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

CODIGO = Path(__file__).resolve().parent
RAIZ = CODIGO.parent
if str(CODIGO) not in sys.path:          # arbol_estadistica y el cuaderno, aunque no esté registrado el paquete
    sys.path.insert(0, str(CODIGO))
VISOR = RAIZ / "visor_arbol.html"
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

    def abrir_fuente(self, ruta):
        """Abre con su programa un fichero del índice (un PDF, una nota…); nada que no esté indexado."""
        import conocimiento
        if conocimiento.es_fuente(str(ruta)) and Path(ruta).exists():
            os.startfile(str(ruta))
            return True
        return False


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
        webview.create_window(TITULO, VISOR.as_uri(), maximized=True, **opciones)
    except TypeError:                                                   # pywebview antiguo, sin `maximized`
        webview.create_window(TITULO, VISOR.as_uri(), **opciones)
    try:   # private_mode=False: recuerda tema, ancho del panel, etc. entre sesiones
        webview.start(private_mode=False, storage_path=str(RAIZ / ".ventana"))
    except TypeError:
        webview.start()
    return True


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
