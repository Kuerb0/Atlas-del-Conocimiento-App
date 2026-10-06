@echo off
rem Indexa tus libros, finanzas y notas (carpetas de conocimiento\fuentes.json) para buscarlos desde el cerebro del visor.
rem La primera vez crea fuentes.json y lo abre para que pongas tus carpetas. Se puede repetir: solo reindexa lo nuevo.
setlocal EnableExtensions

set "PYCMD="
if exist "%~dp0python\python.exe" set PYCMD="%~dp0python\python.exe"
if not defined PYCMD (
  py -3 --version >nul 2>&1 && set "PYCMD=py -3"
)
if not defined PYCMD (
  python --version >nul 2>&1 && set "PYCMD=python"
)
if not defined PYCMD (
  echo No encuentro Python. Ejecuta primero el instalador de la carpeta "instaladores".
  pause
  exit /b 1
)

if not exist "%~dp0conocimiento" mkdir "%~dp0conocimiento"
if not exist "%~dp0conocimiento\fuentes.json" (
  copy "%~dp0py\conocimiento\fuentes.ejemplo.json" "%~dp0conocimiento\fuentes.json" >nul
  echo Se ha creado conocimiento\fuentes.json con carpetas de ejemplo. Pon las tuyas, guarda y cierra el Bloc de notas.
  notepad "%~dp0conocimiento\fuentes.json"
)

pushd "%~dp0py"
%PYCMD% -m pip install --disable-pip-version-check -q pypdf >nul 2>&1
%PYCMD% -m conocimiento indexar
if errorlevel 1 (
  echo.
  echo Error al indexar. Revisa el mensaje de arriba.
  popd
  pause
  exit /b 1
)
%PYCMD% -m conocimiento estado
popd
echo.
echo Listo. Abre el Arbol: el cerebro y el buscador ya incluyen estas carpetas.
pause
