# Instalación del Árbol de la estadística

Funciona en **Windows 10/11**. Necesitas internet la primera vez (para descargar Python y las librerías) y unos **800 MB** libres.
No hace falta ser administrador.

## 1. Conseguir el instalador

Los instaladores están en la carpeta [`instaladores/`](instaladores/) de este repositorio. Hay dos:

| Fichero | Cuándo usarlo |
|---|---|
| `Arbol X.Y.Z - Instalador.bat` | **Primera vez.** Instala todo: Python (si no lo tienes), librerías, el programa y los accesos directos. |
| `Arbol X.Y.Z - Actualizar.bat` | Ya lo tienes instalado y quieres la versión nueva. Solo cambia el programa. |

**Opción A, sin GitHub Desktop:** abre el `.bat` en GitHub y pulsa el botón de descarga (flecha hacia abajo, «Download raw file»).

**Opción B, con GitHub Desktop:** *File → Clone repository*, elige este repositorio, y el `.bat` estará en la carpeta `instaladores`.
Para recibir versiones nuevas, pulsa **Fetch origin / Pull origin**.

## 2. Instalar

1. Haz doble clic en `Arbol X.Y.Z - Instalador.bat`.
2. Si Windows muestra «Windows protegió su PC», pulsa **Más información → Ejecutar de todas formas**
   (es un `.bat` descargado de internet; puedes abrirlo con el Bloc de notas antes para ver qué hace).
3. Elige dónde instalarlo:
   ```
   [1] Documentos\Árbol de la estadística   (recomendado)
   [2] Elegir una carpeta con el explorador de archivos
   [3] Escribir la ruta a mano
   [Q] Cancelar
   ```
   - Si eliges una carpeta con cosas dentro, crea una subcarpeta «Árbol de la estadística».
   - Evita carpetas sincronizadas (OneDrive, Dropbox): Python y las librerías son miles de ficheros y la sincronización los ralentiza.
   - No uses `Program Files` ni `Windows` (necesitan administrador).
4. Confirma con Enter y espera unos minutos. El instalador:
   - copia el programa,
   - busca Python 3.10 o superior y, si no lo encuentra, **lo descarga e instala dentro de la carpeta del Árbol** (no toca el Python del sistema),
   - instala las librerías (numpy, pandas, statsmodels, matplotlib…) y `pywebview`,
   - genera el visor y crea el acceso directo **«Árbol de la estadística»** en el Escritorio,
   - abre la aplicación al terminar.

## 3. Usarlo

- **Visor:** doble clic en el acceso directo del Escritorio (o en `abrir_arbol.bat` dentro de la carpeta).
- **Desde Python o notebooks:**
  ```python
  from arbol_estadistica.modelos import tabla_odds_ratios
  ```
- **Mapa de funciones:** `INDEX.md`. **Guías de teoría:** carpeta `teoria/`.

## 4. Actualizar

Descarga el nuevo `Arbol X.Y.Z - Actualizar.bat` (o haz *Pull* en GitHub Desktop) y ejecútalo. Encuentra tu instalación solo
(o te pide la carpeta), guarda la versión anterior en `anteriores/` y **conserva tu catálogo de conceptos y tus fichas**
(`conceptos/catalogo.json`, `conceptos/fichas_mias.json`); solo le añade los conceptos nuevos.

## 5. Si algo falla

| Problema | Qué hacer |
|---|---|
| No se abre el selector de carpetas | Elige la opción **[3]** y escribe la ruta. |
| «No he podido descargar Python» | Comprueba internet, o instala Python 3.10+ desde python.org y vuelve a ejecutar el instalador. |
| Una librería no se instala | Vuelve a ejecutar el instalador con internet: solo instala lo que falte. |
| El antivirus bloquea el `.bat` | Es un script de texto; añade una excepción o ejecútalo tras revisarlo con el Bloc de notas. |
| La app no abre ventana propia | Se abre con Edge/Chrome en modo aplicación (si `pywebview` no se instaló). |
| Quiero regenerar el visor | Doble clic en `regenerar_visor.bat`. |

## 6. Desinstalar

Borra la carpeta de instalación y el acceso directo del Escritorio. Si quieres quitar también el enlace de Python,
borra `arbol_estadistica.pth` de la carpeta `Lib\site-packages` de tu Python.

## Instalación manual (para desarrolladores)

Con Python 3.10+ y esta carpeta clonada:

```
pip install -r py/requirements.txt
pip install -e py
python py/construir_visor.py
```
