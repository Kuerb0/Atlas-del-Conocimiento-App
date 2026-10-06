# Árbol de la estadística — instrucciones para Claude

Esta carpeta es la biblioteca estadística personal de Mario: funciones probadas (muchas portadas de SAS,
hechas en trabajos de consultoría), guías de teoría y una tabla SAS ↔ Python. **Antes de escribir código
estadístico, consulta este árbol; no reescribas lo que ya existe.**

## Estructura (ver árbol completo en `INDEX.md`)

Código en `py/` (paquete `arbol_estadistica`, `tests/`, `visor/`, `construir_visor.py`); datos de usuario en `conceptos/catalogo.json`
(no lo pisa el actualizador); `teoria/`, `ejemplos/`, `assets/`, `herramientas/` (generador de instaladores), `instaladores/`, `anteriores/`.

## Cómo usarlo (flujo obligatorio)

1. Abre `INDEX.md` y localiza la rama (preprocesado, selección, modelos, diagnóstico, clustering, contrastes, descriptiva, multivariante, ml, actuarial, finanzas, simulacion, diseno).
2. Si existe la función, impórtala: `from arbol_estadistica.modelos import tabla_odds_ratios`
   (instalar una vez con `pip install -e py` desde esta carpeta, o `sys.path.insert(0, <carpeta>/py)`).
3. Lee el docstring de la función: indica **origen** (notebook de consultoría), **equivalente SAS** y las
   **advertencias** (supuestos, errores conocidos del original).
4. Si falta algo, escríbelo siguiendo las convenciones de abajo y **añádelo al árbol** (módulo + test + línea en `INDEX.md`), y regenera el visor con `python py/construir_visor.py`. Si cambias `py/`, `assets/` o los `.bat`, sube `py/VERSION.txt` (y `pyproject.toml`) y ejecuta `python herramientas/generar_instaladores.py`. **Al terminar cualquier tarea que cambie el programa, genera siempre los instaladores, publícalos con `python herramientas/publicar.py "qué cambió"` (regenera, revisa que no haya datos privados, commit y push a GitHub; en `instaladores/` solo queda la versión actual) y dile a Mario la ruta de `Arbol X.Y.Z - Instalador.bat` y `- Actualizar.bat` para que los pruebe.**
5. `visor_arbol.html` (doble clic, `abrir_arbol.bat` o el acceso directo del Escritorio): mapa 3D (núcleo = el árbol, ramas orbitando con sus funciones y conceptos como puntos; motor en `py/visor/mapa3d.js`, canvas sin librerías), buscador y botones para copiar código; lo genera `py/construir_visor.py` leyendo el propio código y `INDEX.md`, sin depender de nada más. Los instaladores autoextraíbles están en `instaladores/` (Instalador = Python + librerías + visor + accesos; Actualizar = solo programa, con copia en `anteriores/`); `regenerar_visor.bat` vuelve a generar el visor.
5c. **Probar (cuaderno):** cada función tiene un ejemplo ejecutable por celdas con datos simulados en `py/cuaderno/ejemplos.py` (escenarios + celdas, con gráfico cuando lo hay). La app (`py/arbol_app.pyw`, pywebview) lo ejecuta en Python desde el visor. Al añadir una función, añade su ejemplo: un test exige que exista y que se ejecute sin errores.
5e. **Guía de aprendizaje:** la pestaña «🎓 Aprender» del visor muestra rutas paso a paso (`py/aprender/*.json`, una ruta por fichero): cada paso tiene idea, instrucciones, una demo, palabras clave, una pregunta y las funciones en Python. Los enlaces (demos, funciones, conceptos) se validan al construir el visor y en `tests/test_aprender.py`; el progreso se guarda en el navegador. Al añadir una demo o un concepto importante, plantéate si encaja en una ruta.
5b. **Demos:** la rama «Cómo funciona» del visor tiene demos interactivas (`py/visor/demos.js`, metadatos en `DEMOS` de `construir_visor.py`); al añadir una, registra ambas cosas.
5d. **Propiedades (fichas 0-10):** cada función tiene una ficha con barras de 0 a 10 en ~33 propiedades agrupadas en 5 bloques
   (Estimación: insesgadez, consistencia, eficiencia, ECM, normalidad asintótica, identificabilidad · Inferencia: tamaño α, potencia,
   cobertura de IC… · Predicción · Datos que soporta · Código: escalabilidad, velocidad, memoria, estabilidad numérica…).
   Definiciones, perfiles de proyecto (equilibrado, cartera grande, pocos datos, regulatorio, predicción pura) y grupos de
   alternativas en `py/propiedades/propiedades.json`; notas estimadas, pros/contras y «úsala si / evítala si» en
   `herramientas/fichas_fuente.py` → `python herramientas/fichas_fuente.py` escribe `py/propiedades/fichas.json`; lo medible lo mide
   `py/medir_propiedades.py` (benchmark n = 1 000…64 000 y Monte Carlo: α real, cobertura, sesgo, potencia relativa) en
   `py/propiedades/medidas.json` (o `medir_propiedades.bat`, que mide en el ordenador de Mario). Prioridad de cada nota en el
   visor: `conceptos/fichas_mias.json` (de Mario; el actualizador no lo toca) > medida > estimada. **Al añadir una función:**
   su ficha en `fichas_fuente.py` (con `grupo` de alternativas) y su entrada `@bench` en `medir_propiedades.py` (hay tests que
   lo exigen), luego `python herramientas/fichas_fuente.py` y `python py/medir_propiedades.py <función>`.
   Cuando Mario pregunte «¿qué uso para X?», mira el grupo de alternativas y ordénalas con el perfil que encaje con su proyecto.
