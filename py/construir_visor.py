"""Genera el visor interactivo del árbol (visor_arbol.html) leyendo el propio código.

Uso (desde la carpeta principal del árbol):
    python py/construir_visor.py     # escribe visor_arbol.html (abrir con doble clic en el navegador)
    (o doble clic en regenerar_visor.bat)

El resultado es un único .html autocontenido: sin internet, sin servidor y sin depender de ninguna herramienta.

Qué lee:
  * py/arbol_estadistica/<rama>/*.py -> funciones públicas (firma, docstring, código, línea)
  * INDEX.md                       -> "para qué", equivalente SAS y origen de cada función
  * conceptos/catalogo.json         -> rama "Conceptos y temario" (conceptos del máster y de Very Normal,
                                      con enlace a las funciones del árbol cuando existen)
  * teoria/*.md, CLAUDE.md, ejemplos/*.py -> rama "Guías y ejemplos"
  * DEMOS (aquí) + visor/demos.js   -> rama "Cómo funciona" (demos interactivas, sin internet)
  * visor/mapa3d.js                 -> mapa 3D del árbol (canvas, sin librerías): núcleo, ramas en órbita, hojas y enlaces
  * propiedades/*.json              -> fichas de propiedades de cada función (barras 0-10, perfiles de proyecto):
                                      propiedades.json (definiciones y perfiles), fichas.json (notas estimadas, pros y
                                      contras), medidas.json (lo medido por medir_propiedades.py) y, si existe,
                                      conceptos/fichas_mias.json (tus notas: mandan sobre todo lo demás)
Regenerar después de añadir o cambiar funciones (el visor no se actualiza solo).
"""
from __future__ import annotations

import ast
import datetime as dt
import json
import re
from pathlib import Path

CODIGO = Path(__file__).resolve().parent      # .../py  (paquete, tests, plantilla del visor)
RAIZ = CODIGO.parent                           # carpeta principal: INDEX.md, teoria/, conceptos/, visor_arbol.html
PAQUETE = CODIGO / "arbol_estadistica"
RAIZ_POR_DEFECTO = str(RAIZ)

RAMAS = [
    ("preprocesado", "Preparar datos", "Dejar los datos listos antes de modelar: tramos, balanceo, codificación."),
    ("seleccion", "Elegir variables", "Qué variables merece la pena probar y cuáles entran al modelo."),
    ("modelos", "Modelos", "Ajustar y explicar modelos: logística, multinomial, GLM, Firth, elasticidad."),
    ("diagnostico", "Diagnóstico", "¿Es fiable el modelo? Colinealidad, calibración, asociación, umbrales."),
    ("clustering", "Segmentación", "Agrupar en segmentos: K-Means, selección de K, PCA."),
    ("contrastes", "Contrastes", "Comparar grupos, elegir el test correcto, potencia y tamaño muestral, FDR."),
    ("graficos", "Gráficos", "Gráficos de matplotlib listos para notebooks: regresión, logística, contrastes, supervivencia."),
    ("descriptiva", "Descriptiva", "Resumen numérico, atípicos, correlaciones, supuestos, ajuste de distribuciones y tablas.",
     {"claro": "#0369A1", "oscuro": "#7DD3FC"}),
    ("multivariante", "Multivariante", "Mahalanobis, Hotelling, MANOVA, PCA, factorial, Cronbach, correspondencias, jerárquico, mezclas, discriminante.",
     {"claro": "#4338CA", "oscuro": "#A5B4FC"}),
    ("ml", "Machine learning", "Árboles, random forest, boosting, k-NN, SVM, redes, stacking; comparación por CV y explicabilidad.",
     {"claro": "#A21CAF", "oscuro": "#F0ABFC"}),
    ("actuarial", "Actuarial", "Tablas de vida, seguros y rentas, primas y provisiones, reservas, agregada, ruina, credibilidad, demografía.",
     {"claro": "#9A3412", "oscuro": "#FDBA74"}),
    ("finanzas", "Finanzas y riesgo", "VaR/TVaR, valores extremos, cópulas, estrés, carteras, CAPM, Black-Litterman, bonos, swaps y opciones.",
     {"claro": "#4D7C0F", "oscuro": "#BEF264"}),
    ("simulacion", "Probabilidad y simulación", "Bayes (conjugadas, MCMC, A/B, bandidos), procesos estocásticos y Markov, Monte Carlo, estimadores y muestreo de encuestas.",
     {"claro": "#0F766E", "oscuro": "#5EEAD4"}),
    ("diseno", "Diseño y causalidad", "ANOVA y diseños (bloques, ANCOVA, medidas repetidas, anidado), 2^k y superficies de respuesta, propensión, DiD, ensayos, mediación y metaanálisis.",
     {"claro": "#B45309", "oscuro": "#FCD34D"}),
]
# Ramas añadidas después de la 0.8: llevan su color aquí (las primeras lo tienen en la plantilla y en mapa3d.js).

