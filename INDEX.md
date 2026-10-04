# Índice del árbol

> Vista interactiva: abre `visor_arbol.html` (doble clic) o el acceso directo del Escritorio (se crea con el instalador de `instaladores/`). Se regenera con `python py/construir_visor.py` (o `regenerar_visor.bat`) tras cambiar el código o este índice.

Cada fila: función → cuándo usarla → equivalente SAS → de dónde sale (trazabilidad). Import: `from arbol_estadistica.<rama> import <función>`.

```
arbol_estadistica
├── (conceptos/)   qué conceptos conoce el árbol: temario del máster y Very Normal → ver «Conceptos» abajo
├── preprocesado   preparar datos antes de modelar
├── seleccion      qué variables entran
├── modelos        ajustar y explicar
├── diagnostico    ¿el modelo es fiable?
├── clustering     segmentar
├── contrastes     comparar grupos, potencia y tamaño muestral, FDR
├── descriptiva    resumen, atípicos, correlaciones, supuestos, ajuste de distribuciones, tablas
├── multivariante  Mahalanobis, Hotelling, MANOVA, PCA, factorial, Cronbach, jerárquico, mezclas, discriminante
├── ml             árboles, random forest, boosting, k-NN, SVM, redes, stacking, importancia y dependencia parcial
├── actuarial      tablas de vida, seguros y rentas, provisiones, chain ladder, Panjer, ruina, credibilidad, demografía
├── finanzas       VaR/TVaR, EVT, cópulas, estrés, Markowitz, CAPM, Black-Litterman, bonos, ETTI, swaps, opciones, BDT
├── simulacion     probabilidad, Monte Carlo, bayesiana (conjugadas, MCMC, A/B, bandidos), Markov y procesos, muestreo
├── diseno         ANOVA y diseños, 2^k, superficies de respuesta, propensión, DiD, ensayos, mediación, metaanálisis
└── graficos       gráficos matplotlib (importar aparte: from arbol_estadistica.graficos import …)
(visor) mapa 3D: núcleo + ramas en órbita; arrastrar = girar, rueda = acercar, clic en una rama = entrar (py/visor/mapa3d.js)
(visor) «Probar»: cada función con su ejemplo ejecutable por celdas (py/cuaderno/ejemplos.py; se ejecuta desde la app)
(visor) fichas de propiedades: barras 0-10 por función y por módulo, perfil de proyecto (arriba) que pondera y ordena las alternativas, comparador
(visor) «Cómo funciona»: 17 demos interactivas (distribuciones básicas animadas y en galería, t-test, potencia, FDR, IC, TCL, regresión, logística, censura, MCMC, Markov, bandidos, PCA, K-means, VaR)
```

## Estructura de carpetas

```
Arbol de la estadística/
├── abrir_arbol.bat · regenerar_visor.bat · ejecutar_tests.bat · medir_propiedades.bat   lanzadores (doble clic)
├── visor_arbol.html          mapa visual 3D (lo genera py/construir_visor.py con visor/plantilla.html + mapa3d.js + demos.js)
├── INDEX.md · CLAUDE.md      índice de funciones y reglas para Claude
├── py/                       TODO el código: arbol_estadistica/, tests/, visor/, construir_visor.py, propiedades/ (fichas 0-10), medir_propiedades.py,
│                             VERSION.txt, requirements.txt, pyproject.toml
├── conceptos/catalogo.json   catálogo de conceptos (datos tuyos: la actualización NO lo pisa)
├── teoria/                   guías de teoría, contrastes, tabla SAS ↔ Python
├── ejemplos/                 flujos completos de uso
├── assets/                   icono.ico / icono.png
├── herramientas/             generar_instaladores.py, descargar_python.ps1, plantillas/
├── instaladores/             "Arbol X.Y.Z - Instalador.bat" y "… - Actualizar.bat" (autoextraíbles)
├── anteriores/               copias de seguridad que hace el actualizador (py_anterior, estructura_plana)
└── python/                   (opcional) Python propio descargado por el instalador si el equipo no tiene
```

**Instaladores**: `python herramientas/generar_instaladores.py` empaqueta todo (py/, teoria/, ejemplos/, los `.bat`, assets/ y el
catálogo) en dos `.bat` autoextraíbles y comprueba que se extraen idénticos. El `.bat` solo arranca PowerShell; el trabajo lo hace
`herramientas/plantillas/motor.ps1`. *Instalador* (vale para un PC limpio): pregunta la carpeta (Enter = Documentos\Árbol de la estadística,
C = elegir otra), instala Python dentro de esa carpeta si no hay, las librerías, registra el paquete (`.pth`), genera el visor y crea accesos.
*Actualizar*: encuentra la instalación (junto al `.bat`, la recordada o la que elijas), mueve `py/` a `anteriores/py_<versión>_<fecha>`,
copia la versión nueva y comprueba `py/VERSION.txt`; tu `conceptos/catalogo.json` se conserva y `py/fusionar_catalogo.py` le añade los
conceptos y enlaces nuevos desde `conceptos/catalogo_base.json`. Sube `py/VERSION.txt` (= `pyproject.toml`) antes de generar.

## Propiedades de cada función (fichas 0-10)

Cada función tiene barras de 0 a 10 en las propiedades que le aplican (las que no, no salen), agrupadas en 5 bloques:

| Bloque | Propiedades |
|---|---|
| Estimación | insesgadez, consistencia, eficiencia, error cuadrático medio, normalidad asintótica, identificabilidad |
| Inferencia | tamaño (error tipo I), potencia, cobertura de los IC, cuantificación de la incertidumbre, validez en muestras pequeñas, validez tras la selección |
| Predicción y modelo | generalización, calibración, discriminación, parsimonia, interpretabilidad, estabilidad |
| Datos que soporta | robustez, pocos supuestos, censura, desbalanceo, dependencia |
| Código | escalabilidad, velocidad, memoria, estabilidad numérica, tolerancia a datos sucios, reproducibilidad, configurabilidad, coste de ajuste, trazabilidad SAS, cobertura de tests |

- **Medido** (`py/medir_propiedades.py` → `py/propiedades/medidas.json`): velocidad, memoria y escalabilidad (benchmark con n = 1 000…64 000; exponente de tiempo ∝ n^b) de todas; α real, cobertura de IC, sesgo, ECM y potencia relativa por Monte Carlo donde hay simulación; cobertura de tests contando los tests.
- **Estimado** (`herramientas/fichas_fuente.py` → `py/propiedades/fichas.json`): el resto, con pros, contras, «úsala si / evítala si» y su **grupo de alternativas**.
- **Tuyo**: `conceptos/fichas_mias.json` (opcional, no lo pisa el actualizador) manda sobre todo: `{"funciones": {"ajustar_logit": {"notas": {"robustez": 6}}}}` (`null` quita una nota).
- **Perfil de proyecto** (selector arriba en el visor): equilibrado, cartera grande / big data, pocos datos / estudio, regulatorio / tarificación, predicción pura o personalizado (tus pesos). La puntuación es la media ponderada y ordena las alternativas del mismo grupo; al pulsar una rama o un módulo sale su media.

