@echo off
rem Abre el arbol en su propia ventana (py\arbol_app.pyw). Usa el Python que comprobo el instalador
rem (python_arbol.txt); sin el, el Python de la carpeta; y si no hay ninguno, abre el visor en el navegador.
setlocal
set "APP=%~dp0py\arbol_app.pyw"
set "EXE="
if exist "%~dp0python_arbol.txt" set /p EXE=<"%~dp0python_arbol.txt"
if defined EXE if exist "%EXE%" goto lanzar
set "EXE=%~dp0python\pythonw.exe"
if exist "%EXE%" goto lanzar
start "" "%~dp0visor_arbol.html"
exit /b 0

:lanzar
rem Igual que el acceso directo del Escritorio: pythonw abre su ventana normal; solo un python.exe con consola se minimiza.
echo %EXE%| find /i "pythonw" >nul && (start "" "%EXE%" "%APP%") || (start "" /min "%EXE%" "%APP%")
exit /b 0
