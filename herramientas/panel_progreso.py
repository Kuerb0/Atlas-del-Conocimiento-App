"""Panel en vivo del entrenamiento y la evaluación del clasificador (se abre en el navegador, se actualiza solo).

    python herramientas/panel_progreso.py RAIZ [--log FICHERO] [--puerto 8765]

RAIZ es la carpeta con `enes/corpus` (corpus de pruebas) y `enes/resultados` (lo que escribe evaluar_corpus.py). Muestra: lo que está corriendo ahora (barra, acierto parcial,
tiempo restante, últimas obras), el corpus, una tabla y un gráfico con todas las configuraciones medidas (con intervalo de Wilson al 95 %) y el estado de la GPU y de Ollama.
Solo lee ficheros: no toca nada y solo escucha en localhost.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estadisticas_clasificacion import wilson  # noqa: E402

RAIZ = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else Path(".")
LOG = Path(sys.argv[sys.argv.index("--log") + 1]) if "--log" in sys.argv else None
PUERTO = int(sys.argv[sys.argv.index("--puerto") + 1]) if "--puerto" in sys.argv else 8765


def leer(f: Path, defecto):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def corpus() -> dict:
    meta = leer(RAIZ / "enes" / "corpus" / "biblioteca" / "metadatos.json", {})
    sp, sv = leer(RAIZ / "enes" / "split.json", {}), leer(RAIZ / "enes" / "split_val.json", {})
    return {"total": len(meta), "tipos": Counter(m.get("tipo", "?") for m in meta.values()), "generos": Counter(m.get("genero", "?") for m in meta.values()),
            "prueba": len(sp.get("prueba", [])), "validacion": len(sv.get("prueba", [])), "entrenamiento": len(sv.get("entrenamiento", []))}


def resultados() -> list[dict]:
    out = []
    for f in sorted((RAIZ / "enes" / "resultados").glob("*.json"), key=lambda p: p.stat().st_mtime):
        if f.name.startswith("_"):
            continue
        r = leer(f, None)
        if not r or not r.get("filas"):
            continue
        fl = r["filas"]
        n, k = len(fl), sum(x["g"] == x["pg"] for x in fl)
        ls = [x for x in fl if x["s"]]
        ks = sum(x["g"] == x["pg"] and x["s"] == x["ps"] for x in ls)
        lo, hi = wilson(k, n)
        out.append({"nombre": r["nombre"], "n": n, "g": k / n, "g_lo": lo, "g_hi": hi, "s": ks / max(len(ls), 1), "n_s": len(ls), "llm": r["modelo_llm"] if r["llm"] else "—",
                    "seg": sum(x["seg"] for x in fl) / n, "sets": ", ".join(s.split(".", 1)[-1] for s in r["sets"]), "hora": time.strftime("%H:%M", time.localtime(f.stat().st_mtime))})
    return out


def progreso() -> list[dict]:
    """La evolución por versión: los pasos de `enes/progreso.json` ([{archivo, version, paso}] en orden) con el acierto de cada resultado medido sobre la misma validación."""
    res = {r["nombre"]: r for r in resultados()}
    return [{"version": p["version"], "paso": p["paso"], "g": r["g"], "g_lo": r["g_lo"], "g_hi": r["g_hi"], "s": r["s"], "n": r["n"], "n_s": r["n_s"]}
            for p in leer(RAIZ / "enes" / "progreso.json", []) for r in [res.get(p["archivo"])] if r]


def vivo() -> dict | None:
    v = leer(RAIZ / "enes" / "resultados" / "_vivo.json", None)
    if v and time.time() - v["t"] < 600:
        v["hace"] = round(time.time() - v["t"])
        return v
    if LOG and LOG.exists():                      # sin _vivo.json (proceso antiguo): se lee la última línea de progreso del log
        for linea in reversed(LOG.read_text(encoding="utf-8", errors="replace").splitlines()):
            m = re.match(r"\s+(\d+)/(\d+)\s+género (\d+) %\s+\((\d+) s\)", linea)
            if m:
                i, n, g, s = map(int, m.groups())
                return {"nombre": "(según el log)", "i": i, "n": n, "aciertos": round(i * g / 100), "seg": s, "hace": round(time.time() - LOG.stat().st_mtime), "ultimas": [], "llm": True}
    return None


def maquina() -> dict:
    r: dict = {}
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4).stdout.strip().split(", ")
        r["gpu"] = {"nombre": o[0], "uso": int(o[1]), "vram": int(o[2]), "vram_total": int(o[3]), "temp": int(o[4])}
    except Exception:
        pass
    try:
        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=2) as x:
            r["ollama"] = [{"modelo": m["name"], "gb": round(m["size"] / 1e9, 1), "vram_gb": round(m.get("size_vram", 0) / 1e9, 1)} for m in json.loads(x.read())["models"]]
    except Exception:
        r["ollama"] = None
    try:
        import psutil
        v = psutil.virtual_memory()
        r["ram"] = {"uso": round(v.percent), "libre_gb": round(v.available / 1e9, 1), "total_gb": round(v.total / 1e9, 1)}
    except Exception:
        pass
    return r


PAGINA = """<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Progreso del clasificador</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--tx:#1d2330;--mut:#667085;--bd:#e4e7ec;--ac:#2563eb;--ok:#16a34a;--ko:#dc2626;--bar:#dbe4f5}
@media(prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#181c25;--tx:#e6e9ef;--mut:#8a93a6;--bd:#2a303d;--ac:#6ea0ff;--ok:#4ade80;--ko:#f87171;--bar:#26324a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 system-ui,Segoe UI,sans-serif;padding:16px;max-width:1100px;margin:auto}
h1{font-size:20px;margin:0 0 4px}h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 10px}
.sub{color:var(--mut);margin-bottom:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px}.full{grid-column:1/-1}
.big{font-size:34px;font-weight:650;font-variant-numeric:tabular-nums}.mut{color:var(--mut)}.row{display:flex;gap:10px;align-items:center;margin:3px 0}
.track{height:12px;background:var(--bar);border-radius:6px;overflow:hidden;flex:1}.fill{height:100%;background:var(--ac);transition:width .6s}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{padding:6px 8px;text-align:right;border-bottom:1px solid var(--bd)}th:first-child,td:first-child{text-align:left}th{font-size:12px;color:var(--mut);font-weight:600}
.ok{color:var(--ok)}.ko{color:var(--ko)}.pill{display:inline-block;padding:1px 8px;border-radius:99px;background:var(--bar);font-size:12px}
.lab{width:96px;color:var(--mut);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.val{width:44px;text-align:right;font-size:12px}
svg text{fill:var(--tx);font-size:11px}svg text.m{fill:var(--mut);font-size:10px}.pulse{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--ok);animation:p 1.4s infinite}@keyframes p{50%{opacity:.25}}
</style><body>
<h1>Progreso del clasificador</h1><div class="sub" id="sub">Cargando…</div>
<div class="grid">
<div class="card" id="ahora"></div><div class="card" id="maq"></div>
<div class="card full"><h2>Progreso por versión: acierto de género y de subgénero (misma validación, sin LLM salvo que se indique)</h2><div id="prog"></div></div>
<div class="card full"><h2>Configuraciones medidas (acierto de género con IC 95 %)</h2><div id="graf"></div><div style="overflow:auto"><table id="tabla"></table></div></div>
<div class="card"><h2>Corpus</h2><div id="corpus"></div></div><div class="card"><h2>Últimas obras evaluadas</h2><div id="ultimas"></div></div>
</div>
<script>
const $=id=>document.getElementById(id), pc=x=>(100*x).toFixed(1)+' %';
function barras(d,max){return Object.entries(d).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<div class="row"><span class="lab" title="${k}">${k}</span><div class="track"><div class="fill" style="width:${100*v/max}%"></div></div><span class="val">${v}</span></div>`).join('')}
function graf(rs){const W=1040,H=26*rs.length+30,x=v=>150+v*(W-190);let s=`<svg viewBox="0 0 ${W} ${H}" width="100%">`;
 for(let t=0;t<=1;t+=.25)s+=`<line x1="${x(t)}" x2="${x(t)}" y1="6" y2="${H-18}" stroke="var(--bd)"/><text x="${x(t)}" y="${H-4}" text-anchor="middle">${100*t}%</text>`;
 rs.forEach((r,i)=>{const y=14+i*26;s+=`<text x="144" y="${y+4}" text-anchor="end">${r.nombre}</text><rect x="${x(0)}" y="${y-7}" width="${x(r.g)-x(0)}" height="14" rx="3" fill="var(--ac)" opacity=".85"/><line x1="${x(r.g_lo)}" x2="${x(r.g_hi)}" y1="${y}" y2="${y}" stroke="var(--tx)" stroke-width="2"/><text x="${x(r.g_hi)+6}" y="${y+4}">${pc(r.g)}</text>`});
 return s+'</svg>'}
function lineas(ps){if(!ps.length)return '<div class="mut">Aún no hay pasos registrados.</div>';const W=1040,H=300,L=46,R=24,T=18,B=64,n=ps.length,x=i=>L+(n===1?(W-L-R)/2:i*(W-L-R)/(n-1)),y=v=>T+(1-v)*(H-T-B);
 let s=`<svg viewBox="0 0 ${W} ${H}" width="100%">`;
 for(let t=0;t<=1.001;t+=.2)s+=`<line x1="${L}" x2="${W-R}" y1="${y(t)}" y2="${y(t)}" stroke="var(--bd)"/><text x="${L-6}" y="${y(t)+4}" text-anchor="end">${Math.round(100*t)}%</text>`;
 const serie=(k,col,off)=>{let d=ps.map((p,i)=>`${i?'L':'M'}${x(i)},${y(p[k])}`).join(' ');let o=`<path d="${d}" fill="none" stroke="${col}" stroke-width="2.5"/>`;
  ps.forEach((p,i)=>{if(k==='g')o+=`<line x1="${x(i)}" x2="${x(i)}" y1="${y(p.g_lo)}" y2="${y(p.g_hi)}" stroke="${col}" stroke-width="1.5" opacity=".55"/>`;o+=`<circle cx="${x(i)}" cy="${y(p[k])}" r="5" fill="${col}"/><text x="${x(i)}" y="${y(p[k])+off}" text-anchor="middle" style="font-weight:650">${(100*p[k]).toFixed(1)}</text>`});return o};
 s+=serie('g','var(--ac)',-10)+serie('s','var(--ok)',17);
 ps.forEach((p,i)=>{s+=`<text x="${x(i)}" y="${H-38}" text-anchor="middle" style="font-weight:650">${p.version}</text><text x="${x(i)}" y="${H-22}" text-anchor="middle" class="m">${p.paso}</text><text x="${x(i)}" y="${H-8}" text-anchor="middle" class="m">n=${p.n}</text>`});
 return s+'</svg><div class="mut" style="margin-top:4px"><span style="color:var(--ac)">●</span> género (con IC 95 %) &nbsp; <span style="color:var(--ok)">●</span> subgénero (género y subgénero correctos)</div>'}
async function ciclo(){try{const e=await (await fetch('estado')).json();
 $('sub').innerHTML=`<span class="pulse"></span> actualizado ${new Date().toLocaleTimeString()} · se refresca cada 3 s`;
 const v=e.vivo;
 $('ahora').innerHTML=v?`<h2>Ahora mismo</h2><div class="mut">${v.nombre}${v.llm?' · con LLM':' · sin LLM'}</div><div class="big">${v.i}<span class="mut"> / ${v.n}</span></div>
  <div class="row"><div class="track"><div class="fill" style="width:${100*v.i/v.n}%"></div></div><span>${(100*v.i/v.n).toFixed(0)} %</span></div>
  <div>Acierto parcial de género: <b>${(100*v.aciertos/Math.max(v.i,1)).toFixed(1)} %</b></div>
  ${v.hilos&&v.hilos.maximo>1?`<div>Obras a la vez: <b>${v.hilos.activos}</b> <span class="mut">(límite ${v.hilos.limite} de ${v.hilos.maximo}, se ajusta solo según RAM, VRAM y GPU)</span></div>`:''}
  <div class="mut">${v.seg.toFixed(0)} s · ${(v.seg/Math.max(v.i,1)).toFixed(1)} s/obra · quedan ~${Math.round(v.seg/Math.max(v.i,1)*(v.n-v.i)/60)} min${v.hace>60?` · <span class="ko">sin novedades hace ${v.hace} s</span>`:''}</div>`:`<h2>Ahora mismo</h2><div class="big mut">En reposo</div><div class="mut">No hay ninguna evaluación corriendo.</div>`;
 const m=e.maquina,g=m.gpu,o=m.ollama,r=m.ram;
 $('maq').innerHTML='<h2>Tu equipo</h2>'+(g?`<div class="row"><span class="lab">GPU ${g.uso}%</span><div class="track"><div class="fill" style="width:${g.uso}%"></div></div></div><div class="row"><span class="lab">VRAM</span><div class="track"><div class="fill" style="width:${100*g.vram/g.vram_total}%"></div></div><span class="val" style="width:auto">${(g.vram/1024).toFixed(1)}/${(g.vram_total/1024).toFixed(0)} GB</span></div><div class="mut">${g.nombre} · ${g.temp} °C</div>`:'<div class="mut">GPU no detectada</div>')+
  (r?`<div class="row"><span class="lab">RAM ${r.uso}%</span><div class="track"><div class="fill" style="width:${r.uso}%"></div></div><span class="val" style="width:auto">${r.libre_gb} GB libres</span></div>`:'')+
  `<div class="mut" style="margin-top:6px">Ollama: ${o===null?'apagado':o.length?o.map(x=>`<span class="pill">${x.modelo} · ${x.gb} GB (${x.vram_gb} GB en GPU)</span>`).join(' '):'sin modelo cargado'}</div>`;
 const rs=e.resultados; $('graf').innerHTML=graf(rs); $('prog').innerHTML=lineas(e.progreso||[]);
 $('tabla').innerHTML='<tr><th>Configuración</th><th>Obras</th><th>Género</th><th>IC 95 %</th><th>Subgénero</th><th>LLM</th><th>s/obra</th><th>Hora</th></tr>'+rs.slice().reverse().map(r=>`<tr><td title="${r.sets}">${r.nombre}</td><td>${r.n}</td><td><b>${pc(r.g)}</b></td><td class="mut">${(100*r.g_lo).toFixed(0)}–${(100*r.g_hi).toFixed(0)}</td><td>${pc(r.s)} <span class="mut">(${r.n_s})</span></td><td>${r.llm}</td><td>${r.seg.toFixed(1)}</td><td class="mut">${r.hora}</td></tr>`).join('');
 const c=e.corpus; $('corpus').innerHTML=`<div class="mut">${c.total} obras · entrenamiento ${c.entrenamiento} · validación ${c.validacion} · prueba ${c.prueba}</div><div style="margin:8px 0 4px"><b>Por tipo</b></div>`+barras(c.tipos,Math.max(...Object.values(c.tipos),1))+`<div style="margin:8px 0 4px"><b>Por género</b></div>`+barras(c.generos,Math.max(...Object.values(c.generos),1));
 $('ultimas').innerHTML=v&&v.ultimas&&v.ultimas.length?v.ultimas.slice().reverse().map(x=>`<div class="row"><span class="${x.g===x.pg?'ok':'ko'}">${x.g===x.pg?'✓':'✗'}</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${x.titulo}">${x.titulo}</span><span class="mut">${x.g}${x.g===x.pg?'':' → '+x.pg}</span></div>`).join(''):'<div class="mut">Aparecerán aquí cuando corra una evaluación nueva.</div>';
 }catch(err){$('sub').textContent='Sin conexión con el panel: '+err}}
ciclo();setInterval(ciclo,3000);
</script></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/estado"):
            cuerpo, tipo = json.dumps({"vivo": vivo(), "corpus": corpus(), "resultados": resultados(), "progreso": progreso(), "maquina": maquina()}, ensure_ascii=False).encode("utf-8"), "application/json"
        else:
            cuerpo, tipo = PAGINA.encode("utf-8"), "text/html"
        self.send_response(200)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)


if __name__ == "__main__":
    print(f"Panel en http://localhost:{PUERTO}  (Ctrl+C para cerrar)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PUERTO), H).serve_forever()
