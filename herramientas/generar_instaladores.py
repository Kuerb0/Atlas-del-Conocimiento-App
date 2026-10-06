"""Genera los instaladores autoextraibles del Arbol de la estadistica.

Uso (desde cualquier sitio):

    python herramientas/generar_instaladores.py

Lee el programa (py/, assets/, teoria/, ejemplos/, INDEX.md, CLAUDE.md, los .bat de la carpeta
principal, conceptos/catalogo.json y catalogo_base.json y herramientas/descargar_python.ps1) y escribe en instaladores/:

    Arbol <version> - Instalador.bat    (instalacion completa: Python si hace falta, librerias, visor, accesos)
    Arbol <version> - Actualizar.bat    (solo el programa y las librerias; guarda lo anterior en anteriores/)

Cada .bat lleva dentro TODOS los ficheros del programa, asi que se puede mandar suelto a otro ordenador
(o a otra persona, p. ej. un companero): al ejecutarlo crea py/, assets/, etc. en su propia carpeta.
Las plantillas estan en herramientas/plantillas/: instalador.bat.txt y actualizar.bat.txt (la cabecera cmd) y
motor.ps1 (el script de PowerShell que instala/actualiza; se incrusta entre :::PSSTART y :::PSEND).

Reglas de empaquetado:
  * La version sale de py/VERSION.txt (debe coincidir con py/pyproject.toml).
  * conceptos/catalogo.json va como "seed": se copia solo si NO existe, para no pisar los conceptos
    que cada usuario haya ido anadiendo. conceptos/catalogo_base.json (el de la version) si se sobrescribe y
    py/fusionar_catalogo.py le anade al del usuario lo que sea nuevo.
  * visor_arbol.html no se empaqueta: el instalador lo genera con construir_visor.py.
  * Nunca se empaquetan caches (__pycache__, .pytest_cache), logs ni la subcarpeta python/ o anteriores/.

Al terminar comprueba que lo empaquetado se extrae identico al original.
Ejecutalo siempre despues de cambiar algo en py/ o assets/, antes de repartir o instalar nada.
"""
import base64
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "herramientas", "plantillas")
SALIDA = os.path.join(RAIZ, "instaladores")

PLANTILLAS_BAT = [
    ("instalador.bat.txt", "Arbol {v} - Instalador.bat"),
    ("actualizar.bat.txt", "Arbol {v} - Actualizar.bat"),
]

FICHEROS_RAIZ = ["INDEX.md", "CLAUDE.md", "abrir_arbol.bat", "regenerar_visor.bat", "indexar_conocimiento.bat", "ejecutar_tests.bat", "medir_propiedades.bat",
                 "herramientas/descargar_python.ps1"]
SEMILLAS = ["conceptos/catalogo.json"]            # se copian solo si no existen
TEXTOS_VERSION = ["conceptos/catalogo_base.json"]  # texto que si se actualiza con cada version
BINARIOS = ["assets/icono.ico", "assets/icono.png"]
CARPETAS_TEXTO = [("teoria", (".md",)), ("ejemplos", (".py",))]
IGNORAR = {"__pycache__", ".pytest_cache", ".git", "build", "dist"}


def leer_bytes(rel, raiz=None):
    with open(os.path.join(raiz or RAIZ, *rel.split("/")), "rb") as f:
        return f.read()


def lineas_de_texto(rel, raiz=None):
    texto = leer_bytes(rel, raiz).decode("utf-8-sig")
    return texto.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n").split("\n")


def version_del_programa(raiz=None):
    version = leer_bytes("py/VERSION.txt", raiz).decode("utf-8-sig").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit(f"py/VERSION.txt no tiene el formato X.Y.Z: {version!r}")
    proyecto = leer_bytes("py/pyproject.toml", raiz).decode("utf-8-sig")
    m = re.search(r'^version\s*=\s*"([^"]+)"', proyecto, re.M)
    if not m or m.group(1) != version:
        sys.exit(f"py/VERSION.txt ({version}) y py/pyproject.toml ({m.group(1) if m else '?'}) no coinciden")
    return version


