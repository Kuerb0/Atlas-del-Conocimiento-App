"""Los instaladores autoextraibles empaquetan lo correcto y se extraen identicos."""
import importlib.util
import re
from pathlib import Path

CODIGO = Path(__file__).resolve().parents[1]
RAIZ = CODIGO.parent


def _generador():
    ruta = RAIZ / "herramientas" / "generar_instaladores.py"
    spec = importlib.util.spec_from_file_location("generar_instaladores", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_version_coherente():
    gen = _generador()
    version = (CODIGO / "VERSION.txt").read_text(encoding="utf-8").strip()
    assert gen.version_del_programa(str(RAIZ)) == version
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)


def test_generar_y_extraer(tmp_path):
    gen = _generador()
    escritos = gen.generar(str(RAIZ), str(tmp_path))      # ya comprueba ida y vuelta byte a byte
    nombres = sorted(Path(e).name for e in escritos)
    version = gen.version_del_programa(str(RAIZ))
    assert nombres == [f"Atlas {version} - Actualizar.bat", f"Atlas {version} - Instalador.bat"]
    for e in escritos:
        sacado = gen.extraer(Path(e).read_bytes())
        assert sacado["py/arbol_estadistica/modelos/logit_sas.py"][0] == "text"
        assert sacado["conceptos/catalogo.json"][0] == "seed"
        assert sacado["conceptos/catalogo_base.json"][0] == "text"           # copia que sí se actualiza
        assert sacado["assets/icono.ico"][0] == "b64"
        assert not any("__pycache__" in rel or rel.endswith(".pyc") for rel in sacado)
        assert "visor_arbol.html" not in sacado
        assert not any(rel.startswith(("anteriores/", "instaladores/", "python/")) for rel in sacado)


def test_plantillas_tienen_marcadores():
    for nombre in ("instalador.bat.txt", "actualizar.bat.txt"):
        texto = (RAIZ / "herramientas" / "plantillas" / nombre).read_text(encoding="utf-8")
        assert texto.count("@@PAYLOAD@@") == 1 and texto.count("@@MOTOR@@") == 1
        assert "\n:::PSSTART\n" in texto and "\n:::PSEND\n" in texto
        assert "chcp 65001" not in texto and "goto" not in texto.lower()       # cmd nunca escanea el contenido empaquetado


def test_fusionar_catalogo_conserva_lo_tuyo_y_anade_lo_nuevo(tmp_path):
    import json, importlib
    sys_path = str(CODIGO)
    import sys
    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    fusionar = importlib.import_module("fusionar_catalogo").fusionar
    (tmp_path / "conceptos").mkdir()
    base = {"areas": [{"id": "a"}, {"id": "b"}], "conceptos": [
        {"id": "c1", "funciones": ["f1", "f2"], "sinonimos": [], "fuentes": [{"tipo": "arbol", "ref": "x"}]},
        {"id": "c2", "funciones": [], "sinonimos": [], "fuentes": []}]}
    mio = {"areas": [{"id": "a"}], "conceptos": [
        {"id": "c1", "nombre": "editado por mi", "funciones": ["f1", "mia"], "sinonimos": ["s"], "fuentes": []},
        {"id": "c_mio", "funciones": [], "sinonimos": [], "fuentes": []}]}
    (tmp_path / "conceptos" / "catalogo_base.json").write_text(json.dumps(base), encoding="utf-8")
    (tmp_path / "conceptos" / "catalogo.json").write_text(json.dumps(mio), encoding="utf-8")
    r = fusionar(tmp_path)
    assert r["conceptos_nuevos"] == 1 and r["areas_nuevas"] == 1 and r["enlaces_nuevos"] == 1
    out = json.loads((tmp_path / "conceptos" / "catalogo.json").read_text(encoding="utf-8"))
    c1 = next(c for c in out["conceptos"] if c["id"] == "c1")
    assert c1["nombre"] == "editado por mi" and c1["funciones"] == ["f1", "mia", "f2"] and len(c1["fuentes"]) == 1
    assert {c["id"] for c in out["conceptos"]} == {"c1", "c2", "c_mio"}
    assert fusionar(tmp_path)["conceptos_nuevos"] == 0                          # idempotente