## preprocesado

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `categorizar_por_cuantiles(df, columnas, q, q_importes)` | Numérica → tramos Q1..Qn / D1..D10 (más tramos si es un importe). No muta. | `PROC RANK GROUPS=` | `crear_numericas_cat` (notebook de consultoría) |
| `balancear_clases(df, objetivo, 'oversample'/'undersample')` | Igualar clases remuestreando (solo train) | `PROC SURVEYSELECT` | `balance_multiclass_df` (notebook de consultoría) |
| `submuestreo_por_ratio(df, objetivo, ratio_neg_pos)` | Todos los positivos + negativos a ratio N:1 (1 = 50/50) | `PROC SURVEYSELECT` | métodos `undersample_*` (notebook de consultoría) |
| `corregir_probabilidades_por_balanceo(p, prev_real, prev_muestra)` | Devolver las probabilidades a la escala real tras entrenar con datos balanceados (corrección de prior). Sin ella, Hosmer-Lemeshow y los umbrales salen mal | — | ejemplo `flujo_logit_binario.py` |
| `pesos_por_clase(y)` | Pesos n/(K·nc) para usar todos los datos con `freq_weights` | `WEIGHT` | `class_weight` (notebook de consultoría) |
| `codificar_ordinal(df, col, orden)` | Categórica ordenada → enteros, con mapping invertible | formato / `PROC FORMAT` | `encode_ordered_column` (notebook de consultoría) |
| `duracion_hasta_evento(df, id, evento, orden)` | Nº de periodos sin evento antes del primero | datos de supervivencia | `calc_duration` (notebook de consultoría) |
| `resumen_faltantes(df)` | % y patrones de faltantes + test MCAR de Little | `PROC MI NIMPUTE=0` (patrones) | nuevo (0.9) |
| `contraste_mcar_little(df)` | Test MCAR de Little (EM) | — | nuevo |
| `imputar(df, 'mediana'/'iterativa'/'knn')` | Imputación simple (copia), con indicadores opcionales | `PROC STDIZE REPONLY` / `MI` | nuevo |
| `imputacion_multiple(df, formula, m)` | m imputaciones + GLM + reglas de Rubin (FMI) | `PROC MI` + `MIANALYZE` | nuevo |
| `agrupar_categorias_raras(df, col, min_frecuencia)` | Junta niveles poco frecuentes en «Otros» | — | nuevo |
| `codificar_por_objetivo(df, col, objetivo, suavizado)` | Target encoding suavizado y fuera de fold | — | nuevo |
| `smote(df, objetivo)` | Casos sintéticos de la clase minoritaria (solo train) | — | nuevo |
| `centrar_por_grupo(df, variables, grupo)` | Centrado dentro del grupo + media del grupo (efecto contextual) para modelos multinivel | — | nuevo (0.10) |

## seleccion

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `cribar_variables(df, objetivo)` | Chi² + V de Cramér de cada columna vs objetivo binario; marca fuga, baja variabilidad, alta cardinalidad | `PROC FREQ / CHISQ` | `valorar_variables_df_orig` (notebook de consultoría) |
| `contraste_chi2_variable(df, var, objetivo)` | Una variable: chi², p, V, diferencia máx. de tasa | `PROC FREQ` | `evaluar_significancia_categoria` |
| `es_posible_fuga(col)` | Detecta `y_*`, `prob_*`, `*_pred` | — | `es_posible_fuga_o_modelo` |
| `seleccion_forward(df, objetivo, candidatas, categoricas, criterio='aic'/'bic')` | Forward por criterio de información; devuelve fórmula, modelo e historial | `SELECTION=FORWARD` | `forward_stepwise_glm` (**corregida: familia**) |
| `seleccion_backward(df, objetivo, candidatas, categoricas, criterio)` | Backward por AIC/BIC con variables protegidas | `SELECTION=BACKWARD` | nuevo (0.9) |
| `seleccion_por_pvalor(df, objetivo, candidatas, sle, sls)` | Stepwise por p-valor (LR) como SAS | `SELECTION=STEPWISE SLENTRY SLSTAY` | INDEX «Pendiente» |
| `mejor_subconjunto(df, objetivo, candidatas)` | Todos los subconjuntos: mejor por tamaño con AIC, BIC, R² aj. y Cp | `SELECTION=SCORE / CP` | nuevo |
| `filtrar_varianza_casi_nula(df)` | Predictores constantes o casi constantes | — | nuevo |
| `filtrar_correlacion_alta(df, umbral)` | Quita variables hasta que ninguna pareja supere |r| | — | nuevo |
| `eliminacion_recursiva(X, y, familia)` | RFE con validación cruzada | — | nuevo |
| `validacion_cruzada(df, formula, familia, k, repeticiones)` | CV estratificada y repetida de un GLM con IC de las métricas | `PROC GLMSELECT CVMETHOD` | nuevo |
| `optimismo_bootstrap(df, formula, familia, n_boot)` | Validación interna de Harrell (métricas corregidas por optimismo) | — | nuevo |
| `comparar_modelos_cv(df, formula_a, formula_b)` | Dos modelos con los mismos folds y t de Nadeau-Bengio | — | nuevo |
| `metricas_regresion(y, pred)` | RMSE, MAE, MAPE, sesgo y R² | — | nuevo |
| `tabla_criterios({nombre: modelo})` | AIC, BIC, R² ajustado, Cp y pesos de Akaike | `REG / SELECTION` | nuevo |
| `tabla_nomograma(modelo, datos, variables)` | Puntos por variable y conversión a probabilidad (nomograma) | — | nuevo (0.10) |
| `aproximar_modelo(X, prediccion, r2_objetivo)` | Simplificar un modelo grande ajustando su predicción (Harrell) | — | nuevo (0.10) |

