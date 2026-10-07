# Motor de instalación / actualización del Árbol de la estadística (Windows PowerShell 5.1 o superior).
# Lo arranca el .bat (instalador o actualizador) con estas variables de entorno:
#   ARBOL_SELF    ruta del propio .bat (lleva empaquetados los ficheros tras la línea :::PSEND)
#   ARBOL_MODO    'instalar' o 'actualizar'
#   ARBOL_VERSION versión empaquetada
# Opcionales (pruebas / instalación desatendida):
#   ARBOL_DESTINO   carpeta de instalación sin preguntar
#   ARBOL_SIN_RED   '1' = no instalar librerías ni Python (solo ficheros y visor si ya hay Python)
#   ARBOL_SIN_ACCESOS '1' = no crear accesos directos, no registrar el paquete en Python, no recordar la ubicación ni abrir la app (para probar sin tocar tu equipo)
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

$Self = $env:ARBOL_SELF
$Modo = $env:ARBOL_MODO
$Version = $env:ARBOL_VERSION
$EnWindows = [Environment]::OSVersion.Platform -eq 'Win32NT'
$Nombre = [string][char]0xC1 + 'rbol de la estad' + [char]0xED + 'stica'
$Utf8 = New-Object Text.UTF8Encoding($false)
$DirRegistro = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'ArbolEstadistica' } else { Join-Path ([IO.Path]::GetTempPath()) 'ArbolEstadistica' }
$FicheroRegistro = Join-Path $DirRegistro 'ubicacion.txt'
# Que Python escriba en UTF-8 y PowerShell lo lea igual (rutas con tildes: Árbol, estadística).
$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = $Utf8 } catch { }
function Ruta { [IO.Path]::Combine([string[]]$args) }
$Estado = @{ py = $null }      # Python encontrado (lo usa el acceso directo)

function Titulo($t) { Write-Host ''; Write-Host ('=' * 64) -ForegroundColor DarkCyan; Write-Host "  $t" -ForegroundColor Cyan; Write-Host ('=' * 64) -ForegroundColor DarkCyan }
function Paso($t) { Write-Host ''; Write-Host $t -ForegroundColor Cyan }
function Info($t) { Write-Host "      $t" }
function Aviso($t) { Write-Host "      AVISO: $t" -ForegroundColor Yellow }
function Fallo($t) { Write-Host ''; Write-Host "ERROR: $t" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- carpeta
function Es-Instalacion($c) {
    if (-not $c) { return $false }
    return (Test-Path -LiteralPath (Ruta $c 'py' 'construir_visor.py')) -or (Test-Path -LiteralPath (Join-Path $c 'construir_visor.py'))
}

# Ventana de la consola (o de Windows Terminal): se minimiza mientras se muestra el selector de carpetas y se restaura después.
function Ventana-Consola {
    try {
        if (-not ('ArbolWin.Consola' -as [type])) {
            Add-Type -Namespace ArbolWin -Name Consola -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
[DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint f);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
'@
        }
        $c = [ArbolWin.Consola]::GetConsoleWindow()
        if ($c -eq [IntPtr]::Zero) { return [IntPtr]::Zero }
        $raiz = [ArbolWin.Consola]::GetAncestor($c, 3)           # GA_ROOTOWNER: con Windows Terminal da la ventana real
        if ($raiz -ne [IntPtr]::Zero) { return $raiz }
        return $c
    } catch { return [IntPtr]::Zero }
}

function Elegir-Con-Dialogo($inicial, $texto) {
    # El selector de carpetas de Windows. La consola se minimiza mientras está abierto (si no, tapa la ventana);
    # si falla se ofrece escribir la ruta a mano.
    Write-Host '  Se abre una ventana para elegir la carpeta (la consola se minimiza mientras tanto).' -ForegroundColor DarkCyan
    $duenio = $null
    $con = Ventana-Consola
    try {
        if ($con -ne [IntPtr]::Zero) { [void][ArbolWin.Consola]::ShowWindow($con, 6) }      # SW_MINIMIZE
        Add-Type -AssemblyName System.Windows.Forms
        [void][Windows.Forms.Application]::EnableVisualStyles()
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = $texto
        $dlg.ShowNewFolderButton = $true
        if ($inicial -and (Test-Path -LiteralPath $inicial)) { $dlg.SelectedPath = $inicial }
        # Ventana propietaria invisible pero activa y siempre encima: el selector sale al frente.
        $duenio = New-Object System.Windows.Forms.Form
        $duenio.TopMost = $true; $duenio.ShowInTaskbar = $false; $duenio.FormBorderStyle = 'None'
        $duenio.StartPosition = 'CenterScreen'; $duenio.Opacity = 0; $duenio.Size = New-Object System.Drawing.Size(1, 1)
        $duenio.Show(); $duenio.Activate()
        $r = $dlg.ShowDialog($duenio)
        if ($r -eq [System.Windows.Forms.DialogResult]::OK -and $dlg.SelectedPath) { return $dlg.SelectedPath }
        return $null
    } catch {
        if ($con -ne [IntPtr]::Zero) { [void][ArbolWin.Consola]::ShowWindow($con, 9); [void][ArbolWin.Consola]::SetForegroundWindow($con); $con = [IntPtr]::Zero }
        Aviso "No he podido abrir el selector de carpetas ($($_.Exception.Message))."
        $p = Read-Host '      Escribe la ruta completa de la carpeta'
        if ($p) { return $p.Trim('"', ' ') }
        return $null
    } finally {
        if ($duenio) { try { $duenio.Close(); $duenio.Dispose() } catch { } }
        if ($con -ne [IntPtr]::Zero) { [void][ArbolWin.Consola]::ShowWindow($con, 9); [void][ArbolWin.Consola]::SetForegroundWindow($con) }   # SW_RESTORE
    }
}

function Normalizar-Ruta($p) {
    if (-not $p) { return $null }
    $p = [Environment]::ExpandEnvironmentVariables(([string]$p).Trim().Trim('"', "'"))
    if ($p -match '^~') { $p = $p -replace '^~', [Environment]::GetFolderPath('UserProfile') }
    if (-not $p) { return $null }
    try { return [IO.Path]::GetFullPath($p) } catch { return $null }
}

function Preguntar-Si($texto) {
    $r = Read-Host "  $texto [s/N]"
    return ($r -match '^\s*[sSyY]')
}

# Comprueba la carpeta elegida; devuelve la carpeta definitiva o $null si no sirve / el usuario se echa atrás.
function Revisar-Destino($ruta) {
    if (-not $ruta) { Write-Host '  Esa ruta no es válida.' -ForegroundColor Yellow; return $null }
    $raiz = [IO.Path]::GetPathRoot($ruta)
    if (-not $raiz -or -not (Test-Path -LiteralPath $raiz)) { Write-Host "  La unidad $raiz no existe." -ForegroundColor Yellow; return $null }
    foreach ($prot in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:windir)) {
        if ($prot -and $ruta.StartsWith($prot, [StringComparison]::OrdinalIgnoreCase)) {
            Write-Host '  Esa ubicación exige permisos de administrador. Elige una carpeta tuya (Documentos, el disco D:...).' -ForegroundColor Yellow; return $null
        }
    }
    if (Test-Path -LiteralPath $ruta -PathType Leaf) { Write-Host '  Esa ruta es un archivo, no una carpeta.' -ForegroundColor Yellow; return $null }
    if (Test-Path -LiteralPath $ruta) {
        $hayAlgo = Get-ChildItem -LiteralPath $ruta -Force -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hayAlgo -and -not (Es-Instalacion $ruta)) {
            $ruta = Join-Path $ruta $Nombre
            Write-Host "  La carpeta no está vacía: lo instalo dentro de una subcarpeta ($Nombre)." -ForegroundColor DarkYellow
        }
    }
    if (Es-Instalacion $ruta) {
        $v = '?'; $fv = Ruta $ruta 'py' 'VERSION.txt'
        if (Test-Path -LiteralPath $fv) { $v = (Get-Content -LiteralPath $fv -Encoding UTF8 | Select-Object -First 1).Trim() }
        Write-Host "  Ya hay una instalación aquí (versión $v): se sustituye el programa y se conservan tus datos (catálogo y fichas)." -ForegroundColor DarkYellow
    }
    if ($ruta -match 'OneDrive|Dropbox|Google Drive|iCloud') {
        Write-Host '  AVISO: esa carpeta se sincroniza en la nube. Python y las librerías son miles de ficheros: la sincronización' -ForegroundColor Yellow
        Write-Host '         irá lenta y puede bloquear ficheros. Es mejor una carpeta local (p. ej. C:\Arbol o Documentos).' -ForegroundColor Yellow
        if (-not (Preguntar-Si '¿Instalar ahí igualmente?')) { return $null }
    }
    try {
        $unidad = New-Object IO.DriveInfo($raiz)
        if ($unidad.IsReady -and $unidad.AvailableFreeSpace -lt 1GB) {
            Write-Host ('  AVISO: solo quedan {0:N0} MB libres en {1} y se necesitan unos 800 MB (Python + librerías).' -f ($unidad.AvailableFreeSpace / 1MB), $raiz) -ForegroundColor Yellow
            if (-not (Preguntar-Si '¿Seguir?')) { return $null }
        }
    } catch { }
    return $ruta
}