def test_fusionar_aplica_la_nueva_organizacion_sin_perder_lo_tuyo(tmp_path):
    import json, importlib, sys
    if str(CODIGO) not in sys.path:
        sys.path.insert(0, str(CODIGO))
    fusionar = importlib.import_module("fusionar_catalogo").fusionar
    (tmp_path / "conceptos").mkdir()
    base = {"temas": [{"id": "t1", "nombre": "T1", "color": {"claro": "#111111", "oscuro": "#eeeeee"}}],
            "areas": [{"id": "nueva", "tema": "t1", "nombre": "Nueva", "ambito": "normativo"}],
            "conceptos": [{"id": "c1", "area": "nueva", "prioridad": "alta", "funciones": [], "sinonimos": [], "fuentes": []},
                          {"id": "c2", "area": "nueva", "funciones": [], "sinonimos": [], "fuentes": []}]}
    mio = {"areas": [{"id": "vieja", "nombre": "Vieja"}], "conceptos": [
        {"id": "c1", "nombre": "mi nombre", "area": "vieja", "funciones": [], "sinonimos": [], "fuentes": []},
        {"id": "c2", "area": "vieja", "area_fija": True, "funciones": [], "sinonimos": [], "fuentes": []},
        {"id": "c_mio", "area": "vieja", "funciones": [], "sinonimos": [], "fuentes": []}]}
    (tmp_path / "conceptos" / "catalogo_base.json").write_text(json.dumps(base), encoding="utf-8")
    (tmp_path / "conceptos" / "catalogo.json").write_text(json.dumps(mio), encoding="utf-8")
    assert fusionar(tmp_path)["reorganizados"] > 0
    out = json.loads((tmp_path / "conceptos" / "catalogo.json").read_text(encoding="utf-8"))
    por_id = {c["id"]: c for c in out["conceptos"]}
    assert por_id["c1"]["area"] == "nueva" and por_id["c1"]["nombre"] == "mi nombre" and por_id["c1"]["prioridad"] == "alta"
    assert por_id["c2"]["area"] == "vieja"                       # area_fija: tu decisión manda
    assert por_id["c_mio"]["area"] == "vieja" and len(out["conceptos"]) == 3
    assert out["temas"] == base["temas"] and any(a["id"] == "vieja" for a in out["areas"])   # sigue en uso (c2 y c_mio): no se retira
    assert fusionar(tmp_path)["reorganizados"] == 0              # idempotente
    por_id["c2"]["area"] = "nueva"; por_id["c_mio"]["area"] = "nueva"                  # si ya nadie usa «vieja», desaparece
    (tmp_path / "conceptos" / "catalogo.json").write_text(json.dumps(out), encoding="utf-8")
    fusionar(tmp_path)
    assert {a["id"] for a in json.loads((tmp_path / "conceptos" / "catalogo.json").read_text(encoding="utf-8"))["areas"]} == {"nueva"}


def test_reorganizar_catalogo_no_toca_un_catalogo_ya_reorganizado():
    import json
    spec = importlib.util.spec_from_file_location("reorganizar_catalogo", RAIZ / "herramientas" / "reorganizar_catalogo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cat = json.loads((RAIZ / "conceptos" / "catalogo_base.json").read_text(encoding="utf-8"))
    assert mod.reorganizar(cat) is cat
    assert {a[0] for a in mod.AREAS} <= {a["id"] for a in cat["areas"]}            # la migración original; después se amplió
    assert sum(len(v) for v in mod.ASIGNACION.values()) == 195 <= len(cat["conceptos"])


def test_lanzador_pyw_compila_y_no_abre_nada_al_importar():
    import importlib.machinery, importlib.util
    ruta = CODIGO / "arbol_app.pyw"
    cargador = importlib.machinery.SourceFileLoader("arbol_app", str(ruta))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("arbol_app", cargador))
    cargador.exec_module(mod)                     # solo define funciones; main() no se ejecuta
    assert mod.VISOR.name == "visor_arbol.html" and callable(mod.main)
    assert "%C3%" in (mod.RAIZ / "Árbol.html").as_uri()      # la URL que recibe el navegador va codificada


