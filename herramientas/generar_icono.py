"""Dibuja assets/icono.png y assets/icono.ico: un cerebro rosa con tres galaxias (naranja, azul, verde) sobre fondo azul noche.

Uso (desde la carpeta principal): python herramientas/generar_icono.py   -> luego python herramientas/generar_instaladores.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
S = 1024                                                    # se dibuja grande y se reduce (bordes suaves)
FONDO, ROSA, SURCO = (22, 33, 58), (240, 140, 192), (176, 70, 130)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * .22), fill=FONDO)

# silueta: nube de círculos (hemisferio) + cerebelo + tronco
for cx, cy, r in [(370, 420, 190), (520, 340, 210), (680, 400, 200), (760, 520, 150), (330, 560, 170), (480, 540, 210), (640, 570, 190)]:
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ROSA)
d.ellipse((560, 640, 800, 800), fill=ROSA)                   # cerebelo
d.rounded_rectangle((470, 650, 560, 880), radius=40, fill=ROSA)   # tronco
# surcos: líneas onduladas recortadas a la silueta (se leen como circunvoluciones, no como una cara)
masc = Image.new("L", (S, S), 0)
mm = ImageDraw.Draw(masc)
for cx, cy, r in [(370, 420, 190), (520, 340, 210), (680, 400, 200), (760, 520, 150), (330, 560, 170), (480, 540, 210), (640, 570, 190)]:
    mm.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
mm.ellipse((560, 640, 800, 800), fill=255)
surcos = Image.new("RGBA", (S, S), (0, 0, 0, 0))
sd = ImageDraw.Draw(surcos)
for y0, amp, fr, ph in [(250, 34, .030, 0), (360, 40, .026, 2), (470, 38, .031, 4), (580, 36, .027, 1), (680, 24, .035, 3)]:
    sd.line([(x, y0 + amp * math.sin(x * fr + ph)) for x in range(200, 860, 6)], fill=SURCO + (255,), width=20, joint="curve")
sd.line([(540, 150), (515, 330), (550, 470), (515, 640)], fill=SURCO + (255,), width=22, joint="curve")   # fisura
img.paste(surcos, (0, 0), Image.composite(surcos.getchannel("A"), Image.new("L", (S, S), 0), masc))

# galaxias dentro del cerebro
for cx, cy, col in [(380, 430, (255, 150, 40)), (680, 300, (111, 162, 255)), (640, 540, (111, 207, 123))]:
    for r, a in [(70, 90), (46, 170), (24, 255)]:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col + (a,))
    d.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=(255, 255, 255, 255))

out = img.resize((256, 256), Image.LANCZOS)
out.save(RAIZ / "assets" / "icono.png")
img.save(RAIZ / "assets" / "icono.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("assets/icono.png y assets/icono.ico escritos")