function Elegir-Destino-Instalacion {
    if ($env:ARBOL_DESTINO) { return $env:ARBOL_DESTINO }
    $aqui = Split-Path -Parent $Self
    $porDefecto = Join-Path ([Environment]::GetFolderPath('MyDocuments')) $Nombre
    if (Es-Instalacion $aqui) { $porDefecto = $aqui }
    elseif ((Split-Path -Leaf $aqui) -eq 'instaladores' -and (Es-Instalacion (Split-Path -Parent $aqui))) { $porDefecto = Split-Path -Parent $aqui }
    $intentos = 0
    while ($intentos -lt 12) {
        $intentos++
        Write-Host ''
        Write-Host '  ¿Dónde quieres instalarlo?' -ForegroundColor Cyan
        Write-Host "    [1] $porDefecto   (recomendado)"
        Write-Host '    [2] Elegir una carpeta con el explorador de archivos...'
        Write-Host '    [3] Escribir la ruta a mano'
        Write-Host '    [Q] Cancelar'
        $op = Read-Host '  Opción (Enter = 1)'
        if ($op -match '^\s*[qQ]') { return $null }
        $cand = $null
        if ($op -match '^\s*2') {
            $cand = Elegir-Con-Dialogo ([Environment]::GetFolderPath('MyDocuments')) 'Elige la carpeta donde instalar el Árbol de la estadística (si no está vacía, se creará dentro una subcarpeta)'
            if (-not $cand) { Write-Host '  No has elegido ninguna carpeta.'; continue }
        } elseif ($op -match '^\s*3') {
            $cand = Read-Host '  Escribe la ruta completa (p. ej. D:\Estadistica\Arbol)'
            if (-not $cand) { continue }
        } elseif ($op -match '^\s*(1)?\s*$') { $cand = $porDefecto }
        else { Write-Host '  Opción no válida.' -ForegroundColor Yellow; continue }
        $fin = Revisar-Destino (Normalizar-Ruta $cand)
        if (-not $fin) { continue }
        Write-Host ''
        Write-Host "  Se instalará en:  $fin" -ForegroundColor Green
        $c = Read-Host '  [Enter] continuar   [R] elegir otra   [Q] cancelar'
        if ($c -match '^\s*[qQ]') { return $null }
        if ($c -match '^\s*[rR]') { continue }
        return $fin
    }
    return $null
}

