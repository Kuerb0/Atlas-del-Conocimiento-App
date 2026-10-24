"""Panel local para revisar y aplicar una estandarización de tu biblioteca (género, subgénero, tipo, título y asignatura), con cifras, gráficos y el detalle documento a documento.

    python herramientas/revision_estandar.py --criterio criterio.json [--propuesta antes.json] [--despues despues.json] [--log registro.txt] [--carpeta CONOCIMIENTO] [--puerto 8770]

Abre http://localhost:8770 (solo escucha en este ordenador). Muestra: cuánto acierta hoy el sistema frente al criterio (`--propuesta`, el JSON de `estandarizar_biblioteca.py --json`), cuánto
acertaría con la biblioteca ya estandarizada (`--despues`, el mismo JSON generado con `--como criterio.json`), el reparto por asignatura, género y tipo antes y después, y las confusiones.
Debajo, cada documento con lo que tiene ahora, lo que propone el sistema y el criterio, que puedes editar. Marcas lo que quieres cambiar y pulsas «Aplicar»: antes se copian
`metadatos.json`, `referencias.json` y `correcciones.json` a `biblioteca/_copia_antes_de_estandarizar/`; «Deshacer» los devuelve. Solo se cambian metadatos: tus archivos no se tocan.

`criterio.json`: {"<ruta relativa en biblioteca/>": {"genero", "subgenero", "tipo", "titulo", "subtema", "galaxia"}, ...}.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
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
DESPUES = Path(_arg("--despues")) if _arg("--despues") else None
LOG = Path(_arg("--log")) if _arg("--log") else None
PUERTO = int(_arg("--puerto", "8770"))
BASE = CARPETA / "biblioteca"
COPIAS = BASE / "_copia_antes_de_estandarizar"
CAMPOS = ("titulo", "genero", "subgenero", "tipo", "subtema", "galaxia")


def leer(f: Path | None, defecto):
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f else defecto
    except (OSError, ValueError):
        return defecto


def _aciertos(filas: list[dict], clave: str) -> dict | None:
    """Cuánto coincide la propuesta (`clave` = 'sistema' | 'despues') con el criterio."""
    con = [f for f in filas if f.get(clave)]
    if not con:
        return None
    g = sum(f[clave]["genero"] == f["criterio"]["genero"] for f in con)
    gs = sum(f[clave]["genero"] == f["criterio"]["genero"] and f[clave]["subgenero"] == f["criterio"]["subgenero"] for f in con)
    t = sum(f[clave]["tipo"] == f["criterio"]["tipo"] for f in con)
    return {"n": len(con), "genero": g, "gs": gs, "tipo": t}


def resumen(filas: list[dict], generos: dict, tipos: dict) -> dict:
    por = {}
    for f in filas:
        a = por.setdefault(f["criterio"]["subtema"], {"asig": f["criterio"]["subtema"], "n": 0, "antes": 0, "despues": 0, "con_antes": 0, "con_despues": 0})
        a["n"] += 1
        for clave, k in (("sistema", "antes"), ("despues", "despues")):
            if f.get(clave):
                a["con_" + k] += 1
                a[k] += f[clave]["genero"] == f["criterio"]["genero"] and f[clave]["subgenero"] == f["criterio"]["subgenero"]
    conf_fuente = "despues" if any(f.get("despues") for f in filas) else "sistema"
    conf = Counter((f"{generos.get(f['criterio']['genero'], f['criterio']['genero'])} › {f['criterio']['subgenero']}", f"{generos.get(f[conf_fuente]['genero'], f[conf_fuente]['genero'])} › {f[conf_fuente]['subgenero']}")
                   for f in filas if f.get(conf_fuente) and (f[conf_fuente]["genero"], f[conf_fuente]["subgenero"]) != (f["criterio"]["genero"], f["criterio"]["subgenero"]))
    return {"antes": _aciertos(filas, "sistema"), "despues": _aciertos(filas, "despues"), "por_asignatura": sorted(por.values(), key=lambda a: a["asig"]),
            "generos": [{"nombre": generos.get(g, g), "ahora": sum(f["actual"]["genero"] == g for f in filas), "criterio": sum(f["criterio"]["genero"] == g for f in filas)}
                        for g in sorted({f["actual"]["genero"] for f in filas} | {f["criterio"]["genero"] for f in filas})],
            "tipos": [{"nombre": tipos.get(t, t), "ahora": sum(f["actual"]["tipo"] == t for f in filas), "criterio": sum(f["criterio"]["tipo"] == t for f in filas)}
                      for t in sorted({f["actual"]["tipo"] for f in filas} | {f["criterio"]["tipo"] for f in filas})],
            "confusiones": [{"criterio": c, "sistema": s, "n": n} for (c, s), n in conf.most_common(9)], "confusion_fuente": conf_fuente,
            "por_revisar_ahora": sum(f["revisar"] for f in filas), "cambian": sum(any(f["actual"][k] != f["criterio"][k] for k in ("genero", "subgenero", "tipo", "titulo")) for f in filas)}


def datos() -> dict:
    meta, crit = importar.leer_metadatos(CARPETA), leer(CRITERIO, {})
    antes = {p["rel"]: p for p in leer(PROPUESTA, [])}
    despues = {p["rel"]: p for p in leer(DESPUES, [])}
    filas = []
    for rel, c in crit.items():
        m = meta.get(rel)
        if not m:
            continue
        filas.append({"rel": rel, "archivo": Path(m.get("origen", "")).name or rel, "paginas": m.get("paginas", 0), "revisar": bool(m.get("revisar")),
                      "actual": {k: m.get(k, "") for k in CAMPOS}, "sistema": (antes.get(rel) or {}).get("ahora"), "despues": (despues.get(rel) or {}).get("ahora"),
                      "criterio": {k: c.get(k, "") for k in CAMPOS}})
    gn, tn = dict(importar.GENEROS), dict(importar.TIPOS)
    generos = [{"id": g, "nombre": n, "subs": [{"id": s[0], "nombre": s[1]} for s in taxonomia.subgeneros(g, CARPETA)]} for g, n in gn.items()]
    copias = sorted(p.name for p in COPIAS.iterdir() if p.is_dir()) if COPIAS.exists() else []
    registro = [x[:180] for x in LOG.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()][-6:] if LOG and LOG.exists() else []
    return {"filas": filas, "generos": generos, "tipos": [{"id": k, "nombre": v} for k, v in tn.items()], "resumen": resumen(filas, gn, tn), "registro": registro,
            "con_sistema": bool(antes), "con_despues": bool(despues), "copias": copias, "carpeta": str(CARPETA), "hay_copia": bool(copias)}


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
:root{--bg:#f6f7f9;--card:#fff;--tx:#1d2330;--mut:#667085;--bd:#e4e7ec;--ac:#2563eb;--ac2:#16a34a;--av:#d97706;--ko:#dc2626;--chip:#eef2ff;--bar:#dbe4f5}
@media(prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#181c25;--tx:#e6e9ef;--mut:#8a93a6;--bd:#2a303d;--ac:#6ea0ff;--ac2:#4ade80;--av:#fbbf24;--ko:#f87171;--chip:#222a44;--bar:#26324a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 system-ui,Segoe UI,sans-serif;padding:16px;max-width:1240px;margin:auto}
h1{font-size:20px;margin:0 0 4px}h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 10px}.sub{color:var(--mut);margin-bottom:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin-bottom:12px}.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px}.full{grid-column:1/-1}.dos{grid-column:span 2}
.big{font-size:34px;font-weight:650;font-variant-numeric:tabular-nums}.mut{color:var(--mut)}.ok{color:var(--ac2)}.ko{color:var(--ko)}.pill{display:inline-block;padding:1px 8px;border-radius:99px;background:var(--chip);font-size:12px;margin-right:4px;white-space:nowrap}
svg text{fill:var(--tx);font-size:11px}svg text.m{fill:var(--mut)}.leyenda{margin-top:6px;font-size:12px;color:var(--mut)}.leyenda i{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:-1px}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:5px 8px;border-bottom:1px solid var(--bd);text-align:left}th{font-size:11px;color:var(--mut);text-transform:uppercase}td.n{text-align:right;font-variant-numeric:tabular-nums}
pre{margin:0;white-space:pre-wrap;font:12px/1.5 ui-monospace,Consolas,monospace;color:var(--mut)}
.barra{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 12px}
select,input[type=text],input[type=search]{padding:6px 8px;border:1px solid var(--bd);border-radius:7px;background:var(--card);color:var(--tx);font:inherit;font-size:13px;min-width:0}
button{padding:7px 12px;border:1px solid var(--bd);border-radius:7px;background:var(--card);color:var(--tx);font:inherit;font-size:13px;cursor:pointer}button:hover{border-color:var(--ac)}
button.prim{background:var(--ac);border-color:var(--ac);color:#fff;font-weight:600}button:disabled{opacity:.5;cursor:default}.res{margin:8px 0;font-size:13px}
.fila{display:grid;grid-template-columns:30px minmax(140px,.8fr) minmax(180px,1fr) minmax(180px,1fr) minmax(320px,1.7fr);gap:10px;align-items:start;background:var(--card);border:1px solid var(--bd);border-left:4px solid var(--bd);border-radius:9px;padding:9px 10px;margin-bottom:8px}
.fila.cambia{border-left-color:var(--av)}.fila.igual{border-left-color:var(--ac2);opacity:.78}.cab{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);margin-bottom:3px}.t{font-size:12.5px;color:var(--mut);overflow-wrap:anywhere}.arch{font-weight:600;overflow-wrap:anywhere}
.ed{display:grid;grid-template-columns:1fr 1fr;gap:6px}.ed .ancho{grid-column:1/-1}.ed select,.ed input{width:100%}
@media(max-width:1100px){.fila{grid-template-columns:30px 1fr}.fila>div:nth-child(n+3){grid-column:2}.dos{grid-column:1/-1}}
</style><body>
<h1>Estandarizar la biblioteca</h1><div class="sub" id="sub">Cargando…</div>
<div class="grid" id="kpis"></div>
<div class="grid"><div class="card dos"><h2>Acierto del sistema por asignatura (género y subgénero)</h2><div id="gAsig"></div><div class="leyenda"><i style="background:var(--ac)"></i>con tus etiquetas de hoy<i style="background:var(--ac2)"></i>con la biblioteca estandarizada (estimado)</div></div>
<div class="card" id="cReg" hidden><h2>Registro en vivo</h2><pre id="reg"></pre></div>
<div class="card"><h2>Por género: ahora y con el criterio</h2><div id="gGen"></div><div class="leyenda"><i style="background:var(--bar)"></i>ahora<i style="background:var(--ac)"></i>criterio</div></div>
<div class="card"><h2>Por tipo de documento</h2><div id="gTipo"></div><div class="leyenda"><i style="background:var(--bar)"></i>ahora<i style="background:var(--ac)"></i>criterio</div></div>
<div class="card"><h2 id="hConf">Dónde se confunde el sistema</h2><div id="tConf"></div></div></div>
<h2 style="margin-top:20px">Detalle documento a documento</h2>
<div class="barra"><select id="fAsig"></select><select id="fEst"><option value="todos">Todos</option><option value="cambia">Los que cambiarían</option><option value="igual">Ya están como el criterio</option><option value="dif">El sistema no coincide con el criterio</option></select>
<input id="fQ" type="search" placeholder="Buscar por título o archivo…"><button id="bTodos">Marcar los que cambian</button><button id="bNinguno">Desmarcar todo</button>
<button class="prim" id="bAplicar">Aplicar</button><button id="bDeshacer">Deshacer</button><button id="bVisor" title="Regenera visor_arbol.html con lo nuevo">Actualizar el visor</button></div>
<div class="res" id="res"></div><main id="lista"></main>
<script>
const $=id=>document.getElementById(id);let D=null,sel=new Set();
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const nomG=id=>{const g=D.generos.find(x=>x.id===id);return g?g.nombre:id||'—'};
const nomS=(g,s)=>{const x=D.generos.find(y=>y.id===g);const z=x&&x.subs.find(w=>w.id===s);return z?z.nombre:(s||'—')};
const nomT=id=>{const t=D.tipos.find(x=>x.id===id);return t?t.nombre:id||'—'};
const pc=(a,n)=>n?Math.round(100*a/n):0;
const cambia=f=>['genero','subgenero','tipo','titulo'].some(k=>(f.actual[k]||'')!==(f.criterio[k]||''));
const sisIgual=f=>f.sistema&&f.sistema.genero===f.criterio.genero&&f.sistema.subgenero===f.criterio.subgenero;
const opts=(l,v)=>l.map(o=>`<option value="${esc(o.id)}"${o.id===v?' selected':''}>${esc(o.nombre)}</option>`).join('');
function kpi(t,v,s,c){return `<div class="card"><h2>${t}</h2><div class="big ${c||''}">${v}</div><div class="mut">${s}</div></div>`}
function barrasH(items,sa,sb){const W=560,L=190,fil=sb?30:20,H=items.length*fil+10;let s=`<svg viewBox="0 0 ${W} ${H}" width="100%">`;
 items.forEach((it,i)=>{const y=6+i*fil;s+=`<text x="${L-6}" y="${y+(sb?12:11)}" text-anchor="end">${esc(it.l)}</text>`;
  s+=`<rect x="${L}" y="${y}" width="${Math.max(0,(W-L-50)*it.a)}" height="11" rx="2" fill="${sa}"/><text x="${L+(W-L-50)*it.a+4}" y="${y+10}" class="m">${it.ta}</text>`;
  if(sb&&it.b!=null)s+=`<rect x="${L}" y="${y+13}" width="${Math.max(0,(W-L-50)*it.b)}" height="11" rx="2" fill="${sb}"/><text x="${L+(W-L-50)*it.b+4}" y="${y+23}" class="m">${it.tb}</text>`});return s+'</svg>'}
function barrasN(items){const m=Math.max(1,...items.map(i=>Math.max(i.ahora,i.criterio)));const W=420,L=150,fil=30,H=items.length*fil+8;let s=`<svg viewBox="0 0 ${W} ${H}" width="100%">`;
 items.forEach((it,i)=>{const y=5+i*fil;s+=`<text x="${L-6}" y="${y+12}" text-anchor="end">${esc(it.nombre)}</text><rect x="${L}" y="${y}" width="${(W-L-34)*it.ahora/m}" height="11" rx="2" fill="var(--bar)"/><text x="${L+(W-L-34)*it.ahora/m+4}" y="${y+10}" class="m">${it.ahora}</text>
 <rect x="${L}" y="${y+13}" width="${(W-L-34)*it.criterio/m}" height="11" rx="2" fill="var(--ac)"/><text x="${L+(W-L-34)*it.criterio/m+4}" y="${y+23}" class="m">${it.criterio}</text>`});return s+'</svg>'}
function resumen(){const R=D.resumen,a=R.antes,d=R.despues;
 $('kpis').innerHTML=kpi('Documentos',D.filas.length,`${R.cambian} cambiarían con el criterio`)+
  kpi('El sistema acierta hoy',a?pc(a.gs,a.n)+' %':'…',a?`género ${pc(a.genero,a.n)} % · género+subgénero ${pc(a.gs,a.n)} % · tipo ${pc(a.tipo,a.n)} %`:'calculando…',a&&pc(a.gs,a.n)<60?'ko':'')+
  kpi('Con la biblioteca estandarizada',d?pc(d.gs,d.n)+' %':'…',d?`género ${pc(d.genero,d.n)} % · género+subgénero ${pc(d.gs,d.n)} % · tipo ${pc(d.tipo,d.n)} % (cada documento, sin contar consigo mismo)`:'se está calculando…',d?'ok':'')+
  kpi('Por revisar ahora',R.por_revisar_ahora,'avisos ⚠ de la cola de revisión con las etiquetas de hoy');
 const it=R.por_asignatura.filter(x=>x.con_antes||x.con_despues).sort((x,y)=>(x.antes/Math.max(x.con_antes,1))-(y.antes/Math.max(y.con_antes,1)));
 $('gAsig').innerHTML=barrasH(it.map(x=>({l:x.asig,a:x.con_antes?x.antes/x.con_antes:0,ta:x.con_antes?x.antes+'/'+x.con_antes:'',b:x.con_despues?x.despues/x.con_despues:null,tb:x.con_despues?x.despues+'/'+x.con_despues:''})),'var(--ac)','var(--ac2)')||'';
 $('gGen').innerHTML=barrasN(R.generos);$('gTipo').innerHTML=barrasN(R.tipos);
 $('hConf').textContent='Dónde se confunde el sistema'+(R.confusion_fuente==='despues'?' (con la biblioteca estandarizada)':' (con las etiquetas de hoy)');
 $('tConf').innerHTML=R.confusiones.length?'<table><tr><th>Criterio</th><th>Sistema dice</th><th>n</th></tr>'+R.confusiones.map(c=>`<tr><td>${esc(c.criterio)}</td><td>${esc(c.sistema)}</td><td class="n">${c.n}</td></tr>`).join('')+'</table>':'<span class="mut">Sin confusiones (o aún sin propuesta).</span>';
 $('cReg').hidden=!D.registro.length;$('reg').textContent=D.registro.join('\\n')}
function fila(f,i){const c=f.criterio,a=f.actual,s=f.sistema,g=D.generos.find(x=>x.id===c.genero);const cl=cambia(f)?'cambia':'igual';
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
 $('sub').innerHTML=`${D.filas.length} documentos de tu biblioteca · marcados para aplicar: <b>${sel.size}</b>`+(D.hay_copia?' · hay copia de seguridad':' · todavía no se ha tocado nada');
 $('bAplicar').textContent='Aplicar '+sel.size+' seleccionado'+(sel.size===1?'':'s');$('bAplicar').disabled=!sel.size;$('bDeshacer').disabled=!D.hay_copia}
async function cargar(){const n=await (await fetch('datos')).json();if(D&&cargar.hecho){const c=D.filas.map(f=>f.criterio);n.filas.forEach((f,i)=>{if(c[i]&&D.filas[i].rel===f.rel)f.criterio=c[i]})}D=n;
 const asig=[...new Set(D.filas.map(f=>f.criterio.subtema))].sort();const ant=$('fAsig').value||'*';$('fAsig').innerHTML='<option value="*">Todas las asignaturas</option>'+asig.map(a=>`<option>${esc(a)}</option>`).join('');$('fAsig').value=asig.includes(ant)?ant:'*';
 if(!cargar.hecho){D.filas.forEach((f,i)=>{if(cambia(f))sel.add(i)});cargar.hecho=1}resumen();pintar()}
$('lista').addEventListener('input',e=>{const f=e.target.closest('.fila');if(!f||!e.target.dataset.k)return;const i=+f.dataset.i;D.filas[i].criterio[e.target.dataset.k]=e.target.value;
 if(e.target.dataset.k==='genero'){const g=D.generos.find(x=>x.id===e.target.value);D.filas[i].criterio.subgenero=g&&g.subs[0]?g.subs[0].id:'';pintar()}});
$('lista').addEventListener('change',e=>{if(e.target.dataset.sel!=null){const i=+e.target.dataset.sel;e.target.checked?sel.add(i):sel.delete(i);pintar()}});
$('lista').addEventListener('click',e=>{const i=e.target.dataset.usar;if(i!=null){const s=D.filas[+i].sistema;Object.assign(D.filas[+i].criterio,{genero:s.genero,subgenero:s.subgenero,tipo:s.tipo,titulo:s.titulo});pintar()}});
['fAsig','fEst'].forEach(x=>$(x).onchange=pintar);$('fQ').oninput=pintar;
$('bTodos').onclick=()=>{D.filas.forEach((f,i)=>{if(cambia(f))sel.add(i)});pintar()};$('bNinguno').onclick=()=>{sel.clear();pintar()};
async function post(ruta,cuerpo){const r=await fetch(ruta,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cuerpo||{})});return r.json()}
$('bAplicar').onclick=async()=>{if(!sel.size||!confirm('Se van a modificar '+sel.size+' documentos de tu biblioteca. Antes se guarda una copia de seguridad y puedes deshacerlo. ¿Continuar?'))return;
 const items=[...sel].map(i=>({rel:D.filas[i].rel,...D.filas[i].criterio}));$('res').textContent='Aplicando…';const r=await post('aplicar',{items});
 $('res').innerHTML=`<b>${r.ok}</b> documentos actualizados (copia «${esc(r.copia)}»).`+(r.errores.length?` <span class="ko">${r.errores.length} con error:</span> `+r.errores.slice(0,4).map(x=>esc(x.error)).join(' · '):'')+' Pulsa «Actualizar el visor» para ver el cambio en el universo.';sel.clear();await cargar()};
$('bDeshacer').onclick=async()=>{if(!confirm('Vuelvo los metadatos al estado de antes de estandarizar. ¿Seguro?'))return;const r=await post('deshacer');$('res').textContent=r.error||('Restaurado el estado de «'+r.restaurada+'». Pulsa «Actualizar el visor».');await cargar()};
$('bVisor').onclick=async()=>{$('res').textContent='Actualizando el visor…';const r=await post('visor');$('res').textContent=(r.codigo===0?'Visor actualizado: ':'Error: ')+(r.salida||[''])[0]};
cargar();setInterval(()=>{if(D&&(!D.con_sistema||!D.con_despues||D.registro.length))cargar()},8000);
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
    print(f"Panel en http://localhost:{PUERTO}  (Ctrl+C para cerrar) · biblioteca: {CARPETA}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PUERTO), H).serve_forever()
