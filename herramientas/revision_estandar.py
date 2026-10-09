"""Interfaz local para revisar y aplicar una estandarización de tu biblioteca (género, subgénero, tipo, título y asignatura), documento a documento.

    python herramientas/revision_estandar.py --criterio criterio.json [--propuesta propuesta.json] [--carpeta CONOCIMIENTO] [--puerto 8770]

Abre http://localhost:8770 (solo escucha en este ordenador). Por cada documento enseña lo que tiene ahora, lo que propone el sistema (si hay `--propuesta`, el JSON que escribe
`herramientas/estandarizar_biblioteca.py --json`) y el criterio, que puedes editar. Marcas lo que quieres cambiar y pulsas «Aplicar»: antes de tocar nada se hace una copia de
`metadatos.json`, `referencias.json` y `correcciones.json` en `biblioteca/_copia_antes_de_estandarizar/`; «Deshacer» la devuelve. Solo se cambian metadatos: tus archivos no se tocan.

`criterio.json`: {"<ruta relativa en biblioteca/>": {"genero", "subgenero", "tipo", "titulo", "subtema", "galaxia"}, ...}.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "py"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from conocimiento import importar, taxonomia  # noqa: E402


def _arg(nombre: str, defecto: str = "") -> str:
    return sys.argv[sys.argv.index(nombre) + 1] if nombre in sys.argv else defecto


CARPETA = Path(_arg("--carpeta") or importar.carpeta_datos())
CRITERIO = Path(_arg("--criterio")) if _arg("--criterio") else None
PROPUESTA = Path(_arg("--propuesta")) if _arg("--propuesta") else None
PUERTO = int(_arg("--puerto", "8770"))
BASE = CARPETA / "biblioteca"
COPIAS = BASE / "_copia_antes_de_estandarizar"
CAMPOS = ("titulo", "genero", "subgenero", "tipo", "subtema", "galaxia")


def leer(f: Path | None, defecto):
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f else defecto
    except (OSError, ValueError):
        return defecto


def datos() -> dict:
    meta, crit = importar.leer_metadatos(CARPETA), leer(CRITERIO, {})
    prop = {p["rel"]: p for p in leer(PROPUESTA, [])}
    filas = []
    for rel, c in crit.items():
        m = meta.get(rel)
        if not m:
            continue
        filas.append({"rel": rel, "archivo": Path(m.get("origen", "")).name or rel, "paginas": m.get("paginas", 0), "revisar": bool(m.get("revisar")),
                      "actual": {k: m.get(k, "") for k in CAMPOS}, "sistema": (prop.get(rel) or {}).get("ahora"), "criterio": {k: c.get(k, "") for k in CAMPOS}})
    generos = [{"id": g, "nombre": n, "subs": [{"id": s[0], "nombre": s[1]} for s in taxonomia.subgeneros(g, CARPETA)]} for g, n in importar.GENEROS.items()]
    copias = sorted(p.name for p in COPIAS.iterdir() if p.is_dir()) if COPIAS.exists() else []
    return {"filas": filas, "generos": generos, "tipos": [{"id": k, "nombre": v} for k, v in importar.TIPOS.items()], "galaxias": list(importar.GALAXIAS), "con_sistema": bool(prop),
            "copias": copias, "carpeta": str(CARPETA), "hay_copia": bool(copias or (COPIAS / "metadatos.json").exists())}


def hacer_copia() -> str:
    """Copia los tres ficheros de metadatos (una carpeta con fecha por aplicación; la primera es el estado original)."""
    destino = COPIAS / time.strftime("%Y%m%d_%H%M%S")
    destino.mkdir(parents=True, exist_ok=True)
    for n in ("metadatos.json", "referencias.json", "correcciones.json"):
        if (BASE / n).exists():
            shutil.copy2(BASE / n, destino / n)
    return destino.name


def aplicar(items: list[dict]) -> dict:
    copia, ok, errores = hacer_copia(), 0, []
    for it in items:
        try:
            importar.editar(it["rel"], {k: it[k] for k in CAMPOS if k in it}, CARPETA)
            ok += 1
        except Exception as e:                                       # un documento con un valor no válido no impide los demás
            errores.append({"rel": it.get("rel"), "error": f"{type(e).__name__}: {e}"})
    return {"ok": ok, "errores": errores, "copia": copia}


def deshacer() -> dict:
    """Devuelve los metadatos al estado de la copia más antigua (el original antes de estandarizar)."""
    copias = sorted(p for p in COPIAS.iterdir() if p.is_dir()) if COPIAS.exists() else []
    if not copias:
        return {"error": "no hay copia que restaurar"}
    for n in ("metadatos.json", "referencias.json", "correcciones.json"):
        if (copias[0] / n).exists():
            shutil.copy2(copias[0] / n, BASE / n)
    return {"restaurada": copias[0].name}


def actualizar_visor() -> dict:
    r = subprocess.run([sys.executable, str(RAIZ / "py" / "construir_visor.py")], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "ARBOL_CONOCIMIENTO": str(CARPETA), "PYTHONIOENCODING": "utf-8"}, cwd=str(RAIZ))
    return {"salida": (r.stdout or r.stderr).strip().splitlines()[-1:] or [""], "codigo": r.returncode}


PAGINA = """<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Estandarizar la biblioteca</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--tx:#1d2330;--mut:#667085;--bd:#e4e7ec;--ac:#2563eb;--ok:#16a34a;--av:#d97706;--ko:#dc2626;--chip:#eef2ff}
@media(prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#181c25;--tx:#e6e9ef;--mut:#8a93a6;--bd:#2a303d;--ac:#6ea0ff;--ok:#4ade80;--av:#fbbf24;--ko:#f87171;--chip:#222a44}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--bd);padding:12px 16px}
h1{font-size:18px;margin:0 0 6px}.sub{color:var(--mut);font-size:13px}
.barra{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:10px}
select,input[type=text],input[type=search]{padding:6px 8px;border:1px solid var(--bd);border-radius:7px;background:var(--card);color:var(--tx);font:inherit;font-size:13px;min-width:0}
button{padding:7px 12px;border:1px solid var(--bd);border-radius:7px;background:var(--card);color:var(--tx);font:inherit;font-size:13px;cursor:pointer}button:hover{border-color:var(--ac)}
button.prim{background:var(--ac);border-color:var(--ac);color:#fff;font-weight:600}button:disabled{opacity:.5;cursor:default}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;background:var(--chip);font-size:12px;margin-right:4px;white-space:nowrap}
main{padding:12px 16px 80px}.fila{display:grid;grid-template-columns:34px minmax(150px,.9fr) minmax(190px,1fr) minmax(190px,1fr) minmax(330px,1.7fr);gap:10px;align-items:start;background:var(--card);border:1px solid var(--bd);border-left:4px solid var(--bd);border-radius:9px;padding:9px 10px;margin-bottom:8px}
.fila.cambia{border-left-color:var(--av)}.fila.igual{border-left-color:var(--ok);opacity:.78}.cab{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);margin-bottom:3px}
.t{font-size:12.5px;color:var(--mut);overflow-wrap:anywhere}.arch{font-weight:600;overflow-wrap:anywhere}.ok{color:var(--ok)}.ko{color:var(--ko)}
.ed{display:grid;grid-template-columns:1fr 1fr;gap:6px}.ed .ancho{grid-column:1/-1}.ed select,.ed input{width:100%}
.res{margin-top:10px;font-size:13px}.res b{color:var(--ac)}.grupo{margin:14px 0 6px;font-weight:600;color:var(--mut)}
@media(max-width:1100px){.fila{grid-template-columns:30px 1fr}.fila>div:nth-child(n+3){grid-column:2}}
</style><body>
<header><h1>Estandarizar la biblioteca</h1><div class="sub" id="sub">Cargando…</div>
<div class="barra"><select id="fAsig" title="Asignatura"></select><select id="fEst"><option value="todos">Todos</option><option value="cambia">Los que cambiarían</option><option value="igual">Ya están como el criterio</option><option value="dif">El sistema no coincide con el criterio</option></select>
<input id="fQ" type="search" placeholder="Buscar por título o archivo…"><button id="bTodos">Marcar los que cambian</button><button id="bNinguno">Desmarcar todo</button>
<button class="prim" id="bAplicar">Aplicar</button><button id="bDeshacer">Deshacer</button><button id="bVisor" title="Regenera visor_arbol.html con lo nuevo">Actualizar el visor</button></div>
<div class="res" id="res"></div></header>
<main id="lista"></main>
<script>
const $=id=>document.getElementById(id);let D=null,sel=new Set();
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const nomG=id=>{const g=D.generos.find(x=>x.id===id);return g?g.nombre:id||'—'};
const nomS=(g,s)=>{const x=D.generos.find(y=>y.id===g);const z=x&&x.subs.find(w=>w.id===s);return z?z.nombre:(s||'—')};
const nomT=id=>{const t=D.tipos.find(x=>x.id===id);return t?t.nombre:id||'—'};
const cambia=f=>['genero','subgenero','tipo','titulo'].some(k=>(f.actual[k]||'')!==(f.criterio[k]||''));
const sisIgual=f=>f.sistema&&f.sistema.genero===f.criterio.genero&&f.sistema.subgenero===f.criterio.subgenero;
const opts=(l,v)=>l.map(o=>`<option value="${esc(o.id)}"${o.id===v?' selected':''}>${esc(o.nombre)}</option>`).join('');
function fila(f,i){const c=f.criterio,a=f.actual,s=f.sistema,g=D.generos.find(x=>x.id===c.genero);
 const cl=cambia(f)?'cambia':'igual';
 return `<div class="fila ${cl}" data-i="${i}"><div><input type="checkbox" data-sel="${i}"${sel.has(i)?' checked':''}></div>
 <div><div class="arch">${esc(f.archivo)}</div><div class="t">${f.paginas} págs.${f.revisar?' · <span class="ko">⚠ por revisar</span>':''}</div></div>
 <div><div class="cab">Ahora</div><span class="pill">${esc(nomG(a.genero))} › ${esc(nomS(a.genero,a.subgenero))}</span><span class="pill">${esc(nomT(a.tipo))}</span><div class="t">${esc(a.titulo)}</div></div>
 <div><div class="cab">Propone el sistema</div>${s?`<span class="pill">${esc(nomG(s.genero))} › ${esc(nomS(s.genero,s.subgenero))}</span><span class="pill">${esc(nomT(s.tipo))}</span> <span class="${sisIgual(f)?'ok':'ko'}">${sisIgual(f)?'✓ coincide':'✗ distinto'}</span><div class="t">${esc(s.titulo)}</div>`:'<span class="t">sin calcular</span>'}</div>
 <div><div class="cab">Criterio (editable) · ${esc(c.subtema)}</div><div class="ed"><input type="text" class="ancho" data-k="titulo" value="${esc(c.titulo)}">
 <select data-k="genero">${opts(D.generos,c.genero)}</select><select data-k="subgenero">${opts(g?g.subs:[],c.subgenero)}</select><select data-k="tipo">${opts(D.tipos,c.tipo)}</select>
 ${s?`<button data-usar="${i}" title="Copiar la propuesta del sistema al criterio">usar el del sistema</button>`:''}</div></div></div>`}
function visibles(){const a=$('fAsig').value,e=$('fEst').value,q=$('fQ').value.toLowerCase();
 return D.filas.map((f,i)=>[f,i]).filter(([f,i])=>(a==='*'||f.criterio.subtema===a)&&(e==='todos'||(e==='cambia'&&cambia(f))||(e==='igual'&&!cambia(f))||(e==='dif'&&f.sistema&&!sisIgual(f)))&&(!q||(f.archivo+' '+f.criterio.titulo+' '+f.actual.titulo).toLowerCase().includes(q)))}
function pintar(){const v=visibles();$('lista').innerHTML=v.map(([f,i])=>fila(f,i)).join('')||'<p class="sub">Nada coincide con el filtro.</p>';
 const n=D.filas.length,c=D.filas.filter(cambia).length,co=D.filas.filter(f=>f.sistema&&sisIgual(f)).length,cs=D.filas.filter(f=>f.sistema).length;
 $('sub').innerHTML=`${n} documentos · <b>${c}</b> cambiarían · marcados para aplicar: <b>${sel.size}</b>`+(D.con_sistema?` · el sistema coincide con el criterio (género y subgénero) en <b>${co}</b> de ${cs} (${cs?Math.round(100*co/cs):0} %)`:' · (el sistema aún no ha propuesto nada)')+(D.hay_copia?' · hay copia de seguridad':'');
 $('bAplicar').textContent='Aplicar '+sel.size+' seleccionado'+(sel.size===1?'':'s');$('bAplicar').disabled=!sel.size;$('bDeshacer').disabled=!D.hay_copia}
async function cargar(){D=await (await fetch('datos')).json();const asig=[...new Set(D.filas.map(f=>f.criterio.subtema))].sort();
 const ant=$('fAsig').value||'*';$('fAsig').innerHTML='<option value="*">Todas las asignaturas</option>'+asig.map(a=>`<option>${esc(a)}</option>`).join('');$('fAsig').value=asig.includes(ant)?ant:'*';
 if(!cargar.hecho){D.filas.forEach((f,i)=>{if(cambia(f))sel.add(i)});cargar.hecho=1}pintar()}
$('lista').addEventListener('input',e=>{const f=e.target.closest('.fila');if(!f||!e.target.dataset.k)return;const i=+f.dataset.i;D.filas[i].criterio[e.target.dataset.k]=e.target.value;
 if(e.target.dataset.k==='genero'){const g=D.generos.find(x=>x.id===e.target.value);D.filas[i].criterio.subgenero=g&&g.subs[0]?g.subs[0].id:'';pintar()}});
$('lista').addEventListener('change',e=>{if(e.target.dataset.sel!=null){const i=+e.target.dataset.sel;e.target.checked?sel.add(i):sel.delete(i);pintar()}});
$('lista').addEventListener('click',e=>{const i=e.target.dataset.usar;if(i!=null){const s=D.filas[+i].sistema;Object.assign(D.filas[+i].criterio,{genero:s.genero,subgenero:s.subgenero,tipo:s.tipo,titulo:s.titulo});pintar()}});
['fAsig','fEst'].forEach(x=>$(x).onchange=pintar);$('fQ').oninput=pintar;
$('bTodos').onclick=()=>{D.filas.forEach((f,i)=>{if(cambia(f))sel.add(i)});pintar()};$('bNinguno').onclick=()=>{sel.clear();pintar()};
async function post(ruta,cuerpo){const r=await fetch(ruta,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cuerpo||{})});return r.json()}
$('bAplicar').onclick=async()=>{if(!sel.size||!confirm('Se van a modificar '+sel.size+' documentos de tu biblioteca. Antes se guarda una copia de seguridad y puedes deshacerlo. ¿Continuar?'))return;
 const items=[...sel].map(i=>({rel:D.filas[i].rel,...D.filas[i].criterio}));$('res').textContent='Aplicando…';const r=await post('aplicar',{items});
 $('res').innerHTML=`<b>${r.ok}</b> documentos actualizados (copia «${esc(r.copia)}»).`+(r.errores.length?` <span class="ko">${r.errores.length} con error:</span> `+r.errores.slice(0,4).map(x=>esc(x.error)).join(' · '):'')+' Pulsa «Actualizar el visor» para ver el cambio en el universo.';sel.clear();cargar.hecho=1;await cargar()};