function Buscar-Instalacion {
    if ($env:ARBOL_DESTINO) { return $env:ARBOL_DESTINO }
    $aqui = Split-Path -Parent $Self
    $cands = @($aqui, (Split-Path -Parent $aqui))
    if (Test-Path -LiteralPath $FicheroRegistro) { $cands += (Get-Content -LiteralPath $FicheroRegistro -Encoding UTF8 | Select-Object -First 1) }
    $cands += (Join-Path ([Environment]::GetFolderPath('MyDocuments')) $Nombre)
    foreach ($c in $cands) { if (Es-Instalacion $c) { return $c } }
    Write-Host ''
    Write-Host '  No encuentro una instalación del Árbol junto a este actualizador.'
    Write-Host '  Elige la carpeta donde lo tienes instalado (la que contiene py, conceptos, teoria...).'
    $c = Elegir-Con-Dialogo ([Environment]::GetFolderPath('MyDocuments')) 'Elige la carpeta donde está instalado el Árbol de la estadística'
    if ($c -and (Es-Instalacion $c)) { return $c }
    if ($c) { Write-Host "  Esa carpeta no parece una instalación del Árbol: $c" }
    return $null
}

# ---------------------------------------------------------------- ficheros empaquetados
function Extraer($dest) {
    $lineas = [IO.File]::ReadAllLines($Self, $Utf8)
    $i = [Array]::IndexOf($lineas, ':::PSEND') + 1
    $n = 0; $omitidos = 0
    while ($i -lt $lineas.Length) {
        $l = $lineas[$i]
        if (-not $l.StartsWith(':::BEGIN ')) { $i++; continue }
        $partes = $l.Substring(9).Trim().Split('|')
        $rel = $partes[0]; $modo = $partes[1]
        $j = $i + 1
        $buf = New-Object System.Collections.Generic.List[string]
        while ($j -lt $lineas.Length -and -not $lineas[$j].StartsWith(':::END')) { $buf.Add($lineas[$j]); $j++ }
        $destino = Join-Path $dest ($rel.Replace('/', [IO.Path]::DirectorySeparatorChar))
        if ($modo -eq 'seed' -and (Test-Path -LiteralPath $destino)) { $omitidos++; $i = $j + 1; continue }
        $carpeta = Split-Path -Parent $destino
        if (-not (Test-Path -LiteralPath $carpeta)) { New-Item -ItemType Directory -Path $carpeta -Force | Out-Null }
        if ($modo -eq 'b64') { [IO.File]::WriteAllBytes($destino, [Convert]::FromBase64String(($buf -join ''))) }
        else { [IO.File]::WriteAllText($destino, (($buf -join "`r`n") + "`r`n"), $Utf8) }
        $n++; $i = $j + 1
    }
    return @($n, $omitidos)
}

# ---------------------------------------------------------------- Python
function Probar-Python($exe, $extra) {
    try {
        $out = @(& $exe @extra -c 'import sys; print(sys.version_info >= (3, 10)); print(sys.executable)' 2>$null)
        if ($LASTEXITCODE -eq 0 -and $out.Count -ge 2 -and $out[0].Trim() -eq 'True') {
            $real = $out[-1].Trim()                                    # la ruta real del intérprete (también con el lanzador «py»)
            if ($real -and (Test-Path -LiteralPath $real)) { return $real }
            if (@($extra).Count -eq 0) { return $exe }
        }
    } catch { }
    return $null
}

function Buscar-Python($dest) {
    $cands = New-Object System.Collections.Generic.List[object]
    foreach ($p in @((Ruta $dest 'python' 'python.exe'), (Ruta $dest 'python' 'bin' 'python3'))) { if (Test-Path -LiteralPath $p) { $cands.Add(@($p, @())) } }
    foreach ($cmd in @('py', 'python', 'python3')) {
        Get-Command $cmd -All -ErrorAction SilentlyContinue | Where-Object { $_.CommandType -eq 'Application' -and $_.Source -notlike '*WindowsApps*' } |
            ForEach-Object { if ($cmd -eq 'py') { $cands.Add(@($_.Source, @('-3'))) } else { $cands.Add(@($_.Source, @())) } }
    }
    foreach ($patron in @("$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe")) {
        if ($env:LOCALAPPDATA) { Get-ChildItem -Path $patron -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object { $cands.Add(@($_.FullName, @())) } }
    }
    foreach ($pasada in @($false, $true)) {                 # 1.ª pasada: todo menos Descargas; 2.ª: lo de Descargas
        foreach ($c in $cands) {
            if (([string]$c[0] -like '*\Downloads\*') -ne $pasada) { continue }
            $r = Probar-Python $c[0] $c[1]; if ($r) { return $r }
        }
    }
    return $null
}

function Descargar-Python($fichero) {
    $base = 'https://www.python.org/ftp/python/'
    $versiones = @()
    try {
        $html = (Invoke-WebRequest -UseBasicParsing -Uri $base -TimeoutSec 30).Content
        $versiones = @([regex]::Matches($html, '3\.12\.\d+(?=/)') | ForEach-Object { $_.Value } | Sort-Object { [version]$_ } -Descending -Unique)
    } catch { }
    $versiones = @($versiones) + @('3.12.10', '3.12.8', '3.12.7', '3.13.9', '3.13.5') | Select-Object -Unique
    foreach ($v in $versiones) {
        try {
            Info "Descargando Python $v ..."
            Invoke-WebRequest -UseBasicParsing -Uri "$base$v/python-$v-amd64.exe" -OutFile $fichero -TimeoutSec 900
            if ((Test-Path -LiteralPath $fichero) -and ((Get-Item -LiteralPath $fichero).Length -gt 5MB)) { return $v }
        } catch { }
        if (Test-Path -LiteralPath $fichero) { Remove-Item -LiteralPath $fichero -Force }
    }
    return $null
}

