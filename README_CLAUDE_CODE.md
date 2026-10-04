# Árbol de la estadística — guía para Claude Code

Léeme al empezar una sesión de Claude Code en esta carpeta. Las **reglas** del proyecto (convenciones, errores conocidos que
no se deben reintroducir, la tabla «qué usar») están en `CLAUDE.md`, que Claude Code carga solo. El **mapa de funciones** está
en `INDEX.md`. Este fichero explica **cómo trabajar**: entorno, comandos, el procedimiento para añadir una función y las
trampas que ya han aparecido.

Estado actual: **v0.13.0**.
- 14 ramas, 343 funciones con ficha y 580 tests en verde.
- 348 de los 374 conceptos del catálogo tienen código. Los 26 restantes son de ámbito normativo y no se programan.

---

## 1. Entorno

- **Windows.** La carpeta se llama «Árbol de la estadística» (con tilde).
  Cita siempre las rutas entre comillas.
- **Python.** Usa el de la carpeta (`python\python.exe`) si existe; si no, `py -3`. Los `.bat` ya lo resuelven así.
  `python_arbol.txt` apunta al Python 3.12 del usuario.
  - Dependencias en `py/requirements.txt`: numpy, pandas 3, scipy, statsmodels, scikit-learn 1.9, matplotlib, patsy, pywebview.
  - **No** están ni sympy ni pytest-xdist.
- **El paquete** se importa como `arbol_estadistica` desde `py/`. Para registrarlo: `pip install -e py`, o ejecuta desde `py/`.
- **OneDrive** puede bloquear ficheros mientras sincroniza. Si una escritura falla con «permiso denegado», reintenta.
- **Recomendado: `git init`** en la carpeta y un commit por versión. Ahora mismo el único historial es `anteriores/` y el de OneDrive.
  - Ignora `__pycache__/`, `.pytest_cache/`, `python/`, `anteriores/` e `instaladores/`. Los `.bat` de `instaladores/` pesan unos 2 MB cada uno y se regeneran.

## 2. Comandos

Ejecuta todo desde la raíz de la carpeta salvo que se indique otra cosa.

| Qué | Comando | Lanzador |
|---|---|---|
| Tests (unos 4 min) | `cd py && python -m pytest -q` | `ejecutar_tests.bat` |
| Tests de un fichero o función | `cd py && python -m pytest -q tests/test_diseno.py -k metaanalisis` | |
| Ejemplos del cuaderno de unas funciones | `cd py && python -m pytest -q tests/test_cuaderno.py -k "f1 or f2"` | |
| Regenerar fichas (`fichas.json`) | `python herramientas/fichas_fuente.py` | |
| Medir velocidad, escalabilidad y memoria de unas funciones | `cd py && python medir_propiedades.py f1 f2` | |
| Medir todo + simulaciones Monte Carlo (lento) | `cd py && python medir_propiedades.py` (`--rapido` para probar) | `medir_propiedades.bat` |
| Regenerar el visor | `python py/construir_visor.py` | `regenerar_visor.bat` |
| Generar instaladores | `python herramientas/generar_instaladores.py` | |

Nota sobre `medir_propiedades.py`: si le pasas nombres de funciones **y** `--sim`, ejecuta además todas las simulaciones.

Las medidas actuales (`py/propiedades/medidas.json`) se tomaron en un Linux en la nube. Para que velocidad y memoria
reflejen el PC del usuario, vuelve a medir con `medir_propiedades.bat` cuando haya tiempo: tarda bastante.

## 3. Estructura del código