$('bDeshacer').onclick=async()=>{if(!confirm('Vuelvo los metadatos al estado de antes de estandarizar. ¿Seguro?'))return;const r=await post('deshacer');$('res').textContent=r.error||('Restaurado el estado de «'+r.restaurada+'». Pulsa «Actualizar el visor».');cargar.hecho=0;await cargar()};
$('bVisor').onclick=async()=>{$('res').textContent='Actualizando el visor…';const r=await post('visor');$('res').textContent=(r.codigo===0?'Visor actualizado: ':'Error: ')+(r.salida||[''])[0]};
cargar();setInterval(async()=>{if(D&&!D.con_sistema){const n=await (await fetch('datos')).json();if(n.con_sistema){const c=D.filas.map(f=>f.criterio);D=n;D.filas.forEach((f,i)=>f.criterio=c[i]||f.criterio);pintar()}}},8000);
</script></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, cuerpo: bytes, tipo: str, codigo: int = 200):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path.startswith("/datos"):
            self._enviar(json.dumps(datos(), ensure_ascii=False).encode("utf-8"), "application/json")
        else:
            self._enviar(PAGINA.encode("utf-8"), "text/html")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        cuerpo = json.loads(self.rfile.read(n) or b"{}") if n else {}
        ruta = self.path.strip("/")
        try:
            r = aplicar(cuerpo.get("items", [])) if ruta == "aplicar" else deshacer() if ruta == "deshacer" else actualizar_visor() if ruta == "visor" else {"error": "ruta desconocida"}
        except Exception as e:
            r = {"error": f"{type(e).__name__}: {e}"}
        self._enviar(json.dumps(r, ensure_ascii=False).encode("utf-8"), "application/json")


if __name__ == "__main__":
    if not CRITERIO:
        print(__doc__)
        raise SystemExit(2)
    print(f"Interfaz en http://localhost:{PUERTO}  (Ctrl+C para cerrar) · biblioteca: {CARPETA}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PUERTO), H).serve_forever()