## modelos

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `preparar_matriz_modelo(df, y, vars, categoricas, numericas, refs)` | Dummies con referencia + z-score; devuelve `std_map` | `CLASS … PARAM=REF` | `preparar_df_modelo` (notebook de consultoría) |
| `ajustar_logit(y, X, pesos=None)` | Logística binaria (Newton) o GLM ponderado | `PROC LOGISTIC` | `fit_logit` (notebook de consultoría, **corregida: pesos**) |
| `tabla_odds_ratios(modelo, unidades, std_map)` | OR con IC95 % reescalados a unidades de negocio | `ODDSRATIO … UNITS=` | `mostrar_odds_ratios` |
| `tabla_parametros_wald(modelo)` | Estimación, SE, Wald χ², Pr>χ², exp(B) | Analysis of ML Estimates | bloque E (notebook de consultoría) |
| `perfil_respuesta(y)` | Frecuencias del objetivo | Response Profile | bloque A |
| `regresion_logistica_firth(X, y)` | MV penalizada (separación, clases raras) | `/ FIRTH` | `firth_logistic` |
| `comparar_tecnicas_estimacion`, `comparar_enlaces` | Newton vs IRLS vs Firth; logit vs probit vs cloglog | `LINK=` | bloques C y D |
| `dividir_train_test(df, objetivo, 0.7)` | Split estratificado | `PROC SURVEYSELECT STRATA` | notebook de consultoría |
| `ajustar_glm_binomial(formula, train, test, objetivo)` | GLM con fórmula + AIC/BIC + AUC train/test + OR | `PROC GENMOD` | notebook de consultoría |
| `logit_multinomial_sas(data, y, x_num, x_cat, base_class, ref_levels)` | Multinomial completo: betas crudos y estandarizados, AUC, confusión, VIF, efectos marginales, `lsmeans_like` | `PROC LOGISTIC LINK=GLOGIT` | `multinomial_logit_sas_like` (notebook de consultoría) |
| `sensibilidad_por_grupo`, `ganancia_por_bajada_precio` | Pendiente lineal estandarizada de la tasa vs precio por segmento; puntos ganados al bajar X % | — | `elasticidad_por_grupo` (notebook de consultoría) |
| `tendencia_polinomica_ponderada(x, y, pesos)` | "Sweet spot" cuadrático ponderado por volumen | `PROC REG` + término² | `plot_mpc_polynomial` |
| `kaplan_meier(df, duracion, evento, grupo)` | Curva de supervivencia con censura, IC log(-log) y medianas | `PROC LIFETEST` | nuevo (Very Normal / temario) |
| `contraste_log_rank(df, duracion, evento, grupo)` | ¿Difieren las curvas de supervivencia? | `LIFETEST STRATA / LOGRANK` | nuevo |
| `ajustar_cox(df, duracion, evento, covariables, categoricas, refs)` | Riesgos proporcionales: HR con IC | `PROC PHREG TIES=EFRON` | nuevo |
| `contraste_schoenfeld(resultado_cox)` | ¿Se cumplen los riesgos proporcionales? (por variable y global) | `PHREG ASSESS PH` / `cox.zph` | nuevo (0.9) |
| `ajustar_supervivencia_parametrica(df, duracion, evento, cov, distribucion)` | AFT Weibull / exponencial / lognormal / log-logística con censura | `PROC LIFEREG` | nuevo |
| `nelson_aalen(df, duracion, evento, grupo)` | Riesgo acumulado H(t) con SE | `LIFETEST NELSON` | nuevo |
| `incidencia_acumulada(df, duracion, causa, grupo)` | Riesgos competitivos: CIF de Aalen-Johansen por causa | `LIFETEST EVENTCODE=` / `%CIF` | nuevo |
| `rmst(df, duracion, evento, tau, grupo)` | Tiempo medio restringido a τ y diferencia entre grupos | `LIFETEST RMST` | nuevo |
| `ajustar_glm_conteo(formula, df, 'poisson'/'negbin', exposicion)` | Frecuencia de siniestros con offset; relatividades y sobredispersión | `GENMOD DIST=POISSON/NEGBIN OFFSET=` | ejercicio 5.2 (formación) |
| `contraste_sobredispersion(modelo_poisson)` | Cameron-Trivedi: ¿α = 0? | — | nuevo |
| `ajustar_glm_severidad(formula, df, 'gamma'/'inversa_gaussiana')` | Coste medio por siniestro (enlace log) | `GENMOD DIST=GAMMA LINK=LOG` | ejercicio 5.3 (formación) |
| `ajustar_tweedie(formula, df, p, exposicion)` | Prima pura en un solo GLM (Poisson-Gamma) | `GENMOD DIST=TWEEDIE` | nuevo |
| `prima_pura(frecuencia, severidad, df, exposicion)` | Frecuencia × severidad por póliza | — | ejercicios 5.2-5.3 |
| `tabla_relatividades(modelo, variable)` | Relatividades por nivel (base = 1) con IC, estilo Emblem/Radar | — | nuevo |
| `ajustar_ols(formula, df, robusto='HC3')` | MCO con SE robustos, β estandarizados y diagnósticos (BP, DW, JB, condición) | `PROC REG / HCC SPEC DW STB` | nuevo |
| `medidas_influencia(modelo)` | Apalancamiento, Cook, DFFITS, estudentizados con cortes | `REG / INFLUENCE R` | nuevo |
| `contraste_f_parcial(reducido, completo)` | Sumas de cuadrados extra: ¿aporta un bloque? | `REG TEST` | nuevo |
| `transformacion_box_cox(y)` | λ de Box-Cox (o Yeo-Johnson) con IC y sugerencia | `PROC TRANSREG BOXCOX` | nuevo |
| `ajustar_wls(formula, df, pesos / estimar_pesos)` | Mínimos cuadrados ponderados (también factibles) | `REG WEIGHT` | nuevo |
| `regresion_robusta(formula, df, 'huber'/'bisquare'/'cuantil')` | M-estimadores y regresión cuantílica | `ROBUSTREG` / `QUANTREG` | nuevo |
| `regresion_no_lineal(f, x, y, p0)` | Mínimos cuadrados no lineales con IC | `PROC NLIN` | nuevo |
| `contraste_falta_ajuste(df, x, y, grado)` | F de falta de ajuste con réplicas | `REG LACKFIT` | nuevo |
| `ajustar_glm_splines(df, objetivo, {var: gl}, otras, familia)` | GLM con splines cúbicos restringidos + test de no linealidad + curvas | `EFFECT SPLINE` / `GAMPL` | nuevo |
| `ajustar_modelo_mixto(formula, df, grupo)` | Efectos mixtos: fijos, varianzas, ICC y BLUP | `PROC MIXED` | nuevo |
| `coeficiente_icc(df, valor, grupo)` | Correlación intraclase con IC y efecto diseño | `MIXED` / `VARCOMP` | nuevo |
| `ajustar_logit_ordinal(df, objetivo, variables, orden)` | Odds proporcionales + comprobación por cortes | `LOGISTIC` (ordinal) | nuevo |
| `ajustar_regularizado(X, y, 'lasso'/'ridge'/'elasticnet', familia)` | Penalizada con λ por CV (regla 1-SE), coeficientes en escala original | `GLMSELECT SELECTION=LASSO` | ejercicio 5.1 (formación) |
| `bandas_confianza_regresion(x, y, metodo)` | Bandas simultáneas Working-Hotelling / Bonferroni y de predicción | `PROC REG CLM CLI` | nuevo (0.10) |
| `regresion_inversa(x, y, y0)` | Calibración: x0 a partir de una lectura con IC de Fieller | `PROC REG INVERSE` | nuevo (0.10) |
| `regresion_por_origen(x, y)` | Recta sin ordenada, contraste de la ordenada y aviso del R² | `MODEL / NOINT` | nuevo (0.10) |
| `correccion_error_medida(x_obs, y, fiabilidad/var_error)` | Errores de medida en X: calibración y SIMEX | — | nuevo (0.10) |
| `regresion_polinomica(x, y, grado_max)` | Polinomios ortogonales con grado por F secuencial o CV | `PROC GLM` | nuevo (0.10) |
| `tamano_muestral_modelo(n_parametros, tipo, prevalencia, r2)` | n mínimo para desarrollar un modelo (criterios de Riley) | — | nuevo (0.10) |
| `regresion_local(x, y, 'loess'/'nadaraya_watson')` | Suavizado local con parámetro por validación cruzada | `PROC LOESS` | nuevo (0.10) |
| `funciones_escalonadas(df, y, x, cortes)` | Regresión por tramos (constante por tramo) | — | nuevo (0.10) |
| `ajustar_mars(X, y)` | MARS aditivo: funciones bisagra con poda GCV | `PROC ADAPTIVEREG` | nuevo (0.10) |
| `regresion_inversa_cortes(X, y)` | SIR: direcciones de reducción suficiente | — | nuevo (0.10) |
| `regresion_pls_pcr(X, y, 'pls'/'pcr')` | PLS o regresión por componentes con nº por CV | `PROC PLS` | nuevo (0.10) |
| `modelo_loglineal(datos, factores, modelo)` | Loglineal para tablas de contingencia (G², jerárquicos) | `PROC CATMOD LOGLIN` | nuevo (0.10) |

## diagnostico

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `calcular_vif(X)` | VIF con diagnóstico OK/Moderado/ALTO | `PROC REG / VIF` | notebook de consultoría |
| `filtrar_vif_iterativo(X, umbral, protegidas)` | Quita la peor columna hasta VIF ≤ umbral | — | `filtrar_vif` (notebook de consultoría) |
| `hosmer_lemeshow(y, p, g=10)` | Calibración: estadístico, gl, p, tabla O/E | `LACKFIT` | `hosmer_lemeshow` |
| `estadisticos_asociacion(y, p)` | c, Somers' D, Gamma, Tau-a **exactos** (sin muestreo) | Association of Predicted Prob. | `_asociacion` (mejorada: O(n log n)) |
| `auc_train_test(modelo, train, test, objetivo)` | AUC y alerta de sobreajuste (gap > 0.02) | `ROC` | notebook de consultoría |
| `metricas_binarias(y, p)` | AUC, LogLoss, Brier | — | `_met` |
| `tabla_umbrales(y, p)`, `umbral_optimo_youden` | Sens/Espec/PPV/NPV/Youden por umbral | `CTABLE` | bloque I |
| `resumen_auc_multiclase`, `matrices_confusion` | AUC OvR/OvO y confusión (conteos y por filas) | — | `multinomial_logit_sas_like` |
| `tabla_ganancia_lift(y, p, grupos)` | Ganancia y lift por deciles (tabla de campañas) | — | nuevo (0.9) |
| `estadistico_ks_gini(y, p)` | KS (con su umbral) y Gini | `NPAR1WAY EDF` | nuevo |
| `curva_precision_recall(y, p)` | Precisión-exhaustividad, AP y umbral de F1 máximo | — | nuevo |
| `descomposicion_brier(y, p)` | Brier = fiabilidad − resolución + incertidumbre | — | nuevo |
| `calibrar_probabilidades(y_cal, p_cal, p_nuevas, metodo)` | Recalibración Platt o isotónica | — | nuevo |
| `dominio_aplicabilidad(X_train, X_nuevo)` | ¿El modelo extrapola? Apalancamiento, Mahalanobis, k-NN y rango | — | nuevo (0.10) |

## clustering

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `preparar_matriz_clustering(df, num, cat, ord, escalado, pesos)` | MinMax/Standard + one-hot + ordinal + pesos por variable | `PROC STDIZE` | notebook de consultoría |
| `buscar_k_silhouette(X, k_min, k_max)` | Silhouette (con muestra), Davies-Bouldin, Calinski-Harabasz por K | — | ídem |
| `ajustar_kmeans(X, k, ordenar_por=precio)` | Etiquetas 1..k ordenadas, pseudo-R² | `PROC FASTCLUS` | ídem |
| `proyeccion_pca(X)` | PC1/PC2 para dibujar | `PROC PRINCOMP` | notebook de consultoría |