```
py/
├── arbol_estadistica/          el paquete; una carpeta por rama
│   ├── preprocesado/ seleccion/ modelos/ diagnostico/ clustering/ contrastes/
│   ├── descriptiva/ multivariante/ ml/ actuarial/ finanzas/ simulacion/ diseno/
│   ├── graficos/               un módulo por tema; NO se importa con `import arbol_estadistica`
│   └── _util.py                _numerico, _columnas, _rng (validación de entradas)
├── tests/                      un test_*.py por rama o versión
├── cuaderno/ejemplos.py        ESCENARIOS + E = {función: (escenario, [celdas])}
├── propiedades/                propiedades.json (definiciones, perfiles, grupos) · fichas.json (generado) · medidas.json (medido)
├── medir_propiedades.py        BENCH (@bench) + simulaciones sim_* (lista SIMULACIONES)
├── construir_visor.py          RAMAS (con color para las ramas posteriores a la 0.8) + lectura de INDEX.md y del código
└── visor/                      plantilla.html, mapa3d.js, demos.js
herramientas/fichas_fuente.py   f(nombre, grupo, notas, pros, contras, usar_si, evitar_si)
conceptos/catalogo.json         datos del usuario (el actualizador no lo pisa) + catalogo_base.json (misma estructura)
```

## 4. Procedimiento: añadir una función

Hay **tests que fallan si falta cualquiera de estos pasos**: ficha, bench, ejemplo, concepto y exportación.

1. **Busca antes en `INDEX.md`** si ya existe algo parecido. No dupliques.
2. **Escribe el código** en el módulo de la rama (`py/arbol_estadistica/<rama>/<modulo>.py`):
   - nombre en español, `snake_case`, sin tildes ni eñes;
   - no mutar las entradas;
   - semilla 42;
   - devolver un `dict` o `DataFrame` con claves en español;
   - validar las entradas con `ValueError` y un mensaje claro;
   - docstring con qué hace, *Equivale a:* (procedimiento SAS) y *Gauss:* cuando haya supuestos o trampas.
3. **Expórtala** en `<rama>/__init__.py`: en el import y en `__all__`.
   `__all__` debe ser una **lista literal**: `construir_visor.py` lo lee con `ast` y `sorted([...])` lo rompe.
4. **Escribe el test** en `py/tests/`, con un caso donde la teoría dé la respuesta (fórmula cerrada, valor publicado o simulación con tolerancia razonable).
   - Usa un rng con semilla por test.
   - Comprueba también un `pytest.raises(ValueError)` de entrada inválida.
5. **Añade el ejemplo** en `py/cuaderno/ejemplos.py`, dentro del dict `E`.
   - Formato: `"funcion": ("escenario", ["celda1", "celda2"])`. Los escenarios disponibles están en `ESCENARIOS`; `"ninguno"` = solo imports.
   - Si una celda «dibuja» (contiene `grafico_`, `.plot` o `plt.`), el test exige que salga una imagen. Ojo: también salta con nombres como `modelo_grafico_gaussiano`.
   - Si la rama es nueva, añade su `from arbol_estadistica.<rama> import *` en `IMPORTS`.
6. **Escribe la ficha** en `herramientas/fichas_fuente.py`, antes de `def main()`:
   ```python
   f("mi_funcion", "<grupo>", "ins=8 con=9 ... esc=9 vel=8", ["pros"], ["contras"], "úsala si…", "evítala si…")
   ```
   - Las abreviaturas están en `ABREV`, al principio del fichero.
   - `A` = plantilla para funciones de fórmula cerrada; `G` = plantilla para gráficos.
   - El **grupo** debe existir en `py/propiedades/propiedades.json` → `grupos`. Si creas uno nuevo, debe tener al menos una función.
   - Los gráficos van en grupos `graf_*`: el visor no los ordena frente a los cálculos.
   - Después ejecuta `python herramientas/fichas_fuente.py`.
7. **Registra el bench** en `py/medir_propiedades.py`:
   - Con `@bench("mi_funcion")`, una función `_(n)` que prepara datos de tamaño `n` y devuelve un `lambda` que la llama. Mide n = 1 000…64 000 y para si pasa de 4 s.
   - Si no depende de n: `bench(nombre, fijo=True)`. Los gráficos, envueltos en `_cerrar(...)`.
   - Si la función es O(n²) en memoria, que lance un `ValueError` por encima de un límite; la medición lo captura y anota el límite.
   - Si tiene una propiedad estadística medible (α real, cobertura, sesgo), añade o amplía una `sim_*` y métela en `SIMULACIONES`.
   - Después ejecuta `python medir_propiedades.py mi_funcion`.