function Instalar-Python($dest) {
    if (-not $EnWindows) { return $null }
    $fichero = Join-Path ([IO.Path]::GetTempPath()) ('python_arbol_' + [guid]::NewGuid().ToString('N') + '.exe')
    $v = Descargar-Python $fichero
    if (-not $v) { Aviso 'No he podido descargar Python (¿hay internet?).'; return $null }
    $destPy = Join-Path $dest 'python'
    Info "Instalando Python $v en $destPy (solo para tu usuario, sin permisos de administrador)..."
    $argumentos = @('/quiet', 'InstallAllUsers=0', ('TargetDir="' + $destPy + '"'), 'Include_launcher=0', 'InstallLauncherAllUsers=0',
              'PrependPath=0', 'Shortcuts=0', 'AssociateFiles=0', 'Include_test=0', 'Include_doc=0', 'Include_pip=1', 'Include_tcltk=1')
    $p = Start-Process -FilePath $fichero -ArgumentList $argumentos -Wait -PassThru
    Remove-Item -LiteralPath $fichero -Force -ErrorAction SilentlyContinue
    if ($p.ExitCode -ne 0) { Aviso "El instalador de Python terminó con código $($p.ExitCode)." }
    return (Buscar-Python $dest)
}

function Enlazar-Paquete($py, $dest) {
    # En vez de 'pip install -e' (necesita internet y setuptools), un .pth que apunta a la carpeta py.
    & $py -m pip uninstall -y -q arbol-estadistica 2>$null | Out-Null
    $rutaPy = Join-Path $dest 'py'
    $purelib = (& $py -c "import sysconfig; print(sysconfig.get_paths()['purelib'])" 2>$null | Select-Object -Last 1)
    $usuario = (& $py -m site --user-site 2>$null | Select-Object -Last 1)
    $enc = if ($EnWindows) { [Text.Encoding]::Default } else { $Utf8 }   # Python < 3.13 lee los .pth con la codificación ANSI
    foreach ($dir in @($purelib, $usuario)) {
        if (-not $dir) { continue }
        try {
            if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force -ErrorAction Stop | Out-Null }
            [IO.File]::WriteAllText((Join-Path $dir 'arbol_estadistica.pth'), $rutaPy + "`r`n", $enc)
            return $true
        } catch { }
    }
    return $false
}

function Elegir-Lanzador {
    # Devuelve @(ejecutable, necesitaConsola). Prefiere el pythonw.exe real de la instalación de Python
    # (sys.base_prefix); un pythonw.exe suelto o de un entorno virtual puede apuntar a algo que ya no existe
    # («Python Launcher: Unable to create process...»), así que solo se usa si el fichero está donde debe.
    if (-not $Estado.py) { return $null }
    $q = @(& $Estado.py -c "import sys,os; p=os.path.join(sys.base_prefix,'pythonw.exe'); print(p if os.path.isfile(p) else '')" 2>$null)
    $pyw = if ($q.Count) { ([string]$q[-1]).Trim() } else { '' }
    if ($pyw -and (Test-Path -LiteralPath $pyw)) { return @($pyw, $false) }
    return @($Estado.py, $true)                  # sin pythonw: python.exe con la ventana minimizada
}

function Crear-Accesos($dest) {
    if (-not $EnWindows) { return }
    try {
        $w = New-Object -ComObject WScript.Shell
        $esc = $w.SpecialFolders('Desktop')
        $ico = Ruta $dest 'assets' 'icono.ico'
        $app = Ruta $dest 'py' 'arbol_app.pyw'
        $fichLanz = Join-Path $dest 'python_arbol.txt'      # lo lee abrir_arbol.bat
        $l = Elegir-Lanzador
        # Un único acceso directo: la app (py\arbol_app.pyw, ventana propia con pywebview).
        $lnk = Join-Path $esc ($Nombre + '.lnk')
        Remove-Item -LiteralPath $lnk -Force -ErrorAction SilentlyContinue     # se recrea entero: así se cambia también el icono de una versión anterior
        $s = $w.CreateShortcut($lnk)
        if ($l) {
            $s.TargetPath = $l[0]; $s.Arguments = '"' + $app + '"'
            if ($l[1]) { $s.WindowStyle = 7 }
            [IO.File]::WriteAllText($fichLanz, $l[0], $Utf8)
        } else {
            $s.TargetPath = (Ruta $dest 'abrir_arbol.bat'); $s.WindowStyle = 7
            Remove-Item -LiteralPath $fichLanz -Force -ErrorAction SilentlyContinue
        }
        $s.WorkingDirectory = $dest
        if (Test-Path -LiteralPath $ico) { $s.IconLocation = $ico + ',0' }
        $s.Description = 'Árbol de la estadística'; $s.Save()
        try { Start-Process -FilePath (Join-Path $env:windir 'System32\ie4uinit.exe') -ArgumentList '-show' -WindowStyle Hidden -Wait } catch { }   # refresca la caché de iconos de Windows
        # El segundo acceso («- regenerar») ya no se crea; si lo dejó una versión anterior, se quita.
        $viejo = Join-Path $esc ($Nombre + ' - regenerar.lnk')
        if (Test-Path -LiteralPath $viejo) { Remove-Item -LiteralPath $viejo -Force -ErrorAction SilentlyContinue; Info 'Quitado el acceso «regenerar» del Escritorio (ya no hace falta; sigue regenerar_visor.bat en la carpeta).' }
        Info "Acceso directo «$Nombre» en el Escritorio -> $(if ($l) { $l[0] } else { 'abrir_arbol.bat' })."
    } catch { Aviso "No se pudieron crear los accesos directos: $($_.Exception.Message)" }
}

