"""Compara modelos de embeddings para clasificar el género (y el subgénero) de un libro, con 84 libros de prueba (título + una frase).

    python herramientas/comparar_clasificadores.py                 # los tres modelos de la lista MODELOS
    python herramientas/comparar_clasificadores.py minishlab/potion-multilingual-128M
    python herramientas/comparar_clasificadores.py --llm qwen2.5:3b       # mide el LLM local (Ollama): solo, y en el híbrido (solo se le pregunta lo dudoso)

Muestra, por modelo: acierto de las reglas solas, del parecido solo (sin biblioteca, solo las semillas) y del híbrido (lo que hace el importador),
el tiempo por libro y los fallos del híbrido. La primera vez descarga cada modelo (0,2-1 GB) a conocimiento/modelos/.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODELOS = ["sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "minishlab/potion-multilingual-128M", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"]

ORO = {
    "historia": [("SPQR: A History of Ancient Rome", "The rise of Rome from a small village to the center of a vast empire and its legacy."),
                 ("La caída de Constantinopla", "Crónica del asedio otomano de 1453 y el final del Imperio bizantino."),
                 ("Guns, Germs, and Steel", "Why some human societies came to dominate others over the last thirteen thousand years."),
                 ("Los Reyes Católicos", "El reinado de Isabel y Fernando, la unificación de España y la expansión atlántica."),
                 ("The Guns of August", "The first month of the First World War and the decisions of European leaders in 1914."),
                 ("Breve historia de la Revolución francesa", "Causas, desarrollo y consecuencias de la revolución de 1789 y el Terror.")],
    "economia": [("The Wealth of Nations", "Division of labor, markets and the invisible hand as sources of national prosperity."),
                 ("El capital en el siglo XXI", "Distribución de la riqueza y la desigualdad, el crecimiento y el rendimiento del capital."),
                 ("A Random Walk Down Wall Street", "Investing in stocks and bonds, market efficiency and portfolio strategy for individuals."),
                 ("Principios de economía", "Oferta, demanda, elasticidad, inflación y política monetaria explicadas a estudiantes."),
                 ("Poor Economics", "How poverty, microcredit and household decisions shape the lives of the poor."),
                 ("Manual de valoración de empresas", "Flujos de caja descontados, múltiplos y estructura de capital para valorar compañías.")],
    "ensayo": [("Meditaciones", "Reflexiones del emperador sobre la virtud, el deber y la aceptación del destino."),
               ("Thus Spoke Zarathustra", "A philosophical work on the overman, eternal recurrence and the death of God."),
               ("Ensayos", "Reflexiones personales sobre la amistad, la muerte y la costumbre."),
               ("The Myth of Sisyphus", "An essay on the absurd and whether life is worth living."),
               ("Crítica de la razón pura", "Los límites del conocimiento, la metafísica y las condiciones de la experiencia."),
               ("On Liberty", "The limits of power society can legitimately exercise over the individual.")],
    "estadistica": [("An Introduction to Statistical Learning", "Linear regression, classification, resampling, trees and cross-validation with applications."),
                    ("Inferencia estadística", "Estimación puntual, intervalos de confianza y contrastes de hipótesis con verosimilitud."),
                    ("Bayesian Data Analysis", "Prior and posterior distributions, hierarchical models and MCMC computation."),
                    ("Probabilidad y procesos estocásticos", "Variables aleatorias, esperanza, cadenas de Markov y teoremas límite."),
                    ("Linear Algebra Done Right", "Vector spaces, linear maps, eigenvalues and inner products without determinants."),
                    ("Análisis de supervivencia", "Kaplan-Meier, modelo de Cox y censura en datos de tiempo hasta evento.")],
    "ciencia": [("A Brief History of Time", "From the big bang to black holes, a popular account of cosmology and space-time."),
                ("El gen egoísta", "La evolución vista desde los genes como unidades de selección natural."),
                ("Cosmos", "A journey through the universe, stars, planets and the scientific method."),
                ("Silent Spring", "How pesticides damaged ecosystems, birds and the environment."),
                ("Química orgánica básica", "Estructura de los compuestos del carbono, reacciones y mecanismos."),
                ("Fundamentos de física cuántica", "Ondas de materia, el principio de incertidumbre y la ecuación de Schrödinger.")],
    "novela": [("Cien años de soledad", "La saga de la familia Buendía en el pueblo imaginario de Macondo."),
               ("The Great Gatsby", "A mysterious millionaire, a lost love and the decline of the American dream in the 1920s."),
               ("El nombre de la rosa", "Un monje franciscano investiga unos asesinatos en una abadía medieval."),
               ("The Hobbit", "A hobbit joins dwarves and a wizard on a quest to reclaim a treasure guarded by a dragon."),
               ("Crimen y castigo", "Un joven estudiante comete un asesinato y lo atormenta la culpa en San Petersburgo."),
               ("Murder on the Orient Express", "A detective investigates a murder aboard a snowbound train.")],
    "biografia": [("Steve Jobs", "The life of the Apple co-founder based on interviews: childhood, career and death."),
                  ("Memorias de Adriano", "La vida del emperador contada en primera persona al final de sus días."),
                  ("The Autobiography of Benjamin Franklin", "Franklin tells the story of his early life, his work as a printer and his public career."),
                  ("Long Walk to Freedom", "Memoir of Nelson Mandela: childhood, imprisonment and the struggle against apartheid."),
                  ("Vida de Beethoven", "Biografía del compositor: su infancia, sordera, obras y muerte en Viena."),
                  ("Einstein: His Life and Universe", "A biography of the physicist, his family, his work and his politics.")],
    "politica": [("The Prince", "Advice on acquiring and keeping political power, statecraft and rulers."),
                 ("La democracia en América", "Análisis de las instituciones, la igualdad y el gobierno en Estados Unidos."),
                 ("The Origins of Totalitarianism", "Antisemitism, imperialism and the rise of totalitarian regimes."),
                 ("Geopolítica de las crisis", "Relaciones internacionales, conflictos, alianzas y orden mundial tras la guerra fría."),
                 ("Imagined Communities", "The origins of nationalism and how nations are imagined by their members."),
                 ("Manual de campañas electorales", "Estrategia, partidos, elecciones y opinión pública.")],
    "tecnologia": [("Clean Code", "Writing readable, maintainable software: functions, naming and refactoring."),
                   ("Python para análisis de datos", "Manipulación de datos con pandas y NumPy, y visualización."),
                   ("The Pragmatic Programmer", "Practical advice for developers on tools, design and automation."),
                   ("Redes de computadores", "Protocolos TCP/IP, enrutamiento, internet y seguridad."),
                   ("Deep Learning", "Neural networks, backpropagation, convolutional and recurrent architectures."),
                   ("Sistemas operativos", "Procesos, memoria virtual, planificación y sistemas de ficheros en Linux.")],
    "psicologia": [("Thinking, Fast and Slow", "Two systems of thought, cognitive biases and decision making."),
                   ("El hombre en busca de sentido", "Experiencia en campos de concentración y la logoterapia para encontrar propósito."),
                   ("Cognitive Behavioral Therapy", "Techniques for anxiety, depression, thoughts and behavior."),
                   ("Inteligencia emocional", "Cómo las emociones influyen en las relaciones, el trabajo y la salud mental."),
                   ("Why We Sleep", "The science of sleep, memory, dreams and health."),
                   ("Manual de psicopatología", "Trastornos mentales, diagnóstico, síntomas y tratamiento.")],
    "arte": [("The Story of Art", "From cave paintings to modern art: painters, sculptors and movements."),
             ("Historia de la música occidental", "Compositores, estilos y épocas desde el canto gregoriano hasta el siglo XX."),
             ("Ways of Seeing", "How we look at paintings, photography and advertising images."),
             ("Poesía completa", "Poemas de amor, naturaleza y tiempo en verso libre."),
             ("Arquitectura moderna", "Le Corbusier, el funcionalismo y la arquitectura del siglo XX."),
             ("El cine como arte", "Directores, montaje, géneros y lenguaje cinematográfico.")],
}

ORO.update({
    "cocina": [("Carbonara con guanciale: recetas romanas", "Recetas de pasta, ingredientes, guanciale, yemas y pecorino paso a paso."),
               ("On Food and Cooking", "The science and lore of the kitchen: techniques, ingredients and why recipes work.")],
    "derecho": [("Manual de derecho civil", "Contratos, propiedad, obligaciones y sociedades mercantiles explicados para estudiantes."),
                ("Derecho penal: parte general", "Delitos, penas, culpabilidad y procesos judiciales en el sistema penal.")],
    "salud": [("Anatomía de Gray", "Anatomía humana, órganos, sistemas, fisiología y diagnóstico por imagen."),
              ("Epidemias y salud pública", "Vacunas, pandemias, epidemiología y cómo se organizan los sistemas sanitarios.")],
    "viajes": [("Lonely Planet Italia", "Guía de viaje con itinerarios, ciudades, alojamiento y consejos para visitar el país."),
               ("A Walk in the Woods", "A travel memoir about hiking the Appalachian Trail and the people met along the way.")],
    "idiomas": [("English Grammar in Use", "Grammar explanations and exercises for learners of English: tenses, vocabulary and practice."),
                ("Etimologías del español", "Origen de las palabras, historia de la lengua y lingüística histórica.")],
    "educacion": [("Técnicas de estudio para oposiciones", "Cómo memorizar, planificar el temario y preparar exámenes y oposiciones."),
                  ("Pedagogía del oprimido", "Educación, enseñanza, docentes, alumnos y práctica pedagógica liberadora.")],
    "religion": [("La Biblia comentada", "Antiguo y Nuevo Testamento, teología cristiana, Jesús y la iglesia primitiva."),
                 ("El Corán y el islam", "Introducción al islam, sus textos sagrados, el judaísmo, el budismo y otras religiones.")],
    "deporte": [("Entrenamiento de fuerza para corredores", "Planes de entrenamiento, running, carga, recuperación y rendimiento deportivo."),
                ("Ajedrez: aperturas y táctica", "Aperturas de ajedrez, finales, táctica y partidas comentadas de grandes maestros.")],
    "hogar": [("Manual de carpintería para principiantes", "Herramientas, uniones de madera, reparaciones y proyectos de bricolaje en casa."),
              ("El huerto en casa", "Cómo plantar, regar y cuidar un huerto y un jardín: semillas, hortalizas y compost.")],
})

# Subgénero esperado de cada libro (para medir el segundo nivel)
SUB = {
    "SPQR: A History of Ancient Rome": "antigua", "La caída de Constantinopla": "medieval", "Guns, Germs, and Steel": "arqueologia", "Los Reyes Católicos": "espana",
    "The Guns of August": "guerras_mundiales", "Breve historia de la Revolución francesa": "revoluciones",
    "The Wealth of Nations": "historia_eco", "El capital en el siglo XXI": "desarrollo", "A Random Walk Down Wall Street": "inversion", "Principios de economía": "macro",
    "Poor Economics": "desarrollo", "Manual de valoración de empresas": "finanzas",
    "Meditaciones": "antigua", "Thus Spoke Zarathustra": "existencialismo", "Ensayos": "ensayo_lit", "The Myth of Sisyphus": "existencialismo", "Crítica de la razón pura": "moderna", "On Liberty": "politica_fil",
    "An Introduction to Statistical Learning": "ml_est", "Inferencia estadística": "inferencia", "Bayesian Data Analysis": "bayes", "Probabilidad y procesos estocásticos": "probabilidad",
    "Linear Algebra Done Right": "algebra", "Análisis de supervivencia": "supervivencia",
    "A Brief History of Time": "cosmos", "El gen egoísta": "biologia", "Cosmos": "cosmos", "Silent Spring": "ecologia", "Química orgánica básica": "quimica", "Fundamentos de física cuántica": "fisica",
    "Cien años de soledad": "contemporanea", "The Great Gatsby": "clasicos", "El nombre de la rosa": "historica", "The Hobbit": "fantasia", "Crimen y castigo": "clasicos", "Murder on the Orient Express": "negra",
    "Steve Jobs": "empresarios", "Memorias de Adriano": "politicos", "The Autobiography of Benjamin Franklin": "memorias", "Long Walk to Freedom": "politicos", "Vida de Beethoven": "artistas", "Einstein: His Life and Universe": "cientificos",
    "The Prince": "persuasion", "La democracia en América": "instituciones", "The Origins of Totalitarianism": "nacionalismo", "Geopolítica de las crisis": "internacional", "Imagined Communities": "nacionalismo", "Manual de campañas electorales": "instituciones",
    "Clean Code": "programacion", "Python para análisis de datos": "datos", "The Pragmatic Programmer": "ingenieria_sw", "Redes de computadores": "redes", "Deep Learning": "ia", "Sistemas operativos": "redes",
    "Thinking, Fast and Slow": "cognitiva", "El hombre en busca de sentido": "sentido", "Cognitive Behavioral Therapy": "clinica", "Inteligencia emocional": "emocional", "Why We Sleep": "sueno", "Manual de psicopatología": "clinica",
    "The Story of Art": "visuales", "Historia de la música occidental": "musica", "Ways of Seeing": "ver", "Poesía completa": "poesia", "Arquitectura moderna": "arquitectura", "El cine como arte": "cine",
    "Carbonara con guanciale: recetas romanas": "recetas", "On Food and Cooking": "tecnica", "Manual de derecho civil": "civil", "Derecho penal: parte general": "penal",
    "Anatomía de Gray": "medicina", "Epidemias y salud pública": "epidemiologia", "Lonely Planet Italia": "guias", "A Walk in the Woods": "relatos",
    "English Grammar in Use": "aprendizaje", "Etimologías del español": "linguistica", "Técnicas de estudio para oposiciones": "estudio", "Pedagogía del oprimido": "pedagogia",
    "La Biblia comentada": "cristianismo", "El Corán y el islam": "otras", "Entrenamiento de fuerza para corredores": "deportes", "Ajedrez: aperturas y táctica": "juegos",
    "Manual de carpintería para principiantes": "bricolaje", "El huerto en casa": "jardin",
}


def evaluar(modelo: str) -> dict:
    from conocimiento import clasificador as c
    from conocimiento import importar as im
    os.environ["ARBOL_MODELO"] = modelo
    c._cache.clear()
    vacia = Path(tempfile.mkdtemp())                       # biblioteca vacía: solo cuentan las semillas
    c.CARPETA = RAIZ / "conocimiento"                      # los modelos se guardan siempre en la carpeta de datos del proyecto
    res = {"reglas": 0, "parecido": 0, "hibrido": 0, "n": 0, "seg": 0.0, "fallos": [], "sub": 0, "sub_dado_genero": 0, "sub_fallos": []}
    for g, libros in ORO.items():
        for titulo, frase in libros:
            f = vacia / f"{titulo.replace(':', '')}.txt"
            f.write_text(frase, encoding="utf-8")
            res["n"] += 1
            c.ACTIVO = False
            res["reglas"] += im.clasificar(f, vacia)["genero"] == g
            c.ACTIVO = True
            t0 = time.time()
            s = c.sugerir(c.texto_libro(titulo, [], frase), RAIZ / "conocimiento")
            res["seg"] += time.time() - t0
            res["parecido"] += bool(s) and s["genero"] == g
            h = im.clasificar(f, vacia)
            res["hibrido"] += h["genero"] == g
            esperado = SUB.get(titulo)
            if esperado:
                sg = c.subgenero(c.texto_libro(titulo, [], frase), g, RAIZ / "conocimiento")           # subgénero dado el género correcto
                res["sub_dado_genero"] += bool(sg) and sg["id"] == esperado
                res["sub"] += h["genero"] == g and h.get("subgenero") == esperado                       # de principio a fin
                if not (sg and sg["id"] == esperado):
                    res["sub_fallos"].append(f"{titulo}: {sg['id'] if sg else '—'} (era {esperado})")
            if h["genero"] != g:
                res["fallos"].append(f"{titulo}: {h['genero']} (era {g}, {h['metodo']})")
    return res


def evaluar_llm(modelo_llm: str) -> None:
    from conocimiento import clasificador as c
    from conocimiento import importar as im
    from conocimiento import llm
    os.environ["ARBOL_LLM"] = modelo_llm
    os.environ["ARBOL_MODELO"] = MODELOS[0]
    c._cache.clear(); llm._estado.clear()
    c.CARPETA = RAIZ / "conocimiento"; c.ACTIVO = True; c.WEB = False
    vacia = Path(tempfile.mkdtemp())
    n = base_ok = llm_ok = hib_ok = dudosos = dudosos_base_ok = dudosos_llm_ok = 0
    seg, fallos = 0.0, []
    for g, libros in ORO.items():
        for titulo, frase in libros:
            f = vacia / f"{titulo.replace(':', '')}.txt"
            f.write_text(frase, encoding="utf-8")
            llm.ACTIVO = False
            b = im.clasificar(f, vacia)                                  # reglas + parecido
            gp = {x["id"]: x["puntos"] for x in b["generos"]}
            dud = c.dudoso(gp, c.sugerir(c.texto_libro(titulo, [], frase), RAIZ / "conocimiento"))
            llm.ACTIVO = True
            t0 = time.time()
            r = llm.clasificar(titulo, [], frase, [], im.GENEROS, vacia)
            seg += time.time() - t0
            if r is None:
                print("El LLM no responde: ¿está Ollama en marcha y bajado el modelo?", modelo_llm)
                return
            n += 1
            base_ok += b["genero"] == g
            llm_ok += r["genero"] == g
            hib = r["genero"] if dud else b["genero"]
            hib_ok += hib == g
            dudosos += dud
            dudosos_base_ok += dud and b["genero"] == g
            dudosos_llm_ok += dud and r["genero"] == g
            if r["genero"] != g:
                fallos.append(f"{titulo}: LLM {r['genero']} (era {g}) {'[dudoso]' if dud else ''}")
    print(f"Modelo {modelo_llm} sobre {n} libros:")
    print(f"  reglas + parecido         {base_ok / n:4.0%}")
    print(f"  LLM solo                  {llm_ok / n:4.0%}   ({seg / n:.1f} s por consulta)")
    print(f"  híbrido (LLM si dudoso)   {hib_ok / n:4.0%}   (pregunta al LLM en {dudosos} de {n}: ahí base acierta {dudosos_base_ok}, LLM {dudosos_llm_ok})")
    for x in fallos:
        print("  -", x)


def main() -> None:
    if "--llm" in sys.argv:
        i = sys.argv.index("--llm")
        evaluar_llm(sys.argv[i + 1] if len(sys.argv) > i + 1 else "qwen2.5:3b")
        return
    modelos = sys.argv[1:] or MODELOS
    print(f"{'modelo':62} {'reglas':>7} {'parecido':>9} {'híbrido':>8} {'s/libro':>8}")
    detalle = {}
    for m in modelos:
        try:
            r = evaluar(m)
        except Exception as e:
            print(f"{m:62} no disponible: {type(e).__name__}: {str(e)[:80]}")
            continue
        n = r["n"]
        print(f"{m:62} {r['reglas'] / n:7.0%} {r['parecido'] / n:9.0%} {r['hibrido'] / n:8.0%} {r['seg'] / n:8.2f}   subgénero: {r['sub_dado_genero'] / n:4.0%} (dado el género) · {r['sub'] / n:4.0%} (de principio a fin)")
        detalle[m] = r["fallos"]
        detalle[m + " [subgénero]"] = r["sub_fallos"]
    for m, fl in detalle.items():
        print(f"\nFallos del híbrido con {m.split('/')[-1]} ({len(fl)}):")
        for x in fl:
            print("  -", x)


if __name__ == "__main__":
    main()
