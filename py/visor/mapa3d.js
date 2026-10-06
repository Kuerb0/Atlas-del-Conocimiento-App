/* mapa3d.js — mapa 3D del árbol de la estadística.
   Canvas 2D con proyección en perspectiva escrita a mano: sin librerías, sin WebGL, sin internet.
   Lo incrusta py/construir_visor.py dentro de visor/plantilla.html (marcador MAPA3D_JS).

   Es una galaxia: un núcleo y dos brazos en espiral donde se reparten las ramas (como las galaxias del cerebro, visor/cerebro.js).
   Qué dibuja (de dentro afuera):
     núcleo      el árbol entero (naranja incandescente)
     ramas       preprocesado, modelos, conceptos… orbitan el núcleo; cada una con su color y un anillo con su nº de elementos
     módulos     ficheros / áreas dentro de una rama (solo se ven al entrar en la rama)
     hojas       funciones, conceptos, demos y guías: puntos que orbitan su módulo (punteados = conceptos de método sin código)
     enlaces     arcos finos concepto ↔ función (y demo ↔ función/concepto): se iluminan al señalar un nodo
   Navegación: arrastrar = girar · rueda = acercar · clic en una rama/módulo = entrar · clic en el vacío = salir.
   API (window.crearMapa3D(opciones) devuelve el controlador): ver el final del fichero. */
