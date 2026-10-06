"""Dibuja assets/icono.png y assets/icono.ico: una galaxia en espiral (núcleo naranja, brazos que pasan de naranja a violeta y azul) sobre fondo azul noche.

Uso (desde la carpeta principal): python herramientas/generar_icono.py   -> luego python herramientas/generar_instaladores.py
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent
S = 1024                                                    # se dibuja grande y se reduce (bordes suaves)
FONDO = (14, 20, 40)
NARANJA, VIOLETA, AZUL = (255, 160, 60), (190, 130, 245), (110, 165, 255)


def mezcla(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


random.seed(7)
base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(base).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * .22), fill=FONDO)

# estrellas de fondo
est = ImageDraw.Draw(base)
for _ in range(90):
    x, y, r = random.randint(40, S - 40), random.randint(40, S - 40), random.choice((2, 2, 3, 4))
    est.ellipse((x - r, y - r, x + r, y + r), fill=(200, 215, 255, random.randint(70, 200)))

# la galaxia: dos brazos logarítmicos, vista algo inclinada
luz = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(luz)
cx, cy, inc, giro = S / 2, S / 2, .72, -.35
for brazo in (0, math.pi):
    for _ in range(900):
        r = 40 + 400 * random.random() ** .8
        a = brazo + (r - 40) * .0105 + random.gauss(0, .2)
        x0, y0 = r * math.cos(a), r * math.sin(a) * inc
        x, y = cx + x0 * math.cos(giro) - y0 * math.sin(giro), cy + x0 * math.sin(giro) + y0 * math.cos(giro)
        k = min(1, r / 440)
        c = mezcla(NARANJA, VIOLETA, k * 2) if k < .5 else mezcla(VIOLETA, AZUL, (k - .5) * 2)
        t = random.choice((5, 6, 8, 10)) * (1.1 - .5 * k)
        d.ellipse((x - t, y - t, x + t, y + t), fill=c + (random.randint(120, 230),))
resplandor = luz.filter(ImageFilter.GaussianBlur(14))
base = Image.alpha_composite(base, resplandor)
base = Image.alpha_composite(base, luz)
nucleo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
n = ImageDraw.Draw(nucleo)
for r, a in [(150, 70), (105, 120), (65, 190), (32, 255)]:
    n.ellipse((cx - r, cy - r * inc - 6, cx + r, cy + r * inc - 6), fill=mezcla(NARANJA, (255, 255, 255), 1 - a / 255) + (a,))
base = Image.alpha_composite(base, nucleo.filter(ImageFilter.GaussianBlur(6)))

# recorte con las esquinas redondeadas
mascara = Image.new("L", (S, S), 0)
ImageDraw.Draw(mascara).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * .22), fill=255)
base.putalpha(mascara)

out = base.resize((256, 256), Image.LANCZOS)
out.save(RAIZ / "assets" / "icono.png")
base.save(RAIZ / "assets" / "icono.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("assets/icono.png y assets/icono.ico escritos")