## contrastes

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `elegir_contraste(df, valor, grupo)` | Elige y ejecuta el test; devuelve supuestos, tamaño del efecto, avisos e interpretación | `TTEST`, `NPAR1WAY`, `ANOVA`, `FREQ` | `Stats/Contrastes de Igualdad.txt` |
| `tukey_entre_grupos(df, valor, grupo)` | Tukey HSD por pares | `MEANS / TUKEY` | notebook de consultoría |
| `ajustar_p_valores(p, metodo='fdr_bh')` | Comparaciones múltiples: BH (FDR), BY, Holm, Bonferroni | `PROC MULTTEST` | nuevo (Very Normal) |
| `tamano_muestral_medias(efecto)`, `tamano_muestral_proporciones(p1, p2)` | n por grupo para una potencia dada | `PROC POWER` | nuevo |
| `potencia_contraste_medias(n, efecto)`, `curva_potencia(efecto)` | Potencia de un t-test / tabla n → potencia | `PROC POWER PLOT` | nuevo |
| `potencia_por_simulacion(generador, contraste, n)` | Potencia (o error tipo I real) por Monte Carlo para cualquier test | — | nuevo (Very Normal) |
| `contraste_apareado(antes, despues)` | Muestras relacionadas: t apareado o Wilcoxon de rangos con signo, IC y d_z | `TTEST PAIRED` | nuevo (0.9) |
| `contraste_friedman(df, sujeto, condicion, valor)` | Medidas repetidas no paramétrico + W de Kendall | `FREQ CMH2 SCORES=RANK` | nuevo |
| `contraste_mcnemar(antes, despues)` | Proporciones apareadas (exacto si hay pocos discordantes) | `FREQ / AGREE` | nuevo |
| `contraste_permutacion(a, b, estadistico)` | Contraste exacto por permutación (media, mediana o propio) | `NPAR1WAY EXACT / MC` | nuevo |
| `contraste_jonckheere(df, valor, grupo, orden)` | Tendencia ordenada entre grupos | `FREQ JT` | nuevo |
| `posthoc_dunn(df, valor, grupo)` | Post-hoc no paramétrico tras Kruskal-Wallis | `NPAR1WAY DSCF` (similar) | nuevo |
| `games_howell(df, valor, grupo)` | Pares sin varianzas iguales | — | nuevo |
| `intervalo_proporcion(exitos, n, metodo)` | IC de una proporción: Wilson, Clopper-Pearson, Jeffreys, Agresti-Coull, Wald | `FREQ / BINOMIAL` | nuevo |
| `bootstrap_ic(x, estadistico, metodo='bca')` | IC bootstrap percentil o BCa de cualquier estadístico | `PROC SURVEYSELECT` + macro | nuevo |
| `bondad_ajuste_multinomial(observados, probs)` | χ² de bondad de ajuste con residuos | `FREQ / TESTP=` | nuevo |

## descriptiva

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `resumen_descriptivo(df, columnas, recorte)` | Posición, variabilidad (MAD, IQR), percentiles, asimetría y curtosis por variable | `PROC MEANS` / `UNIVARIATE` | nuevo (0.9) |
| `detectar_atipicos(x, 'iqr'/'mad'/'z')` | Marca atípicos con Tukey, z robusto (MAD) o z clásico | `UNIVARIATE` (extremos) | nuevo |
| `correlacion_con_ic(x, y, metodo)` | Pearson / Spearman / Kendall con IC (Fisher) y p | `PROC CORR … FISHER` | nuevo |
| `matriz_correlaciones(df, columnas, metodo)` | Matrices de r, p y n por pares | `PROC CORR` | nuevo |
| `correlacion_parcial(df, x, y, controles)` | Correlación parcial y semiparcial | `PROC CORR PARTIAL` | nuevo |
| `contraste_normalidad(x)` | Shapiro, D'Agostino, Jarque-Bera, Anderson-Darling, Lilliefors | `UNIVARIATE NORMAL` | nuevo |
| `homogeneidad_varianzas(df, valor, grupo)` | Levene, Brown-Forsythe, Bartlett, Fligner | `GLM / HOVTEST` | nuevo |
| `ajustar_distribuciones(x, candidatas)` | MLE de 8 distribuciones continuas ordenadas por AIC (+KS) | `UNIVARIATE HISTOGRAM / LOGNORMAL GAMMA…` | nuevo |
| `ajustar_distribucion_discreta(x)` | Poisson vs binomial negativa vs geométrica (AIC y test LR) | `PROC GENMOD DIST=` | nuevo |
| `indice_dispersion(x)` | Sobredispersión de un conteo (varianza/media, χ²) | — | nuevo |
| `funcion_distribucion_empirica(x)` | F empírica con banda DKW | `UNIVARIATE CDFPLOT` | nuevo |
| `estimar_densidad(x, ancho)` | Densidad por núcleo gaussiano | `PROC KDE` | nuevo |
| `tabla_contingencia(df, fila, columna)` | χ², G², Fisher, V de Cramér, residuos ajustados | `PROC FREQ / CHISQ` | nuevo |
| `medidas_riesgo_2x2(a, n1, c, n0)` | Riesgo relativo, diferencia de riesgos, OR y NNT con IC | `FREQ / RELRISK RISKDIFF` | nuevo |
| `diccionario_datos(df, descripciones)` | Diccionario del dataset con rol sugerido y alerta de fuga | `PROC CONTENTS` | nuevo (0.10) |

## multivariante

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `distancia_mahalanobis(X, robusta=True)` | Atípicos multivariantes con MCD (no se enmascaran) | `PROC ROBUSTCOV` | nuevo (0.9) |
| `contraste_hotelling(X1, X2)` | T² de Hotelling: ¿difieren los vectores de medias? | `PROC GLM MANOVA` (2 grupos) | nuevo |
| `contraste_box_m(df, variables, grupo)` | M de Box: igualdad de covarianzas | `DISCRIM POOL=TEST` | nuevo |
| `manova(df, respuestas, grupo)` | Wilks, Pillai, Hotelling-Lawley, Roy | `PROC GLM / MANOVA` | nuevo |
| `correlacion_canonica(X, Y)` | Correlaciones canónicas con contrastes y cargas | `PROC CANCORR` | nuevo |
| `pca_completo(X, escalar)` | Varianza, cargas, puntuaciones, Kaiser y contribuciones | `PROC PRINCOMP` | nuevo |
| `adecuacion_factorial(X)` | KMO y esfericidad de Bartlett | `FACTOR MSA` | nuevo |
| `analisis_factorial(X, n_factores, rotacion)` | Factorial ML con varimax, comunalidades | `PROC FACTOR METHOD=ML` | nuevo |
| `alfa_cronbach(items)` | Fiabilidad con IC, α si se elimina e ítem-total | `PROC CORR ALPHA` | nuevo |
| `escalamiento_multidimensional(D o X)` | MDS clásico | `PROC MDS` | nuevo |
| `analisis_correspondencias(tabla)` | Correspondencias simple: inercia y coordenadas | `PROC CORRESP` | nuevo |
| `clustering_jerarquico(X, k, metodo)` | Ward/average/complete + cofenética | `PROC CLUSTER / TREE` | nuevo |
| `mezclas_gaussianas(X, k_max)` | Clustering por modelos, k por BIC y probabilidades | — (mclust) | nuevo |
| `analisis_discriminante(X, y, 'lda'/'qda')` | Discriminante con exactitud CV y funciones | `PROC DISCRIM / CANDISC` | nuevo |
| `regresion_multivariante(df, respuestas, predictores)` | Varias respuestas: Wilks/Pillai por predictor | `PROC GLM MANOVA` | nuevo (0.10) |
| `analisis_perfiles(df, medidas, grupo)` | Paralelismo, niveles y planitud | `PROC GLM REPEATED PROFILE` | nuevo (0.10) |
| `control_t2_multivariante(X_fase1, X_fase2)` | Gráfico de control T² de Hotelling | `PROC SHEWHART` | nuevo (0.10) |
| `analisis_conjunto(df, valoracion, atributos)` | Conjoint: utilidades e importancia de atributos | `PROC TRANSREG` | nuevo (0.10) |
| `modelo_grafico_gaussiano(X)` | Lasso gráfico: correlaciones parciales y aristas | — | nuevo (0.10) |
| `pca_funcional(curvas, t)` | Datos funcionales: B-splines + PCA funcional | — | nuevo (0.10) |
| `regresion_matriz_indicadora(X, y)` | Clasificación por MCO (enmascaramiento) | — | nuevo (0.10) |
| `centroides_contraidos(X, y)` | Centroides contraídos más cercanos (p ≫ n) | — | nuevo (0.10) |
| `pls_da(X, y)` | Discriminante PLS con VIP | `PROC PLS` | nuevo (0.10) |

