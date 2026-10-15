"""Crea el banner estandar de los .bat y el titulo grande de cada uno.

Uso (desde cualquier sitio):

    python herramientas/crear_banner.py CALENDARIO

Escribe en herramientas/plantillas/:

    banner.txt             cuervo + KUERB0 + frase, con marcos (se pinta en aguamarina)
    titulo_instalador.txt  INSTALADOR <PROYECTO> + version (se pinta en blanco)
    titulo_actualizar.txt  ACTUALIZADOR <PROYECTO> + version (se pinta en blanco)

El cuervo sale de plantillas/cuervo.txt: la '§' marca el ojo, que se pinta dorado.
Los titulos llevan @@VERSION@@; generar_instaladores.py lo sustituye.

Para otro proyecto: copia este script y cuervo.txt, y cambia el nombre.
"""
import os
import sys

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plantillas")
GAP = 3
FRASE = "Without data, you’re just another person with an opinion"

# fuente "ANSI Shadow": 6 filas por letra, filas separadas por '|'
LETRAS = {
    "A": " █████╗ |██╔══██╗|███████║|██╔══██║|██║  ██║|╚═╝  ╚═╝",
    "B": "██████╗ |██╔══██╗|██████╔╝|██╔══██╗|██████╔╝|╚═════╝ ",
    "C": " ██████╗|██╔════╝|██║     |██║     |╚██████╗| ╚═════╝",
    "D": "██████╗ |██╔══██╗|██║  ██║|██║  ██║|██████╔╝|╚═════╝ ",
    "E": "███████╗|██╔════╝|█████╗  |██╔══╝  |███████╗|╚══════╝",
    "F": "███████╗|██╔════╝|█████╗  |██╔══╝  |██║     |╚═╝     ",
    "G": " ██████╗ |██╔════╝ |██║  ███╗|██║   ██║|╚██████╔╝| ╚═════╝ ",
    "H": "██╗  ██╗|██║  ██║|███████║|██╔══██║|██║  ██║|╚═╝  ╚═╝",
    "I": "██╗|██║|██║|██║|██║|╚═╝",
    "J": "     ██╗|     ██║|     ██║|██   ██║|╚█████╔╝| ╚════╝ ",
    "K": "██╗  ██╗|██║ ██╔╝|█████╔╝ |██╔═██╗ |██║  ██╗|╚═╝  ╚═╝",
    "L": "██╗     |██║     |██║     |██║     |███████╗|╚══════╝",
    "M": "███╗   ███╗|████╗ ████║|██╔████╔██║|██║╚██╔╝██║|██║ ╚═╝ ██║|╚═╝     ╚═╝",
    "N": "███╗   ██╗|████╗  ██║|██╔██╗ ██║|██║╚██╗██║|██║ ╚████║|╚═╝  ╚═══╝",
    "O": " ██████╗ |██╔═══██╗|██║   ██║|██║   ██║|╚██████╔╝| ╚═════╝ ",
    "P": "██████╗ |██╔══██╗|██████╔╝|██╔═══╝ |██║     |╚═╝     ",
    "Q": " ██████╗ |██╔═══██╗|██║   ██║|██║▄▄ ██║|╚██████╔╝| ╚══▀▀═╝ ",
    "R": "██████╗ |██╔══██╗|██████╔╝|██╔══██╗|██║  ██║|╚═╝  ╚═╝",
    "S": "███████╗|██╔════╝|███████╗|╚════██║|███████║|╚══════╝",
    "T": "████████╗|╚══██╔══╝|   ██║   |   ██║   |   ██║   |   ╚═╝   ",
    "U": "██╗   ██╗|██║   ██║|██║   ██║|██║   ██║|╚██████╔╝| ╚═════╝ ",
    "V": "██╗   ██╗|██║   ██║|██║   ██║|╚██╗ ██╔╝| ╚████╔╝ |  ╚═══╝  ",
    "W": "██╗    ██╗|██║    ██║|██║ █╗ ██║|██║███╗██║|╚███╔███╔╝| ╚══╝╚══╝ ",
    "X": "██╗  ██╗|╚██╗██╔╝| ╚███╔╝ | ██╔██╗ |██╔╝ ██╗|╚═╝  ╚═╝",
    "Y": "██╗   ██╗|╚██╗ ██╔╝| ╚████╔╝ |  ╚██╔╝  |   ██║   |   ╚═╝   ",
    "Z": "███████╗|╚══███╔╝|  ███╔╝ | ███╔╝  |███████╗|╚══════╝",
    "0": " ██████╗ |██╔═████╗|██║██╔██║|████╔╝██║|╚██████╔╝| ╚═════╝ ",
    "-": "       |       |█████╗ |╚════╝ |       |       ",
    " ": "    |    |    |    |    |    ",
}


def grande(texto):
    """El texto en letras grandes: 6 filas."""
    glifos = []
    for c in texto.upper():
        if c not in LETRAS:
            sys.exit(f"Falta la letra {c!r} en LETRAS de crear_banner.py")
        glifos.append(LETRAS[c].split("|"))
    return [" ".join(g[i] for g in glifos).rstrip() for i in range(6)]


def escribir(nombre, lineas):
    with open(os.path.join(DIR, nombre), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lineas) + "\n")
    print("OK ", os.path.join("herramientas", "plantillas", nombre))


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python herramientas/crear_banner.py NOMBRE_DEL_PROYECTO")
    proyecto = sys.argv[1]

    with open(os.path.join(DIR, "cuervo.txt"), encoding="utf-8") as f:
        cuervo = f.read().rstrip("\n").split("\n")
    ancho = max(map(len, cuervo))

    # a la derecha del cuervo, centrado en vertical: KUERB0 y la frase
    derecha = grande("KUERB0") + ["", FRASE]
    rw = max(map(len, derecha))
    total = ancho + GAP + rw
    arriba = (len(cuervo) - len(derecha)) // 2
    cuerpo = []
    for i, linea in enumerate(cuervo):
        r = derecha[i - arriba] if 0 <= i - arriba < len(derecha) else ""
        if i - arriba == len(derecha) - 1:
            r = r.center(rw)
        cuerpo.append((linea.ljust(ancho) + " " * GAP + r).rstrip())
    marco = "░▒▓█ " + "═" * (total - 10) + " █▓▒░"
    escribir("banner.txt", [marco] + cuerpo + [marco])

    # titulo: la palabra grande, el proyecto grande y la version pequena
    def centrar(bloque, ancho_real=None):
        # el mismo margen para todas las filas del bloque, para que no se descuadren
        margen = " " * ((total - (ancho_real or max(map(len, bloque)))) // 2)
        return [margen + linea for linea in bloque]

    def titulo(palabra):
        etiqueta = "V E R S I Ó N   "
        # ponytail: la version se centra contando 3 caracteres ("2.0"); con otra longitud se mueve 1-2 columnas
        version = centrar([etiqueta + "@@VERSION@@"], len(etiqueta) + 3)
        return [""] + centrar(grande(palabra)) + [""] + centrar(grande(proyecto)) + [""] + version + [""]

    escribir("titulo_instalador.txt", titulo("INSTALADOR"))
    escribir("titulo_actualizar.txt", titulo("ACTUALIZADOR"))


if __name__ == "__main__":
    main()
