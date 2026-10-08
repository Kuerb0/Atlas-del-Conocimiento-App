"""Corpus de pruebas del clasificador. Orden:
1) python herramientas/corpus/libros_gutenberg.py CARPETA   (necesita CARPETA/pg_catalog.csv: https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv; baja EPUB en/es con la etiqueta de su estantería oficial)
2) python herramientas/corpus/articulos_arxiv.py CARPETA [N]  (artículos de arXiv con el género de su categoría)
3) python herramientas/corpus/codigo_y_datos.py CARPETA        (código y datos de los paquetes instalados, etiquetados por paquete)
4) python herramientas/corpus/montar.py CARPETA               (junta todo en CARPETA/enes/corpus con las etiquetas buenas; luego herramientas/evaluar_corpus.py)
Todo de fuentes legales (dominio público, acceso abierto, licencias BSD/PSF). El corpus no se publica: pesa GB.
"""

import csv, json, random, re, sys, time, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "py")); sys.stdout.reconfigure(encoding="utf-8")
from concurrent.futures import ThreadPoolExecutor
from conocimiento import telescopio
D = pathlib.Path(sys.argv[1]); RAW = D / "raw"; RAW.mkdir(exist_ok=True)
POR_GENERO = int(sys.argv[2]) if len(sys.argv) > 2 else 28
M = {  # estantería -> (género, subgénero)
 "History - Ancient": ("historia", "antigua"), "History - Medieval/Middle Ages": ("historia", "medieval"), "History - Early Modern (c. 1450-1750)": ("historia", "moderna"),
 "History - Modern (1750+)": ("historia", "moderna"), "History - Warfare": ("historia", "militar"), "History - American": ("historia", "america"),
 "History - European": ("historia", ""), "History - British": ("historia", ""), "History - Other": ("historia", ""), "History - Royalty": ("historia", ""),
 "Archaeology & Anthropology": ("historia", "arqueologia"), "Biographies": ("biografia", ""),
 "Historical Novels": ("novela", "historica"), "Crime, Thrillers and Mystery": ("novela", "negra"), "Romance": ("novela", "romance"), "Children & Young Adult Reading": ("novela", "juvenil"),
 "Science Fiction": ("novela", "scifi"), "Science-Fiction & Fantasy": ("novela", ""), "Short Stories": ("novela", ""), "Novels": ("novela", ""), "Adventure": ("novela", ""),
 "Philosophy & Ethics": ("ensayo", ""), "Essays, Letters & Speeches": ("ensayo", "ensayo_lit"), "Politics": ("politica", ""), "Sociology": ("politica", "sociologia"), "Economics": ("economia", ""),
 "Science - Biology": ("ciencia", "biologia"), "Science - Physics": ("ciencia", "fisica"), "Science - Chemistry/Biochemistry": ("ciencia", "quimica"), "Science - Earth/Agricultural/Farming": ("ciencia", "tierra"),
 "Engineering & Technology": ("tecnologia", ""), "Research Methods/Statistics/Information Sys": ("estadistica", ""),
 "Art": ("arte", "visuales"), "Music": ("arte", "musica"), "Architecture": ("arte", "arquitectura"), "Poetry": ("arte", "poesia"),
 "Law & Criminology": ("derecho", ""), "Cooking & Drinking": ("cocina", ""), "Health & Medicine": ("salud", "medicina"), "Psychiatry/Psychology": ("psicologia", ""),
 "Travel Writing": ("viajes", "relatos"), "Language & Communication": ("idiomas", ""), "Teaching & Education": ("educacion", ""), "Religion/Spirituality": ("religion", ""), "Sports/Hobbies": ("deporte", "")}
LANG = {"en", "es"}
CUOTA = {"novela": (70, 25), "historia": (50, 20), "ensayo": (40, 12), "economia": (30, 10), "politica": (30, 10), "ciencia": (30, 10), "biografia": (30, 10)}   # (inglés, español)
YA = {f.stem for f in RAW.glob("*.epub")}
def autor(a):
    a = re.sub(r"\s*\(.*?\)|,?\s*\d{3,4}\??-\d{0,4}\??", "", a.split(";")[0]).strip()
    return " ".join(reversed([x.strip() for x in a.split(",", 1)])) if "," in a else a
cand = collections.defaultdict(list)
for x in csv.DictReader(open(D / "pg_catalog.csv", encoding="utf-8")):
    if x["Type"] != "Text" or x["Language"] not in LANG or not x["Authors"]:
        continue
    sh = [s.strip().replace("Category: ", "") for s in x["Bookshelves"].split(";")]
    hits = [M[s] for s in sh if s in M]
    gens = {g for g, _ in hits}
    if len(gens) != 1:
        continue
    g = gens.pop(); subs = {s for gg, s in hits if s}
    sub = subs.pop() if len(subs) == 1 else ""
    if g == "novela" and not sub and "Novels" not in sh and "Short Stories" not in sh and "Science-Fiction & Fantasy" not in sh:
        pass
    cand[g].append({"id": x["Text#"], "titulo": re.sub(r"\s+", " ", x["Title"].split("\n")[0]).strip(), "autor": autor(x["Authors"]), "idioma": x["Language"], "genero": g, "subgenero": sub})
random.seed(7)
sel = []
for g, l in sorted(cand.items()):
    random.shuffle(l)
    nen, nes = CUOTA.get(g, (22, 8))
    l = [b for b in l if b["id"] not in YA]
    es = [b for b in l if b["idioma"] == "es"][:nes]
    en = [b for b in l if b["idioma"] == "en"][:nen]
    sel += es + en
    print(g, len(l), "->", len(es), "es +", len(en), "en", flush=True)
def bajar(b):
    f = RAW / f"{b['id']}.epub"
    if f.exists() and f.stat().st_size > 5000:
        return b, True
    try:
        time.sleep(0.4)
        d = telescopio._get(f"https://www.gutenberg.org/ebooks/{b['id']}.epub3.images", binario=True)
        if d[:2] != b"PK":
            return b, False
        f.write_bytes(d); return b, True
    except Exception as e:
        return b, False
with ThreadPoolExecutor(3) as ex:
    res = list(ex.map(bajar, sel))
ok = [b for b, k in res if k]
(D / "libros2_etiquetas.json").write_text(json.dumps(ok, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(ok), "de", len(sel), "bajados")
