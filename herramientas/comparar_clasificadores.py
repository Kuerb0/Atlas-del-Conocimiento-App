"""Compara modelos de embeddings para clasificar el género de un libro, con 66 libros de prueba (título + una frase).

    python herramientas/comparar_clasificadores.py                 # los tres modelos de la lista MODELOS
    python herramientas/comparar_clasificadores.py minishlab/potion-multilingual-128M

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


def evaluar(modelo: str) -> dict:
    from conocimiento import clasificador as c
    from conocimiento import importar as im
    os.environ["ARBOL_MODELO"] = modelo
    c._cache.clear()
    vacia = Path(tempfile.mkdtemp())                       # biblioteca vacía: solo cuentan las semillas
    c.CARPETA = RAIZ / "conocimiento"                      # los modelos se guardan siempre en la carpeta de datos del proyecto
    res = {"reglas": 0, "parecido": 0, "hibrido": 0, "n": 0, "seg": 0.0, "fallos": []}
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
            if h["genero"] != g:
                res["fallos"].append(f"{titulo}: {h['genero']} (era {g}, {h['metodo']})")
    return res


def main() -> None:
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
        print(f"{m:62} {r['reglas'] / n:7.0%} {r['parecido'] / n:9.0%} {r['hibrido'] / n:8.0%} {r['seg'] / n:8.2f}")
        detalle[m] = r["fallos"]
    for m, fl in detalle.items():
        print(f"\nFallos del híbrido con {m.split('/')[-1]} ({len(fl)}):")
        for x in fl:
            print("  -", x)


if __name__ == "__main__":
    main()