# Demos interactivas (rama «Cómo funciona»). El código de cada una está en visor/demos.js con la misma clave.
DEMOS = [
    ("Fundamentos", "Conceptos básicos: las distribuciones fundamentales", [
        {"id": "demo_dist_animada", "nombre": "Se dibujan al añadir datos",
         "desc": "Elige una distribución (uniforme, normal, exponencial, Bernoulli, binomial, geométrica, Poisson, gamma, beta, chi-cuadrado, t, lognormal, Weibull) y añade observaciones de una en una, de 10 en 10 o en reproducción continua: el histograma va tomando la forma de la curva teórica.",
         "aprender": "Con pocos datos el histograma es irregular y la media muestral se mueve mucho; al crecer n se aproxima a la distribución teórica y la media se estabiliza (ley de los grandes números), con un error típico σ/√n. Si la distribución no tiene media o varianza finita (t con 1 gl = Cauchy) la media NO se estabiliza nunca.",
         "funciones": ["generar_por_inversion", "convergencia_media_muestral", "grafico_qq"],
         "conceptos": ["c_distribucion_uniforme", "c_distribucion_de_bernoulli", "c_distribucion_geometrica", "c_distribucion_exponencial",
                       "c_distribucion_de_weibull", "c_distribucion_normal", "c_distribucion_binomial", "c_distribucion_de_poisson",
                       "c_distribuciones_chi_cuadrado_y_f", "c_ley_de_los_grandes_numeros", "c_generacion_de_variables_aleatorias"]},
        {"id": "demo_dist_galeria", "nombre": "Galería de distribuciones básicas",
         "desc": "Todas las distribuciones fundamentales (continuas y discretas) una al lado de otra con sus parámetros por defecto, su media, su varianza y para qué se usan.",
         "aprender": "Cada familia responde a una situación: uniforme (todo igual de probable), normal (suma de efectos), exponencial y Weibull (tiempos), Bernoulli, binomial, geométrica y Poisson (sucesos y conteos), gamma y lognormal (importes positivos), beta (proporciones), t y chi-cuadrado (inferencia). Comparar formas ayuda a elegir la familia antes de ajustar.",
         "funciones": ["ajustar_distribuciones", "ajustar_distribucion_discreta", "momentos_distribucion"],
         "conceptos": ["c_variables_aleatorias_y_distribuciones", "c_distribucion_uniforme", "c_distribucion_de_bernoulli", "c_distribucion_geometrica",
                       "c_distribucion_exponencial", "c_distribucion_de_weibull", "c_distribucion_normal", "c_distribucion_binomial",
                       "c_distribucion_de_poisson", "c_distribucion_binomial_negativa", "c_distribucion_gamma", "c_distribucion_lognormal",
                       "c_distribucion_t_de_student", "c_distribuciones_chi_cuadrado_y_f"]},
    ]),
    ("Contrastes", "Contrastes de hipótesis vistos por dentro", [
        {"id": "demo_contraste_t", "nombre": "Cómo decide un t-test",
         "desc": "Dos grupos simulados: mueve la diferencia real y el tamaño, mira dónde cae el estadístico t y cuántas veces se rechaza H0 al repetir el experimento.",
         "aprender": "El p-valor cambia de una muestra a otra. Con diferencia real 0, alrededor de un alpha de las repeticiones salen «significativas» por azar (error tipo I); con diferencia real, el porcentaje de rechazos ES la potencia.",
         "funciones": ["elegir_contraste", "grafico_region_rechazo", "grafico_comparar_grupos"],
         "conceptos": ["c_contraste_de_hipotesis", "c_significacion_estadistica_y_p_valor", "c_test_t_y_test_t_de_welch", "c_error_tipo_i_y_potencia"]},
        {"id": "demo_potencia", "nombre": "Potencia y tamaño muestral",
         "desc": "Las distribuciones del estadístico sin efecto (H0) y con efecto (H1): alpha, beta y potencia como áreas.",
         "aprender": "La potencia sube al aumentar n o el efecto (las curvas se separan) y al aumentar alpha (el corte se mueve). Para efectos pequeños (d = 0.2) hacen falta cientos de observaciones por grupo: el «n = 30» no garantiza nada.",
         "funciones": ["tamano_muestral_medias", "potencia_contraste_medias", "grafico_potencia", "grafico_curva_potencia"],
         "conceptos": ["c_error_tipo_i_y_potencia", "c_tamano_muestral"]},
        {"id": "demo_fdr", "nombre": "Muchos contrastes a la vez (FDR)",
         "desc": "Simula decenas o cientos de contrastes, unos con efecto real y otros no, y compara cuántos falsos descubrimientos deja pasar cada criterio.",
         "aprender": "Sin corregir, los falsos positivos crecen con el nº de contrastes. Bonferroni casi los elimina pero se deja efectos reales; Benjamini-Hochberg mantiene la proporción de falsos descubrimientos cerca de alpha encontrando bastantes más efectos.",
         "funciones": ["ajustar_p_valores", "grafico_fdr"],
         "conceptos": ["c_tasa_de_falsos_descubrimientos_fdr", "c_significacion_estadistica_y_p_valor"]},
    ]),
    ("Probabilidad", "Distribuciones: forma, media, varianza y probabilidades", [
        {"id": "demo_distribuciones", "nombre": "Explorador de distribuciones",
         "desc": "Elige una distribución (normal, t, lognormal, gamma, inversa gaussiana, Poisson, binomial negativa, Pareto…), mueve sus parámetros y mira la densidad, la acumulada y P(X ≤ x).",
         "aprender": "Cada familia tiene su forma: simétrica (normal, t), asimétrica a la derecha (lognormal, gamma, inversa gaussiana: importes y siniestros) o discreta (Poisson, binomial negativa: número de siniestros). Comparar con la normal de igual media y varianza enseña las colas pesadas y por qué un supuesto normal infravalora los extremos.",
         "funciones": ["grafico_qq"],
         "conceptos": ["c_distribucion_normal", "c_distribucion_t_de_student", "c_distribucion_lognormal", "c_distribucion_gamma",
                       "c_distribucion_inversa_gaussiana", "c_distribucion_binomial", "c_distribucion_de_poisson",
                       "c_distribucion_binomial_negativa", "c_distribucion_compuesta_poisson_gamma", "c_distribuciones_de_la_clase_a_b_0_y_a_b_1",
                       "c_distribuciones_con_colas_pesadas", "c_familias_parametricas", "c_variables_aleatorias_y_distribuciones",
                       "c_glm_de_conteo_poisson_y_binomial_negativa", "c_glm_de_variable_continua_gamma_e_inversa_gaussiana", "c_sobredispersion",
                       "c_value_at_risk_var", "c_tvar_y_medidas_coherentes_de_riesgo", "c_teoria_de_valores_extremos", "c_siniestralidad_agregada"]},
    ]),
    ("Inferencia", "Estimar con incertidumbre", [
        {"id": "demo_intervalos", "nombre": "Qué significa un IC del 95 %",
         "desc": "50 muestras, 50 intervalos de confianza: los naranjas no contienen la media verdadera.",
         "aprender": "El 95 % describe el PROCEDIMIENTO: a la larga, 95 de cada 100 intervalos contienen el valor verdadero. Un intervalo concreto lo contiene o no; no hay un 95 % de probabilidad «dentro» de él. Más n = intervalos más estrechos, no más cobertura.",
         "funciones": ["grafico_regresion_simple"],
         "conceptos": ["c_intervalos_de_confianza", "c_estadisticos_y_estimadores"]},
        {"id": "demo_tcl", "nombre": "Teorema central del límite",
         "desc": "Elige una población (asimétrica, bimodal, rara…) y mira cómo se distribuyen las medias muestrales al subir n.",
         "aprender": "La media de n observaciones tiende a una normal aunque la población no lo sea, pero la velocidad depende de la asimetría: con poblaciones muy sesgadas o sucesos raros n = 30 se queda corto.",
         "funciones": ["grafico_qq", "elegir_contraste"],
         "conceptos": ["c_teorema_central_del_limite", "c_distribucion_normal", "c_variables_aleatorias_y_distribuciones"]},
    ]),
    ("Modelos", "Qué hace el modelo con tus datos", [
        {"id": "demo_regresion", "nombre": "Regresión lineal y atípicos",
         "desc": "Mueve pendiente, ruido y tamaño; añade un punto atípico con mucho apalancamiento y mira cómo arrastra la recta.",
         "aprender": "Más ruido = estimación más incierta (IC más ancho) y R² más bajo aunque la pendiente sea la misma. Un solo punto alejado en X puede cambiar la recta: por eso se mira la distancia de Cook en el diagnóstico de residuos.",
         "funciones": ["grafico_regresion_simple", "grafico_diagnostico_residuos"],
         "conceptos": ["c_regresion_lineal", "c_diagnostico_de_residuos"]},
        {"id": "demo_logistica", "nombre": "Curva logística y odds ratio",
         "desc": "Mueve el intercepto y el coeficiente: la curva de probabilidad, el odds ratio y la regla de «dividir entre 4».",
         "aprender": "El coeficiente actúa sobre el log-odds: exp(β1) es el odds ratio y es constante, pero el efecto sobre la PROBABILIDAD depende de dónde estés en la curva (máximo β1/4 cerca de p = 0.5, casi nulo en los extremos).",
         "funciones": ["ajustar_logit", "tabla_odds_ratios", "grafico_odds_ratios"],
         "conceptos": ["c_regresion_logistica_binaria", "c_odds_ratio", "c_funcion_de_enlace_logit_probit_y_cloglog"]},
        {"id": "demo_censura", "nombre": "Censura y Kaplan-Meier",
         "desc": "Tiempos de supervivencia simulados con censura: compara Kaplan-Meier con el error típico de quitar a los censurados.",
         "aprender": "Quitar a los censurados sesga la supervivencia hacia abajo: precisamente los que más duran son los que más se censuran. Kaplan-Meier los usa mientras están en riesgo y recupera la curva verdadera.",
         "funciones": ["kaplan_meier", "grafico_kaplan_meier", "contraste_log_rank"],
         "conceptos": ["c_analisis_de_supervivencia_y_censura", "c_estimador_de_kaplan_meier"]},
    ]),
    ("Simulación", "Procesos que evolucionan paso a paso", [
        {"id": "demo_mcmc", "nombre": "MCMC: el algoritmo de Metropolis",
         "desc": "Una cadena que camina por una distribución de dos picos: mueve el tamaño del salto, la separación de los picos y el punto de partida, y mira la traza, el histograma y la tasa de aceptación.",
         "aprender": "Un salto demasiado grande rechaza casi todo y uno demasiado pequeño acepta todo pero avanza despacio: en los dos casos hay pocas muestras efectivas. Con picos separados la cadena puede quedarse en uno solo y parecer que converge; por eso se usan varias cadenas, R-hat y la traza.",
         "funciones": ["metropolis", "diagnostico_mcmc", "grafico_trazas_mcmc"],
         "conceptos": ["c_algoritmo_de_metropolis_y_mcmc"]},
        {"id": "demo_markov", "nombre": "Cadenas de Markov y distribución estacionaria",
         "desc": "Tres cadenas de ejemplo (tiempo, bonus-malus, estado absorbente): cómo evoluciona la probabilidad de cada estado y a qué distribución estacionaria converge; simula una trayectoria de 1000 pasos.",
         "aprender": "La cadena olvida su estado inicial y converge a π, la distribución estacionaria; la fracción de tiempo en cada estado de una trayectoria larga coincide con π. Más persistencia solo ralentiza la convergencia; con un estado absorbente no hay π única que valga para cualquier inicio.",
         "funciones": ["cadena_markov", "simular_cadena_markov", "bonus_malus"],
         "conceptos": ["c_cadenas_de_markov_en_tiempo_discreto", "c_cadenas_de_markov_regulares_y_modelo_bonus_malus"]},
        {"id": "demo_bandido", "nombre": "Bandidos multibrazo: explorar o explotar",
         "desc": "Tres estrategias (al azar, ε-greedy y Thompson) juegan contra los mismos tres brazos: compara el arrepentimiento acumulado y el porcentaje de tiradas en el mejor brazo.",
         "aprender": "Al azar pierde de forma lineal; ε-greedy explora un 10 % para siempre; Thompson explora mucho al principio y casi solo explota cuando ya sabe cuál es el mejor. Cuanto más parecidos son los brazos, más tarda en distinguirlos.",
         "funciones": ["simular_bandido", "grafico_bandido", "ab_bayesiano"],
         "conceptos": ["c_bandidos_multibrazo"]},
    ]),
    ("Multivariante", "Reducir y agrupar datos", [
        {"id": "demo_pca", "nombre": "PCA: los ejes de máxima varianza",
         "desc": "Una nube de puntos con dos variables: mueve la correlación y la desviación relativa y mira los ejes de las dos componentes principales y la varianza que explica cada una.",
         "aprender": "Con correlación alta la nube se alarga y PC1 recoge casi toda la varianza (una variable basta); con correlación 0 y desviaciones iguales no hay dirección preferente y PCA no reduce nada.",
         "funciones": ["pca_completo", "proyeccion_pca", "grafico_clusters_pca"],
         "conceptos": ["c_analisis_de_componentes_principales_pca", "c_reduccion_de_datos_y_agrupamiento_de_variables", "c_regresion_por_componentes_principales_y_pls"]},
        {"id": "demo_kmeans", "nombre": "K-means: cuántos grupos",
         "desc": "Tres grupos simulados: elige k y la separación real; mira los grupos, la inercia (codo) y el silhouette para k = 1..6.",
         "aprender": "K-means siempre devuelve k grupos, haya o no estructura. Con grupos bien separados la inercia deja de bajar de golpe en k = 3 y el silhouette es máximo ahí; con grupos mezclados no hay codo y el silhouette es bajo.",
         "funciones": ["ajustar_kmeans", "buscar_k_silhouette", "grafico_clusters_pca"],
         "conceptos": ["c_k_means"]},
    ]),
    ("Riesgo", "Colas y pérdidas extremas", [
        {"id": "demo_var", "nombre": "VaR y TVaR: la cola importa",
         "desc": "Tres distribuciones de pérdida con la misma media y dispersión (normal, lognormal, Pareto): compara el VaR y el TVaR según el nivel de confianza y el coeficiente de variación.",
         "aprender": "Con la misma media y desviación, la cola cambia el riesgo: el VaR solo marca el umbral, el TVaR promedia lo que se pierde al superarlo. Con cola pesada (Pareto) el TVaR se aleja mucho más del VaR y la normal infravalora el riesgo extremo.",
         "funciones": ["var_tvar"],
         "conceptos": ["c_value_at_risk_var", "c_tvar_y_medidas_coherentes_de_riesgo", "c_teoria_de_valores_extremos", "c_distribuciones_con_colas_pesadas"]},
    ]),
]
DOCS = {
    "contrastes.md": "Qué test usar: árbol de decisión, supuestos y cómo reportar.",
    "glm.md": "Guía de GLM: familia y enlace, flujo de trabajo, interpretación y problemas típicos.",
    "equivalencias_SAS_Python.md": "Qué función sustituye a cada PROC de SAS y en qué se diferencian.",
    "referencias.md": "Qué manual de tu colección consultar para cada tema.",
}
CATALOGO = RAIZ / "conceptos" / "catalogo.json"
PROPIEDADES = CODIGO / "propiedades"
FICHAS_MIAS = RAIZ / "conceptos" / "fichas_mias.json"
EJEMPLOS = None   # se carga en construir()
AVISO_RE = re.compile(r"OJO|ATENCI[ÓO]N|CORRECCI[ÓO]N|IMPORTANTE|Gauss", re.I)