function Abrir-App($dest) {
    # Abre la app EXACTAMENTE como el acceso directo del Escritorio (mismo programa, mismos argumentos, misma carpeta, misma ventana): se lanza el propio acceso.
    # Así lo que se abre al terminar el instalador/actualizador y lo que se abre con el icono es siempre lo mismo.
    $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) ($Nombre + '.lnk')
    if (Test-Path -LiteralPath $lnk) { Start-Process -FilePath $lnk -WorkingDirectory $dest }
    else { Start-Process -FilePath (Ruta $dest 'abrir_arbol.bat') -WindowStyle Hidden -WorkingDirectory $dest }
}


# ---------------------------------------------------------------- IA local: embeddings (fastembed) + LLM (Ollama), con barras de progreso
$Bloque = [string][char]0x2588; $Claro = [string][char]0x2591; $Ok = [string][char]0x2713; $No = [string][char]0x2717
$ModeloLLM = 'qwen2.5:3b'
$ModeloEmb = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'

function Barra($pct, $texto) {
    if ($pct -lt 0) { $pct = 0 }; if ($pct -gt 100) { $pct = 100 }
    $n = [int](30 * $pct / 100)
    $linea = ('      ' + ($Bloque * $n) + ($Claro * (30 - $n)) + (' {0,3}%  ' -f [int]$pct) + $texto)
    try { [Console]::Write("`r" + $linea.PadRight(110)) } catch { }
}
function Barra-Fin { try { [Console]::WriteLine() } catch { } }

function Estado-Linea($bien, $texto, $detalle) {                  # ojo: PowerShell no distingue mayúsculas, un parámetro $ok taparía el símbolo $Ok
    if ($bien) { Write-Host ("      $Ok $texto" + $(if ($detalle) { "  ($detalle)" } else { '' })) -ForegroundColor Green }
    else { Write-Host ("      $No $texto" + $(if ($detalle) { "  ($detalle)" } else { '' })) -ForegroundColor Yellow }
}

function Tamano-Remoto($url) {
    $n = [int64]0
    try { foreach ($l in @(& curl.exe -sIL $url 2>$null)) { if ($l -match '^(?i)content-length:\s*(\d+)') { $n = [int64]$Matches[1] } } } catch { }
    return $n
}

# Descarga con barra de progreso, velocidad y reanudación (curl -C -): si se corta, al repetir sigue por donde iba.
function Descargar-Con-Barra($url, $fichero, $etiqueta) {
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) {
        try { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $fichero -TimeoutSec 3600; return (Test-Path -LiteralPath $fichero) } catch { return $false }
    }
    $total = Tamano-Remoto $url
    $p = Start-Process -FilePath $curl.Source -ArgumentList @('-L', '-C', '-', '--fail', '--retry', '5', '-s', '-o', ('"' + $fichero + '"'), ('"' + $url + '"')) -PassThru -WindowStyle Hidden
    $null = $p.Handle
    $ultimo = [int64]0; $tUlt = Get-Date; $vel = 0.0
    while (-not $p.HasExited) {
        Start-Sleep -Milliseconds 400
        $tam = if (Test-Path -LiteralPath $fichero) { (Get-Item -LiteralPath $fichero).Length } else { 0 }
        $dt = ((Get-Date) - $tUlt).TotalSeconds
        if ($dt -ge 1) { $vel = ($tam - $ultimo) / $dt; $ultimo = $tam; $tUlt = Get-Date }
        $pct = if ($total -gt 0) { 100.0 * $tam / $total } else { 0 }
        Barra $pct ('{0}  {1:N0} de {2:N0} MB  {3:N1} MB/s' -f $etiqueta, ($tam / 1MB), ($total / 1MB), ($vel / 1MB))
    }
    $p.WaitForExit()
    $tam = if (Test-Path -LiteralPath $fichero) { (Get-Item -LiteralPath $fichero).Length } else { 0 }
    $bien = ($p.ExitCode -eq 0) -and ($total -le 0 -or $tam -ge $total)
    if ($bien) { Barra 100 ('{0}  {1:N0} MB' -f $etiqueta, ($tam / 1MB)) }
    Barra-Fin
    return $bien
}

# Espera a que termine un proceso mostrando una barra que avanza con el tiempo (no se sabe cuánto falta) y, si se indica, el tamaño de una carpeta.
function Esperar-Con-Barra($proceso, $texto, $carpeta, $esperadoMB) {
    $giro = '|', '/', '-', '\'
    $i = 0
    while (-not $proceso.HasExited) {
        $extra = ''; $pct = -1
        if ($carpeta -and (Test-Path -LiteralPath $carpeta) -and $esperadoMB -gt 0) {
            $mb = ((Get-ChildItem -LiteralPath $carpeta -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum) / 1MB
            $pct = 100.0 * $mb / $esperadoMB; $extra = ('  {0:N0} de ~{1:N0} MB' -f $mb, $esperadoMB)
        }
        if ($pct -ge 0) { Barra $pct ($texto + $extra) }
        else { try { [Console]::Write("`r      " + $giro[$i % 4] + ' ' + $texto + '   ') } catch { } }
        $i++; Start-Sleep -Milliseconds 400
    }
    $proceso.WaitForExit()
    if ($carpeta -and $esperadoMB -gt 0) { Barra 100 $texto }
    Barra-Fin
}

function Buscar-Ollama {
    $c = Get-Command ollama -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $p = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path -LiteralPath $p) { return $p }
    return $null
}
function Ollama-Responde { try { Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -TimeoutSec 8 | Out-Null; return $true } catch { return $false } }      # la primera llamada de PowerShell tarda 2-3 s: con 2 s de margen daba falsos negativos
function Arrancar-Ollama($exe) {
    if (Ollama-Responde) { return $true }
    # El servidor es «ollama serve». La aplicación de la bandeja a veces no lo levanta (queda «server not ready»), así que si en 8 s no responde se arranca directamente.
    try { Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput (Join-Path ([IO.Path]::GetTempPath()) 'ollama_serve_out.txt') -RedirectStandardError (Join-Path ([IO.Path]::GetTempPath()) 'ollama_serve_err.txt') } catch { }      # con la salida redirigida arranca; oculta y sin redirigir se queda colgado
    for ($i = 0; $i -lt 40; $i++) { if (Ollama-Responde) { return $true }; Start-Sleep -Seconds 1 }
    return $false
}
function Tiene-Modelo-Ollama($modelo) {
    try { $r = Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -TimeoutSec 8; return [bool]($r.models | Where-Object { $_.name -eq $modelo }) } catch { return $false }
}
function Tiene-Modelo-Embeddings($dest) {
    $m = Ruta $dest 'conocimiento' 'modelos'
    if (-not (Test-Path -LiteralPath $m)) { return $false }
    $mb = ((Get-ChildItem -LiteralPath $m -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match 'MiniLM' } | Measure-Object Length -Sum).Sum) / 1MB
    return ($mb -gt 150)
}

