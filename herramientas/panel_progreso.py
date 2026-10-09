"""Panel en vivo del entrenamiento y la evaluación del clasificador (se abre en el navegador, se actualiza solo).

    python herramientas/panel_progreso.py RAIZ [--log FICHERO] [--puerto 8765]

RAIZ es la carpeta con `enes/corpus` (corpus de pruebas) y `enes/resultados` (lo que escribe evaluar_corpus.py). Muestra: lo que está corriendo ahora (barra, acierto parcial,
tiempo restante, últimas obras), el corpus, una tabla y un gráfico con todas las configuraciones medidas (con intervalo de Wilson al 95 %) y el estado de la GPU y de Ollama.
Con varias etiquetas por obra (1.13 en adelante) añade el cuadro «Etiquetas múltiples» (la etiqueta real entre las predichas, etiquetas por obra, precisión, exhaustividad, Jaccard, pares de géneros
que se dan juntos) y, si hay carpetas en `enes/entrenamiento/*/` (las crea `herramientas/entrenador/entrenar.py`), el cuadro «Entrenamiento del LLM»: barra de progreso, curva de pérdida,
VRAM, tiempo que queda y resultado en la validación. Solo lee ficheros: no toca nada y solo escucha en localhost.
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
from metricas_etiquetas import etiquetas_multiples, metricas  # noqa: E402

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


_VISTO: dict = {}          # paso -> cuándo se vio por primera vez en curso (si plan.json no trae `inicio`)


def plan() -> list[dict]:
    """Los pasos del proyecto (`enes/plan.json`: [{id, titulo, estado: hecho|en curso|pendiente|bloqueado, detalle, progreso?}]); lo escribe quien trabaja en ello. Algunos pasos se completan solos con lo que hay en disco."""
    pasos = leer(RAIZ / "enes" / "plan.json", [])
    d = descargas()
    meta = leer(RAIZ / "enes" / "corpus" / "biblioteca" / "metadatos.json", {})
    for p in pasos:
        if p["id"] == "montar" and d["total"] and p["estado"] == "en curso":
            base = RAIZ / "enes" / "corpus" / "biblioteca"                 # el importador escribe los metadatos al final: mientras tanto se cuentan los ficheros ya copiados
            copiados = max(0, sum(1 for x in base.rglob("*") if x.is_file() and "portadas" not in x.parts and x.suffix not in (".json", ".npz")) - d["biblioteca_propia"])
            p["progreso"] = min(1.0, copiados / d["total"])
            p["detalle"] = f"{copiados} de {d['total']} ficheros copiados y clasificados en el corpus (los metadatos se guardan al final)"
        if p["id"] in ("base", "evaluar") and p["estado"] == "en curso":                # una evaluación corriendo: su avance (obras clasificadas de las de prueba)
            v = leer(RAIZ / "enes" / "resultados" / "_vivo.json", None)
            if v and time.time() - v["t"] < 600 and v.get("n"):
                p["progreso"] = v["i"] / v["n"]
                p["detalle"] = f"{v['nombre']}: {v['i']} de {v['n']} obras · género {100 * v['aciertos'] / max(v['i'], 1):.1f} % (acierto parcial)"
        if p["id"] == "entrenar" and p["estado"] == "en curso":                       # el entrenamiento cuenta sus propios pasos (el más reciente)
            ests = sorted((RAIZ / "enes" / "entrenamiento").glob("*/estado.json"), key=lambda q: q.stat().st_mtime)
            e = leer(ests[-1], {}) if ests else {}
            if e.get("pasos_total"):
                est_run = entrenamiento_de(ests[-1].parent)
                if est_run.get("seg_paso") is not None:                                    # (hasta tener 3 pasos no hay ritmo fiable)
                    p["quedan_seg"] = round(est_run["quedan_min"] * 60)
                    p["ritmo"] = f" · {est_run['seg_paso']} s por paso"
                p["progreso"] = (e.get("paso") or 0) / e["pasos_total"]
                p["detalle"] = f"{e.get('fase', '')}: paso {e.get('paso', 0)} de {e['pasos_total']} · pérdida {e.get('loss', '–')} · época {e.get('epoca', '–')} de {e.get('epocas', '–')}"
            elif e.get("fase"):
                p["detalle"] = e["fase"]
        if p["estado"] == "en curso" and p.get("progreso") is not None:           # tiempo que lleva y, por regla de tres con lo avanzado, el que le queda
            ini = p.get("inicio") or _VISTO.setdefault(p["id"], time.time())
            p["seg"] = round(time.time() - ini)
            if "quedan_seg" not in p:                                                  # (el entrenamiento ya trae la suya, por el ritmo de los últimos pasos)
                p["quedan_seg"] = round(p["seg"] * (1 - p["progreso"]) / p["progreso"]) if p["progreso"] > 0.01 else None
    return pasos


def descargas() -> dict:
    """Lo descargado para el corpus (los `*_etiquetas.json` de RAIZ): obras por género, combinaciones de géneros de las que llevan varias etiquetas y por tipo."""
    por_genero, combos, tipos, total = Counter(), Counter(), Counter(), 0
    for nombre, tipo in (("libros_etiquetas.json", "libro"), ("libros2_etiquetas.json", "libro"), ("libros_multi_etiquetas.json", "libro (varias etiquetas)"), ("arxiv_etiquetas.json", "artículo"), ("codigo_etiquetas.json", None)):
        for b in leer(RAIZ / nombre, []):
            total += 1
            tipos[tipo or b.get("tipo", "código")] += 1
            por_genero[b["genero"]] += 1
            if len(b.get("generos") or []) > 1:
                combos[" + ".join(sorted(b["generos"]))] += 1
    meta_propia = leer(RAIZ / "enes" / "corpus" / "biblioteca" / "referencias.json", {})
    return {"total": total, "por_genero": dict(por_genero), "combos": dict(combos.most_common(10)), "tipos": dict(tipos), "multi": sum(combos.values()), "biblioteca_propia": len(meta_propia) or 187}


def etiquetas_res() -> list[dict]:
    """Por cada resultado con varias etiquetas (`pgs` en sus filas): métricas de género y subgénero, cuántas etiquetas predice, y los pares de géneros que se dan juntos."""
    out = []
    for f in sorted((RAIZ / "enes" / "resultados").glob("*.json"), key=lambda p: p.stat().st_mtime):
        if f.name.startswith("_"):
            continue
        r = leer(f, None)
        if not r or not r.get("filas") or not any("pgs" in x for x in r["filas"]):
            continue
        fl = r["filas"]
        m, em = metricas(fl), etiquetas_multiples(fl)
        top1 = sum(x["g"] == x["pg"] for x in fl)
        out.append({"nombre": r["nombre"], "n": len(fl), "top1": top1 / len(fl), "genero": m["genero"], "subgenero": m["subgenero"], "hist": dict(Counter(len(x.get("pgs") or []) for x in fl)),
                    "reales_multiples": em["reales_multiples"], "predichas_multiples": em["predichas_multiples"],
                    "pares": [[a, b, c] for (a, b), c in sorted(em["coocurrencia"].items(), key=lambda kv: -kv[1])[:8]], "llm": r["modelo_llm"] if r["llm"] else "—", "hora": time.strftime("%H:%M", time.localtime(f.stat().st_mtime))})
    return out


def entrenamiento_de(d: Path) -> dict:
    """Estado de un entrenamiento (`estado.json`) con el tiempo que queda calculado por el ritmo de los últimos 10 pasos de `registro.jsonl` (el que escribe el entrenador cuenta también la carga del modelo)."""
    est = leer(d / "estado.json", {})
    try:
        pasos = [x for x in (json.loads(l) for l in (d / "registro.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()) if x.get("tipo") == "paso"]
    except (OSError, ValueError):
        pasos = []
    if len(pasos) >= 3 and est.get("pasos_total") and est.get("fase") == "entrenando":
        rec = pasos[-10:]
        est["seg_paso"] = round((rec[-1]["t"] - rec[0]["t"]) / (len(rec) - 1), 1)
        est["quedan_min"] = round(est["seg_paso"] * (est["pasos_total"] - est.get("paso", 0)) / 60, 1)
    return est


def entrenamiento() -> dict:
    """Los entrenamientos del LLM (`enes/entrenamiento/<nombre>/{estado.json,registro.jsonl,resultado.json}`) y el resumen de los datos con que se entrena (`enes/entrenamiento/datos/resumen.json`)."""
    base = RAIZ / "enes" / "entrenamiento"
    runs = []
    for d in sorted((p for p in base.glob("*") if p.is_dir() and (p / "estado.json").exists()), key=lambda p: (p / "estado.json").stat().st_mtime) if base.exists() else []:
        est = entrenamiento_de(d)
        lineas = []
        try:
            lineas = [json.loads(x) for x in (d / "registro.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        except (OSError, ValueError):
            pass
        pasos = [x for x in lineas if x.get("tipo") == "paso"]
        est["activo"] = est.get("fase") not in ("terminado",) and time.time() - est.get("t", 0) < 900
        runs.append({"nombre": d.name, "estado": est, "pasos": [[x["paso"], x["loss"]] for x in pasos][-400:], "evals": [[x["paso"], x["eval_loss"]] for x in lineas if x.get("tipo") == "eval" and x.get("eval_loss") is not None],
                     "vram": [x.get("vram_mb", 0) for x in pasos][-120:], "resultado": leer(d / "resultado.json", None)})
    return {"runs": runs, "datos": leer(base / "datos" / "resumen.json", None)}


def registro(n: int = 14) -> list[str]:
    """Las últimas líneas del registro (--log) de lo que corre ahora, sin los avisos ruidosos de las librerías."""
    if not (LOG and LOG.exists()):
        return []
    ruido = ("Fetching", "warn", "symlink", "Developer", "Exceeded", "Ignoring", "Got invalid", "HF_TOKEN")
    return [x[:200] for x in LOG.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip() and not any(r in x for r in ruido)][-n:]


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
<div class="card full" id="plancard" hidden><h2>Qué se está haciendo: pasos del proyecto</h2><div id="plan"></div></div>
<div class="card full" id="descard" hidden><h2>Corpus descargado para entrenar y medir</h2><div id="descarga"></div></div>
<div class="card" id="ahora"></div><div class="card" id="maq"></div>
<div class="card full"><h2>Progreso por versión: acierto de género y de subgénero (misma validación, sin LLM salvo que se indique)</h2><div id="prog"></div></div>
<div class="card full"><h2>Configuraciones medidas (acierto de género con IC 95 %)</h2><div id="graf"></div><div style="overflow:auto"><table id="tabla"></table></div></div>
<div class="card full" id="entcard" hidden><h2>Entrenamiento del LLM</h2><div id="entren"></div></div>
<div class="card full" id="etcard" hidden><h2>Etiquetas múltiples: varios géneros y subgéneros por obra</h2><div id="etiq"></div></div>
<div class="card full" id="regcard" hidden><h2>Registro en vivo</h2><pre id="reg" style="margin:0;white-space:pre-wrap;font:12px/1.5 ui-monospace,Consolas,monospace;color:var(--mut)"></pre></div>
<div class="card"><h2>Corpus</h2><div id="corpus"></div></div><div class="card"><h2>Últimas obras evaluadas</h2><div id="ultimas"></div></div>
</div>
<script>
const $=id=>document.getElementById(id), pc=x=>(100*x).toFixed(1)+' %';
function barras(d,max,w){return Object.entries(d).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<div class="row"><span class="lab" style="width:${w||96}px" title="${k}">${k}</span><div class="track"><div class="fill" style="width:${100*v/max}%"></div></div><span class="val">${v}</span></div>`).join('')}
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
function curva(ps,evs){if(!ps.length)return '<div class="mut">Aún no hay pasos registrados.</div>';const W=1040,H=230,L=46,R=24,T=14,B=26,xm=Math.max(...ps.map(p=>p[0]),...evs.map(p=>p[0]),1),all=ps.map(p=>p[1]).concat(evs.map(p=>p[1])),ym=Math.max(...all)*1.05,x=v=>L+v/xm*(W-L-R),y=v=>T+(1-v/ym)*(H-T-B);
 let s=`<svg viewBox="0 0 ${W} ${H}" width="100%">`;for(let t=0;t<=4;t++){const v=ym*t/4;s+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--bd)"/><text x="${L-6}" y="${y(v)+4}" text-anchor="end">${v.toFixed(2)}</text>`}
 s+=`<path d="${ps.map((p,i)=>(i?'L':'M')+x(p[0])+','+y(p[1])).join(' ')}" fill="none" stroke="var(--ac)" stroke-width="2"/>`;
 if(evs.length){s+=`<path d="${evs.map((p,i)=>(i?'L':'M')+x(p[0])+','+y(p[1])).join(' ')}" fill="none" stroke="var(--ok)" stroke-width="2.5"/>`+evs.map(p=>`<circle cx="${x(p[0])}" cy="${y(p[1])}" r="4" fill="var(--ok)"/>`).join('')}
 s+=`<text x="${W-R}" y="${H-6}" text-anchor="end" class="m">paso ${xm}</text></svg><div class="mut"><span style="color:var(--ac)">●</span> pérdida de entrenamiento (media de un paso) &nbsp; <span style="color:var(--ok)">●</span> pérdida en validación</div>`;return s}
function spark(v){if(!v.length)return '';const W=300,H=40,lo=Math.min(...v),m=Math.max(...v,lo+1),s=v.map((a,i)=>(i?'L':'M')+(i*W/Math.max(v.length-1,1))+','+(H-4-(a-lo)/(m-lo)*(H-8))).join(' ');return `<svg viewBox="0 0 ${W} ${H}" width="300" height="40"><path d="${s}" fill="none" stroke="var(--ac)" stroke-width="1.5"/></svg>`}
function pintaEntren(en){const rs=en.runs||[],d=en.datos;$('entcard').hidden=!(rs.length||d);if(rs.length===0&&!d)return;let h='';
 if(d)h+=`<div class="mut" style="margin-bottom:8px">Datos: <b>${d.obras}</b> obras (${d.con_varias_etiquetas} con varias etiquetas de género) · <b>${d.ejemplos_train}</b> ejemplos de entrenamiento (${Object.entries(d.por_tarea).map(([k,v])=>k+' '+v).join(', ')}) y ${d.ejemplos_val} de validación · ~${(d.tokens_aprox*1/1000).toFixed(0)} k tokens · prompt con ${d.vecinos} vecinos</div>`;
 rs.slice().reverse().forEach((r,i)=>{const e=r.estado,fin=e.fase==='terminado';
  h+=`<div style="border-top:${i?'1px solid var(--bd)':'0'};padding-top:${i?10:0}px;margin-top:${i?10:0}px"><div class="row"><b>${r.nombre}</b><span class="pill">${e.modelo||''}</span><span class="pill">${e.fase||''}</span>${e.activo?'<span class="pulse"></span>':''}<span class="mut">${e.gpu||''}</span></div>`;
  if(e.pasos_total){const p=e.paso||0;h+=`<div class="row"><div class="track"><div class="fill" style="width:${100*p/e.pasos_total}%"></div></div><span>${p} / ${e.pasos_total}</span>${tiempos(e.seg,fin||e.quedan_min==null?null:e.quedan_min*60)}</div><div class="mut">época ${e.epoca||'–'} de ${e.epocas||'–'} · pérdida <b>${e.loss??'–'}</b>${e.quedan_min!=null&&!fin?` · quedan ~${e.quedan_min} min`:''} · ${(e.seg/60).toFixed(0)} min de entrenamiento · lr ${e.lr_inicial||e.lr||''} · rango LoRA ${e.rango||''}</div>`}
  h+=curva(r.pasos,r.evals);if(r.vram.length)h+=`<div class="row"><span class="mut">VRAM (MB) por paso</span>${spark(r.vram)}<span class="mut">${r.vram[r.vram.length-1]} MB</span></div>`;
  if(r.resultado)h+=`<div style="margin-top:6px">Resultado en validación (generación libre, ${r.resultado.ejemplos} ejemplos): JSON válido <b>${pc(r.resultado.json_valido)}</b> · etiqueta principal <b>${pc(r.resultado.principal)}</b> · conjunto exacto <b>${pc(r.resultado.conjunto_exacto)}</b> · ${r.resultado.minutos} min</div>`;
  h+='</div>'});$('entren').innerHTML=h}
function pintaEtiq(es){$('etcard').hidden=!es.length;if(!es.length)return;
 let h='<div style="overflow:auto"><table><tr><th>Configuración</th><th>Acierto 1.ª</th><th>Real entre las predichas</th><th>Etiquetas por obra (pred / real)</th><th>Precisión</th><th>Exhaust.</th><th>Jaccard</th><th>F1 macro</th><th>Subgénero en el conjunto</th><th>Obras con 2+</th></tr>'+
 es.slice().reverse().map(r=>{const g=r.genero,s=r.subgenero;return `<tr><td title="${r.llm}">${r.nombre}</td><td>${pc(r.top1)}</td><td><b>${pc(g.principal_en_conjunto/g.n)}</b> <span class="mut">${(100*g.ic_principal[0]).toFixed(0)}–${(100*g.ic_principal[1]).toFixed(0)}</span></td><td>${g.pred_media.toFixed(2)} / ${g.real_media.toFixed(2)}</td><td>${pc(g.precision)}</td><td>${pc(g.exhaustividad)}</td><td>${pc(g.jaccard)}</td><td>${pc(g.f1_macro)}</td><td>${s.n?pc(s.principal_en_conjunto/s.n):'–'}</td><td>${r.predichas_multiples} <span class="mut">(reales ${r.reales_multiples})</span></td></tr>`}).join('')+'</table></div>';
 const u=es[es.length-1];h+=`<div class="grid" style="margin-top:12px"><div><div style="margin-bottom:4px"><b>Cuántos géneros predice por obra</b> <span class="mut">(${u.nombre})</span></div>${barras(Object.fromEntries(Object.entries(u.hist).map(([k,v])=>[k+(k==='1'?' género':' géneros'),v])),Math.max(...Object.values(u.hist),1))}</div>
  <div><div style="margin-bottom:4px"><b>Géneros que se dan juntos</b> <span class="mut">(obras con ambos)</span></div>${u.pares.length?barras(Object.fromEntries(u.pares.map(p=>[p[0]+' + '+p[1],p[2]])),Math.max(...u.pares.map(p=>p[2]),1),210):'<div class="mut">Ninguna obra con varios géneros todavía.</div>'}</div></div>
  <div class="mut" style="margin-top:8px">«Real entre las predichas» es lo comparable con el acierto de antes (una etiqueta real por obra); las «etiquetas por obra» avisan de si acierta solo porque reparte etiquetas de más. Precisión, exhaustividad y Jaccard miden el conjunto entero.</div>`;$('etiq').innerHTML=h}
function fmin(seg){if(seg==null)return '–';const m=Math.round(seg/60);if(m<1)return '<1 min';return m>=60?Math.floor(m/60)+' h '+String(m%60).padStart(2,'0')+' min':m+' min'}
function tiempos(llevaSeg,quedaSeg){return `<span class="mut">lleva ${fmin(llevaSeg)} · ${quedaSeg==null?'quedan: calculando…':'quedan ~'+fmin(quedaSeg)}</span>`}
function pintaPlan(p){$('plancard').hidden=!p.length;if(!p.length)return;const ic={'hecho':'✓','en curso':'⏳','pendiente':'○','bloqueado':'⛔'},col={'hecho':'var(--ok)','en curso':'var(--ac)','pendiente':'var(--mut)','bloqueado':'var(--ko)'};
 const hechos=p.filter(x=>x.estado==='hecho').length;
 let h=`<div class="row"><div class="track"><div class="fill" style="width:${100*hechos/p.length}%"></div></div><b>${hechos} de ${p.length} pasos</b></div><div style="margin-top:8px">`;
 p.forEach((x,i)=>{const c=col[x.estado]||'var(--mut)';
  h+=`<div style="display:grid;grid-template-columns:34px 1fr;gap:10px;padding:7px 0;border-top:${i?'1px solid var(--bd)':'0'};${x.estado==='pendiente'?'opacity:.62':''}"><div style="width:26px;height:26px;border-radius:50%;border:2px solid ${c};color:${c};display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px">${ic[x.estado]||'○'}</div>
  <div><div><b>${i+1}. ${x.titulo}</b> <span class="pill" style="color:${c}">${x.estado}</span></div><div class="mut">${x.detalle||''}</div>
  ${x.progreso!=null&&x.estado==='en curso'?`<div class="row"><div class="track"><div class="fill" style="width:${100*x.progreso}%"></div></div><span>${(100*x.progreso).toFixed(0)} %</span>${x.seg!=null?tiempos(x.seg,x.quedan_seg):''}</div>`:''}</div></div>`});
 $('plan').innerHTML=h+'</div>'}
function pintaDescarga(d){$('descard').hidden=!d.total;if(!d.total)return;
 $('descarga').innerHTML=`<div class="mut" style="margin-bottom:8px"><b>${d.total}</b> obras descargadas (${Object.entries(d.tipos).map(([k,v])=>k+' '+v).join(' · ')}) · <b>${d.multi}</b> con varias etiquetas de género</div>
 <div class="grid"><div><div style="margin-bottom:4px"><b>Por género</b> <span class="mut">(etiqueta principal)</span></div>${barras(d.por_genero,Math.max(...Object.values(d.por_genero),1),110)}</div>
 <div><div style="margin-bottom:4px"><b>Combinaciones de géneros</b> <span class="mut">(obras con varias etiquetas)</span></div>${Object.keys(d.combos).length?barras(d.combos,Math.max(...Object.values(d.combos),1),210):'<div class="mut">Ninguna todavía.</div>'}</div></div>`}
async function ciclo(){try{const e=await (await fetch('estado')).json();
 $('sub').innerHTML=`<span class="pulse"></span> actualizado ${new Date().toLocaleTimeString()} · se refresca cada 3 s`;
 const v=e.vivo;
 $('ahora').innerHTML=v?`<h2>Ahora mismo</h2><div class="mut">${v.nombre}${v.llm?' · con LLM':' · sin LLM'}</div><div class="big">${v.i}<span class="mut"> / ${v.n}</span></div>
  <div class="row"><div class="track"><div class="fill" style="width:${100*v.i/v.n}%"></div></div><span>${(100*v.i/v.n).toFixed(0)} %</span>${tiempos(v.seg,v.i?v.seg/v.i*(v.n-v.i):null)}</div>
  <div>Acierto parcial de género: <b>${(100*v.aciertos/Math.max(v.i,1)).toFixed(1)} %</b></div>
  ${v.hilos&&v.hilos.maximo>1?`<div>Obras a la vez: <b>${v.hilos.activos}</b> <span class="mut">(límite ${v.hilos.limite} de ${v.hilos.maximo}, se ajusta solo según RAM, VRAM y GPU)</span></div>`:''}
  <div class="mut">${v.seg.toFixed(0)} s · ${(v.seg/Math.max(v.i,1)).toFixed(1)} s/obra · quedan ~${Math.round(v.seg/Math.max(v.i,1)*(v.n-v.i)/60)} min${v.hace>60?` · <span class="ko">sin novedades hace ${v.hace} s</span>`:''}</div>`:`<h2>Ahora mismo</h2><div class="big mut">En reposo</div><div class="mut">No hay ninguna evaluación corriendo.</div>`;
 const m=e.maquina,g=m.gpu,o=m.ollama,r=m.ram;
 $('maq').innerHTML='<h2>Tu equipo</h2>'+(g?`<div class="row"><span class="lab">GPU ${g.uso}%</span><div class="track"><div class="fill" style="width:${g.uso}%"></div></div></div><div class="row"><span class="lab">VRAM</span><div class="track"><div class="fill" style="width:${100*g.vram/g.vram_total}%"></div></div><span class="val" style="width:auto">${(g.vram/1024).toFixed(1)}/${(g.vram_total/1024).toFixed(0)} GB</span></div><div class="mut">${g.nombre} · ${g.temp} °C</div>`:'<div class="mut">GPU no detectada</div>')+
  (r?`<div class="row"><span class="lab">RAM ${r.uso}%</span><div class="track"><div class="fill" style="width:${r.uso}%"></div></div><span class="val" style="width:auto">${r.libre_gb} GB libres</span></div>`:'')+
  `<div class="mut" style="margin-top:6px">Ollama: ${o===null?'apagado':o.length?o.map(x=>`<span class="pill">${x.modelo} · ${x.gb} GB (${x.vram_gb} GB en GPU)</span>`).join(' '):'sin modelo cargado'}</div>`;
 if(e.registro&&e.registro.length){$('regcard').hidden=false;$('reg').textContent=e.registro.join('\\n')+(e.hace_log>90?'\\n(sin novedades hace '+e.hace_log+' s)':'')}
 pintaPlan(e.plan||[]);pintaDescarga(e.descargas||{total:0});pintaEntren(e.entrenamiento||{runs:[],datos:null});pintaEtiq(e.etiquetas||[]);
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
            cuerpo, tipo = json.dumps({"vivo": vivo(), "corpus": corpus(), "resultados": resultados(), "progreso": progreso(), "maquina": maquina(), "plan": plan(), "descargas": descargas(), "etiquetas": etiquetas_res(), "entrenamiento": entrenamiento(), "registro": registro(), "hace_log": round(time.time() - LOG.stat().st_mtime) if LOG and LOG.exists() else None}, ensure_ascii=False).encode("utf-8"), "application/json"
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