def leer_indice() -> dict[str, dict]:
    """Tablas de INDEX.md -> {función: {desc, sas, origen}}."""
    info: dict[str, dict] = {}
    for linea in (RAIZ / "INDEX.md").read_text(encoding="utf-8").splitlines():
        if not linea.startswith("|") or set(linea.replace("|", "").strip()) <= set("-: "):
            continue
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if len(celdas) < 4 or celdas[0].lower().startswith("función"):
            continue
        nombres = re.findall(r"`([A-Za-z_]\w*)", celdas[0])
        datos = {"desc": celdas[1].replace("`", ""), "sas": celdas[2].replace("`", ""),
                 "origen": celdas[3].replace("`", "")}
        for n in nombres:
            info.setdefault(n, datos)
    return info


def exportadas(init: Path) -> set[str]:
    try:
        arbol = ast.parse(init.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and any(getattr(t, "id", "") == "__all__" for t in nodo.targets):
            return {e.value for e in nodo.value.elts}
    return set()


def llamada(f: ast.FunctionDef) -> tuple[str, str]:
    a = f.args
    pos = a.posonlyargs + a.args
    n_def = len(a.defaults)
    obligatorios = [x.arg for x in pos[: len(pos) - n_def]]
    opcionales = [f"{x.arg}={ast.unparse(d)}" for x, d in zip(pos[len(pos) - n_def:], a.defaults)]
    opcionales += [f"{x.arg}={ast.unparse(d) if d is not None else '...'}" for x, d in zip(a.kwonlyargs, a.kw_defaults)]
    obligatorios += [x.arg for x, d in zip(a.kwonlyargs, a.kw_defaults) if d is None]
    return f"{f.name}({', '.join(obligatorios)})", ", ".join(opcionales)


def _ejemplos():
    """Celdas de ejemplo (py/cuaderno/ejemplos.py) para la sección «Probar» del visor."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ejemplos_cuaderno", CODIGO / "cuaderno" / "ejemplos.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def funciones_de(archivo: Path, rama: str, exp: set[str], indice: dict) -> list[dict]:
    fuente = archivo.read_text(encoding="utf-8")
    lineas = fuente.splitlines()
    items = []
    for nodo in ast.parse(fuente).body:
        if not isinstance(nodo, ast.FunctionDef) or nodo.name.startswith("_"):
            continue
        ini = min([nodo.lineno] + [d.lineno for d in nodo.decorator_list])
        doc = ast.get_docstring(nodo) or ""
        info = indice.get(nodo.name, {})
        firma = f"{nodo.name}({ast.unparse(nodo.args)})" + (f" -> {ast.unparse(nodo.returns)}" if nodo.returns else "")
        avisos = [l.strip() for l in doc.splitlines() if AVISO_RE.search(l)][:2]
        modulo_imp = f"arbol_estadistica.{rama}" if nodo.name in exp else f"arbol_estadistica.{rama}.{archivo.stem}"
        call, opc = llamada(nodo)
        items.append({
            "id": nodo.name, "nombre": nodo.name, "tipo": "funcion", "firma": firma, "doc": doc,
            "desc": info.get("desc") or (doc.splitlines()[0] if doc else ""),
            "sas": info.get("sas", ""), "origen": info.get("origen", ""),
            "archivo": archivo.relative_to(RAIZ).as_posix(), "linea": ini,
            "lineas": nodo.end_lineno - ini + 1, "codigo": "\n".join(lineas[ini - 1: nodo.end_lineno]),
            "importar": f"from {modulo_imp} import {nodo.name}", "llamada": call, "opcionales": opc,
            "aviso": " ".join(avisos), "ejemplo": EJEMPLOS.celdas_de(nodo.name) or [],
        })
    return items


def ramas_conceptos(funciones: set[str]) -> list[dict]:
    """Ramas de conceptos: una por TEMA del catálogo (módulo = área; hoja = concepto, con o sin código).

    Si el catálogo no define `temas` (catálogos antiguos o mínimos) sale una sola rama «Conceptos y temario».
    Los temas/áreas sin conceptos no se dibujan.
    """
    cat = json.loads(CATALOGO.read_text(encoding="utf-8"))
    temas = cat.get("temas") or [{"id": "conceptos", "nombre": "Conceptos y temario",
                                  "desc": "Qué conceptos conoce el árbol: temario del máster y de Very Normal."}]
    tema_por_defecto = temas[0]["id"]
    areas = {a["id"]: a for a in cat["areas"]}
    ambito_de = {a["id"]: a.get("ambito", "") for a in cat["areas"]}
    archivo = CATALOGO.relative_to(RAIZ).as_posix()

    def item(k: dict) -> dict:
        desconocidas = [f for f in k["funciones"] if f not in funciones]
        if desconocidas:   # no se rompe el visor: se avisa y se ignoran (el test sí lo exige)
            print(f"AVISO: el concepto «{k['nombre']}» cita funciones que no están en py/: {desconocidas} "
                  "(¿falta ejecutar el actualizador?)")
            k = dict(k, funciones=[f for f in k["funciones"] if f in funciones])
        origen = "; ".join({"very_normal": "Very Normal: ", "master": "Máster: ", "manual": "Manual: "}.get(f["tipo"], "Árbol (consultoría): ") + f["ref"] + (f" ({f['base']})" if f.get("base") else "")
                           for f in k["fuentes"])
        return {
            "id": k["id"], "nombre": k["nombre"], "tipo": "concepto", "firma": "", "doc": " ".join(k["sinonimos"] + k["funciones"]),
            "desc": k["desc"], "sas": "", "origen": origen, "archivo": archivo, "linea": 1,
            "lineas": 8 + 4 * len(k["funciones"]), "codigo": "", "importar": "", "llamada": "", "opcionales": "", "aviso": "",
            "texto": "", "funciones": k["funciones"], "sinonimos": k["sinonimos"], "fuentes": k["fuentes"],
            "ambito": ambito_de.get(k.get("area"), ""), "prioridad": k.get("prioridad", ""),
            "ejemplo": (EJEMPLOS.celdas_concepto(k["id"], k["funciones"]) if EJEMPLOS else None) or [],
        }

    ramas = []
    for tema in temas:
        modulos = []
        for area in cat["areas"]:
            if area.get("tema", tema_por_defecto) != tema["id"]:
                continue
            items = [item(k) for k in cat["conceptos"] if k.get("area") == area["id"]]
            if items:
                modulos.append({"id": area["id"], "nombre": area["nombre"], "desc": area.get("desc", ""),
                                "ambito": area.get("ambito", ""), "archivo": archivo, "items": items})
        if modulos:
            rama = {"id": tema["id"], "nombre": tema["nombre"], "desc": tema.get("desc", ""),
                    "grupo": "conceptos", "modulos": modulos}
            if tema.get("color"):
                rama["color"] = tema["color"]
            ramas.append(rama)
    return ramas


def rama_demos(funciones: set[str]) -> dict:
    """Rama «Cómo funciona»: demos interactivas (JS en visor/demos.js) enlazadas a funciones y conceptos."""
    conceptos = {k["id"]: k["nombre"] for k in json.loads(CATALOGO.read_text(encoding="utf-8"))["conceptos"]}
    modulos = []
    for nombre_mod, desc_mod, demos in DEMOS:
        items = []
        for d in demos:
            malas = [f for f in d["funciones"] if f not in funciones] + [c for c in d["conceptos"] if c not in conceptos]
            if malas:
                print(f"AVISO: la demo «{d['nombre']}» enlaza cosas que no existen: {malas}")
                d = dict(d, funciones=[f for f in d["funciones"] if f in funciones],
                         conceptos=[c for c in d["conceptos"] if c in conceptos])
            items.append({
                "id": d["id"], "nombre": d["nombre"], "tipo": "demo", "firma": "", "desc": d["desc"],
                "doc": " ".join([d["aprender"]] + d["funciones"] + [conceptos[c] for c in d["conceptos"]]),
                "aprender": d["aprender"], "relFunciones": d["funciones"], "relConceptos": d["conceptos"],
                "sas": "", "origen": "", "archivo": "py/visor/demos.js", "linea": 1, "lineas": 60, "codigo": "",
                "importar": "", "llamada": "", "opcionales": "", "aviso": "", "texto": "",
            })
        modulos.append({"id": nombre_mod.lower(), "nombre": nombre_mod, "desc": desc_mod, "archivo": "py/visor/demos.js", "items": items})
    return {"id": "demos", "nombre": "Cómo funciona",
            "desc": "Demos interactivas: mueve los controles y mira qué hace cada método.", "modulos": modulos}


def _nota_tests(n: int) -> float:
    """Cobertura de tests medida: nº de veces que los tests citan la función -> nota 0-10."""
    return float({0: 0, 1: 4, 2: 6, 3: 7, 4: 8, 5: 9}.get(n, 10))


def cargar_propiedades(nombres_fn: set[str]) -> tuple[dict, dict]:
    """(meta, fichas): meta = bloques, propiedades, perfiles y grupos; fichas = {función: ficha con notas resueltas}.

    Prioridad de cada nota: conceptos/fichas_mias.json (tuya) > medidas.json (medida) > fichas.json (estimada).
    """
    meta = json.loads((PROPIEDADES / "propiedades.json").read_text(encoding="utf-8"))
    base = json.loads((PROPIEDADES / "fichas.json").read_text(encoding="utf-8"))["funciones"]
    ruta_med = PROPIEDADES / "medidas.json"
    medidas = json.loads(ruta_med.read_text(encoding="utf-8")) if ruta_med.exists() else {"funciones": {}}
    mias = json.loads(FICHAS_MIAS.read_text(encoding="utf-8")).get("funciones", {}) if FICHAS_MIAS.exists() else {}
    validas = {p["id"] for p in meta["propiedades"]}
    textos_tests = " ".join(p.read_text(encoding="utf-8") for p in (CODIGO / "tests").glob("test_*.py"))
    fichas = {}
    for nombre in sorted(nombres_fn):
        b = base.get(nombre, {})
        notas = {k: {"nota": v, "origen": "estimado"} for k, v in b.get("notas", {}).items() if k in validas}
        for k, v in medidas["funciones"].get(nombre, {}).items():
            if k in validas:
                notas[k] = {"nota": v["nota"], "origen": "medido", "detalle": v.get("detalle", "")}
        n_t = len(re.findall(r"\b" + re.escape(nombre) + r"\b", textos_tests))
        notas["cobertura_tests"] = {"nota": _nota_tests(n_t), "origen": "medido", "detalle": f"{n_t} menciones en py/tests/"}
        m = mias.get(nombre, {})
        for k, v in m.get("notas", {}).items():
            if k in validas:
                notas[k] = {"nota": v, "origen": "tuyo"} if v is not None else None
        notas = {k: v for k, v in notas.items() if v is not None}
        fichas[nombre] = {"notas": notas, "grupo": m.get("grupo", b.get("grupo", "")),
                          **{c: m.get(c, b.get(c, [] if c in ("pros", "contras") else "")) for c in ("pros", "contras", "usar_si", "evitar_si")}}
    meta = dict(meta, medido=medidas.get("generado", ""), equipo=medidas.get("equipo", ""))
    return meta, fichas


def construir() -> dict:
    global EJEMPLOS
    EJEMPLOS = _ejemplos()
    indice = leer_indice()
    ramas = []
    for rid, nombre, desc, *color in RAMAS:
        carpeta = PAQUETE / rid
        exp = exportadas(carpeta / "__init__.py")
        modulos = []
        for py in sorted(carpeta.glob("*.py")):
            if py.name == "__init__.py":
                continue
            items = funciones_de(py, rid, exp, indice)
            if items:
                mdoc = (ast.get_docstring(ast.parse(py.read_text(encoding="utf-8"))) or "").splitlines()
                modulos.append({"id": py.stem, "nombre": py.name, "desc": mdoc[0] if mdoc else "",
                                "archivo": py.relative_to(RAIZ).as_posix(), "items": items})
        ramas.append({"id": rid, "nombre": nombre, "desc": desc, "modulos": modulos, **({"color": color[0]} if color else {})})

    nombres_fn = {i["nombre"] for r in ramas for m in r["modulos"] for i in m["items"]}
    meta_prop, fichas = cargar_propiedades(nombres_fn)
    for r in ramas:
        for m in r["modulos"]:
            for i in m["items"]:
                i["ficha"] = fichas[i["nombre"]]
    ramas.extend(ramas_conceptos(nombres_fn))

    guias = []
    for md in sorted((RAIZ / "teoria").glob("*.md")) + [RAIZ / "CLAUDE.md"]:
        texto = md.read_text(encoding="utf-8")
        titulo = next((l[2:].strip() for l in texto.splitlines() if l.startswith("# ")), md.stem)
        guias.append({"id": md.stem, "nombre": md.name, "tipo": "doc", "firma": "", "doc": "", "texto": texto,
                      "desc": DOCS.get(md.name, "Instrucciones de uso del árbol para Claude." if md.name == "CLAUDE.md" else titulo),
                      "sas": "", "origen": "", "archivo": md.relative_to(RAIZ).as_posix(), "linea": 1,
                      "lineas": len(texto.splitlines()), "codigo": "", "importar": "", "llamada": "",
                      "opcionales": "", "aviso": ""})
    ejemplos = []
    for py in sorted((RAIZ / "ejemplos").glob("*.py")):
        texto = py.read_text(encoding="utf-8")
        doc = (ast.get_docstring(ast.parse(texto)) or "").splitlines()
        ejemplos.append({"id": py.stem, "nombre": py.name, "tipo": "ejemplo", "firma": "", "doc": "",
                         "desc": doc[0] if doc else "Ejemplo ejecutable", "sas": "", "origen": "",
                         "archivo": py.relative_to(RAIZ).as_posix(), "linea": 1,
                         "lineas": len(texto.splitlines()), "codigo": texto, "importar": "", "llamada": "",
                         "opcionales": "", "aviso": "", "texto": ""})
    ramas.append(rama_demos(nombres_fn))
    ramas.append({"id": "guias", "nombre": "Guías y ejemplos",
                  "desc": "Teoría, equivalencias SAS, reglas para Claude y un flujo de ejemplo.",
                  "modulos": [{"id": "teoria", "nombre": "teoria/", "desc": "Guías en Markdown", "archivo": "teoria", "items": guias},
                              {"id": "ejemplos", "nombre": "ejemplos/", "desc": "Scripts de ejemplo", "archivo": "ejemplos", "items": ejemplos}]})

    n_tests = sum(len(re.findall(r"^def test_", p.read_text(encoding="utf-8"), re.M)) for p in (CODIGO / "tests").glob("test_*.py"))
    return {"raiz": RAIZ_POR_DEFECTO, "generado": dt.date.today().isoformat(), "pruebas": n_tests, "ramas": ramas,
            "propiedades": meta_prop}


def ensamblar(datos: dict) -> str:
    plantilla = (CODIGO / "visor" / "plantilla.html").read_text(encoding="utf-8")
    demos_js = (CODIGO / "visor" / "demos.js").read_text(encoding="utf-8").replace("</", "<\\/")
    mapa_js = (CODIGO / "visor" / "mapa3d.js").read_text(encoding="utf-8").replace("</", "<\\/")
    js = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    return plantilla.replace("/*__DEMOS_JS__*/", demos_js).replace("/*__MAPA3D_JS__*/", mapa_js).replace("__DATOS__", js)


def main() -> None:
    datos = construir()
    salida = RAIZ / "visor_arbol.html"
    salida.write_text(ensamblar(datos), encoding="utf-8")
    n = sum(len(m["items"]) for r in datos["ramas"] for m in r["modulos"])
    print(f"{salida.name}: {n} elementos en {len(datos['ramas'])} ramas, {datos['pruebas']} pruebas")


if __name__ == "__main__":
    main()
