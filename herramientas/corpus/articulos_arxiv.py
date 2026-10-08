"""Corpus de pruebas del clasificador. Orden:
1) python herramientas/corpus/libros_gutenberg.py CARPETA   (necesita CARPETA/pg_catalog.csv: https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv; baja EPUB en/es con la etiqueta de su estantería oficial)
2) python herramientas/corpus/articulos_arxiv.py CARPETA [N]  (artículos de arXiv con el género de su categoría)
3) python herramientas/corpus/codigo_y_datos.py CARPETA        (código y datos de los paquetes instalados, etiquetados por paquete)
4) python herramientas/corpus/montar.py CARPETA               (junta todo en CARPETA/enes/corpus con las etiquetas buenas; luego herramientas/evaluar_corpus.py)
Todo de fuentes legales (dominio público, acceso abierto, licencias BSD/PSF). El corpus no se publica: pesa GB.
"""

import json, random, re, sys, time, pathlib, xml.etree.ElementTree as ET
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "py")); sys.stdout.reconfigure(encoding="utf-8")
from conocimiento import telescopio
D = pathlib.Path(sys.argv[1]); RAW = D / "raw_arxiv"; RAW.mkdir(exist_ok=True)
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
CAT = {"stat.ME": ("estadistica", "inferencia"), "stat.ML": ("estadistica", "ml_est"), "math.ST": ("estadistica", "inferencia"), "stat.AP": ("estadistica", ""), "stat.CO": ("estadistica", ""),
       "math.PR": ("estadistica", "probabilidad"), "cs.LG": ("tecnologia", "ia"), "cs.AI": ("tecnologia", "ia"), "cs.SE": ("tecnologia", "ingenieria_sw"), "cs.DB": ("tecnologia", "datos"),
       "cs.NI": ("tecnologia", "redes"), "cs.CR": ("tecnologia", ""), "cs.DS": ("tecnologia", "algoritmos"), "econ.GN": ("economia", ""), "econ.EM": ("economia", ""), "econ.TH": ("economia", ""),
       "q-fin.PM": ("economia", "inversion"), "q-fin.RM": ("economia", "finanzas"), "q-fin.PR": ("economia", "derivados"), "physics.optics": ("ciencia", "fisica"), "astro-ph.CO": ("ciencia", "cosmos"),
       "astro-ph.GA": ("ciencia", "cosmos"), "q-bio.PE": ("ciencia", "biologia"), "q-bio.NC": ("ciencia", "neuro"), "quant-ph": ("ciencia", "fisica"), "cond-mat.mtrl-sci": ("ciencia", "fisica"),
       "physics.ao-ph": ("ciencia", "tierra"), "physics.chem-ph": ("ciencia", "quimica")}
A = "{http://www.w3.org/2005/Atom}"; X = "{http://arxiv.org/schemas/atom}"
random.seed(42); out = []
for cat, (g, sub) in CAT.items():
    try:
        time.sleep(3.2)
        url = f"https://export.arxiv.org/api/query?search_query=cat:{cat}&start={random.randint(0, 400)}&max_results={N}&sortBy=submittedDate&sortOrder=descending"
        raiz = ET.fromstring(telescopio._get(url).encode("utf-8"))
        for e in raiz.findall(A + "entry"):
            if (e.find(X + "primary_category").get("term") if e.find(X + "primary_category") is not None else cat) != cat:
                continue
            aid = e.findtext(A + "id").rsplit("/abs/", 1)[-1]
            f = RAW / (aid.replace("/", "_") + ".pdf")
            if not (f.exists() and f.stat().st_size > 5000):
                time.sleep(3.2)
                d = telescopio._get(f"https://arxiv.org/pdf/{aid}", binario=True)
                if d[:5] != b"%PDF-":
                    continue
                f.write_bytes(d)
            autores = [a.findtext(A + "name") for a in e.findall(A + "author")]
            out.append({"id": aid, "archivo": f.name, "titulo": re.sub(r"\s+", " ", e.findtext(A + "title")).strip(), "autor": autores[0] if autores else "", "cat": cat, "genero": g, "subgenero": sub})
    except Exception as ex:
        print("fallo", cat, type(ex).__name__, str(ex)[:80], flush=True)
    print(cat, sum(1 for o in out if o["cat"] == cat), flush=True)
(D / "arxiv_etiquetas.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(out), "artículos")