## ml

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `ajustar_arbol_decision(X, y, poda='cv')` | CART con poda por complejidad, reglas e importancias | `PROC HPSPLIT` | nuevo (0.9) |
| `ajustar_random_forest(X, y, n_arboles)` | Random forest con OOB e importancias (bagging si max_variables=None) | `PROC HPFOREST` | nuevo |
| `ajustar_gradient_boosting(X, y, tasa)` | Boosting por histogramas con parada temprana | `PROC GRADBOOST` | nuevo |
| `ajustar_adaboost(X, y)` | AdaBoost con tocones | — | nuevo |
| `ajustar_knn(X, y, k='cv')` | k vecinos (X escaladas, k por CV) | `PROC DISCRIM METHOD=NPAR K=` | nuevo |
| `ajustar_svm(X, y, kernel)` | Máquina de vectores soporte | `PROC SVMACHINE` | nuevo |
| `ajustar_naive_bayes(X, y)` | Naive Bayes gaussiano | — | nuevo |
| `ajustar_red_neuronal(X, y, capas)` | Perceptrón multicapa con parada temprana | `PROC NNET` | nuevo |
| `ajustar_stacking(X, y)` | Logística + bosque + boosting combinados | — | nuevo |
| `comparar_clasificadores(X, y, modelos)` | Misma CV para varios modelos: AUC, log-loss, Brier, tiempo | — | nuevo |
| `importancia_permutacion(resultado)` | Importancia por permutación en test | — | nuevo |
| `dependencia_parcial(resultado, variable, ice)` | Dependencia parcial y curvas ICE | — | nuevo |
| `reglas_asociacion(transacciones, soporte_min, confianza_min)` | Apriori: soporte, confianza, lift | `PROC ASSOC` | nuevo (0.10) |
| `mapa_autoorganizado(X, filas, columnas)` | SOM de Kohonen con matriz U | `PROC SOM` (EM) | nuevo (0.10) |
| `modelo_ngramas(textos, n)` | Modelo de lenguaje de n-gramas y perplejidad | — | nuevo (0.10) |
| `muestrear_siguiente(probs, temperatura, top_k, top_p)` | Muestreo del siguiente token como un LLM | — | nuevo (0.10) |
| `muestrear_texto(modelo, inicio)` | Generación autorregresiva con un modelo de n-gramas | — | nuevo (0.10) |
| `ajustar_bradley_terry(comparaciones)` | Modelo de recompensa por pares (RLHF, rankings) | — | nuevo (0.10) |
| `recuperar_tfidf(documentos, consulta)` | Recuperación por similitud (la R de RAG) | — | nuevo (0.10) |
| `autoconsistencia_votacion(prob_acierto)` | Precisión de votar entre varias cadenas de razonamiento | — | nuevo (0.10) |
| `proceso_difusion(x0)` | Proceso de difusión directo (DDPM) | — | nuevo (0.10) |

Todos los `ajustar_*` de ml devuelven lo mismo: `modelo`, `metricas_train`, `metricas_test`, `sobreajuste`, `predecir(df)`, `columnas`, `X_test`, `y_test`.

## actuarial

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `qx_ley(edades, 'gompertz'/'makeham', A, B, c)` | qx de una ley de mortalidad | — | Biometría (máster) |
| `tabla_mortalidad(qx)` | lx, dx, Lx, Tx, esperanzas completa y abreviada | — | Biometría |
| `ajustar_ley_mortalidad(edades, defunciones, expuestos)` | Gompertz/Makeham por MV de Poisson (graduación) | `PROC NLMIXED` | Biometría |
| `probabilidad_supervivencia(tabla, x, t, hipotesis)` | tpx fraccionaria: UDD, fuerza constante, Balducci | — | Biometría |
| `vida_futura(tabla, x)` | K_x: probabilidades, esperanza, varianza, cuantiles | — | Biometría |
| `tabla_conjunta(tabla_x, x, tabla_y, y)` | Vida conjunta y último superviviente | — | Mate Vida |
| `decrementos_multiples(q_dependientes / q_independientes)` | Tasas dependientes ↔ independientes (UDD) | — | Mate Vida |
| `conmutados(tabla, i)` | Dx, Nx, Sx, Cx, Mx, Rx | — | Mate Vida |
| `seguro_vida(tabla, x, i, tipo, n, diferido, momento)` | Ax, temporal, dotal puro, mixto; varianza | — | Mate Vida |
| `renta_actuarial(tabla, x, i, n, anticipada, diferido, fraccionamiento, creciente)` | äx y variantes | — | Mate Vida |
| `prima_neta(tabla, x, i, tipo, n, pagos)` | Principio de equivalencia | — | Mate Vida |
| `provision_matematica(tabla, x, i, tipo, n)` | Provisión prospectiva año a año | — | Mate Vida |
| `prima_tarifa(..., alfa, beta, gamma)` | Prima comercial con gastos e inventario | — | Mate Vida |
| `sensibilidad_longevidad(tabla, x, i, choque)` | Impacto del choque de longevidad (SII −20 %) | — | Solvencia |
| `chain_ladder(triangulo)` | Factores, reservas IBNR y error de Mack | — | No Vida |
| `bootstrap_chain_ladder(triangulo, n_sim)` | Distribución de la reserva (ODP) y percentil 99.5 % | — | No Vida |
| `recursion_panjer(frecuencia, parametros, severidad)` | Siniestralidad agregada exacta (clase (a,b,0)) | — | No Vida |
| `simular_siniestralidad_agregada(frecuencia, severidad)` | Agregada por simulación con VaR y TVaR | — | No Vida |
| `probabilidad_ruina(u, recargo, media, ...)` | Cramér-Lundberg: ψ(u), Lundberg y horizonte finito | — | No Vida |
| `prima_por_principios(x / distribucion)` | Primas por 7 principios | — | No Vida |
| `credibilidad_buhlmann(df, riesgo, valor, exposicion)` | Bühlmann-Straub: Z, k y prima de credibilidad | — | No Vida |
| `tasas_especificas(defunciones, poblacion)` | Tasas con IC de Poisson y tasa bruta | `PROC STDRATE` | Demografía |
| `estandarizar_tasas(defs, pob, referencia, metodo)` | Estandarización directa e indirecta (SMR) | `PROC STDRATE` | Demografía |
| `exposicion_por_edad(df, nac, entrada, salida, evento)` | Exposición central por edad (Lexis) y m_x | — | Demografía |
| `indicadores_fecundidad(nacimientos, mujeres, edades)` | ISF, TBR, edad media a la maternidad | — | Demografía |
| `proyeccion_leslie(poblacion, supervivencia, fecundidad)` | Proyección por cohortes y λ | `PROC IML` | Demografía |