def test_un_solo_acceso_directo_y_lanzador_comprobado():
    motor = (RAIZ / "herramientas" / "plantillas" / "motor.ps1").read_text(encoding="utf-8")
    assert motor.count("CreateShortcut(") == 1                       # solo el acceso de la app (no el de «regenerar»)
    assert "Elegir-Lanzador" in motor and "sys.base_prefix" in motor    # pythonw solo si existe de verdad
    bat = (RAIZ / "abrir_arbol.bat").read_text(encoding="utf-8", errors="replace").lower()
    assert "where pythonw" not in bat and "where pyw" not in bat       # no adivinar con el PATH (podía coger uno roto)


def test_el_actualizador_abre_lo_mismo_que_el_acceso_directo():
    motor = (RAIZ / "herramientas" / "plantillas" / "motor.ps1").read_text(encoding="utf-8")
    assert "function Abrir-App" in motor and motor.count("Abrir-App $dest") == 2                    # instalador y actualizador abren la app con el propio acceso directo
    assert "Start-Process -FilePath $lnk" in motor
    assert motor.count("Start-Process -FilePath (Ruta $dest 'abrir_arbol.bat')") == 1               # abrir_arbol.bat solo como último recurso (sin acceso directo)
    bat = (RAIZ / "abrir_arbol.bat").read_text(encoding="utf-8", errors="replace")
    assert 'find /i "pythonw"' in bat                                                                # pythonw no se lanza minimizado: igual que el acceso directo


def test_el_motor_del_instalador_es_powershell_valido():
    """Un error de sintaxis en motor.ps1 solo se vería al ejecutar el .bat en otro ordenador: se valida con el propio analizador de PowerShell."""
    import shutil
    import subprocess
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        import pytest
        pytest.skip("no hay PowerShell")
    motor = RAIZ / "herramientas" / "plantillas" / "motor.ps1"
    orden = ("$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('" + str(motor) + "',[ref]$t,[ref]$e);"
             "if($e.Count){$e|%{ 'L'+$_.Extent.StartLineNumber+': '+$_.Message };exit 1}")
    r = subprocess.run([ps, "-NoProfile", "-Command", orden], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_el_instalador_detecta_e_instala_la_ia_local():
    texto = (RAIZ / "herramientas" / "plantillas" / "motor.ps1").read_text(encoding="utf-8")
    for clave in ("Preparar-IA", "Buscar-Ollama", "Descargar-Con-Barra", "Get-AuthenticodeSignature", "qwen2.5:3b", "ARBOL_SIN_IA", "conocimiento', 'modelos'"):
        assert clave in texto, clave
    assert "ARBOL_SIN_RED" in texto.split("function Preparar-Python-Y-Visor")[1]          # sin red no se intenta ninguna descarga


def test_actualizar_con_la_misma_version_rehace_el_acceso_directo():
    """Si se movió o renombró la carpeta, el acceso directo viejo no abre: aunque no haya nada que actualizar, el actualizador debe rehacerlo."""
    motor = (Path(__file__).resolve().parents[2] / "herramientas" / "plantillas" / "motor.ps1").read_text(encoding="utf-8-sig")
    rama = motor[motor.index("Preparar-IA $pyc $dest"):motor.index("Comprobación terminada")]
    assert "Crear-Accesos $dest" in rama and "Registrar $dest" in rama