8. **Añade la fila en `INDEX.md`** dentro de la sección de su rama, con el formato `| \`firma(args)\` | Para qué | SAS | Origen |`. El visor saca la descripción de aquí.
9. **Enlázala al catálogo**: añade su nombre a `funciones` de al menos un concepto, **en `conceptos/catalogo.json` y en `catalogo_base.json`**. Respeta el sangrado que ya tenga cada JSON.
10. **Si la rama es nueva**, regístrala además en cuatro sitios:
    - `RAMAS` de `construir_visor.py`, con color claro/oscuro;
    - `packages` de `py/pyproject.toml`;
    - el import y `__all__` de `arbol_estadistica/__init__.py`;
    - el árbol de texto al principio de `INDEX.md`.
11. **Cierra**:
    - `python py/construir_visor.py`;
    - la suite completa de tests;
    - si la tabla «qué usar» de `CLAUDE.md` gana una fila, añádela.

### Publicar una versión

1. Sube la versión **en los tres sitios**: `py/VERSION.txt`, `py/pyproject.toml` y `__version__` en `arbol_estadistica/__init__.py`.
2. Ejecuta la suite completa y regenera el visor.
3. Ejecuta `python herramientas/generar_instaladores.py`, que comprueba que se extraen idénticos.
4. El usuario actualiza con `instaladores/Arbol X.Y.Z - Actualizar.bat`, que conserva su `catalogo.json` y le fusiona los conceptos nuevos.

## 5. Trampas que ya han salido (no repetirlas)

- **patsy evalúa las fórmulas en el entorno de la función.** Una variable local llamada `C`, `Q` o `I` rompe `C(x)` en la fórmula.
- **Nombres de columna arbitrarios en fórmulas:** usa `Q("col")`. Para tratar como categórica: `C(Q("col"))`, o convierte antes a `str`.
- **pandas 3:** `sum(1)` posicional está obsoleto (usa `axis=`); `.values` puede ser de solo lectura (usa `to_numpy(copy=True)`).
- **scikit-learn 1.9:**
  - `LassoCV(n_alphas=…)` ya no existe (usa `alphas=`);
  - `penalty` de `LogisticRegression` está obsoleto: usa el helper `_logistica` de `modelos/flexibles.py`.
- **`statsmodels` `_MultivariateOLS.mv_test()`** devuelve las claves `x0, x1…` en lugar de los nombres de columna.
- **Monte Carlo en tests:** semilla fija y tolerancias de unos 3 errores estándar. Si un test «casi» pasa, revisa la teoría antes de aflojar la tolerancia.
- **Coste:** nada O(n²) sin submuestrear (kernels, distancias, silhouette). Con n = 64 000 una matriz n×n son 30 GB.
- **Cambios en el código del usuario:** si ha editado un fichero, respeta su versión. `catalogo.json` y `conceptos/fichas_mias.json` son datos suyos.

## 6. Ideas pendientes

- **Código de consultoría: cerrado**; no hay nada que revisar de ahí.
- **Ampliar el catálogo:** Shorts de Very Normal y el temario real de Derivados, Fiscalidad, Seguridad Social y Derecho Bancario.
- **Volver a medir las propiedades en el PC del usuario** (`medir_propiedades.bat`).
- **Demos del visor** (`py/visor/demos.js` + `DEMOS` en `construir_visor.py`): hay 21 (distribuciones, MCMC, Markov, bandidos, PCA, K-means, VaR, diversificación, ruina, DiD, sobreajuste…) y faltan para ANOVA/diseño de experimentos, supervivencia avanzada, chain-ladder y otras ramas. `python`-free test: `py/tests/test_demos_js.py` las ejecuta con Node sin navegador.

## 7. Cómo pedirle cosas a Claude Code

- **«Añade `<función>` al árbol»:** se sigue el procedimiento de la sección 4 completo.
- **«¿Qué uso para X?»:** mira la tabla de `CLAUDE.md` y el grupo de alternativas en las fichas, y ordénalas con el perfil del proyecto (cartera grande, pocos datos, regulatorio…).
- **«Aprender lección: …»:** añade la regla a la sección de reglas de estilo de `CLAUDE.md`.
- **Conviene crear una skill «añadir-funcion-arbol»** con la sección 4, para que no se salte pasos.