## finanzas

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `var_tvar(perdidas, niveles, metodo)` | VaR y TVaR: histórico, normal, Cornish-Fisher | `PROC RISK` | Medidas de riesgo (máster) |
| `ajustar_gpd(datos, umbral)` | EVT: picos sobre umbral (Pareto generalizada) y VaR/TVaR extremos | — | Valores extremos |
| `estimador_hill(datos)` | Índice de cola de Hill por k | — | Valores extremos |
| `funcion_exceso_medio(datos)` | e(u) para diagnosticar la cola y el umbral | — | Valores extremos |
| `simular_copula(tipo, parametro, n, marginales)` | Cópulas gaussiana, t, Clayton y Gumbel | `PROC COPULA` | Dependencia |
| `prueba_estres(exposiciones, escenarios)` | Pérdida por escenario de estrés | — | Solvencia |
| `matriz_covarianzas(rendimientos, 'ledoit_wolf')` | Covarianza contraída (estable) | — | Carteras |
| `frontera_eficiente(medias, covarianza, tasa_libre)` | Markowitz: frontera, mínima varianza y tangente | `PROC OPTMODEL` | Carteras |
| `beta_capm(activo, mercado, rf)` | β, α y SML | `PROC REG` | Carteras |
| `modelo_factores(rendimientos, factores)` | APT / multifactor | `PROC REG` | Carteras |
| `black_litterman(covarianza, pesos, P, Q)` | Equilibrio + opiniones → pesos | — | Carteras |
| `dominancia_estocastica(a, b)` | FSD y SSD empíricas | — | Carteras |
| `equivalente_cierto(resultados, probs, utilidad, aversion)` | Equivalente cierto y prima de riesgo | — | Utilidad |
| `fraccion_anio(inicio, fin, convencion)` | Act/365, Act/360, 30/360, Act/Act | `YRDIF` | Renta fija |
| `precio_bono(nominal, cupon, anios, tir)` | Precio, duraciones y convexidad | `FINANCE` | Renta fija |
| `tir_bono(precio, nominal, cupon, anios)` | Rentabilidad al vencimiento | `FINANCE YIELDP` | Renta fija |
| `bootstrapping_etti(plazos, cupones, precios)` | ETTI cupón cero y forwards | — | Renta fija |
| `inmunizacion(duracion_pasivo, valor_pasivo, bonos)` | Redington con dos bonos | — | Renta fija |
| `valorar_swap(tipo_fijo, factores_descuento)` | IRS / FRA y tipo swap par | — | Derivados |
| `black_scholes(S, K, T, r, sigma, tipo)` | Opción europea y griegas | `BLACKS` | Derivados |
| `arbol_binomial(S, K, T, r, sigma, pasos, tipo, americana)` | CRR neutral al riesgo, europea o americana | — | Derivados |
| `arbol_black_derman_toy(tipos_cero, volatilidades)` | Árbol de tipos BDT calibrado a la curva | — | Derivados (0.10) |

## simulacion

Probabilidad, Monte Carlo, inferencia por simulación, bayesiana, procesos estocásticos y muestreo de encuestas.

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `posterior_conjugado(modelo, datos, previa)` | Beta-binomial, gamma-Poisson, normal-normal: posterior, IC creíble, Z | `PROC MCMC` | Bayesiana (0.10) |
| `bayes_empirico_beta(exitos, ensayos)` | Previa estimada y contracción de tasas por grupo | — | Bayesiana |
| `metropolis(log_posterior, inicial)` | MCMC de paseo aleatorio con varias cadenas, R-hat y ESS | `PROC MCMC` | Bayesiana |
| `diagnostico_mcmc(muestras)` | R-hat dividido, ESS y error de Monte Carlo | `PROC MCMC DIAG` | Bayesiana |
| `chequeo_predictivo(observado, muestras, simulador)` | Chequeo predictivo previo/posterior con p bayesianos | — | Very Normal |
| `accion_bayes(muestras, perdida)` | Acción de Bayes (cuadrática, absoluta, asimétrica o matriz) | — | Teoría de la decisión |
| `ab_bayesiano(exitos_a, n_a, exitos_b, n_b)` | P(B > A), uplift y pérdida esperada | — | Very Normal |
| `simular_bandido(probabilidades, n_rondas, estrategia)` | Thompson, UCB, ε-greedy frente a A/B | — | Very Normal |
| `cadena_markov(P, inicial)` | Clases, periodo, estacionaria, absorción y tiempos | `PROC IML` | Procesos estocásticos |
| `simular_cadena_markov(P, n_pasos)` | Trayectorias de una cadena | — | Procesos estocásticos |
| `bonus_malus(coeficientes, reglas, frecuencia)` | Bonus-malus: estacionaria y eficiencia de Loimaranta | — | Procesos estocásticos |
| `cadena_markov_continua(Q, t)` | P(t) = exp(Qt), estacionaria y permanencias | — | Procesos estocásticos |
| `nacimiento_muerte(nacimiento, muerte, servidores)` | Equilibrio y colas M/M/c(/K) | `PROC QSIM` | Procesos estocásticos |
| `simular_proceso_poisson(tasa, horizonte)` | Poisson homogéneo y no homogéneo | — | Procesos estocásticos |
| `contraste_proceso_poisson(tiempos, horizonte)` | ¿Las llegadas son Poisson? | — | Procesos estocásticos |
| `ruina_jugador(capital, objetivo, p)` | Probabilidad de ruina y duración | — | Procesos estocásticos |
| `paseo_aleatorio(n_pasos, p)` | Paseo aleatorio y martingalas | — | Procesos estocásticos |
| `simular_browniano(horizonte, n_pasos, mu, sigma, geometrico)` | Browniano aritmético y geométrico | — | Cálculo estocástico |
| `generador_congruencial(n, semilla, a, c, m)` | LCG (y RANDU) | `RANUNI` | Simulación |
| `contrastes_aleatoriedad(u)` | KS, χ², rachas, autocorrelación, pares y tripletas | — | Simulación |
| `generar_por_inversion(n, cuantil/cdf)` | Transformada inversa | `RAND('TABLE')` | Simulación |
| `generar_por_aceptacion_rechazo(n, densidad, propuesta)` | Aceptación-rechazo | — | Simulación |
| `generar_normal_multivariante(medias, covarianza, n)` | Cholesky o espectral | `RANDNORMAL` | Simulación |
| `estimar_montecarlo(f, n, metodo)` | Monte Carlo con antitéticas y variable de control | — | Simulación |
| `teorema_bayes(previas, verosimilitudes)` | Bayes discreto y VPP/VPN | — | Probabilidad |
| `analizar_distribucion_conjunta(tabla)` | Marginales, condicionadas, E[Y|X], independencia | `PROC FREQ` | Probabilidad |
| `distribucion_estadistico_orden(dist, n, k)` | Distribución del k-ésimo de n | — | Probabilidad |
| `momentos_distribucion(dist)` | Momentos y función generadora | — | Probabilidad |
| `convergencia_media_muestral(dist, tamanos)` | TCL y ley de los grandes números | — | Probabilidad |
| `metodo_momentos(datos, distribucion)` | Estimadores por momentos frente a MV | `PROC UNIVARIATE` | Estimación |
| `informacion_fisher(log_densidad, theta)` | Información de Fisher y cota de Cramér-Rao | — | Estimación |
| `comparar_estimadores(estimadores, generar, verdadero)` | Sesgo, varianza, ECM, eficiencia | — | Estimación |
| `metodo_delta(funcion, estimacion, covarianza)` | EE de una función de parámetros | `PROC NLMIXED ESTIMATE` | Estimación |
| `distribucion_muestral_simulada(tipo, gl)` | t, χ², F, T² desde normales; n − 1 | — | Inferencia |
| `simular_regresion_a_la_media(correlacion)` | Regresión a la media | — | Inferencia |
| `coste_de_dicotomizar(correlacion)` | Pérdida de potencia al partir una continua | — | Harrell |
| `extraer_muestra(df, n, metodo)` | MAS, sistemática, estratificada, conglomerados con pesos | `PROC SURVEYSELECT` | Muestreo |
| `estimar_mas(muestra, N)` | Media, total y proporción con corrección finita | `PROC SURVEYMEANS` | Muestreo |
| `tamano_muestra_encuesta(margen, N)` | n con efecto de diseño y no respuesta | — | Muestreo |
| `asignacion_estratos(N_h, S_h, n, metodo)` | Proporcional, Neyman u óptima | `PROC SURVEYSELECT ALLOC` | Muestreo |
| `estimar_estratificado(muestra, variable, estrato, N_h)` | Estimador estratificado y efecto de diseño | `PROC SURVEYMEANS STRATA` | Muestreo |
| `estimador_razon(y, x, media_x)` | Estimador de razón | `PROC SURVEYMEANS RATIO` | Muestreo |
| `ajuste_no_respuesta(df, respondio, celdas)` | Tasa de respuesta y pesos ajustados | — | Muestreo |

## diseno