function Instalar-Ollama {
    $url = 'https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe'
    $f = Join-Path ([IO.Path]::GetTempPath()) 'OllamaSetup.exe'
    Info 'Descargando el instalador oficial de Ollama (github.com/ollama/ollama, ~1,6 GB; si se corta, repite y sigue donde iba)...'
    if (-not (Descargar-Con-Barra $url $f 'Ollama')) { Aviso 'No se pudo descargar Ollama (¿internet?). Repite esto cuando tengas conexión.'; return $null }
    $firma = Get-AuthenticodeSignature -LiteralPath $f
    if ($firma.Status -ne 'Valid' -or ([string]$firma.SignerCertificate.Subject) -notmatch 'Ollama') {
        Aviso 'La firma digital del instalador no es la de Ollama Inc.: no lo ejecuto.'
        Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue
        return $null
    }
    Info 'Firma digital verificada (Ollama Inc.). Instalando (solo para tu usuario)...'
    $p = Start-Process -FilePath $f -ArgumentList @('/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES') -PassThru
    $null = $p.Handle
    Esperar-Con-Barra $p 'Instalando Ollama' $null 0
    Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue
    return (Buscar-Ollama)
}

# Comprueba qué hay, muestra una tabla ✓/✗ con lo que ya está instalado y descarga solo lo que falta.
function Preparar-IA($py, $dest) {
    Paso '[IA local] Comprobando qué hay instalado (reglas + parecido con embeddings + LLM con Ollama)...'
    $tieneFE = $false
    try { & $py -c 'import fastembed' 2>$null; $tieneFE = ($LASTEXITCODE -eq 0) } catch { }
    $tieneEmb = Tiene-Modelo-Embeddings $dest
    $exe = Buscar-Ollama
    $respondia = if ($exe) { Arrancar-Ollama $exe } else { $false }          # si está instalado pero apagado, se arranca para poder mirar qué modelos tiene
    $tieneLLM = if ($respondia) { Tiene-Modelo-Ollama $ModeloLLM } else { $false }
    Estado-Linea $tieneFE 'fastembed (embeddings locales)' $(if ($tieneFE) { 'ya instalado' } else { 'falta, ~60 MB' })
    Estado-Linea $tieneEmb 'modelo de parecido MiniLM' $(if ($tieneEmb) { 'ya descargado' } else { 'falta, ~240 MB' })
    Estado-Linea ([bool]$exe) 'Ollama' $(if ($exe) { $exe } else { 'falta, ~1,6 GB' })
    Estado-Linea $tieneLLM "modelo $ModeloLLM" $(if ($tieneLLM) { 'ya descargado' } elseif ($exe -and -not $respondia) { 'Ollama no arranca: ábrelo y repite' } else { 'falta, ~1,9 GB' })
    $faltaAlgo = (-not $tieneFE) -or (-not $tieneEmb) -or (-not $exe) -or ($exe -and -not $tieneLLM)
    if (-not $faltaAlgo) { Info 'Todo al día: no hay nada que descargar.'; return }
    if (-not $env:ARBOL_DESTINO) {
        $r = Read-Host '  ¿Instalar lo que falta? Es opcional: sin ello el Árbol clasifica con reglas, pero peor [S/n]'
        if ($r -match '^\s*[nN]') { Info 'Omitido. Puedes repetirlo cuando quieras ejecutando de nuevo este archivo.'; return }
    }
    if (-not $tieneFE) {
        Paso '[IA local] Instalando fastembed...'
        & $py -m pip install --disable-pip-version-check --no-warn-script-location -q fastembed | Out-Host
        $tieneFE = ($LASTEXITCODE -eq 0)
        if (-not $tieneFE) { Aviso 'fastembed no se instaló (¿internet o versión de Python?): el Árbol seguirá con reglas.' }
    }
    if ($tieneFE -and -not $tieneEmb) {
        Paso '[IA local] Descargando el modelo de parecido (MiniLM, 240 MB)...'
        $env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
        $p = Start-Process -FilePath $py -ArgumentList @('-m', 'conocimiento', 'modelos') -WorkingDirectory (Ruta $dest 'py') -PassThru -WindowStyle Hidden
        $null = $p.Handle
        Esperar-Con-Barra $p 'Modelo MiniLM' (Ruta $dest 'conocimiento' 'modelos') 240
        if ($p.ExitCode -ne 0) { Aviso 'El modelo de parecido no se descargó del todo; se reintentará la próxima vez que se use.' }
    }
    if (-not $exe) {
        Paso '[IA local] Instalando Ollama (el motor del LLM local)...'
        $exe = Instalar-Ollama
        if (-not $exe) { return }
        Info "Ollama instalado en $exe"
    }
    Paso '[IA local] Arrancando Ollama...'
    if (-not (Arrancar-Ollama $exe)) { Aviso 'Ollama no respondió. Ábrelo desde el menú Inicio y repite esto para bajar el modelo.'; return }
    if (-not (Tiene-Modelo-Ollama $ModeloLLM)) {
        Paso "[IA local] Descargando el modelo $ModeloLLM (1,9 GB; Ollama muestra su propio progreso)..."
        & $exe pull $ModeloLLM | Out-Host
        if (Tiene-Modelo-Ollama $ModeloLLM) { Estado-Linea $true "modelo $ModeloLLM" 'listo' } else { Aviso "El modelo $ModeloLLM no se descargó. Repite esto con conexión." }
    } else { Estado-Linea $true "modelo $ModeloLLM" 'ya descargado' }
}

