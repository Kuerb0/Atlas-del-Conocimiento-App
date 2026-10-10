@echo off
rem Reentrena el LLM que clasifica (varios generos y subgeneros por obra). Uso:
rem   entrenar_llm.bat preparar                          crea el entorno aparte (.venv) con torch (CUDA), transformers, peft... (unos 5 GB)
rem   entrenar_llm.bat datos CORPUS                       construye train.jsonl y val.jsonl desde el corpus (CORPUS = carpeta con enes\corpus)
rem   entrenar_llm.bat entrenar CORPUS [MODELO] [NOMBRE]  entrena (por defecto Qwen/Qwen2.5-3B-Instruct) y guarda en CORPUS\enes\entrenamiento\NOMBRE
rem   entrenar_llm.bat exportar CORPUS NOMBRE             crea el modelo de Ollama "arbol-clasificador" con el adaptador entrenado
rem   entrenar_llm.bat panel CORPUS                       abre el panel con el progreso (http://localhost:8765)
rem ARBOL_VENV (opcional): carpeta de otro entorno ya preparado (la app lo pone sola al lanzar el entrenamiento desde la pestaña Entrenamiento).
rem Antes de entrenar, cierra lo que use la GPU (juegos, Wallpaper Engine, etc.): con 12 GB el modelo de 3B necesita unos 6 GB libres.
setlocal EnableExtensions
set "AQUI=%~dp0"
set "RAIZ=%AQUI%..\.."
set "VPY=%AQUI%.venv\Scripts\python.exe"
if defined ARBOL_VENV set "VPY=%ARBOL_VENV%\Scripts\python.exe"
set "ACCION=%~1"
set "CORPUS=%~2"

if /i "%ACCION%"=="preparar" goto preparar
if not exist "%VPY%" (
  echo Falta el entorno. Ejecuta primero: entrenar_llm.bat preparar
  exit /b 1
)
if /i "%ACCION%"=="datos" goto datos
if /i "%ACCION%"=="entrenar" goto entrenar
if /i "%ACCION%"=="exportar" goto exportar
if /i "%ACCION%"=="panel" goto panel
type "%~f0" | findstr /b "rem"
exit /b 1

:preparar
if not exist "%VPY%" (
  py -3 -m venv "%AQUI%.venv" || python -m venv "%AQUI%.venv" || exit /b 1
)
"%VPY%" -m pip install --upgrade pip || exit /b 1
"%VPY%" -m pip install torch --index-url https://download.pytorch.org/whl/cu124 || exit /b 1
"%VPY%" -m pip install -r "%AQUI%requisitos.txt" || exit /b 1
"%VPY%" -c "import torch; print('GPU:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
exit /b 0

:datos
if "%CORPUS%"=="" (echo Falta CORPUS & exit /b 1)
"%VPY%" "%AQUI%construir_datos.py" "%CORPUS%" %3 %4 %5 %6
exit /b %errorlevel%

:entrenar
if "%CORPUS%"=="" (echo Falta CORPUS & exit /b 1)
set "MODELO=%~3"
if "%MODELO%"=="" set "MODELO=Qwen/Qwen2.5-3B-Instruct"
set "NOMBRE=%~4"
if "%NOMBRE%"=="" set "NOMBRE=ft1"
set "SAL=%CORPUS%\enes\entrenamiento\%NOMBRE%"
set "INTENTOS=0"
:otro_intento
set "EXTRA="
if exist "%SAL%\adaptador\adapter_model.safetensors" if exist "%SAL%\estado.json" set "EXTRA=--reanudar"
"%VPY%" "%AQUI%entrenar.py" "%CORPUS%\enes\entrenamiento\datos" "%SAL%" --modelo "%MODELO%" %EXTRA% >> "%SAL%.log" 2>&1
if exist "%SAL%\resultado.json" exit /b 0
set /a INTENTOS+=1
if %INTENTOS% geq 20 (echo El entrenamiento se corto 20 veces: mira %SAL%.log & exit /b 1)
echo [vigilante] intento %INTENTOS% cortado; reanudo en 60 s (la GPU se comparte con otras aplicaciones)
ping -n 61 127.0.0.1 >nul
goto otro_intento

:exportar
if "%~3"=="" (echo Falta NOMBRE & exit /b 1)
"%VPY%" "%AQUI%exportar_ollama.py" "%CORPUS%\enes\entrenamiento\%~3" %4 %5 %6
exit /b %errorlevel%

:panel
if "%CORPUS%"=="" (echo Falta CORPUS & exit /b 1)
start "" http://localhost:8765
"%VPY%" "%RAIZ%\herramientas\panel_progreso.py" "%CORPUS%"
exit /b 0