(function () {
'use strict';

var PAL = {preprocesado: '#45C3B3', seleccion: '#B18CF0', modelos: '#6FA2FF', diagnostico: '#FF8A73', clustering: '#6FCF7B',
           contrastes: '#E5A23A', graficos: '#D4BD45', conceptos: '#F08CC0', demos: '#4FC3DC', guias: '#93A3BD'};
var RESERVA = ['#6FA2FF', '#45C3B3', '#E5A23A', '#F08CC0', '#6FCF7B', '#B18CF0'];
var NUCLEO = [255, 150, 40];
var SANS = 'system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
var MONO = 'ui-monospace,"Cascadia Code","SF Mono",Consolas,"Liberation Mono",monospace';

function aRgb(h) { var n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
function mez(a, b, t) { return [Math.round(a[0] + (b[0] - a[0]) * t), Math.round(a[1] + (b[1] - a[1]) * t), Math.round(a[2] + (b[2] - a[2]) * t)]; }
function rgba(c, a) { return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + (a < 0 ? 0 : a > 1 ? 1 : a).toFixed(3) + ')'; }
function azar(sem) { var a = sem >>> 0; return function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function fib(i, n) { var y = 1 - 2 * (i + .5) / n, r = Math.sqrt(Math.max(0, 1 - y * y)), f = i * 2.399963229728653; return {x: r * Math.cos(f), y: y, z: r * Math.sin(f)}; }
function acota(v, a, b) { return v < a ? a : v > b ? b : v; }
function cuenta(n) {                        /* nº de elementos; un libro (módulo cuyos hijos son capítulos) cuenta como 1: sus capítulos no se amontonan en el mapa */
  if (n.kind === 'hoja') return 1;
  if (n.kind === 'modulo' && n.hijos.length && n.hijos[0].tipo === 'capitulo') return 1;
  return n.hijos.reduce(function (a, c) { return a + cuenta(c); }, 0);
}

var sprites = {};
function sprite(rgb) {                      /* mancha de luz con el centro casi blanco */
  var k = rgb.join(','); if (sprites[k]) return sprites[k];
  var c = document.createElement('canvas'); c.width = c.height = 64; var g = c.getContext('2d');
  var gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  gr.addColorStop(0, rgba(mez(rgb, [255, 255, 255], .6), 1)); gr.addColorStop(.16, rgba(rgb, .9));
  gr.addColorStop(.45, rgba(rgb, .22)); gr.addColorStop(1, rgba(rgb, 0));
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64); return sprites[k] = c;
}
function spriteNucleo(c) {                   /* el núcleo: gradiente del color de la galaxia (naranja por defecto) */
  c = c || NUCLEO; var k = 'n' + c.join(','); if (sprites[k]) return sprites[k];
  var cv = document.createElement('canvas'); cv.width = cv.height = 256; var g = cv.getContext('2d'), B = [255, 255, 255], N = [0, 0, 0];
  var gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  gr.addColorStop(0, rgba(mez(c, B, .9), 1)); gr.addColorStop(.07, rgba(mez(c, B, .5), .98)); gr.addColorStop(.16, rgba(c, .8));
  gr.addColorStop(.38, rgba(mez(c, N, .2), .28)); gr.addColorStop(.7, rgba(mez(c, N, .5), .07)); gr.addColorStop(1, rgba(mez(c, N, .6), 0));
  g.fillStyle = gr; g.fillRect(0, 0, 256, 256); return sprites[k] = cv;
}

window.crearMapa3D = function (o) {
  var NUC = o.color || NUCLEO;          /* color de la galaxia: núcleo, polvo y brazos */
  var canvas = o.canvas, ctx = canvas.getContext('2d'), root = o.root, hojas = o.hojas, estado = o.estado, esDesc = o.esDesc;
  var rnd = azar(42), gauss = function () { return (rnd() + rnd() + rnd() + rnd() - 2) * 1.7321; };
  var W = 800, H = 600, DPR = 1, F = 700, F0 = 700, CX = 400, CY = 300, AJUSTE = 250, vuelo = null, focoPrevio = root, sincro = false;
  var t = 0, pausa = !!o.reducir, autorot = !o.reducir, raf = 0, tPrev = 0, tocado = 0;
  var baja = false, modoCalidad = 'auto', ema = 16, lento = 0, rapido = 0, desdeBaja = 0, cambios = 0;   /* calidad adaptativa: si va lento pasa a «baja» (menos halos, polvo y enlaces; resolución 1×) */
  var cam = {yaw: .62, pitch: .4, dist: 1400, tx: 0, ty: 0, tz: 0}, meta = {yaw: .62, pitch: .4}, zoomMul = 1;
  var vineta = null, hover = null, arrastrando = false, cursor = {x: -99, y: -99}, dentro = false, items = [], sinTocar = 0;
  var cosY = 1, sinY = 0, cosP = 1, sinP = 0, PX = 0, PY = 0, PS = 1, PD = 1;
  var ramas = root.hijos, ESCENA = 600, ESPIRAL = .0095, GIRO = .04;   /* ESPIRAL: cuánto se enrolla el brazo (rad por unidad de radio) · GIRO: rotación rígida, para que los brazos no se deshagan */

  /* ================= construcción del mundo (determinista) ================= */
  var ordenadas = ramas.slice().sort(function (a, b) { return cuenta(b) - cuenta(a); });
  var todas = [];                         /* hojas con su módulo y rama, para recorrerlas rápido */
  var enlaces = [];

  ordenadas.forEach(function (rn, i) {
    /* una galaxia: las ramas (de mayor a menor) se reparten por dos brazos en espiral, de dentro afuera */
    var R = 190 + 340 * Math.pow((i + .5) / ordenadas.length, .85) + 14 * (rnd() - .5), th = (i % 2) * Math.PI + (R - 190) * ESPIRAL + .2 * gauss(), mods = rn.hijos;
    var col = aRgb(rn.colorHex || PAL[rn.rama] || RESERVA[i % RESERVA.length]);
    var p = rn.p3 = {rgb: col, bx: R * Math.cos(th), by: 60 * (rnd() - .5), bz: R * Math.sin(th), w: GIRO * (1 + .1 * (rnd() - .5)), x: 0, y: 0, z: 0, a: 1, mods: mods, n: cuenta(rn)};
    var M = mods.length, rls = mods.map(function (m) { return 16 + 5.6 * Math.sqrt(m.hijos.length); });
    var media = rls.reduce(function (a, b) { return a + b; }, 0) / Math.max(M, 1), sp = 2.15 * media;
    var Rm = M <= 1 ? 0 : M === 2 ? sp / 2 : sp / Math.sqrt(4 * Math.PI / M);
    p.ext = Rm + Math.max.apply(null, rls.concat([20]));
    mods.forEach(function (mn, j) {
      var g = M <= 1 ? {x: 0, y: 0, z: 0} : M === 2 ? {x: j ? 1 : -1, y: 0, z: 0} : fib(j, M), rl = rls[j];
      var q = mn.p3 = {rgb: col, ox: g.x * Rm, oy: g.y * Rm * .8, oz: g.z * Rm, rl: rl, x: 0, y: 0, z: 0, a: 1, rama: rn, visible: M > 1};
      mn.hijos.forEach(function (h) {
        var r = rl * (.3 + .7 * Math.cbrt(rnd())), u = 2 * rnd() - 1, ph = 2 * Math.PI * rnd(), s = Math.sqrt(1 - u * u);
        h.p3 = {rgb: col, lx: r * s * Math.cos(ph), ly: r * u * .8, lz: r * s * Math.sin(ph), w: .1 + .22 * (1 - r / rl) + .05 * rnd(),
                rad: 2.1 + .42 * Math.sqrt(Math.max(h.lineas || 10, 5)), video: !!h.video, hueco: h.tipo === 'concepto' && !(h.funciones || []).length && h.ambito !== 'normativo',
                x: 0, y: 0, z: 0, a: 1, rama: rn, modulo: mn, vec: []};
        todas.push(h);
      });
    });
  });
  ESCENA = Math.max.apply(null, ramas.map(function (r) { return Math.hypot(r.p3.bx, r.p3.bz) + r.p3.ext; }).concat([300]));
  var porNombre = {}; hojas.forEach(function (h) { porNombre[h.rid] = h; });
  hojas.forEach(function (h) {            /* enlaces concepto→función y demo→función/concepto */
    var destinos = h.tipo === 'concepto' ? (h.funciones || []) : h.tipo === 'demo' ? (h.relFunciones || []).concat(h.relConceptos || []) : [];
    destinos.forEach(function (d) { var b = porNombre[d]; if (b && b !== h) { enlaces.push({a: h, b: b}); h.p3.vec.push(b); b.p3.vec.push(h); } });
  });

  /* polvo: núcleo (disco que gira), nubes alrededor de cada rama y estrellas lejanas */
  var grupos = [], polvo = [];
  function grupoDe(rgb, base) { var k = rgb.join(','); for (var g = 0; g < grupos.length; g++) if (grupos[g].k === k) return g;
    grupos.push({k: k, rgb: rgb, ini: 0, fin: 0, base: base}); return grupos.length - 1; }
  function p(g, hub, lx, ly, lz, w, sz, al) { polvo.push({g: g, hub: hub, lx: lx, ly: ly, lz: lz, w: w, sz: sz, al: al}); }
  [NUC, mez(NUC, [255, 255, 255], .4), mez(NUC, [0, 0, 0], .25), mez(NUC, [255, 255, 255], .75)].forEach(function (c, k) {
    var g = grupoDe(c, 0), n = [850, 500, 440, 170][k];
    for (var i = 0; i < n; i++) {
      var r = 38 + 640 * Math.pow(rnd(), 1.65), a = r > 190 && rnd() < .85 ? (rnd() < .5 ? 0 : Math.PI) + (r - 190) * ESPIRAL + .3 * gauss() : 2 * Math.PI * rnd(), esp = (rnd() + rnd() + rnd() - 1.5) * .34 * (30 + r * .22);
      p(g, -1, r * Math.cos(a), esp, r * Math.sin(a), GIRO, .8 + 1.2 * rnd(), .25 + .6 * rnd());
    }
  });
  ramas.forEach(function (rn, i) {
    var q = rn.p3, g = grupoDe(q.rgb, 1), n = 190 + Math.round(q.n * .5);
    for (var k = 0; k < n; k++) {
      var d = (.35 + .85 * rnd()) * q.ext * 1.15, u = 2 * rnd() - 1, ph = 2 * Math.PI * rnd(), s = Math.sqrt(1 - u * u);
      p(g, i, d * s * Math.cos(ph), d * u * .8, d * s * Math.sin(ph), .06 + .22 * rnd(), .7 + 1.1 * rnd(), .2 + .55 * rnd());
    }
  });
  var estrellas = [], gE = grupoDe([170, 190, 255], 2), gB = grupoDe([255, 255, 255], 2);
  for (var e = 0; e < 520; e++) { var uu = 2 * rnd() - 1, pp = 2 * Math.PI * rnd(), ss = Math.sqrt(1 - uu * uu);
    estrellas.push({x: ss * Math.cos(pp), y: uu, z: ss * Math.sin(pp), g: rnd() < .7 ? gE : gB, sz: .5 + 1.1 * rnd(), al: .12 + .45 * rnd()}); }
  var ordenEnl = enlaces.map(function (e, i) { return i; }), rzE = azar(7);
  for (var ie = ordenEnl.length - 1; ie > 0; ie--) { var je = Math.floor(rzE() * (ie + 1)), te = ordenEnl[ie]; ordenEnl[ie] = ordenEnl[je]; ordenEnl[je] = te; }
  polvo.sort(function (a, b) { return a.g - b.g; });
  var N = polvo.length, DL = new Float32Array(N * 5), DG = new Uint8Array(N), DH = new Int16Array(N);
  var DS = new Float32Array(N * 2);
  polvo.forEach(function (d, i) { DL[i * 5] = d.lx; DL[i * 5 + 1] = d.ly; DL[i * 5 + 2] = d.lz; DL[i * 5 + 3] = d.w; DL[i * 5 + 4] = 0;
    DS[i * 2] = d.sz; DS[i * 2 + 1] = d.al; DG[i] = d.g; DH[i] = d.hub; });
  grupos.forEach(function (g, gi) { g.ini = -1; g.fin = -1; });
  for (var di = 0; di < N; di++) { var gg = grupos[DG[di]]; if (gg.ini < 0) gg.ini = di; gg.fin = di + 1; }

  /* ================= cámara ================= */
  function posDe(n) { return n.kind === 'raiz' ? {x: 0, y: 0, z: 0} : n.kind === 'rama' ? n.p3 : n.kind === 'modulo' ? n.p3 : n.p3; }
  function extentDe(n) { return n.kind === 'raiz' ? ESCENA * (ramas.length > 12 ? .86 : .74) : n.kind === 'rama' ? n.p3.ext * 1.2 : n.kind === 'modulo' ? n.p3.rl * 1.9 : 60; }
  function distBase(n) { return extentDe(n) * F0 / AJUSTE; }
  function metaCamara(instante) {
    var f = estado().focus, c = posDe(f);
    var dg = acota(distBase(f) * zoomMul, 70, ESCENA * 5);
    if (instante) { cam.tx = c.x; cam.ty = c.y; cam.tz = c.z; cam.dist = dg; cam.yaw = meta.yaw; cam.pitch = meta.pitch; }
    return {x: c.x, y: c.y, z: c.z, d: dg};
  }
  function proy(x, y, z) {
    x -= cam.tx; y -= cam.ty; z -= cam.tz;
    var x1 = x * cosY + z * sinY, z1 = -x * sinY + z * cosY, y2 = y * cosP + z1 * sinP, z2 = -y * sinP + z1 * cosP, d = z2 + cam.dist;
    if (d < 25) return false;
    var s = F / d; PX = CX + x1 * s; PY = CY - y2 * s; PS = s; PD = d; return true;
  }

  /* ================= mundo en movimiento ================= */
  function mundo() {
    ramas.forEach(function (rn) {
      var q = rn.p3, a = q.w * t, c = Math.cos(a), s = Math.sin(a);
      q.x = q.bx * c + q.bz * s; q.z = -q.bx * s + q.bz * c; q.y = q.by;
      rn.hijos.forEach(function (mn) {
        var m = mn.p3; m.x = q.x + m.ox; m.y = q.y + m.oy; m.z = q.z + m.oz;
        mn.hijos.forEach(function (h) {
          var l = h.p3, b = l.w * t, cb = Math.cos(b), sb = Math.sin(b);
          l.x = m.x + l.lx * cb + l.lz * sb; l.y = m.y + l.ly; l.z = m.z - l.lx * sb + l.lz * cb;
        });
      });
    });
  }
  function nivel(n) {                      /* 1 = dentro del foco · .38 = hermanos · .1 = el resto */
    var f = estado().focus;
    if (n.kind === 'hoja' && n.tipo === 'capitulo') return f === n.parent || f === n ? 1 : 0;      /* los capítulos de un libro solo se ven al pulsar el libro */
    if (f.kind === 'raiz') return 1;
    if (esDesc(n, f) || esDesc(f, n)) return 1;
    if (f.parent && esDesc(n, f.parent)) return .38;
    return .1;
  }

  /* ================= dibujo ================= */
  var rects = [];
  function libre(x, y, w, h) { for (var i = 0; i < rects.length; i++) { var r = rects[i]; if (x < r[0] + r[2] && x + w > r[0] && y < r[1] + r[3] && y + h > r[1]) return false; } return true; }
  function marcaR(x, y, w, h) { rects.push([x, y, w, h]); }
  function fuente(px, peso, mono) { ctx.font = (peso || 500) + ' ' + px + 'px ' + (mono ? MONO : SANS); }
  function espaciado(px) { if ('letterSpacing' in ctx) ctx.letterSpacing = px + 'px'; }
  function texto(s, x, y, color, alpha, align) {
    ctx.textAlign = align || 'left'; ctx.textBaseline = 'middle';
    ctx.lineWidth = 3.2; ctx.lineJoin = 'round'; ctx.strokeStyle = 'rgba(3,4,8,' + (.85 * alpha).toFixed(3) + ')'; ctx.strokeText(s, x, y);
    ctx.fillStyle = rgba(color, alpha); ctx.fillText(s, x, y);
  }
  function recorta(s, max) { return s.length > max ? s.slice(0, max - 1) + '…' : s; }
  function ajustaTexto(s, ancho) {          /* parte en líneas de unos «ancho» caracteres */
    var pal = s.split(' '), out = [], act = '';
    pal.forEach(function (w) { if ((act + ' ' + w).trim().length > ancho && act) { out.push(act); act = w; } else act = (act + ' ' + w).trim(); });
    if (act) out.push(act); return out;
  }

  function dibujar(dt) {
    var st = estado(), focus = st.focus, sel = st.sel, filtrando = st.filtrando, coincide = st.coincide || {}, conCoin = st.conCoincidencia || {};
    var ease = 1 - Math.exp(-dt * 6);
    if (!pausa && !sincro) t += dt * .7;
    if (dentro && !arrastrando) { var h0 = elegir(cursor.x, cursor.y); if (h0 !== hover) { hover = h0; canvas.style.cursor = h0 ? 'pointer' : 'grab'; if (o.alHover) o.alHover(h0); } }
    if (autorot && !pausa && !arrastrando && !hover && !vuelo && !sincro) meta.yaw += dt * .02;
    mundo();
    var g = metaCamara(false), enVuelo = sincro;
    if (sincro) { F = F0; }                  /* la cámara la lleva el cerebro (ver sync) */
    else if (o.reducir) { vuelo = null; cam.tx = g.x; cam.ty = g.y; cam.tz = g.z; cam.dist = g.d; cam.yaw = meta.yaw; cam.pitch = meta.pitch; F = F0; }
    else if (vuelo) {      /* vuelo: aceleración y frenado, el viaje se aleja a mitad de camino, gira y se inclina un poco */
      vuelo.t += dt; var u = Math.min(vuelo.t / vuelo.dur, 1), A = vuelo.a, sn = Math.sin(Math.PI * u);
      var e = u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
      cam.tx = A.x + (g.x - A.x) * e; cam.ty = A.y + (g.y - A.y) * e; cam.tz = A.z + (g.z - A.z) * e;
      cam.dist = Math.exp(Math.log(A.d) + (Math.log(g.d) - Math.log(A.d)) * e) * (1 + .38 * sn);
      meta.yaw = vuelo.yaw0 + vuelo.giro * e; cam.yaw = meta.yaw; cam.pitch = meta.pitch - .1 * sn; F = F0 * (1 + .07 * sn);
      if (u >= 1) { vuelo = null; F = F0; } else enVuelo = true;
    } else {
      F = F0;
      cam.tx += (g.x - cam.tx) * ease; cam.ty += (g.y - cam.ty) * ease; cam.tz += (g.z - cam.tz) * ease;
      cam.dist = Math.exp(Math.log(cam.dist) + (Math.log(g.d) - Math.log(cam.dist)) * ease);
      cam.yaw += (meta.yaw - cam.yaw) * ease; cam.pitch += (meta.pitch - cam.pitch) * ease;
    }
    cosY = Math.cos(cam.yaw); sinY = Math.sin(cam.yaw); cosP = Math.cos(cam.pitch); sinP = Math.sin(cam.pitch);
    var mueve = enVuelo || Math.abs(g.x - cam.tx) + Math.abs(g.y - cam.ty) + Math.abs(g.z - cam.tz) > .4 || Math.abs(Math.log(g.d / cam.dist)) > .003 ||
                Math.abs(meta.yaw - cam.yaw) > .0008 || Math.abs(meta.pitch - cam.pitch) > .0008;

    /* niveles de visibilidad suavizados */
    function suaviza(n, objetivo) { var q = n.p3; q.a += (objetivo - q.a) * ease; return q.a; }
    ramas.forEach(function (rn) {
      var base = nivel(rn); if (filtrando && !conCoin[rn.id]) base *= .35; suaviza(rn, base);
      rn.hijos.forEach(function (mn) { suaviza(mn, nivel(mn));
        mn.hijos.forEach(function (h) { var a = nivel(h); if (filtrando) a *= coincide[h.id] ? 1 : .07; suaviza(h, a); }); });
    });

    /* fondo */
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    ctx.fillStyle = '#03040a'; ctx.fillRect(0, 0, W, H);
    items = []; rects = [];

    /* estrellas lejanas (cielo: solo giran con la cámara) */
    ctx.globalCompositeOperation = 'lighter';
    for (var e = 0; e < estrellas.length; e++) {
      var s = estrellas[e], x1 = s.x * cosY + s.z * sinY, z1 = -s.x * sinY + s.z * cosY, y2 = s.y * cosP + z1 * sinP, z2 = -s.y * sinP + z1 * cosP;
      if (z2 < .12) continue;
      var sx = CX + F * 1.5 * x1 / z2, sy = CY - F * 1.5 * y2 / z2; if (sx < -4 || sx > W + 4 || sy < -4 || sy > H + 4) continue;
      ctx.globalAlpha = s.al; ctx.fillStyle = rgba(grupos[s.g].rgb, 1); ctx.fillRect(sx, sy, s.sz, s.sz);
    }

    /* resplandor del núcleo (detrás de todo lo demás) */
    var nuc = proy(0, 0, 0) ? {x: PX, y: PY, s: PS, d: PD} : null;
    if (nuc) {
      var pulso = 1 + .035 * Math.sin(t * 1.7), rh = acota(300 * nuc.s, 70, 380) * pulso;
      ctx.globalAlpha = focus.kind === 'raiz' ? .92 : .5; ctx.drawImage(spriteNucleo(NUC), nuc.x - rh, nuc.y - rh, rh * 2, rh * 2);
    }

    /* polvo */
    var cualHub = ramas.map(function (r) { return r.p3; }), hubVis = cualHub.map(function (q) {
      if (!proy(q.x, q.y, q.z)) return true; var rd = q.ext * 1.4; if (PD - rd < 60) return true;      /* el polvo llega a ≈ 1.4·ext del centro */
      var rad = rd * F / (PD - rd) + 4; return PX + rad > 0 && PX - rad < W && PY + rad > 0 && PY - rad < H; });
    for (var gi = 0; gi < grupos.length; gi++) {
      var gr = grupos[gi]; if (gr.ini < 0) continue;
      ctx.fillStyle = rgba(gr.rgb, 1);
      for (var i = gr.ini; i < gr.fin; i++) {
        if (DH[i] >= 0 && !hubVis[DH[i]]) continue;
        var hub = DH[i], b = DL[i * 5 + 3] * t, cb = Math.cos(b), sb = Math.sin(b), lx = DL[i * 5], lz = DL[i * 5 + 2];
        var wx = lx * cb + lz * sb, wz = -lx * sb + lz * cb, wy = DL[i * 5 + 1], cx0 = 0, cy0 = 0, cz0 = 0, act = 1;
        if (hub >= 0) { var q = cualHub[hub]; cx0 = q.x; cy0 = q.y; cz0 = q.z; act = q.a; }
        if (!proy(cx0 + wx, cy0 + wy, cz0 + wz)) continue;
        if (PX < -3 || PX > W + 3 || PY < -3 || PY > H + 3) continue;
        var qd = PD / cam.dist, df = acota(1.45 - .6 * qd, .25, 1.15);
        ctx.globalAlpha = DS[i * 2 + 1] * df * (hub >= 0 ? .35 + .65 * act : 1) * (filtrando ? .55 : 1);
        var sz = DS[i * 2] * acota(1 / qd, .7, 1.5); ctx.fillRect(PX - sz / 2, PY - sz / 2, sz, sz);
      }
    }
    ctx.globalAlpha = 1;

    /* brazos de la espiral: dos curvas logarítmicas desde el núcleo, por donde se reparten las ramas */
    ctx.lineWidth = 1.4;
    for (var brazo = 0; brazo < 2; brazo++) {
      ctx.strokeStyle = rgba(NUC, .32 * (focus.kind === 'raiz' ? 1 : .5)); ctx.beginPath(); var seguido = false;
      for (var rr0 = 30; rr0 <= 620; rr0 += 8) { var aa = brazo * Math.PI + (rr0 - 190) * ESPIRAL + GIRO * t;
        if (proy(rr0 * Math.cos(aa), 0, rr0 * Math.sin(aa))) { if (seguido) ctx.lineTo(PX, PY); else ctx.moveTo(PX, PY); seguido = true; } else seguido = false; }
      ctx.stroke();
    }
    if (proy(0, 0, 0)) {                       /* anillos del núcleo */
      [[58, .22], [96, .11]].forEach(function (rr) { ctx.strokeStyle = rgba(NUC, rr[1]); ctx.beginPath();
        for (var k = 0; k <= 72; k++) { var a = k / 72 * Math.PI * 2; if (proy(rr[0] * Math.cos(a), 0, rr[0] * Math.sin(a))) { if (k === 0) ctx.moveTo(PX, PY); else ctx.lineTo(PX, PY); } }
        ctx.stroke(); });
    }

    /* líneas rama → módulo → hoja y enlaces concepto ↔ función (ya no hay líneas rectas del núcleo a las ramas: las reparten los brazos de la espiral) */
    var activo = hover || sel, vec = activo && activo.p3 && activo.kind === 'hoja' ? activo.p3.vec : [];
    var focoRama = focus.kind === 'raiz' ? null : (focus.kind === 'rama' ? focus : focus.parent);
    ctx.lineWidth = 1;
    ramas.forEach(function (rn) {
      var q = rn.p3, entrando = focoRama === rn;
      if (!proy(q.x, q.y, q.z)) return; var hx = PX, hy = PY;
      rn.hijos.forEach(function (mn) {
        var m = mn.p3;
        if (entrando && m.visible) {
          if (proy(m.x, m.y, m.z)) { var mx = PX, my = PY;
            ctx.strokeStyle = rgba(q.rgb, .3 * m.a); ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(mx, my); ctx.stroke();
            ctx.strokeStyle = rgba(q.rgb, .16 * m.a); ctx.beginPath();
            mn.hijos.forEach(function (h) { var l = h.p3; if (l.a > .04 && proy(l.x, l.y, l.z)) { ctx.moveTo(mx, my); ctx.lineTo(PX, PY); } }); ctx.stroke(); }
        } else {
          ctx.strokeStyle = rgba(q.rgb, .05 * (.4 + .6 * q.a)); ctx.beginPath();
          mn.hijos.forEach(function (h) { var l = h.p3; if (l.a > .04 && proy(l.x, l.y, l.z)) { ctx.moveTo(hx, hy); ctx.lineTo(PX, PY); } }); ctx.stroke();
        }
      });
    });
    var lw = ctx.lineWidth;
    var dibujados = 0, MAXE = baja ? 40 : 120;          /* máximo de enlaces tenues por fotograma */
    ordenEnl.forEach(function (ix) { var en = enlaces[ix];
      var A = en.a.p3, B = en.b.p3, aa = Math.min(A.a, B.a), resalta = activo && (en.a === activo || en.b === activo);
      if (!resalta && (aa < .05 || dibujados >= MAXE)) return;
      if (!proy(A.x, A.y, A.z)) return; var ax = PX, ay = PY;
      if (!proy(B.x, B.y, B.z)) return; var bx = PX, by = PY;
      if ((ax < -30 && bx < -30) || (ax > W + 30 && bx > W + 30) || (ay < -30 && by < -30) || (ay > H + 30 && by > H + 30)) return;
      if (!proy((A.x + B.x) * .17, (A.y + B.y) * .17, (A.z + B.z) * .17)) return;
      var al = resalta ? .85 : .075 * aa; if (!resalta) dibujados++;
      if (resalta) { var gdt = ctx.createLinearGradient(ax, ay, bx, by);
        gdt.addColorStop(0, rgba(mez(A.rgb, [255, 255, 255], .35), al)); gdt.addColorStop(1, rgba(mez(B.rgb, [255, 255, 255], .35), al)); ctx.strokeStyle = gdt; }
      else ctx.strokeStyle = rgba(mez(A.rgb, B.rgb, .5), al);
      ctx.lineWidth = resalta ? 1.5 : .8;
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.quadraticCurveTo(PX, PY, bx, by); ctx.stroke();
    });
    ctx.lineWidth = lw;

    /* nodos: se ordenan de lejos a cerca */
    var nodos = [];
    todas.forEach(function (h) { var l = h.p3; if (proy(l.x, l.y, l.z) && PX > -60 && PX < W + 60 && PY > -60 && PY < H + 60) nodos.push({n: h, x: PX, y: PY, s: PS, d: PD, q: l}); });
    ramas.forEach(function (rn) {
      var q = rn.p3; if (proy(q.x, q.y, q.z)) nodos.push({n: rn, x: PX, y: PY, s: PS, d: PD, q: q});
      if (focoRama === rn) rn.hijos.forEach(function (mn) { var m = mn.p3; if (m.visible && proy(m.x, m.y, m.z)) nodos.push({n: mn, x: PX, y: PY, s: PS, d: PD, q: m}); });
    });
    nodos.sort(function (a, b) { return b.d - a.d; });
    var enSel = {}; vec.forEach(function (v) { enSel[v.id] = 1; });

    /* 1.ª pasada: brillos (aditivos) */
    ctx.globalCompositeOperation = 'lighter';
    nodos.forEach(function (nd) {
      var n = nd.n, q = nd.q, qd = nd.d / cam.dist, df = acota(1.4 - .55 * qd, .3, 1.1), a = q.a * df;
      if (n.kind === 'hoja') {
        var r0 = q.rad * nd.s * 1.25, r = Math.max(r0 <= 5 ? r0 : 5 + (r0 - 5) * .22, 1.4); r = Math.min(r, 13); nd.r = r; nd.a = a;
        if (q.hueco || (a < .12 && n !== sel && n !== hover) || (baja && n !== sel && n !== hover && !enSel[n.id])) return;
        var gs = r * (n === sel || n === hover ? 6.5 : 4.2); ctx.globalAlpha = Math.min(1, a * .85) * (n === sel ? 1 : .8);
        ctx.drawImage(sprite(q.rgb), nd.x - gs, nd.y - gs, gs * 2, gs * 2);
      } else if (n.kind === 'rama') {
        var rr = acota(21 * nd.s * (focus === n ? .6 : 1), 9, 24); nd.r = rr; nd.a = a;
        var gs2 = rr * 3.6; ctx.globalAlpha = Math.min(1, a * .75); ctx.drawImage(sprite(q.rgb), nd.x - gs2, nd.y - gs2, gs2 * 2, gs2 * 2);
      } else { var rm = acota(11 * nd.s, 5, 11); nd.r = rm; nd.a = a; ctx.globalAlpha = Math.min(1, a * .5); ctx.drawImage(sprite(q.rgb), nd.x - rm * 3, nd.y - rm * 3, rm * 6, rm * 6); }
    });
    /* núcleo (disco brillante) */
    if (nuc) { var rc = acota(15 * nuc.s * (focus.kind === 'raiz' ? 1 : .8), 7, 20); ctx.globalAlpha = 1; ctx.drawImage(spriteNucleo(NUC), nuc.x - rc * 2.2, nuc.y - rc * 2.2, rc * 4.4, rc * 4.4); }

    /* 2.ª pasada: puntos, anillos y marcas */
    ctx.globalCompositeOperation = 'source-over';
    var pase2 = function (nd) {
      var n = nd.n, q = nd.q, a = nd.a, r = nd.r;
      if (n.kind === 'hoja') {
        var marcado = n === sel || n === hover || enSel[n.id], coin = filtrando && coincide[n.id];
        if (q.hueco) { ctx.strokeStyle = rgba(q.rgb, Math.min(1, a * .95)); ctx.fillStyle = rgba(q.rgb, a * .14); ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(nd.x, nd.y, r, 0, 6.2832); ctx.fill();
          ctx.setLineDash([2, 2]); ctx.stroke(); ctx.setLineDash([]); }
        else { ctx.fillStyle = rgba(mez(q.rgb, [255, 255, 255], .25), Math.min(1, a)); ctx.beginPath(); ctx.arc(nd.x, nd.y, r, 0, 6.2832); ctx.fill(); }
        if (q.video && a > .35) { var vx = nd.x + r * .95 + 2, vy = nd.y - r * .95 - 1, vs = Math.max(3.2, r * .6);      /* ▶ : el concepto tiene vídeo */
          ctx.fillStyle = rgba([255, 255, 255], Math.min(1, a) * .95); ctx.beginPath(); ctx.moveTo(vx - vs * .45, vy - vs * .62); ctx.lineTo(vx + vs * .75, vy); ctx.lineTo(vx - vs * .45, vy + vs * .62); ctx.closePath(); ctx.fill(); }
        if (marcado || coin) { ctx.strokeStyle = rgba([255, 255, 255], n === sel ? 1 : (coin && !marcado ? .55 : .9)); ctx.lineWidth = n === sel ? 2 : 1.2;
          ctx.beginPath(); ctx.arc(nd.x, nd.y, r + (n === sel ? 4.5 + Math.sin(t * 4) * .8 : 3.2), 0, 6.2832); ctx.stroke(); }
        if (a > .25) items.push({n: n, x: nd.x, y: nd.y, r: Math.max(r, 3.5) + 3, d: nd.d});
      } else if (n.kind === 'rama') {
        ctx.fillStyle = 'rgba(3,4,8,' + (.7 * a).toFixed(3) + ')'; ctx.beginPath(); ctx.arc(nd.x, nd.y, r, 0, 6.2832); ctx.fill();
        ctx.strokeStyle = rgba(q.rgb, Math.min(1, a * (hover === n || focus === n ? 1 : .88))); ctx.lineWidth = hover === n ? 2.6 : 1.8; ctx.beginPath(); ctx.arc(nd.x, nd.y, r, 0, 6.2832); ctx.stroke();
        ctx.strokeStyle = rgba(q.rgb, a * .35); ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(nd.x, nd.y, r + 4, 0, 6.2832); ctx.stroke();
        fuente(Math.round(r * .78), 650); espaciado(0); texto(String(filtrando ? (conCoin[n.id] || 0) : q.n), nd.x, nd.y + .5, mez(q.rgb, [255, 255, 255], .55), Math.min(1, a), 'center');
        items.push({n: n, x: nd.x, y: nd.y, r: r + 6, d: nd.d - 500});
      } else {
        ctx.strokeStyle = rgba(q.rgb, a * .95); ctx.lineWidth = 1.4; ctx.fillStyle = 'rgba(3,4,8,' + (.6 * a).toFixed(3) + ')';
        ctx.beginPath(); ctx.arc(nd.x, nd.y, r * .62, 0, 6.2832); ctx.fill(); ctx.stroke();
        ctx.strokeStyle = rgba(q.rgb, a * .35); ctx.beginPath(); ctx.arc(nd.x, nd.y, r * .62 + 3, 0, 6.2832); ctx.stroke();
        items.push({n: n, x: nd.x, y: nd.y, r: r + 4, d: nd.d - 250});
      }
    };
    nodos.forEach(function (nd) { if (nd.n.kind === 'hoja') pase2(nd); });     /* hojas debajo… */
    nodos.forEach(function (nd) { if (nd.n.kind !== 'hoja') pase2(nd); });     /* …ramas y módulos encima */
    if (nuc) { items.push({n: root, x: nuc.x, y: nuc.y, r: 24, d: nuc.d - 800}); }

    ctx.globalAlpha = 1;
    /* etiquetas (con colisiones: ramas y núcleo primero, luego lo señalado y lo más cercano) */
    espaciado(0);
    var ramaNd = nodos.filter(function (x) { return x.n.kind === 'rama'; }).sort(function (a, b) { return a.d - b.d; });   /* las más cercanas mandan */
    if (nuc) marcaR(nuc.x - 52, nuc.y + acota(34 * nuc.s, 20, 44) - 14, 104, 36);      /* el núcleo reserva su sitio */
    ramaNd.forEach(function (nd) {
      var n = nd.n, q = nd.q, a = Math.min(1, q.a + .15), fs = acota(12 * Math.sqrt(nd.s / (F / 1400)), 10, 14) * (W < 600 ? .78 : 1), y0 = nd.y + nd.r + 12;
      fuente(fs, 700); espaciado(1.4);
      var nom = n.nombre.toUpperCase(), w = ctx.measureText(nom).width, fuerteR = n === hover || n === sel;
      var conSub = W >= 600, alto = conSub ? fs * 2.1 : fs + 4;
      if (!libre(nd.x - w / 2 - 3, y0 - fs / 2 - 2, w + 6, alto)) {                    /* ¿choca? prueba encima del nodo; si no, sin subtítulo; si no, se omite */
        var y1 = nd.y - nd.r - 12 - (conSub ? fs : 0);
        if (libre(nd.x - w / 2 - 3, y1 - fs / 2 - 2, w + 6, alto)) y0 = y1;
        else if (libre(nd.x - w / 2 - 3, y0 - fs / 2 - 2, w + 6, fs + 4)) { conSub = false; alto = fs + 4; }
        else if (!fuerteR) return;
      }
      marcaR(nd.x - w / 2 - 3, y0 - fs / 2 - 2, w + 6, alto);
      texto(nom, nd.x, y0, mez(q.rgb, [255, 255, 255], .35), a, 'center');
      var sub = filtrando ? (conCoin[n.id] || 0) + ' de ' + q.n : q.n + (q.n === 1 ? ' elemento' : ' elementos');
      if (conSub) { fuente(fs - 2.5, 500); espaciado(.3); texto(sub, nd.x, y0 + fs + 1, [190, 200, 220], a * .72, 'center'); }
    });
    if (nuc) {
      var fn = acota(12 * Math.sqrt(nuc.s / (F / 1400)), 10, 14), yN = nuc.y + acota(34 * nuc.s, 20, 44);
      fuente(fn, 700); espaciado(2); texto(String(root.nombre || 'Núcleo').toUpperCase(), nuc.x, yN, mez(NUC, [255, 255, 255], .55), .95, 'center');
      fuente(fn - 2.5, 500); espaciado(.4); texto('núcleo de la galaxia', nuc.x, yN + fn + 1, [200, 190, 175], .65, 'center');
    }
    espaciado(0);
    var cola = nodos.filter(function (x) { return x.n.kind !== 'rama' && (x.n.kind === 'modulo' || x.a > .5); }).sort(function (a, b) {
      var pa = (a.n === sel || a.n === hover ? -2 : a.n.kind === 'modulo' ? -1 : 0), pb = (b.n === sel || b.n === hover ? -2 : b.n.kind === 'modulo' ? -1 : 0); return pa - pb || a.d - b.d; });
    var etiquetables = focus.kind !== 'raiz', cont = 0, maximo = focus.kind === 'modulo' ? 60 : 38;
    cola.forEach(function (nd) {
      var n = nd.n, q = nd.q, fuerte = n === sel || n === hover || (activo && enSel[n.id]);
      if (n.kind === 'modulo') {
        var fm = 11.5; fuente(fm, 650); espaciado(1); var s1 = n.nombre.replace(/\.(py|md)$/, '').toUpperCase(); s1 = recorta(s1, 26);
        var wm = ctx.measureText(s1).width, xm = nd.x + nd.r * .62 + 8; if (!libre(xm, nd.y - 8, wm, 16) ) { return; }
        marcaR(xm, nd.y - 8, wm, 16); texto(s1, xm, nd.y, mez(q.rgb, [255, 255, 255], .4), Math.min(1, q.a + .1), 'left'); return;
      }
      var quiere = fuerte || (etiquetables && q.a > .6 && esDesc(n, focus) && cont < maximo) || (filtrando && coincide[n.id] && cont < 30 && etiquetables);
      if (!quiere) return;
      var fs2 = acota(10.5 + (focus.kind === 'modulo' ? 1 : 0), 10, 12); fuente(fs2, fuerte ? 650 : 500, true); espaciado(0);
      var nom2 = recorta(n.nombre, 34), w2 = ctx.measureText(nom2).width, x2 = nd.x + nd.r + 6, y2 = nd.y;
      if (!fuerte && !libre(x2, y2 - 7, w2, 14)) return;
      marcaR(x2, y2 - 7, w2, 14); cont++;
      texto(nom2, x2, y2, fuerte ? [255, 255, 255] : mez(q.rgb, [255, 255, 255], .45), fuerte ? 1 : Math.min(1, q.a * .85), 'left');
    });

    /* tarjeta de la rama / módulo en el que estamos + ayuda */
    espaciado(0);
    if (focus.kind !== 'raiz') {
      var col = (focus.kind === 'rama' ? focus.p3 : focus.p3).rgb || NUCLEO, yy = H - 16, lineas = ajustaTexto(focus.desc || '', 54).slice(0, 3);
      yy -= lineas.length * 15;
      fuente(11, 500); lineas.forEach(function (l, i) { texto(l, 18, yy + i * 15, [175, 186, 206], .8, 'left'); });
      fuente(15, 700); espaciado(.6); texto(focus.nombre.replace(/\.(py|md)$/, ''), 18, yy - 17, mez(col, [255, 255, 255], .35), 1, 'left');
      fuente(10, 700); espaciado(1.6); texto(focus.kind === 'rama' ? 'RAMA' : 'MÓDULO', 18, yy - 36, col, .85, 'left'); espaciado(0);
    } else if (sinTocar > 2.5 || tocado === 0) {
      fuente(11, 500); espaciado(.3); var al = acota(1 - (sinTocar - 2.5) * .0, 0, 1) * .5;
      texto('arrastra para girar · rueda para acercar · clic en una rama para entrar · Ctrl+clic: ir a su módulo principal', W / 2, H - 16, [190, 200, 220], al, 'center'); espaciado(0);
    }

    /* tooltip */
    var h = hover;
    if (h && !arrastrando && h !== root) {
      var q2 = h.p3 || {}, c2 = q2.rgb || NUCLEO, tit = h.nombre.replace(/\.(py|md)$/, ''), cuerpo = ajustaTexto(h.desc || '', 46).slice(0, 3);
      var pie = h.kind === 'hoja' ? (h.ramaNombre + ' · ' + ({funcion: 'función', concepto: (h.funciones || []).length ? 'concepto' : h.ambito === 'normativo' ? 'concepto normativo' : 'concepto sin código', demo: 'demo', doc: 'guía', ejemplo: 'ejemplo'}[h.tipo] || '')) :
                (h.kind === 'rama' ? cuenta(h) + ' elementos · clic: entrar · Ctrl+clic: módulo principal' : cuenta(h) + ' elementos');
      fuente(12, 700, true); var wt = ctx.measureText(recorta(tit, 40)).width; fuente(11, 500); var wc = 0; cuerpo.forEach(function (l) { wc = Math.max(wc, ctx.measureText(l).width); });
      fuente(10.5, 600); var wp = ctx.measureText(pie).width;
      var bw = Math.max(wt, wc, wp) + 26, bh = 16 + 17 + cuerpo.length * 15 + 20, bx = cursor.x + 16, by = cursor.y + 16;
      if (bx + bw > W - 6) bx = cursor.x - bw - 12; if (by + bh > H - 6) by = cursor.y - bh - 12; bx = Math.max(6, bx); by = Math.max(6, by);
      ctx.fillStyle = 'rgba(8,10,18,.94)'; ctx.strokeStyle = rgba(c2, .7); ctx.lineWidth = 1; ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(bx, by, bw, bh, 8); else ctx.rect(bx, by, bw, bh); ctx.fill(); ctx.stroke();
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillStyle = rgba(mez(c2, [255, 255, 255], .4), 1); fuente(12, 700, true); ctx.fillText(recorta(tit, 40), bx + 13, by + 17);
      ctx.fillStyle = 'rgba(200,210,228,.9)'; fuente(11, 500); cuerpo.forEach(function (l, i) { ctx.fillText(l, bx + 13, by + 36 + i * 15); });
      ctx.fillStyle = rgba(c2, .95); fuente(10.5, 600); ctx.fillText(pie, bx + 13, by + bh - 13);
    }

    /* viñeta */
    if (!vineta || vineta.width !== canvas.width || vineta.height !== canvas.height) {       /* se pinta una vez por tamaño */
      vineta = document.createElement('canvas'); vineta.width = canvas.width; vineta.height = canvas.height;
      var vg = vineta.getContext('2d'), v = vg.createRadialGradient(vineta.width / 2, vineta.height / 2, Math.min(vineta.width, vineta.height) * .35, vineta.width / 2, vineta.height / 2, Math.hypot(vineta.width, vineta.height) * .62);
      v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.6)'); vg.fillStyle = v; vg.fillRect(0, 0, vineta.width, vineta.height);
    }
    ctx.globalAlpha = 1; ctx.drawImage(vineta, 0, 0, W, H);
    return mueve;
  }

  /* ================= bucle ================= */
  function fijarCalidad(b) { baja = b; desdeBaja = performance.now(); lento = 0; rapido = 0; ema = b ? 25 : 16; medir(); }
  function calidadAuto(ms, ahora) {
    if (modoCalidad !== 'auto' || ms > 250) return;                 /* pausa o pestaña oculta: no cuenta */
    ema += (ms - ema) * .08;
    if (!baja) { lento = ema > 34 ? lento + 1 : 0; if (lento > 25) { cambios++; fijarCalidad(true); } }
    else if (cambios < 3) { rapido = ema < 19 ? rapido + 1 : 0; if (rapido > 150 && ahora - desdeBaja > 8000) { cambios++; fijarCalidad(false); } }   /* prueba a volver a alta; tras 3 cambios se queda en baja */
  }
  function frame(ahora) {
    raf = 0; var bruto = tPrev ? ahora - tPrev : 16, dt = tPrev ? Math.min(bruto / 1000, .1) : .016; tPrev = ahora; sinTocar += dt;
    calidadAuto(bruto, ahora);
    var mueve = dibujar(dt);
    if (!pausa || mueve || tPrev - tocado < 600) raf = requestAnimationFrame(frame); else tPrev = 0;
  }
  function pedir() { tocado = performance.now(); if (!raf) raf = requestAnimationFrame(frame); }

  function medir() {
    var r = canvas.getBoundingClientRect(); W = Math.max(Math.round(r.width), 200); H = Math.max(Math.round(r.height), 200);
    DPR = baja ? 1 : Math.min(window.devicePixelRatio || 1, 2); canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
    CX = W / 2; CY = H / 2; F0 = F = Math.min(W, H) * 1.05; AJUSTE = Math.min(H * .5, W * (W < 600 ? .46 : .36)) * .92;
    metaCamara(true); pedir();
  }

  /* ================= ratón / táctil ================= */
  function elegir(x, y) {
    var mejor = null, md = 1e9;
    for (var i = 0; i < items.length; i++) { var it = items[i], dx = x - it.x, dy = y - it.y;
      if (dx * dx + dy * dy <= it.r * it.r && it.d < md) { md = it.d; mejor = it; } }
    return mejor ? mejor.n : null;
  }
  var ptrs = {}, inicio = null, moved = 0, pinch0 = 0;
  canvas.style.touchAction = 'none';
  canvas.addEventListener('pointerdown', function (ev) {
    canvas.setPointerCapture && canvas.setPointerCapture(ev.pointerId); ptrs[ev.pointerId] = {x: ev.clientX, y: ev.clientY};
    var ids = Object.keys(ptrs); if (ids.length === 1) { inicio = {x: ev.clientX, y: ev.clientY}; moved = 0; arrastrando = false; }
    else if (ids.length === 2) { var a = ptrs[ids[0]], b = ptrs[ids[1]]; pinch0 = Math.hypot(a.x - b.x, a.y - b.y); }
    sinTocar = 0; pedir();
  });
  canvas.addEventListener('pointermove', function (ev) {
    var r = canvas.getBoundingClientRect(); cursor.x = ev.clientX - r.left; cursor.y = ev.clientY - r.top; dentro = true;
    var p0 = ptrs[ev.pointerId];
    if (p0) {
      var ids = Object.keys(ptrs), dx = ev.clientX - p0.x, dy = ev.clientY - p0.y; p0.x = ev.clientX; p0.y = ev.clientY;
      if (ids.length === 2) { var a = ptrs[ids[0]], b = ptrs[ids[1]], d = Math.hypot(a.x - b.x, a.y - b.y); if (pinch0 > 0) zoomMul = acota(zoomMul * pinch0 / d, .2, 4); pinch0 = d; arrastrando = true; }
      else { moved += Math.abs(dx) + Math.abs(dy); if (moved > 5) arrastrando = true;
        if (arrastrando) { if (vuelo) { meta.yaw = cam.yaw; vuelo = null; } meta.yaw -= dx * .0065; meta.pitch = acota(meta.pitch + dy * .005, -1.35, 1.35); canvas.style.cursor = 'grabbing'; } }
    }
    if (!arrastrando) { var h = elegir(cursor.x, cursor.y); if (h !== hover) { hover = h; canvas.style.cursor = h ? 'pointer' : 'grab'; if (o.alHover) o.alHover(h); } }
    sinTocar = 0; pedir();
  });
  function suelta(ev) {
    var fue = ptrs[ev.pointerId]; delete ptrs[ev.pointerId];
    if (fue && Object.keys(ptrs).length === 0 && ev.type === 'pointerup' && !arrastrando) {
      var r = canvas.getBoundingClientRect(), n = elegir(ev.clientX - r.left, ev.clientY - r.top);
      if (n) { if (o.alNodo) o.alNodo(n, ev); } else if (o.alFondo) o.alFondo();
    }
    if (Object.keys(ptrs).length === 0) { arrastrando = false; pinch0 = 0; canvas.style.cursor = hover ? 'pointer' : 'grab'; }
    pedir();
  }
  canvas.addEventListener('pointerup', suelta); canvas.addEventListener('pointercancel', suelta);
  canvas.addEventListener('pointerleave', function () { dentro = false; if (!Object.keys(ptrs).length) { hover = null; if (o.alHover) o.alHover(null); pedir(); } });
  canvas.addEventListener('wheel', function (ev) {
    ev.preventDefault(); if (vuelo) { meta.yaw = cam.yaw; vuelo = null; } zoomMul = acota(zoomMul * Math.exp(ev.deltaY * (ev.deltaMode === 1 ? .04 : .0012)), .2, 4); sinTocar = 0; pedir();
  }, {passive: false});
  canvas.addEventListener('dblclick', function (ev) { ev.preventDefault(); });
  canvas.tabIndex = 0;
  canvas.addEventListener('keydown', function (ev) {
    var k = ev.key, ok = true;
    if (k === 'ArrowLeft') meta.yaw += .12; else if (k === 'ArrowRight') meta.yaw -= .12; else if (k === 'ArrowUp') meta.pitch = acota(meta.pitch - .08, -1.35, 1.35);
    else if (k === 'ArrowDown') meta.pitch = acota(meta.pitch + .08, -1.35, 1.35);
    else if (k === '+' || k === '=') zoomMul = acota(zoomMul * .85, .2, 4); else if (k === '-' || k === '_') zoomMul = acota(zoomMul / .85, .2, 4); else ok = false;
    if (ok) { ev.preventDefault(); pedir(); }
  });

  /* ================= API ================= */
  return {
    pintar: pedir, medir: medir,
    ir: function (n, instante) {
      var prev = focoPrevio; focoPrevio = n; zoomMul = 1;
      if (instante || o.reducir) { vuelo = null; metaCamara(true); }
      else {
        mundo(); var g1 = metaCamara(false);
        var d = Math.abs(Math.log(g1.d / cam.dist)) + Math.hypot(g1.x - cam.tx, g1.y - cam.ty, g1.z - cam.tz) / ESCENA;
        vuelo = {a: {x: cam.tx, y: cam.ty, z: cam.tz, d: cam.dist}, yaw0: cam.yaw, t: 0, dur: 1.25 + .45 * Math.min(1, d / 1.6),
                 giro: (n.depth > prev.depth ? .5 : n.depth < prev.depth ? -.42 : .3)};
        meta.yaw = cam.yaw;
      }
      sinTocar = 0; pedir();
    },
    /* El universo (cerebro.js) maneja la cámara mientras vuela hacia la galaxia o hacia un nodo de dentro, para que este mapa se vea ya durante el vuelo con la misma pose y escala.
       sync({yaw, pitch, px: píxeles por unidad, t: tiempo, tx, ty, tz: centro}) la pone a mano; sync(null) la suelta y la deja donde está (misma pose, sin movimiento). */
    sync: function (s) {
      if (!s) { sincro = false; meta.yaw = cam.yaw; meta.pitch = cam.pitch; sinTocar = 0; pedir(); return; }
      sincro = true; vuelo = null; zoomMul = 1; F = F0; t = s.t;
      cam.tx = s.tx || 0; cam.ty = s.ty || 0; cam.tz = s.tz || 0; cam.yaw = s.yaw; cam.pitch = s.pitch; cam.dist = F0 / s.px; sinTocar = 0; pedir();
    },
    /* Dónde queda el centro del nodo n (unidades del mapa, en el instante tt) y a cuántos px/unidad se ve cuando la cámara está sobre él. */
    camaraDe: function (n, tt) {
      var t0 = t; t = tt; mundo(); var c = posDe(n), r = {x: c.x, y: c.y, z: c.z, px: F0 / acota(distBase(n), 70, ESCENA * 5)}; t = t0; return r;
    },
    geometria: function () { return {extent: extentDe(root), px: AJUSTE / extentDe(root), pxActual: F0 / cam.dist, t: t, yaw: cam.yaw, pitch: cam.pitch}; },   /* tamaño de la galaxia (unidades), escala de la vista general y de la actual (px/unidad) y pose */
    recentrar: function () { meta.yaw = .62; meta.pitch = .4; zoomMul = 1; pedir(); },
    rotacion: function (v) { if (v === undefined) return !pausa; pausa = !v; autorot = !!v; pedir(); return !pausa; },
    pausar: function (v) { pausa = !!v; pedir(); },
    enPausa: function () { return pausa; },
    calidad: function (v) {                /* 'auto' (por defecto) | 'alta' | 'baja'; sin argumento devuelve la actual */
      if (v === undefined) return baja ? 'baja' : 'alta';
      if (v === 'auto') { modoCalidad = 'auto'; cambios = 0; return 'auto'; }
      modoCalidad = 'manual'; fijarCalidad(v === 'baja'); return v; },
    perfil: function (n, zoom) {          /* ms por fotograma (CPU) a un zoom dado; para medir el rendimiento: mapa.perfil(60, 0.5) */
      if (zoom !== undefined) { zoomMul = zoom; metaCamara(true); }
      n = n || 30; var t0 = performance.now(); for (var i = 0; i < n; i++) { dibujar(.016); ctx.getImageData(0, 0, 1, 1); } return +((performance.now() - t0) / n).toFixed(2); },    /* getImageData fuerza a terminar de pintar: mide también la GPU */
    cuenta: cuenta
  };
};
})();