# ---------------------------------------------------------------- flujo común tras copiar los ficheros
function Preparar-Python-Y-Visor($dest) {
    Paso '[Python] Buscando Python 3.10 o superior...'
    $py = Buscar-Python $dest
    if (-not $py -and $env:ARBOL_SIN_RED -ne '1') {
        Info 'No hay Python en este equipo: lo descargo e instalo dentro de la carpeta del Árbol.'
        $py = Instalar-Python $dest
    }
    if (-not $py) {
        Aviso 'Sin Python no puedo instalar las librerías ni generar el visor. Los ficheros sí están copiados.'
        Aviso 'Instala Python desde https://www.python.org (marca "Add python.exe to PATH") y vuelve a ejecutar esto.'
        return $false
    }
    Info "Python: $py"
    $Estado.py = $py

    if ($env:ARBOL_SIN_RED -ne '1') {
        Paso '[Librerías] Instalando lo que falte (numpy, pandas, statsmodels, matplotlib...). Puede tardar unos minutos.'
        & $py -m pip install --disable-pip-version-check --no-warn-script-location -q -r (Ruta $dest 'py' 'requirements.txt') | Out-Host
        if ($LASTEXITCODE -ne 0) { Aviso 'Algunas librerías no se instalaron (¿internet?). Vuelve a ejecutar esto cuando tengas conexión.' }
        if ($EnWindows) {
            Paso '[Ventana] Instalando pywebview (abre el árbol en su propia ventana, como una app)...'
            & $py -m pip install --disable-pip-version-check --no-warn-script-location -q 'pywebview>=5' | Out-Host
            if ($LASTEXITCODE -ne 0) { Aviso 'pywebview no se instaló: el árbol se abrirá con Edge/Chrome en modo aplicación.' }
        }
    }

    Paso '[Paquete] Haciendo que «import arbol_estadistica» funcione desde cualquier notebook...'
    if ($env:ARBOL_SIN_ACCESOS -eq '1') { Info 'Omitido (modo prueba: no se toca el Python del equipo).' }
    elseif (Enlazar-Paquete $py $dest) { Info 'Hecho.' } else { Aviso 'No pude registrar el paquete; en tus notebooks usa sys.path.insert(0, r"<carpeta>\py").' }
    $prueba = & $py -c 'import arbol_estadistica, arbol_estadistica.graficos; print(arbol_estadistica.__version__)' 2>&1
    if ($LASTEXITCODE -eq 0) { Info "Comprobado: arbol_estadistica $($prueba | Select-Object -Last 1)" }
    else { Aviso ('La importación de prueba falló: ' + (($prueba | Select-Object -Last 3) -join ' | ')) }

    if ($EnWindows -and $env:ARBOL_SIN_RED -ne '1' -and $env:ARBOL_SIN_IA -ne '1') { Preparar-IA $py $dest }

    Paso '[Catálogo] Añadiendo los conceptos nuevos sin tocar los tuyos...'
    & $py (Ruta $dest 'py' 'fusionar_catalogo.py') | Out-Host
    Paso '[Visor] Generando visor_arbol.html...'
    & $py (Ruta $dest 'py' 'construir_visor.py') | Out-Host
    if ($LASTEXITCODE -ne 0) { Aviso 'No se pudo generar el visor (mira el mensaje de arriba).'; return $false }
    return $true
}

function Registrar($dest) {
    try {
        if (-not (Test-Path -LiteralPath $DirRegistro)) { New-Item -ItemType Directory -Path $DirRegistro -Force | Out-Null }
        [IO.File]::WriteAllText($FicheroRegistro, $dest, $Utf8)
    } catch { }
}

# ================================================================ INSTALAR
if ($Modo -eq 'instalar') {
    Titulo "ÁRBOL DE LA ESTADÍSTICA $Version - instalador"
    Write-Host '  Copia el programa en la carpeta que elijas, instala Python si no lo tienes'
    Write-Host '  (dentro de esa carpeta, sin permisos de administrador), las librerías,'
    Write-Host '  genera el visor y crea accesos directos en el Escritorio.'
    $dest = Elegir-Destino-Instalacion
    if (-not $dest) { Write-Host ''; Write-Host '  Cancelado. No se ha tocado nada.'; exit 2 }
    try { New-Item -ItemType Directory -Path $dest -Force -ErrorAction Stop | Out-Null } catch { Fallo "No puedo crear la carpeta $dest" }
    $pruebaEsc = Join-Path $dest '.prueba_escritura'
    try { [IO.File]::WriteAllText($pruebaEsc, 'ok'); Remove-Item -LiteralPath $pruebaEsc -Force } catch { Fallo "No puedo escribir en $dest. Elige una carpeta tuya (Documentos, OneDrive...)." }

    Paso "[Ficheros] Copiando el programa en $dest ..."
    $r = Extraer $dest
    Info "$($r[0]) ficheros copiados$(if ($r[1]) { " ($($r[1]) tuyos conservados)" })."
    $ok = Preparar-Python-Y-Visor $dest
    if ($env:ARBOL_SIN_ACCESOS -ne '1') { Crear-Accesos $dest; Registrar $dest }
    Titulo 'Instalación terminada'
    Write-Host "  Carpeta: $dest"
    Write-Host '  En tus notebooks:  from arbol_estadistica.modelos import tabla_odds_ratios'
    if ($ok -and $EnWindows -and $env:ARBOL_SIN_ACCESOS -ne '1') { Abrir-App $dest }
    exit 0
}