ANOVA y diseños, diseño de experimentos e inferencia causal.

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `anova_factorial(df, respuesta, factores, tipo)` | ANOVA de varios factores, tipo II/III, η²p y ω² | `PROC GLM` | Diseño (0.10) |
| `anova_bloques(df, respuesta, tratamiento, bloque)` | Bloques aleatorizados con eficiencia relativa | `PROC GLM` | Diseño |
| `ancova(df, respuesta, grupo, covariables)` | ANCOVA: pendientes homogéneas y medias ajustadas | `PROC GLM LSMEANS` | Diseño |
| `anova_medidas_repetidas(df, sujeto, dentro, respuesta, entre)` | Medidas repetidas y mixto con GG/HF | `PROC GLM REPEATED` | Diseño |
| `anova_anidado(df, respuesta, factor, anidado)` | Diseño anidado y componentes de la varianza | `PROC NESTED` | Diseño |
| `diagnostico_anova(df, respuesta, factores)` | Supuestos y remedio recomendado | — | Diseño |
| `diseno_factorial_2k(k, generadores)` | 2^k y fraccionados con alias y resolución | `PROC FACTEX` | Diseño de experimentos |
| `efectos_factorial_2k(df, respuesta, factores)` | Efectos con Lenth y curvatura | `PROC GLM` / ADX | Diseño de experimentos |
| `cuadrado_latino(n)` | Generar un cuadrado latino | `PROC PLAN` | Diseño de experimentos |
| `anova_cuadrado_latino(df, respuesta)` | ANOVA del cuadrado latino | `PROC GLM` | Diseño de experimentos |
| `diseno_central_compuesto(k, alfa)` | Diseño central compuesto | `PROC ADX` | Superficie de respuesta |
| `superficie_respuesta(df, respuesta, factores)` | Segundo orden, punto estacionario y análisis canónico | `PROC RSREG` | Superficie de respuesta |
| `puntuacion_propension(df, tratamiento, resultado, covariables, metodo)` | IPW, emparejamiento o estratificación con balance | `PROC PSMATCH`, `CAUSALTRT` | Causal |
| `diferencias_en_diferencias(df, resultado, tratado, post)` | DiD con errores agrupados y tendencias previas | `PROC SURVEYREG` | Causal |
| `aleatorizar_ensayo(n, brazos, tamano_bloque, estratos)` | Lista de aleatorización por bloques | `PROC PLAN` | Ensayos |
| `analisis_intencion_tratar(df, asignado, recibido, resultado)` | ITT, por protocolo, según recibido y CACE | — | Ensayos |
| `mediacion(df, x, mediador, y)` | Efecto indirecto con IC bootstrap | `PROC CALIS` | Causal |
| `moderacion(df, y, x, moderador)` | Pendientes simples y Johnson-Neyman | `PROC GLM` | Causal |
| `metaanalisis(efectos, errores, metodo, hartung_knapp)` | Fijos, DL, REML; I², τ², predicción, Egger | `PROC MIXED` | Metaanálisis |

## graficos

Todas devuelven la `Figure` de matplotlib; galería ejecutable en `ejemplos/galeria_graficos.py`.

| Función | Para qué | SAS | Origen |
|---|---|---|---|
| `grafico_regresion_simple(df, x, y)` | Recta MCO con banda de confianza y de predicción | `PROC REG` FITPLOT | nuevo |
| `grafico_diagnostico_residuos(modelo)` | 4 paneles: residuos-ajustados, Q-Q, escala-localización, Cook | `PROC REG PLOTS=DIAGNOSTICS` | nuevo |
| `grafico_residuos_agrupados(y, p)` | Residuos agrupados (Gelman) para modelos 0/1 | — | nuevo |
| `grafico_curva_roc(y, p o {modelo: p})` | ROC con AUC y punto de Youden; compara modelos | `PLOTS=ROC` | nuevo |
| `grafico_calibracion(y, p)` | Observado vs predicho por deciles + Hosmer-Lemeshow | `PLOTS=CALIBRATION` | nuevo |
| `grafico_odds_ratios(tabla)` | Forest plot de `tabla_odds_ratios` | `PLOTS=ODDSRATIO` | nuevo |
| `grafico_umbrales(y, p)` | Sensibilidad, especificidad y Youden según el umbral | `CTABLE` | nuevo |
| `grafico_region_rechazo(estadistico, 't', gl)` | Distribución bajo H0, región de rechazo y área del p-valor | — | nuevo |
| `grafico_potencia(efecto, n)`, `grafico_curva_potencia(efectos)` | alpha, beta y potencia como áreas; potencia vs n | `PROC POWER PLOT` | nuevo |
| `grafico_comparar_grupos(df, valor, grupo)` | Caja + puntos (o barras 100 %) con el test de `elegir_contraste` en el título | `TTEST`/`NPAR1WAY PLOTS` | nuevo |
| `grafico_qq(x)` | Q-Q normal con Shapiro-Wilk | `UNIVARIATE QQPLOT` | nuevo |
| `grafico_fdr(p)` | p ordenados con recta BH y Bonferroni | `MULTTEST PLOTS` | nuevo |
| `grafico_kaplan_meier(df, duracion, evento, grupo)` | Curvas KM con censuras, IC y log-rank | `LIFETEST PLOTS=SURVIVAL` | nuevo |
| `grafico_seleccion_k(tabla)`, `grafico_clusters_pca(X, etiquetas)` | Silhouette/codo por K; clusters en PC1-PC2 | `SGPLOT` | notebook de consultoría |
| `grafico_vif(tabla)` | Barras de VIF con cortes 5 y 10 | `REG / VIF` | nuevo |
| `grafico_distribucion(x)` | Histograma + densidad + caja, con media y mediana | `UNIVARIATE HISTOGRAM` | nuevo (0.9) |
| `grafico_ajuste_distribuciones(x, tabla)` | Mejores distribuciones superpuestas y P-P | `UNIVARIATE PPPLOT` | nuevo |
| `grafico_matriz_correlaciones(r, p)` | Mapa de calor de correlaciones | `CORR PLOTS=MATRIX` | nuevo |
| `grafico_efecto_spline(resultado, variable)` | Curva parcial de un spline | `GAMPL PLOTS` | nuevo |
| `grafico_regularizacion(resultado)` | Error de CV frente a λ | `GLMSELECT PLOTS` | nuevo |
| `grafico_relatividades(tabla)` | Relatividades con IC | — | nuevo |
| `grafico_incidencia_acumulada(tabla)` | CIF por causa | `LIFETEST PLOTS=CIF` | nuevo |
| `grafico_ganancia_lift(y, p)` | Curva de ganancia y lift por decil | — | nuevo |
| `grafico_precision_recall(y, p)` | Curva precisión-exhaustividad | — | nuevo |
| `grafico_dendrograma(resultado, k)` | Dendrograma con corte | `PROC TREE` | nuevo |
| `grafico_biplot(pca)` | Biplot de componentes principales | `PRINCOMP PLOTS` | nuevo |
| `grafico_importancias(tabla)` | Importancias con sd | — | nuevo |
| `grafico_dependencia_parcial(dp)` | Dependencia parcial + ICE | — | nuevo |
| `grafico_tabla_mortalidad(*tablas)` | qx (log) y supervivientes | — | nuevo |
| `grafico_reserva_bootstrap(resultado)` | Distribución de la reserva con el 99.5 % | — | nuevo |
| `grafico_frontera_eficiente(resultado, medias, covarianza)` | Frontera de Markowitz | — | nuevo |
| `grafico_copula(datos)` | Nube de una cópula | — | nuevo |
| `grafico_trazas_mcmc(resultado)` | Trazas y densidades de MCMC con R-hat | `PROC MCMC PLOTS` | nuevo (0.10) |
| `grafico_bandido(resultados)` | Arrepentimiento acumulado por estrategia | — | nuevo (0.10) |
| `grafico_trayectorias(trayectorias)` | Trayectorias de un proceso con banda 5-95 % | — | nuevo (0.10) |
| `grafico_interaccion(df, respuesta, x, traza)` | Gráfico de interacción con ±EE | `LSMEANS PLOTS` | nuevo (0.10) |
| `grafico_efectos_2k(resultado)` | Seminormal de efectos con Lenth | `PROC FACTEX/ADX` | nuevo (0.10) |
| `grafico_superficie_respuesta(resultado)` | Contornos de la superficie de segundo orden | `PROC RSREG` | nuevo (0.10) |
| `grafico_balance(resultado)` | Love plot de la propensión | `PROC PSMATCH` | nuevo (0.10) |
| `grafico_metaanalisis(resultado)` | Forest plot con intervalo de predicción | — | nuevo (0.10) |
| `grafico_hexbin(df, x, y)` | Densidad de nubes grandes | `SGPLOT HEATMAP` | nuevo (0.10) |
| `grafico_violin(df, variable, grupo)` | Violín por grupo | — | nuevo (0.10) |
| `grafico_coordenadas_paralelas(df, variables, clase)` | Coordenadas paralelas | — | nuevo (0.10) |
| `grafico_curvas_andrews(df, variables, clase)` | Curvas de Andrews | — | nuevo (0.10) |
| `grafico_caras_chernoff(df, variables)` | Caras de Chernoff | — | nuevo (0.10) |
| `grafico_variable_anadida(modelo, variable)` | Regresión parcial | `PROC REG PARTIAL` | nuevo (0.10) |
| `grafico_bandas_regresion(bandas, x, y)` | Recta con banda simultánea | `PROC REG FITPLOT` | nuevo (0.10) |
| `grafico_control_t2(resultado)` | Control T² fases I y II | `PROC SHEWHART` | nuevo (0.10) |