5g. **Universo (primera capa del visor):** el visor se abre en un universo 3D (`py/visor/cerebro.js`; el fichero y las variables se siguen llamando «cerebro» por historia) con paisaje (estrellas con paralaje, nebulosas, galaxias lejanas, hilos entre galaxias) y una galaxia en espiral por parte: **Código** (las ramas de funciones), **Conceptos** (los temas `t_*` salvo finanzas), **Demos y guías**, **Finanzas** (rama `finanzas` + `t_fin`) —cada una con su propio mapa 3D, que es también una galaxia: núcleo, polvo y dos brazos espirales (`ESPIRAL`/`GIRO` en `mapa3d.js`), con su color (`color` en `crearMapa3D`)— y **Libros** y **Notas** (solo ámbitos de búsqueda del gestor). El reparto está en `GALAXIAS` de `plantilla.html`; la galaxia pequeña del universo es una miniatura exacta de la de dentro. El buscador ilumina las galaxias con coincidencias y, al elegir un resultado, vuela a su galaxia. **Vuelo:** un único movimiento continuo hasta el destino (galaxia o nodo), sin parada en la vista general: la cámara no cambia de orientación, el mapa de dentro se dibuja ya por debajo con la cámara del universo (`mapa.sync()`, `camaraDe()`, `geometria()`) y toma el relevo con un fundido; al volver (🌌) es lo mismo al revés, desde el nodo en el que estés. Icono (una galaxia): `python herramientas/generar_icono.py`. `indexar_conocimiento.bat` crea `conocimiento/fuentes.json` (tus carpetas) e indexa.
5f. **Gestor de conocimiento:** `py/conocimiento/` es un buscador único (SQLite FTS5, BM25, sinónimos del catálogo) sobre código, conceptos, teoría y tus libros/finanzas/notas (`conocimiento/fuentes.json`, no se publica). `cd py && python -m conocimiento indexar | buscar "consulta" [-c colección] | estado`. Antes de buscar a mano en `Manuales Estadística` o en `teoria/`, usa `buscar`.
5hh. **Un solo arranque:** el instalador/actualizador abre la app lanzando el propio acceso directo del Escritorio (`Abrir-App` en `herramientas/plantillas/motor.ps1`), y `abrir_arbol.bat` no minimiza pythonw: lo que se abre al terminar y lo que se abre con el icono es lo mismo.
5h. **Modo vivo (para ver los cambios mientras se trabaja):** el acceso directo con `--vivo` (`powershell -ExecutionPolicy Bypass -File herramientascceso_vivo.ps1 on|off` lo apunta a esta carpeta o lo restaura) recarga la app solo cuando se regenera `visor_arbol.html` y la coloca donde indique `.foco`. Para enseñar un cambio: `python herramientas/ver.py [destino]` regenera el visor y escribe el foco (`cerebro`, `galaxia:codigo|conceptos|demos|finanzas` o el nombre de una función/concepto/demo; el visor también lo admite como `#destino`).
5i. **Pestañas e importador:** el visor tiene pestañas **🌌 Universo** (el mapa) y **⚫ Importar** (además de 🎓 Aprender). «Importar» es un agujero negro (`py/visor/agujero.js`): clic o soltar archivos abre el explorador de Windows (`Api.elegir_archivos`); `py/conocimiento/importar.py` analiza cada fichero (`clasificar`: galaxia finanzas/libros/notas, **género** —historia, economía, ensayo, estadística, ciencia, novela…—, subtema = tema del catálogo (palabras clave en inglés y español, peso del título) y solo para estadística/economía/tecnología —un libro de historia queda en «General»—, tipo, capítulos, vista previa, idioma, duplicado) y el panel muestra una tarjeta desplegable por archivo (barras con lo detectado: pulsar una fija el género o el subtema; desplegables de galaxia/género/tipo, título editable —los nombres largos se recortan con `titulo_corto`—, etiquetas, «Para todos»). Se importa archivo a archivo con progreso: `importar()` copia a `conocimiento/biblioteca/<galaxia>/<subtema>/` con nombre corto, guarda `biblioteca/metadatos.json` (hash: no duplica) y lo indexa; después `Api.actualizar_visor` regenera `visor_arbol.html` y el visor se recarga. `enriquecer()` completa capítulos/género/títulos de lo importado con versiones anteriores. Al final de la pestaña hay un desplegable «¿Cómo funciona la importación?». **Mapas con tu biblioteca** (`ramas_biblioteca` en `construir_visor.py`): Libros = una rama por género › un módulo por libro › un punto por capítulo (PDF: marcadores o tramos de 25 págs.; EPUB: su índice) con «Abrir en la página N»; los capítulos NO se dibujan hasta que pulsas el libro (`nivel()` en `mapa3d.js`; el panel del libro, `detalleLibro`, los lista siempre); el recuento de una rama son sus libros; Notas = una rama por subtema con un punto por documento; las demás galaxias reciben una rama «Documentos importados». Una galaxia sin nada no tiene mapa ni líneas (solo búsqueda). **Conceptos con vídeo:** los conceptos con fuentes de vídeo (Very Normal, Harvard, MIT, 3Blue1Brown…; `es_video`) llevan un ▶ en el mapa y la lista de vídeos arriba del panel (la cabecera ya no tiene filtros ni chips de ramas: solo buscador y perfil). **Observatorio (pestaña 🔭; internamente «biblioteca»: carpeta `conocimiento/biblioteca`, `biblioteca_*` en la API):** lista lo importado y deja editar título, galaxia, género, subtema, tipo y etiquetas (se guarda al momento; `importar.editar`), reclasificar (`reclasificar_uno`) y borrar (`borrar`: quita la copia de `biblioteca/`, nunca el original); lo que fijas se recuerda (`biblioteca/correcciones.json`: obras de nombre parecido se clasifican igual). El universo se regenera al volver a él. **Importar:** «Original: copiar/mover» (mover quita el original de su carpeta tras importar) y progreso real por páginas (`conocimiento.PROGRESO`, trabajo en segundo plano `Api.importar_archivos` + `estado_trabajo`). **Búsqueda con ámbito:** prefijos `libros:`, `código:`, `conceptos:`, `demos:`, `notas:`, `finanzas:`, `vídeo:` y géneros (`historia:`, `economía:`…), combinables; con la barra vacía salen los atajos; flechas/Enter sirven también para los resultados de tus carpetas y hay indicador de «buscando…».
**Buscador:** la barra ocupa todo el espacio libre de la cabecera y cada resultado lleva un icono (`iconoNodo`/`iconoRes` en la plantilla): portada del libro (la del EPUB, la primera página del PDF con Poppler si está, o una generada por género; `importar.portada`, `DATA.portadas`), logo de Python (funciones y ejemplos), ∑ (conceptos; con ▶ si tienen vídeo), f(x) (demos), documento (guías) y la etiqueta del formato (PDF, DOCX, MD…). Al buscar, el universo reacciona: la galaxia con más coincidencias late y la cámara se acerca un poco (`cerebro.enfocar`), el resto se atenúa; los capítulos de un mismo libro se agrupan en un resultado. Los `*.pdf` y `*.epub` están en `.gitignore`. Por consola: `cd py && python -m conocimiento importar f.pdf [-g libros] [-G historia] [-s "Inferencia y contrastes"] [-t libro]`.
5j. **Eclipses (almacenaje):** pestaña «🌘 Eclipses» (`py/visor/eclipses.js`, medición en `py/conocimiento/almacenaje.py`, API `Api.almacenaje`): el Sol es el límite de GitHub (1 GB recomendado, 5 GB tope, 100 MB por archivo) y cada galaxia o tipo de archivo es una luna cuya área es proporcional a lo que ocupa. Dos escenarios: «En disco» (todo) y «En GitHub» (`git ls-files -co --exclude-standard`: respeta `.gitignore`), y dos vistas (por galaxia / por tipo). Avisa de archivos >100 MB. Test: `tests/test_almacenaje.py`.
5k. **Telescopio:** pestaña «📡 Telescopio» (`py/conocimiento/telescopio.py`, API `Api.telescopio_buscar/traer`, consola `python -m conocimiento telescopio <consulta> [--traer N]`). Busca **solo fuentes legales**: Project Gutenberg (Gutendex, dominio público), arXiv, OpenAlex (solo con PDF abierto) e Internet Archive (solo licencia CC/dominio público o publicado ≤ 1929). **No se añaden fuentes piratas (Anna's Archive, Z-Library, LibGen…) ni descargadores de ellas.** `traer` descarga (https, ≤ 200 MB, comprueba que es PDF/EPUB de verdad) y pasa por `importar.importar` con el género sacado de las materias de la obra (`genero_desde_materias`); `materias_de` consulta Open Library para clasificar un título que ya tienes. Tests sin red (`_get` se sustituye): `tests/test_telescopio.py`.
6. **Conceptos:** `conceptos/catalogo.json` lista los conceptos del temario del máster y de Very Normal con las funciones que los implementan. Organización: `temas` (ramas del mapa, con color) > `areas` (módulos, con `ambito`) > conceptos (`area`, `prioridad` opcional, `area_fija` para que la actualización no lo mueva). La migración de 0.6.0 está en `herramientas/reorganizar_catalogo.py`.
   Si un concepto no tiene función (*hueco*), es que el árbol aún no lo cubre: impleméntalo (módulo + test), enlázalo en el catálogo (`funciones`) y regenera el visor.
   Al añadir una función nueva, enlázala al menos a un concepto (hay un test que lo exige).
7. Si Mario pregunta "¿qué contraste uso?" o "¿cómo se hacía esto en SAS?", ve a `teoria/`.

## Qué usar según la necesidad

| Necesito… | Usa |
|---|---|
| Comparar una variable entre grupos | `contrastes.elegir_contraste` (elige t / Welch / Mann-Whitney / ANOVA / Kruskal / chi² / Fisher y avisa de supuestos) |
| Comparaciones por pares tras un ANOVA | `contrastes.tukey_entre_grupos` |
| Qué variables merece la pena probar | `seleccion.cribar_variables` (chi² + V de Cramér, detecta fuga) |
| Seleccionar variables en un GLM | `seleccion.seleccion_forward` (AIC/BIC; familia correcta) |
| Logística binaria "estilo PROC LOGISTIC" | `modelos.preparar_matriz_modelo` → `ajustar_logit` → `tabla_odds_ratios`, `tabla_parametros_wald` |
| GLM con fórmula + train/test | `modelos.dividir_train_test`, `ajustar_glm_binomial` |
| Logit multinomial (PROC LOGISTIC GLOGIT) | `modelos.logit_multinomial_sas` (incluye `lsmeans_like`) |
| Separación perfecta / clase rara | `modelos.regresion_logistica_firth` |
| Justificar técnica o enlace | `modelos.comparar_tecnicas_estimacion`, `comparar_enlaces` |
| Multicolinealidad | `diagnostico.calcular_vif`, `filtrar_vif_iterativo` |
| Calibración y asociación | `diagnostico.hosmer_lemeshow`, `estadisticos_asociacion` (c, Somers' D, Gamma, Tau-a) |
| Umbral de decisión | `diagnostico.tabla_umbrales` (CTABLE), `umbral_optimo_youden` |
| Clasificación desbalanceada | `preprocesado.balancear_clases`, `submuestreo_por_ratio`, `pesos_por_clase`; tras entrenar balanceado, `corregir_probabilidades_por_balanceo` |
| Numérica → tramos | `preprocesado.categorizar_por_cuantiles` |
| Segmentar | `clustering.preparar_matriz_clustering` → `buscar_k_silhouette` → `ajustar_kmeans` → `proyeccion_pca` |
| Sensibilidad al precio por segmento | `modelos.sensibilidad_por_grupo`, `ganancia_por_bajada_precio`, `tendencia_polinomica_ponderada` |
| Muchos contrastes a la vez | `contrastes.ajustar_p_valores` (BH por defecto; Holm/Bonferroni si un falso positivo es caro) |
| Tamaño muestral / potencia | `contrastes.tamano_muestral_medias`, `tamano_muestral_proporciones`, `potencia_por_simulacion` |
| Supervivencia (tiempo hasta evento con censura) | `modelos.kaplan_meier`, `contraste_log_rank`, `ajustar_cox` |
| Describir variables, atípicos, correlaciones, normalidad, varianzas | `descriptiva.resumen_descriptivo`, `detectar_atipicos`, `correlacion_con_ic`, `contraste_normalidad`, `homogeneidad_varianzas` |
| Qué distribución siguen importes / nº de siniestros | `descriptiva.ajustar_distribuciones`, `ajustar_distribucion_discreta`, `indice_dispersion` |
| Tablas cruzadas, riesgo relativo | `descriptiva.tabla_contingencia`, `medidas_riesgo_2x2` |
| Antes/después, medidas repetidas | `contrastes.contraste_apareado`, `contraste_friedman`, `contraste_mcnemar` |
| IC de una tasa o de cualquier estadístico | `contrastes.intervalo_proporcion` (Wilson), `bootstrap_ic` (BCa) |
| Tarificación (frecuencia, severidad, prima pura) | `modelos.ajustar_glm_conteo` (offset, NB), `ajustar_glm_severidad`, `prima_pura`, `tabla_relatividades`, `ajustar_tweedie` |
| Regresión lineal con diagnóstico | `modelos.ajustar_ols` (HC3), `medidas_influencia`, `contraste_f_parcial`, `transformacion_box_cox`, `regresion_robusta` |
| Efectos no lineales / datos agrupados / respuesta ordinal | `modelos.ajustar_glm_splines`, `ajustar_modelo_mixto`, `ajustar_logit_ordinal` |
| Muchas variables / colinealidad | `modelos.ajustar_regularizado` (Lasso/Ridge, CV 1-SE), `seleccion.filtrar_correlacion_alta` |
| Supervivencia avanzada | `modelos.contraste_schoenfeld`, `ajustar_supervivencia_parametrica`, `incidencia_acumulada`, `rmst` |
| Validar un modelo | `seleccion.validacion_cruzada`, `optimismo_bootstrap`, `comparar_modelos_cv`; `diagnostico.tabla_ganancia_lift`, `estadistico_ks_gini`, `calibrar_probabilidades` |
| Faltantes | `preprocesado.resumen_faltantes`, `imputar`, `imputacion_multiple` |
| Multivariante | `multivariante.distancia_mahalanobis`, `pca_completo`, `analisis_factorial`, `alfa_cronbach`, `clustering_jerarquico`, `mezclas_gaussianas`, `analisis_discriminante` |
| ANOVA de varios factores, bloques, ANCOVA, medidas repetidas, anidado | `diseno.anova_factorial`, `anova_bloques`, `ancova`, `anova_medidas_repetidas` (GG/HF), `anova_anidado`, `diagnostico_anova` |
| Diseñar experimentos | `diseno.diseno_factorial_2k` (fraccionados, alias) → `efectos_factorial_2k` (Lenth); `cuadrado_latino`; `diseno_central_compuesto` → `superficie_respuesta` |
| Efecto causal sin aleatorizar / ensayos | `diseno.puntuacion_propension` (IPW, emparejamiento; mira el balance), `diferencias_en_diferencias`, `aleatorizar_ensayo`, `analisis_intencion_tratar` (ITT, CACE) |
| Mediación, moderación, combinar estudios | `diseno.mediacion`, `moderacion`; `metaanalisis` (con pocos estudios `hartung_knapp=True`: el IC de DL cubre ≈ 88 %) |
| Bayes | `simulacion.posterior_conjugado`, `bayes_empirico_beta`, `metropolis` (+ `diagnostico_mcmc`, `chequeo_predictivo`), `accion_bayes`, `ab_bayesiano`, `simular_bandido` |
| Markov, colas, procesos | `simulacion.cadena_markov`, `bonus_malus`, `cadena_markov_continua`, `nacimiento_muerte`, `simular_proceso_poisson`, `simular_browniano` |
| Simular / Monte Carlo / encuestas | `simulacion.generar_normal_multivariante`, `estimar_montecarlo` (antitéticas, control); `extraer_muestra`, `estimar_mas`, `asignacion_estratos`, `estimar_estratificado`, `estimador_razon`, `ajuste_no_respuesta` |
| Teoría de estimación | `simulacion.metodo_momentos`, `informacion_fisher` (Cramér-Rao), `comparar_estimadores`, `metodo_delta` |
| Regresión: bandas, calibración, error de medida, n mínimo | `modelos.bandas_confianza_regresion`, `regresion_inversa`, `correccion_error_medida` (SIMEX), `tamano_muestral_modelo` (Riley) |
| No paramétrica / reducción supervisada | `modelos.regresion_local`, `ajustar_mars`, `funciones_escalonadas`, `regresion_pls_pcr`, `regresion_inversa_cortes`; tablas: `modelo_loglineal` |
| Explicar o vigilar un modelo | `seleccion.tabla_nomograma`, `aproximar_modelo`; `diagnostico.dominio_aplicabilidad` |
| Cualquier gráfico (ROC, calibración, residuos, forest de OR, KM, potencia…) | `from arbol_estadistica.graficos import grafico_…` (devuelven la Figure; ver `ejemplos/galeria_graficos.py`) |

## Convenciones del código

- Nombres de funciones y variables en español, `snake_case`, sin tildes ni eñes en identificadores.
- Docstring con: qué hace, **Origen** (notebook de consultoría), **Equivale a** (procedimiento SAS) y **OJO/Gauss** cuando haya trampa.
- Las funciones **no mutan** el DataFrame de entrada; devuelven una copia o tablas nuevas.
- Resultados como `DataFrame` o `dict` con claves en español; semilla por defecto `42`.
- Código genérico: **nada de nombres de negocio** (`tasa_fuga`, `policy_complement`…) ni datos de cliente
  (de ningún cliente). Los tests usan datos sintéticos.
- Todo cambio lleva test en `py/tests/` (`python -m pytest -q py`, o `ejecutar_tests.bat`). Un test por comportamiento, con casos donde la teoría dé la respuesta.

## Commits y versiones

- **Un commit por entrega**, con la versión: `vX.Y.Z: resumen en una línea` (lo genera `herramientas/publicar.py`).
- El resumen va en español, dice el **efecto** («el mapa 3D limita los enlaces a 120») y no el método, y cabe en ~70 caracteres.
- **Versión:** parche (`0.11.7` → `0.11.8`) para arreglos, textos y ajustes de rendimiento o instalador; menor (`0.12.0`) para funciones, demos o ramas nuevas; mayor (`1.0.0`, publicada: universo, importador, observatorio y buscador con ámbitos) cuando Mario decida que es estable.
- Cambios que no tocan el programa (solo documentación) van como `docs: …`, sin subir versión ni regenerar instaladores.
- Nunca `Co-Authored-By`. Nunca datos privados (`publicar.py` lo comprueba antes de hacer commit).

## Reglas de estilo heredadas de los agentes de Mario

- **Gauss (estadística):** explicita supuestos y justifica el método; no uses el p-valor a ciegas
  (con n grande todo sale significativo: reporta tamaño del efecto); prefiere contrastes robustos si las X no son normales.
  Con OLS, test robustos a heterocedasticidad. Mario puede decir "Aprender Lección": añade la regla a esta sección.
- **Linus (robustez y eficiencia):** carga solo lo necesario, tipos eficientes, nada de lecturas repetidas; valida entradas y falla con
  mensaje claro; muestrea para métricas O(n²) (silhouette) y avisa del coste de los bucles (stepwise, VIF iterativo).
- **Apolonio (notebooks):** secciones numeradas (`## 3.2 TÍTULO` + línea `Objetivo:`), código con cabecera `# ---- 3.2.1 ----`
  y bloques `#region 3.2.1.a … #endregion`; ejecutar todo antes de entregar. (No pude leer `prompt_estilo_ipynb.txt`; si cambia, ese fichero manda.)

## Errores conocidos del código original (ya corregidos aquí; no los reintroduzcas)

1. `smf.glm(formula, data)` **sin `family`** ajusta un modelo gaussiano. Siempre indicar familia (`Binomial()` para 0/1).
2. `sm.Logit(..., freq_weights=w)` **ignora los pesos** en silencio. Con pesos usar `sm.GLM(..., freq_weights=w)` (`ajustar_logit(pesos=...)`).
3. `lsmeans_like` ≠ `LSMEANS` de SAS: es estandarización marginal (se fija el nivel y se promedia la predicción).
4. En SAS, con `LINK=GLOGIT` la referencia por defecto es la **última** categoría; aquí hay que fijar `base_class`. Fijarla siempre.
5. AIC es permisivo (una variable de ruido entra ~16 % de las veces); si el objetivo es parsimonia, usar BIC o confirmar con validación.
6. Balancear **solo el train**; nunca el test; y si luego evalúas calibración o umbrales en datos con prevalencia real, **corregir las probabilidades** (`corregir_probabilidades_por_balanceo`): sin ello el Hosmer-Lemeshow rechaza siempre (en el ejemplo: χ²=147 → 8.3). Y excluir columnas derivadas del objetivo (`y_*`, `prob_*`, `*_pred`): fuga de información.
7. `duracion_hasta_evento` no distingue censura de evento (si nunca hay un 1, cuenta todos los 0).
8. Hosmer-Lemeshow con decenas de miles de filas casi siempre rechaza: mirar la tabla observado/esperado y la calibración visual.

## Conceptos y fuentes (estado)

383 conceptos en 38 áreas y 8 temas (348 con código; los 26 sin código son de ámbito normativo y no se programan). Fuentes: guías docentes de 2º, nueve manuales de estadística de `Manuales Estadística` (`fuentes[].tipo` = `manual`), índices de temas de 1º y Very Normal: los **73 vídeos largos** del canal `@very-normal` (lista completa en `teoria/very_normal.md`, enlazados por título y descripción) y varios posts de su Substack. **Pendiente:** Shorts de Very Normal (no revisados) y el temario real de Derivados,
Fiscalidad, Economía y SS y Derecho Bancario. Para ampliar el catálogo, editar el JSON (un objeto por concepto; `fuentes[].tipo` ∈ `master`, `very_normal`, `manual`, `curso`, `arbol`; Very Normal y los cursos en vídeo (Harvard Stat 110, MIT 18.650, 3Blue1Brown) exigen `url`).

## Qué hay y qué no hay (estado)

Construido a partir de notebooks de consultoría (GLM binomial, multinomial, One-vs-Rest, ETL, FE; logística con VIF, Hosmer-Lemeshow,
Firth, clustering y elasticidad) y de notas de contrastes. Ese código está cerrado: el árbol es ahora una biblioteca personal y el trabajo
es mejorar el código, las demos de conceptos y la organización de la carpeta.
