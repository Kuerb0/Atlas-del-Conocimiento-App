# Apunta el acceso directo «Árbol de la estadística» del Escritorio a ESTA carpeta, en modo vivo (se recarga sola y sigue el foco).
#   powershell -ExecutionPolicy Bypass -File herramientas\acceso_vivo.ps1 on     # usa esta carpeta
#   powershell -ExecutionPolicy Bypass -File herramientas\acceso_vivo.ps1 off    # lo deja como estaba
# Lo original se guarda en %LOCALAPPDATA%\ArbolEstadistica\acceso_original.json.
param([Parameter(Mandatory)][ValidateSet('on', 'off')][string]$Modo)
$raiz = Split-Path -Parent $PSScriptRoot
$lnk = Get-ChildItem ([Environment]::GetFolderPath('Desktop')) -Filter '*.lnk' | Where-Object { $_.BaseName -like '*rbol de la estad*' } | Select-Object -First 1
if (-not $lnk) { Write-Host 'No encuentro el acceso directo del Arbol en el Escritorio.'; exit 1 }
$w = New-Object -ComObject WScript.Shell
$s = $w.CreateShortcut($lnk.FullName)
$copia = Join-Path $env:LOCALAPPDATA 'ArbolEstadistica\acceso_original.json'
if ($Modo -eq 'on') {
    if (-not (Test-Path -LiteralPath $copia)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $copia) | Out-Null
        @{ Target = $s.TargetPath; Args = $s.Arguments; Dir = $s.WorkingDirectory; Icon = $s.IconLocation } | ConvertTo-Json | Set-Content -LiteralPath $copia -Encoding UTF8
    }
    $s.Arguments = '"' + (Join-Path $raiz 'py\arbol_app.pyw') + '" --vivo'
    $s.WorkingDirectory = $raiz
    $s.IconLocation = (Join-Path $raiz 'assets\icono.ico') + ',0'
    $s.Save()
    Write-Host "Acceso directo -> $raiz (modo vivo)."
} else {
    if (-not (Test-Path -LiteralPath $copia)) { Write-Host 'No hay copia del acceso original.'; exit 1 }
    $o = Get-Content -LiteralPath $copia -Raw -Encoding UTF8 | ConvertFrom-Json
    $s.TargetPath = $o.Target; $s.Arguments = $o.Args; $s.WorkingDirectory = $o.Dir; $s.IconLocation = $o.Icon
    $s.Save(); Remove-Item -LiteralPath $copia -Force
    Write-Host 'Acceso directo restaurado.'
}