def lista_de_archivos(raiz=None):
    """[(ruta relativa, modo)] con modo text / seed / b64."""
    raiz = raiz or RAIZ
    archivos = []
    for base, carpetas, ficheros in os.walk(os.path.join(raiz, "py")):
        carpetas[:] = sorted(c for c in carpetas if c not in IGNORAR and not c.endswith(".egg-info"))
        for f in sorted(ficheros):
            if f.endswith((".pyc", ".pyo")):
                continue
            rel = os.path.relpath(os.path.join(base, f), raiz).replace(os.sep, "/")
            archivos.append((rel, "text"))
    for carpeta, extensiones in CARPETAS_TEXTO:
        ruta = os.path.join(raiz, carpeta)
        if os.path.isdir(ruta):
            archivos += [(f"{carpeta}/{f}", "text") for f in sorted(os.listdir(ruta)) if f.endswith(extensiones)]
    archivos += [(rel, "text") for rel in FICHEROS_RAIZ]
    archivos += [(rel, "seed") for rel in SEMILLAS]
    archivos += [(rel, "text") for rel in TEXTOS_VERSION]
    archivos += [(rel, "b64") for rel in BINARIOS]
    for rel, _ in archivos:
        if not os.path.exists(os.path.join(raiz, *rel.split("/"))):
            sys.exit(f"Falta el fichero a empaquetar: {rel}")
    return archivos


def bloque(rel, modo, raiz=None):
    """Las lineas de un fichero dentro del .bat."""
    salida = [f":::BEGIN {rel}|{modo}"]
    if modo == "b64":
        b64 = base64.b64encode(leer_bytes(rel, raiz)).decode("ascii")
        salida += [b64[i:i + 76] for i in range(0, len(b64), 76)]
    else:
        for linea in lineas_de_texto(rel, raiz):
            if linea.startswith(":::"):
                sys.exit(f"{rel}: una linea empieza por ':::' y rompe el empaquetado")
            salida.append(linea)
    salida.append(":::END")
    return salida


def extraer(contenido):
    """Misma logica que el extractor de PowerShell del .bat (para comprobar). Devuelve {ruta: (modo, bytes)}."""
    lineas = contenido.decode("utf-8").replace("\r\n", "\n").split("\n")
    salida, i = {}, 0
    while i < len(lineas):
        if lineas[i].startswith(":::BEGIN "):
            rel, modo = lineas[i][9:].strip().split("|")
            j, buf = i + 1, []
            while j < len(lineas) and not lineas[j].startswith(":::END"):
                buf.append(lineas[j])
                j += 1
            if modo == "b64":
                salida[rel] = (modo, base64.b64decode("".join(buf)))
            else:
                salida[rel] = (modo, ("\r\n".join(buf) + "\r\n").encode("utf-8"))
            i = j
        i += 1
    return salida


def generar(raiz=None, salida=None):
    """Escribe los instaladores y devuelve las rutas. `raiz`/`salida` permiten probarlo en una carpeta temporal."""
    raiz = raiz or RAIZ
    salida = salida or os.path.join(raiz, "instaladores")
    version = version_del_programa(raiz)
    archivos = lista_de_archivos(raiz)
    carga = []
    for rel, modo in archivos:
        carga += bloque(rel, modo, raiz)
    os.makedirs(salida, exist_ok=True)
    with open(os.path.join(raiz, "herramientas", "plantillas", "motor.ps1"), encoding="utf-8-sig") as f:
        motor = f.read().replace("\r\n", "\n").rstrip("\n").split("\n")
    if any(l.startswith(":::") for l in motor):
        sys.exit("motor.ps1: una linea empieza por ':::' y rompe el empaquetado")
    escritos = []
    for plantilla, nombre in PLANTILLAS_BAT:
        with open(os.path.join(raiz, "herramientas", "plantillas", plantilla), encoding="utf-8") as f:
            texto = f.read().replace("\r\n", "\n")
        assert "@@PAYLOAD@@" in texto and "@@MOTOR@@" in texto, plantilla
        completo = []
        for linea in texto.replace("@@VERSION@@", version).split("\n"):
            if linea.strip() == "@@PAYLOAD@@":
                completo += carga
            elif linea.strip() == "@@MOTOR@@":
                completo += motor
            else:
                completo.append(linea)
        contenido = ("\r\n".join(completo).rstrip("\r\n") + "\r\n").encode("utf-8")

        # comprobacion: lo que sale al extraer == lo que hay en el proyecto
        sacado = extraer(contenido)
        if set(sacado) != {rel for rel, _ in archivos}:
            sys.exit(f"{nombre}: la lista de ficheros extraidos no coincide con la empaquetada")
        for rel, modo in archivos:
            esperado = leer_bytes(rel, raiz)
            if modo != "b64":
                esperado = ("\r\n".join(lineas_de_texto(rel, raiz)) + "\r\n").encode("utf-8")
            if sacado[rel] != (modo, esperado):
                sys.exit(f"{nombre}: {rel} no sale igual al extraerlo")

        destino = os.path.join(salida, nombre.format(v=version))
        with open(destino, "wb") as f:
            f.write(contenido)
        escritos.append(destino)
    return escritos


def main():
    for destino in generar():
        print(f"OK  {os.path.relpath(destino, RAIZ)}  ({os.path.getsize(destino) // 1024} KB)")


if __name__ == "__main__":
    main()