# ================================================================ ACTUALIZAR
if ($Modo -eq 'actualizar') {
    Titulo "ÁRBOL DE LA ESTADÍSTICA $Version - actualizar"
    $dest = Buscar-Instalacion
    if (-not $dest) { Fallo 'No hay instalación que actualizar. Usa el instalador completo.' }
    $anterior = '?'
    $fv = Ruta $dest 'py' 'VERSION.txt'
    if (Test-Path -LiteralPath $fv) { $anterior = (Get-Content -LiteralPath $fv -Encoding UTF8 | Select-Object -First 1).Trim() }
    Write-Host "  Instalación: $dest"
    Write-Host "  Versión instalada: $anterior  ->  nueva: $Version"
    Write-Host '  Se sustituye el programa (py, teoria, ejemplos, assets, documentos); tu catálogo de'
    Write-Host '  conceptos se conserva y solo se le añaden los conceptos nuevos.'
    if ($anterior -eq $Version -and -not $env:ARBOL_DESTINO) {
        Write-Host ''
        Write-Host "  Ya tienes instalada la versión ${Version}: no hace falta sustituir el programa." -ForegroundColor Green
        Write-Host '  Solo voy a comprobar que están todos los componentes (Python, librerías, IA local) e instalar los que falten.'
        $r = Read-Host '  Enter = comprobar componentes   R = reinstalar el programa igualmente   Q = salir'
        if ($r -match '^\s*[qQ]') { exit 2 }
        if ($r -notmatch '^\s*[rR]') {
            $pyc = Buscar-Python $dest
            if (-not $pyc) { Fallo 'No encuentro Python en esta instalación. Usa el instalador completo.' }
            $Estado.py = $pyc
            Preparar-IA $pyc $dest
            Titulo 'Comprobación terminada'
            exit 0
        }
    } elseif (-not $env:ARBOL_DESTINO) { $r = Read-Host '  Pulsa Enter para continuar o Q para cancelar'; if ($r -match '^\s*[qQ]') { exit 2 } }
    if ($EnWindows) {                                            # una app abierta bloquea la carpeta py: se cierra (con aviso) antes de moverla
        $abiertas = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -like '*arbol_app.pyw*' })
        if ($abiertas.Count) {
            Info 'La app del Árbol está abierta: la cierro para poder actualizarla (se volverá a abrir al terminar).'
            foreach ($a in $abiertas) { try { Stop-Process -Id $a.ProcessId -Force -ErrorAction Stop } catch { } }
            Start-Sleep -Seconds 2
        }
    }

    $marca = Get-Date -Format 'yyyyMMdd_HHmmss'
    $copias = Join-Path $dest 'anteriores'
    New-Item -ItemType Directory -Path $copias -Force | Out-Null
    Paso '[Copia] Apartando la versión anterior...'
    $pyViejo = Join-Path $dest 'py'
    $guardado = $null
    if (Test-Path -LiteralPath $pyViejo) {
        $guardado = Join-Path $copias ("py_" + $anterior + "_" + $marca)
        try { Move-Item -LiteralPath $pyViejo -Destination $guardado -ErrorAction Stop; Info "py anterior guardado en $guardado" }
        catch { Fallo "No puedo mover la carpeta py (¿hay un notebook o VS Code usándola? ciérralos y repite). $($_.Exception.Message)" }
    }
    $plana = Join-Path $copias ("estructura_plana_" + $marca)
    foreach ($x in @('arbol_estadistica', 'tests', 'visor', 'construir_visor.py', 'pyproject.toml', 'instalador.bat', 'crear_accesos_directos.ps1', 'icono.ico')) {
        $p = Join-Path $dest $x
        if (Test-Path -LiteralPath $p) { New-Item -ItemType Directory -Path $plana -Force | Out-Null; Move-Item -LiteralPath $p -Destination (Join-Path $plana $x) -ErrorAction SilentlyContinue }
    }

    Paso '[Ficheros] Copiando la versión nueva...'
    $r = Extraer $dest
    $nueva = ''
    if (Test-Path -LiteralPath $fv) { $nueva = (Get-Content -LiteralPath $fv -Encoding UTF8 | Select-Object -First 1).Trim() }
    if ($nueva -ne $Version) {
        if ($guardado -and -not (Test-Path -LiteralPath $pyViejo)) { Move-Item -LiteralPath $guardado -Destination $pyViejo -ErrorAction SilentlyContinue }
        Fallo "La copia no se completó (py\VERSION.txt = '$nueva', esperado '$Version'). Se ha restaurado lo anterior."
    }
    Info "$($r[0]) ficheros actualizados$(if ($r[1]) { " ($($r[1]) tuyos conservados)" }). Versión instalada: $nueva"
    $ok = Preparar-Python-Y-Visor $dest
    if ($env:ARBOL_SIN_ACCESOS -ne '1') { Crear-Accesos $dest; Registrar $dest }
    Titulo 'Actualización terminada'
    Write-Host "  Si algo fuera mal, la versión anterior está en: $guardado"
    if ($ok -and $EnWindows -and $env:ARBOL_SIN_ACCESOS -ne '1') { Abrir-App $dest }
    exit 0
}

Fallo "Modo desconocido: '$Modo'"