## Conceptos (temario del máster y Very Normal)

`conceptos/catalogo.json` es la lista de conceptos del árbol (se edita a mano; después `python py/construir_visor.py`). Los conceptos se agrupan en **8 temas** (cada tema es una rama del mapa 3D, con su color) y **38 áreas** (los módulos de la rama). Cada concepto tiene
nombre, área, descripción, `prioridad` (opcional: `"alta"`), sinónimos, **funciones del árbol que lo implementan** (vacío = *hueco*) y **fuentes** (asignatura y tema, o vídeo/post de Very Normal con enlace).
El `ambito` del área (`metodologico`, `actuarial`, `financiero`, `normativo`) sirve para no contar como hueco lo que solo se estudia (contabilidad, derecho, solvencia): esos conceptos son *normativos* y no se programan.
Para mover un concepto de área edita su `area` en el catálogo; si no quieres que una actualización lo recoloque, añade `"area_fija": true` al concepto. Los ids de concepto no cambian al reorganizar.
Una prueba (`py/tests/test_visor.py`) exige que las funciones citadas existan y que **toda función pública esté enlazada a algún concepto**.

| Tema (rama del mapa) | Área (módulo) | Ámbito | Conceptos | Sin código |
|---|---|---|---|---|
| Probabilidad y distribuciones | Fundamentos de probabilidad | metodologico | 12 | 12 |
| Probabilidad y distribuciones | Distribuciones univariantes | metodologico | 13 | 12 |
| Probabilidad y distribuciones | Colas pesadas y dependencia | metodologico | 3 | 3 |
| Inferencia y contrastes | Fundamentos de inferencia | metodologico | 12 | 10 |
| Inferencia y contrastes | Estimación e intervalos | metodologico | 10 | 7 |
| Inferencia y contrastes | Lógica del contraste | metodologico | 10 | 4 |
| Inferencia y contrastes | Tests concretos | metodologico | 10 | 5 |
| Inferencia y contrastes | Descriptiva y correlación | metodologico | 15 | 15 |
| Inferencia y contrastes | ANOVA y diseño de experimentos | metodologico | 13 | 13 |
| Regresión y GLM | Regresión lineal | metodologico | 27 | 23 |
| Regresión y GLM | GLM de respuesta categórica | metodologico | 11 | 4 |
| Regresión y GLM | GLM de conteo y continua | metodologico | 4 | 3 |
| Regresión y GLM | Modelos avanzados | metodologico | 12 | 12 |
| Validación y machine learning | Selección y validación de modelos | metodologico | 28 | 22 |
| Validación y machine learning | Evaluación de clasificadores | metodologico | 10 | 4 |
| Validación y machine learning | Preprocesado | metodologico | 9 | 6 |
| Validación y machine learning | Aprendizaje no supervisado | metodologico | 5 | 2 |
| Validación y machine learning | Árboles y ensembles | metodologico | 9 | 9 |
| Validación y machine learning | Análisis multivariante | metodologico | 21 | 21 |
| Validación y machine learning | Otros modelos de aprendizaje | metodologico | 11 | 11 |
| Validación y machine learning | IA generativa y LLM | metodologico | 5 | 5 |
| Simulación, Bayes y diseño | Simulación | metodologico | 6 | 4 |
| Simulación, Bayes y diseño | Estadística bayesiana | metodologico | 6 | 6 |
| Simulación, Bayes y diseño | Diseño y causalidad | metodologico | 11 | 9 |
| Simulación, Bayes y diseño | Muestreo en encuestas | metodologico | 3 | 3 |
| Demografía y supervivencia | Demografía y tasas | actuarial | 8 | 8 |
| Demografía y supervivencia | Tablas de vida y supervivencia actuarial | actuarial | 10 | 10 |
| Demografía y supervivencia | Análisis de supervivencia | metodologico | 11 | 7 |
| Demografía y supervivencia | Procesos estocásticos | metodologico | 9 | 9 |
| Seguros y riesgo | Seguros no vida | actuarial | 8 | 8 |
| Seguros y riesgo | Seguros de vida | actuarial | 7 | 7 |
| Seguros y riesgo | Medidas de riesgo | actuarial | 4 | 4 |
| Seguros y riesgo | Solvencia y capital | normativo | 11 | 11 |
| Finanzas y normativa | Carteras | financiero | 7 | 7 |
| Finanzas y normativa | Renta fija y derivados | financiero | 8 | 8 |
| Finanzas y normativa | Marco contable | normativo | 7 | 7 |
| Finanzas y normativa | Marco legal de seguros | normativo | 4 | 4 |
| Finanzas y normativa | Previsión social | normativo | 4 | 4 |

Fuentes usadas: **manuales de estadística** de tu carpeta «Manuales Estadística» (fuente `manual`; se citan por título de capítulo con una sigla: ALSM (solo su resumen), JW (Johnson-Wichern 4.ª ed.), HS (Härdle-Simar), ISLR (1.ª ed.), APM, RMS (Harrell), MSDA (Rice), ESL (1.ª ed.), PSDS (3.ª ed. incompleta: solo caps. 1 y 10) y DSUS (Field)); lo que figura como «(2.ª ed.)» no está en tu copia. Alta de conceptos con `herramientas/ampliar_catalogo_manuales.py`; guías docentes de 2º (Simulación y modelos, Renta Fija, Previsión Social Complementaria, Contabilidad, Derecho del seguro, Matemática actuarial de la solvencia); de 1º **no hay guías docentes** en la carpeta,
así que se usaron los índices de los temas (Biometría, Mate No Vida, Mate Vida, Procesos Estocásticos, VBA y Modelos de Cartera, Matemáticas). Derivados, Fiscalidad, Economía y Seguridad Social y Derecho Bancario están **solo mencionados**, no leídos tema a tema.

## Pendiente (ideas que ya aparecen en tus materiales)

- **Very Normal:** los 73 vídeos largos ya están enlazados (`teoria/very_normal.md`); faltan los Shorts. FDR, Kaplan-Meier/Cox y tamaño muestral ya tienen código, gráfico y demo.
- **Guías de 1º y asignaturas leídas solo por título:** añadir Derivados, Fiscalidad, Economía y SS y Derecho Bancario con su temario real.
- Los **huecos** del visor (casilla «Solo huecos») son la cola de trabajo: los de mayor interés estadístico son Poisson/NegBin/Gamma, Ridge/Lasso, CV, bootstrap, Bayes, comprobación de riesgos proporcionales (Schoenfeld).
- Frecuencia y severidad (formación, ejercicios 5.2 y 5.3): Poisson, sobredispersión (deviance/gl), Binomial Negativa, Gamma con enlace log, prima pura = frecuencia × severidad.
- Ridge / Lasso en logit (ejercicio 5.1) y validación cruzada estratificada con IC por bootstrap.
- Contrastes para muestras apareadas (Wilcoxon, Friedman) y post-hoc no paramétrico (Dunn).
- `LSMEANS` exacto de SAS (evaluado en las medias de las covariables) además del `lsmeans_like` marginal.
- Selección backward / bidireccional y por p-valor (`SLENTRY`/`SLSTAY`).
- KS y Gini, curvas de calibración, lift por decil.
