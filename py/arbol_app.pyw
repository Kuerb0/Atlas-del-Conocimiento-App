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
        self._job = {"fase": "", "texto": "", "frac": 0.0, "resultado": None}      # la importación en curso (se consulta con estado_trabajo)

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

    # ---- importador (pestaña «Importar»): ver py/conocimiento/importar.py ----
    def opciones_importador(self):
        try:
            from conocimiento import importar
            return importar.opciones()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def elegir_archivos(self):
        """Abre el explorador de archivos de Windows (varios a la vez) y devuelve las rutas elegidas."""
        try:
            import webview
            from conocimiento.importar import filtros_dialogo
            tipos = filtros_dialogo()
            modo = webview.FileDialog.OPEN if hasattr(webview, "FileDialog") else webview.OPEN_DIALOG
            r = webview.windows[0].create_file_dialog(modo, allow_multiple=True, file_types=tipos)
            return [str(x) for x in (r or [])]
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def clasificar_archivos(self, rutas):
        try:
            from conocimiento import importar
            return [{"ruta": str(r), **importar.clasificar(str(r))} for r in rutas]
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def importar_archivos(self, items):
        """Importa en segundo plano (un PDF grande tarda): vuelve enseguida y el visor consulta estado_trabajo() hasta que acabe."""
        import threading
        if self._job.get("fase") == "trabajando":
            return {"error": "ya hay una importación en curso"}
        self._job = {"fase": "trabajando", "texto": "Empezando…", "frac": 0.0, "resultado": None}
        items = list(items)

        def correr():
            import conocimiento
            from conocimiento import importar
            conocimiento.PROGRESO = lambda txt, fr: self._job.update(texto=txt, frac=(.1 + .85 * fr) if txt.startswith("Leyendo") else fr)
            try:
                self._job.update(resultado=importar.importar(items))
            except Exception as e:
                self._job.update(resultado={"error": f"{type(e).__name__}: {e}"})
            finally:
                conocimiento.PROGRESO = None
                self._job.update(fase="fin", frac=1.0)
        threading.Thread(target=correr, daemon=True).start()
        return {"ok": True}

    def estado_trabajo(self):
        return dict(self._job)

    # ---- biblioteca: gestionar lo importado ----
    def _bib(self, nombre, *args):
        try:
            from conocimiento import importar
            return getattr(importar, nombre)(*args)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def biblioteca_listar(self):
        return self._bib("listar")

    def biblioteca_editar(self, rel, cambios):
        return self._bib("editar", str(rel), dict(cambios))

    def biblioteca_reclasificar(self, rel):
        return self._bib("reclasificar_uno", str(rel))

    def biblioteca_borrar(self, rel):
        return self._bib("borrar", str(rel))

    def actualizar_visor(self):
        """Regenera visor_arbol.html (con lo recién importado) para que el universo lo incluya; el visor se recarga después."""
        try:
            import contextlib
            import io
            import construir_visor
            with contextlib.redirect_stdout(io.StringIO()):     # pythonw no tiene consola
                construir_visor.main()
            return True
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def almacenaje(self):
        """Pestaña «Eclipses»: lo que ocupa cada galaxia/tipo en disco y en GitHub frente a su límite."""
        try:
            from conocimiento import almacenaje
            return almacenaje.medir()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    # ---- telescopio (pestaña «Telescopio»): ver py/conocimiento/telescopio.py ----
    def telescopio_buscar(self, consulta="", titulo="", autor="", tipo="todo", formato=""):
        try:
            from conocimiento import telescopio
            return telescopio.buscar(str(consulta), titulo=str(titulo), autor=str(autor), tipo=str(tipo), formato=str(formato))
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def abrir_enlace(self, url):
        """Abre un enlace https en el navegador del usuario (fichas del telescopio)."""
        import webbrowser
        url = str(url)
        if url.startswith("https://"):
            webbrowser.open(url)
            return True
        return False

    def telescopio_traer(self, item):
        try:
            from conocimiento import telescopio
            return telescopio.traer(dict(item))
        except Exception as e:
            return {"estado": "error", "mensaje": f"{type(e).__name__}: {e}"}

    def resumen_biblioteca(self):
        try:
            from conocimiento import importar
            return importar.resumen()
        except Exception:
            return {}

    def estado_conocimiento(self):
        """{colección: nº de ficheros indexados}, para rotular las galaxias del cerebro."""
        try:
            import conocimiento
            return {c: nf for c, nf, _ in conocimiento.estado()}
        except Exception:
            return {}

    def buscar_conocimiento(self, consulta, n=12, coleccion=None, genero=None, formato=None):
        """Gestor de conocimiento (py/conocimiento): los mejores trozos de código, conceptos, teoría, libros, finanzas y notas."""
        try:
            import conocimiento
            return {"resultados": conocimiento.buscar(str(consulta), coleccion or None, int(n), genero=genero or None, formato=formato or None)}
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
