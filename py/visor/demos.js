/* Demos interactivas del visor (rama «Cómo funciona»). SVG + JavaScript puro, sin internet.
   Cada demo es DEMOS['id'] = function (contenedor) {...}; la clave debe coincidir con DEMOS en construir_visor.py.
   Las fórmulas (t de Student, normal, Kaplan-Meier, MCO) están escritas aquí para no depender de nada. */
var DEMOS = (function () {
'use strict';
var NS = 'http://www.w3.org/2000/svg', D = {};

/* ---------- azar reproducible y distribuciones ---------- */
function semilla(s) { return function () { s |= 0; s = s + 0x6D2B79F5 | 0; var t = Math.imul(s ^ s >>> 15, 1 | s);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function normal(r) { var u = 0; while (u === 0) u = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r()); }
function erfc(x) { var z = Math.abs(x), t = 1 / (1 + 0.5 * z);
  var r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 +
    t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))));
  return x >= 0 ? r : 2 - r; }
function Phi(x) { return 0.5 * erfc(-x / Math.SQRT2); }
function colaNormal(z) { return 0.5 * erfc(Math.abs(z) / Math.SQRT2); }          /* P(Z > |z|) */
function npdf(x, m, s) { var z = (x - m) / s; return Math.exp(-0.5 * z * z) / (s * Math.sqrt(2 * Math.PI)); }
function lgamma(x) { var g = [76.18009172947146, -86.50532032941677, 24.01409824083091, -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
  var y = x, t = x + 5.5; t -= (x + 0.5) * Math.log(t); var s = 1.000000000190015;
  for (var j = 0; j < 6; j++) s += g[j] / ++y; return -t + Math.log(2.5066282746310005 * s / x); }
function betacf(a, b, x) { var FP = 1e-300, qab = a + b, qap = a + 1, qam = a - 1, c = 1, d = 1 - qab * x / qap;
  if (Math.abs(d) < FP) d = FP; d = 1 / d; var h = d;
  for (var m = 1; m <= 300; m++) { var m2 = 2 * m, aa = m * (b - m) * x / ((qam + m2) * (a + m2));
    d = 1 + aa * d; if (Math.abs(d) < FP) d = FP; c = 1 + aa / c; if (Math.abs(c) < FP) c = FP; d = 1 / d; h *= d * c;
    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
    d = 1 + aa * d; if (Math.abs(d) < FP) d = FP; c = 1 + aa / c; if (Math.abs(c) < FP) c = FP; d = 1 / d;
    var del = d * c; h *= del; if (Math.abs(del - 1) < 3e-14) break; }
  return h; }
function ibeta(x, a, b) { if (x <= 0) return 0; if (x >= 1) return 1;
  var bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
  return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b; }
function tCola(t, gl) { return gl > 2000 ? colaNormal(t) : 0.5 * ibeta(gl / (gl + t * t), gl / 2, 0.5); }   /* P(T > |t|); con gl enorme, normal */
function tcdf(t, gl) { var c = tCola(t, gl); return t >= 0 ? 1 - c : c; }
function tpdf(x, gl) { return Math.exp(lgamma((gl + 1) / 2) - lgamma(gl / 2) - 0.5 * Math.log(gl * Math.PI) - (gl + 1) / 2 * Math.log(1 + x * x / gl)); }
function tinv(p, gl) { var lo = -80, hi = 80; for (var i = 0; i < 90; i++) { var m = (lo + hi) / 2; if (tcdf(m, gl) < p) lo = m; else hi = m; } return (lo + hi) / 2; }
/* potencia de un t-test bilateral de dos grupos (aprox. t desplazada, como en el gráfico) */
function potenciaT(d, n, alpha) { var gl = 2 * n - 2, tc = tinv(1 - alpha / 2, gl), nc = d * Math.sqrt(n / 2);
  return 1 - tcdf(tc - nc, gl) + tcdf(-tc - nc, gl); }
function nPara(d, alpha, obj) {            /* búsqueda binaria: la potencia crece con n */
  if (d <= 0 || potenciaT(d, 100000, alpha) < obj) return Infinity;
  var lo = 2, hi = 100000; while (lo < hi) { var m = (lo + hi) >> 1; if (potenciaT(d, m, alpha) >= obj) hi = m; else lo = m + 1; } return lo; }
function media(a) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i]; return s / a.length; }
function varianza(a, m) { var s = 0; for (var i = 0; i < a.length; i++) s += (a[i] - m) * (a[i] - m); return s / (a.length - 1); }

/* ---------- formato ---------- */
function f(x, k) { return isFinite(x) ? x.toFixed(k == null ? 2 : k) : '—'; }
function fp(p) { return p < 0.0001 ? '< 0.0001' : p < 0.001 ? p.toExponential(1) : p.toFixed(3); }
function pct(x, k) { return (100 * x).toFixed(k == null ? 0 : k) + ' %'; }

/* ---------- DOM y SVG ---------- */
function sv(tag, at, padre, texto) { var e = document.createElementNS(NS, tag); for (var k in at) e.setAttribute(k, at[k]);
  if (texto != null) e.textContent = texto; if (padre) padre.appendChild(e); return e; }
function ht(tag, at, padre, texto) { var e = document.createElement(tag); for (var k in at) e.setAttribute(k, at[k]);
  if (texto != null) e.textContent = texto; if (padre) padre.appendChild(e); return e; }
function marcas(a, b, n) { var paso = Math.pow(10, Math.floor(Math.log10((b - a) / (n || 5)))), err = (b - a) / (n || 5) / paso;
  paso *= err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1; var out = [];
  for (var v = Math.ceil(a / paso) * paso; v <= b + paso * 1e-9; v += paso) out.push(Math.abs(v) < paso * 1e-9 ? 0 : v); return out; }
function etiq(v) { var a = Math.abs(v); return a >= 1000 ? v.toFixed(0) : a >= 10 ? (+v.toFixed(1)).toString() : (+v.toFixed(2)).toString(); }

function Lienzo(cont, op) {
  var W = op.w || 360, H = op.h || 200, m = {t: 10, r: 12, b: 30, l: 40};
  for (var k in (op.m || {})) m[k] = op.m[k];
  var svg = sv('svg', {viewBox: '0 0 ' + W + ' ' + H, 'class': 'dm-svg', role: 'img', 'aria-label': op.aria || ''}, cont);
  var o = {svg: svg, W: W, H: H, m: m, logY: !!op.logY};
  o.sx = function (v) { return m.l + (v - o.x0) / (o.x1 - o.x0) * (W - m.l - m.r); };
  o.sy = function (v) { if (o.logY) v = Math.log10(Math.max(v, 1e-300)); return H - m.b - (v - o.y0) / (o.y1 - o.y0) * (H - m.t - m.b); };
  o.nuevo = function (x, y, ejes) {             /* borra y dibuja ejes; x=[a,b], y=[c,d] (en log10 si logY) */
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    o.x0 = x[0]; o.x1 = x[1]; o.y0 = y[0]; o.y1 = y[1]; ejes = ejes || {};
    var g = sv('g', {}, svg);
    if (ejes.y !== false) {
      var ty = o.logY ? (function () { var r = []; for (var e = Math.ceil(o.y0); e <= Math.floor(o.y1); e++) r.push(e); return r; })() : marcas(o.y0, o.y1, ejes.ny || 4);
      ty.forEach(function (v) { var yy = H - m.b - (v - o.y0) / (o.y1 - o.y0) * (H - m.t - m.b);
        sv('line', {x1: m.l, x2: W - m.r, y1: yy, y2: yy, 'class': 'dm-grid'}, g);
        sv('text', {x: m.l - 5, y: yy + 3.5, 'class': 'dm-tick', 'text-anchor': 'end'}, g, o.logY ? (v === 0 ? '1' : '1e' + v) : etiq(v)); });
    }
    sv('line', {x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, 'class': 'dm-eje'}, g);
    if (ejes.x !== false) marcas(o.x0, o.x1, ejes.nx || 6).forEach(function (v) {
      sv('text', {x: o.sx(v), y: H - m.b + 13, 'class': 'dm-tick', 'text-anchor': 'middle'}, g, etiq(v)); });
    if (ejes.xl) sv('text', {x: (m.l + W - m.r) / 2, y: H - 3, 'class': 'dm-etq-eje', 'text-anchor': 'middle'}, g, ejes.xl);
    if (ejes.yl) sv('text', {x: 11, y: (m.t + H - m.b) / 2, 'class': 'dm-etq-eje', 'text-anchor': 'middle',
      transform: 'rotate(-90 11 ' + (m.t + H - m.b) / 2 + ')'}, g, ejes.yl);
    return o;
  };
  o.capa = function () { return sv('g', {}, svg); };
  o.linea = function (xs, ys, cls, padre) { var d = '';
    for (var i = 0; i < xs.length; i++) d += (i ? 'L' : 'M') + o.sx(xs[i]).toFixed(1) + ' ' + o.sy(ys[i]).toFixed(1);
    return sv('path', {d: d, 'class': cls}, padre || svg); };
  o.escalera = function (xs, ys, cls, padre) { var d = 'M' + o.sx(xs[0]).toFixed(1) + ' ' + o.sy(ys[0]).toFixed(1);
    for (var i = 1; i < xs.length; i++) d += 'H' + o.sx(xs[i]).toFixed(1) + 'V' + o.sy(ys[i]).toFixed(1);
    return sv('path', {d: d, 'class': cls}, padre || svg); };
  o.area = function (xs, ys, cls, cond, padre) { var d = '', dentro = false, ini = 0, y0 = o.sy(o.logY ? Math.pow(10, o.y0) : o.y0);
    for (var i = 0; i <= xs.length; i++) { var ok = i < xs.length && (!cond || cond(xs[i]));
      if (ok && !dentro) { d += 'M' + o.sx(xs[i]).toFixed(1) + ' ' + y0.toFixed(1); dentro = true; ini = i; }
      if (ok) d += 'L' + o.sx(xs[i]).toFixed(1) + ' ' + o.sy(ys[i]).toFixed(1);
      if (!ok && dentro) { d += 'L' + o.sx(xs[i - 1]).toFixed(1) + ' ' + y0.toFixed(1) + 'Z'; dentro = false; } }
    return d ? sv('path', {d: d, 'class': cls}, padre || svg) : null; };
  o.vline = function (x, cls, padre) { return sv('line', {x1: o.sx(x), x2: o.sx(x), y1: m.t, y2: H - m.b, 'class': cls}, padre || svg); };
  o.texto = function (x, y, t, at, padre) { var a = {x: x, y: y, 'class': 'dm-txt'}; for (var k in (at || {})) a[k] = at[k]; return sv('text', a, padre || svg, t); };
  return o;
}
function control(padre, c, alCambiar) {
  var fila = ht('label', {'class': 'dm-ctrl'}, padre);
  ht('span', {}, fila, c.etq);
  var inp = ht('input', {type: 'range', min: c.min, max: c.max, step: c.paso, value: c.valor}, fila);
  var fmt = c.fmt || function (v) { return v; }, out = ht('output', {'class': 'dm-val'}, fila, fmt(c.valor));
  inp.addEventListener('input', function () { out.textContent = fmt(+inp.value); alCambiar(); });
  return {valor: function () { return +inp.value; }};
}
function selector(padre, etq, opciones, valor, alCambiar) {
  var fila = ht('label', {'class': 'dm-ctrl'}, padre); ht('span', {}, fila, etq);
  var s = ht('select', {'class': 'dm-sel'}, fila);
  opciones.forEach(function (o) { var op = ht('option', {value: o.v}, s, o.t); if (String(o.v) === String(valor)) op.selected = true; });
  ht('span', {}, fila);
  s.addEventListener('change', alCambiar);
  return {valor: function () { return s.value; }};
}
function casilla(padre, etq, alCambiar) { var l = ht('label', {'class': 'dm-chk'}, padre), i = ht('input', {type: 'checkbox'}, l);
  l.appendChild(document.createTextNode(' ' + etq)); i.addEventListener('change', alCambiar); return {valor: function () { return i.checked; }}; }
function boton(padre, t, fn) { var b = ht('button', {type: 'button', 'class': 'btn'}, padre, t); b.addEventListener('click', fn); return b; }
function leyenda(padre, items) { var l = ht('div', {'class': 'dm-ley'}, padre);
  items.forEach(function (it) { var s = ht('span', {}, l); ht('i', {'class': it[0]}, s); s.appendChild(document.createTextNode(it[1])); }); return l; }
function lectura(padre) { return ht('div', {'class': 'dm-lect', 'aria-live': 'polite'}, padre); }
/* lectura: lista de [texto, negrita?] para no usar innerHTML */
function escribir(el, lineas) { while (el.firstChild) el.removeChild(el.firstChild);
  lineas.forEach(function (ln) { var p = ht('div', {}, el); ln.forEach(function (tr) {
    if (typeof tr === 'string') p.appendChild(document.createTextNode(tr)); else ht('b', {}, p, tr[0]); }); }); }
function alphas() { return [{v: 0.01, t: '0.01'}, {v: 0.05, t: '0.05'}, {v: 0.10, t: '0.10'}]; }

/* ================= 1. Cómo decide un t-test ================= */
D.demo_contraste_t = function (cont) {
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var cD = control(ctr, {etq: 'Diferencia real (en desv. típicas)', min: 0, max: 1.5, paso: 0.05, valor: 0.5, fmt: function (v) { return v.toFixed(2); }}, nueva);
  var cN = control(ctr, {etq: 'n por grupo', min: 5, max: 200, paso: 1, valor: 30}, nueva);
  var sA = selector(ctr, 'alpha', alphas(), 0.05, function () { sim = null; pintar(); });
  var bt = ht('div', {'class': 'dm-bots'}, cont);
  boton(bt, 'Nueva muestra', nueva); boton(bt, 'Repetir 1000 veces', repetir);
  var L1 = Lienzo(cont, {h: 92, m: {l: 64, b: 22, t: 8}, aria: 'Valores de los dos grupos'});
  var L2 = Lienzo(cont, {h: 190, aria: 'Distribución del estadístico t si H0 fuera cierta'});
  leyenda(cont, [['dm-k1', 'grupo A / t observado'], ['dm-k2', 'grupo B / región de rechazo'], ['dm-km', 't si H0 es cierta']]);
  var lec = lectura(cont), r = semilla(11), A = [], B = [], sim = null;
  function nueva() { var n = cN.valor(), d = cD.valor(); A = []; B = [];
    for (var i = 0; i < n; i++) { A.push(normal(r)); B.push(d + normal(r)); } sim = null; pintar(); }
  function prueba(a, b) { var n = a.length, ma = media(a), mb = media(b), sp = Math.sqrt((varianza(a, ma) + varianza(b, mb)) / 2);
    var t = (mb - ma) / (sp * Math.sqrt(2 / n)); return {t: t, gl: 2 * n - 2, p: 2 * tCola(t, 2 * n - 2), ma: ma, mb: mb}; }
  function repetir() { var n = cN.valor(), d = cD.valor(), al = +sA.valor(), rech = 0, rr = semilla(99), a = new Array(n), b = new Array(n);
    for (var k = 0; k < 1000; k++) { for (var i = 0; i < n; i++) { a[i] = normal(rr); b[i] = d + normal(rr); } if (prueba(a, b).p < al) rech++; }
    sim = {tasa: rech / 1000, d: d}; pintar(); }
  function pintar() {
    var al = +sA.valor(), res = prueba(A, B), todos = A.concat(B), lo = Math.min.apply(null, todos), hi = Math.max.apply(null, todos);
    L1.nuevo([lo - 0.3, hi + 0.3], [0, 2], {y: false, nx: 6});
    [[A, 1.45, 'dm-f1', 'A', res.ma], [B, 0.55, 'dm-f2', 'B', res.mb]].forEach(function (g) {
      var capa = L1.capa();
      g[0].forEach(function (v, i) { sv('circle', {cx: L1.sx(v), cy: L1.sy(g[1]) + ((i * 7919) % 13 - 6), r: 2.8, 'class': g[2], 'fill-opacity': 0.55}, capa); });
      sv('line', {x1: L1.sx(g[4]), x2: L1.sx(g[4]), y1: L1.sy(g[1]) - 13, y2: L1.sy(g[1]) + 13, 'class': 'dm-ltinta'}, capa);
      L1.texto(L1.m.l - 6, L1.sy(g[1]) + 4, 'Grupo ' + g[3], {'text-anchor': 'end'});
    });
    var tc = tinv(1 - al / 2, res.gl), lim = Math.max(4.5, Math.abs(res.t) + 0.8), xs = [], ys = [];
    for (var i = 0; i <= 300; i++) { var x = -lim + 2 * lim * i / 300; xs.push(x); ys.push(tpdf(x, res.gl)); }
    L2.nuevo([-lim, lim], [0, 0.45], {xl: 'estadístico t', ny: 3});
    L2.area(xs, ys, 'dm-f2 dm-op35', function (x) { return Math.abs(x) >= tc; });
    L2.area(xs, ys, 'dm-f1 dm-op45', function (x) { return Math.abs(x) >= Math.abs(res.t); });
    L2.linea(xs, ys, 'dm-lm');
    L2.vline(res.t, 'dm-l1');
    var der = res.t < 0;
    L2.texto(L2.sx(res.t) + (der ? 6 : -6), L2.m.t + 12, 't = ' + f(res.t), {'text-anchor': der ? 'start' : 'end'});
    L2.texto(L2.sx(tc) + 4, L2.sy(tpdf(tc, res.gl)) - 14, 'crítico ±' + f(tc), {'class': 'dm-tick'});
    var rech = res.p < al, lin = [['t = ', [f(res.t)], ' con ' + res.gl + ' gl · p = ', [fp(res.p)], ' → ', [rech ? 'se rechaza H0' : 'no se rechaza H0']]];
    if (sim) {
      var teor = sim.d > 0 ? potenciaT(sim.d, cN.valor(), al) : al;
      lin.push(['En 1000 repeticiones se rechazó H0 el ', [pct(sim.tasa, 1)], ' de las veces ',
        sim.d > 0 ? '= potencia (teórica ≈ ' + pct(teor, 0) + ').' : '= error tipo I (debería ser ≈ alpha = ' + al + ').']);
    } else lin.push(['Pulsa «Repetir 1000 veces» para ver con qué frecuencia acierta el test.']);
    escribir(lec, lin);
  }
  nueva();
};

/* ================= 2. Potencia y tamaño muestral ================= */
D.demo_potencia = function (cont) {
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var cD = control(ctr, {etq: 'Efecto (d de Cohen)', min: 0, max: 1.5, paso: 0.05, valor: 0.5, fmt: function (v) { return v.toFixed(2); }}, pintar);
  var cN = control(ctr, {etq: 'n por grupo', min: 5, max: 300, paso: 1, valor: 30}, pintar);
  var sA = selector(ctr, 'alpha', alphas(), 0.05, pintar);
  var L = Lienzo(cont, {h: 210, aria: 'Distribuciones del estadístico bajo H0 y bajo H1'});
  leyenda(cont, [['dm-km', 'H0: sin efecto'], ['dm-k1', 'H1: con efecto · potencia'], ['dm-kg', 'beta'], ['dm-k2', 'alpha']]);
  var lec = lectura(cont);
  function pintar() {
    var d = cD.valor(), n = cN.valor(), al = +sA.valor(), gl = 2 * n - 2, tc = tinv(1 - al / 2, gl), nc = d * Math.sqrt(n / 2);
    var x0 = -4.2, x1 = Math.max(4.5, nc + 4), xs = [], y0 = [], y1 = [];
    for (var i = 0; i <= 400; i++) { var x = x0 + (x1 - x0) * i / 400; xs.push(x); y0.push(tpdf(x, gl)); y1.push(tpdf(x - nc, gl)); }
    L.nuevo([x0, x1], [0, 0.45], {xl: 'estadístico t', ny: 3});
    L.area(xs, y1, 'dm-fm dm-op30', function (x) { return x < tc; });
    L.area(xs, y1, 'dm-f1 dm-op35', function (x) { return x >= tc; });
    L.area(xs, y0, 'dm-f2 dm-op60', function (x) { return Math.abs(x) >= tc; });
    L.linea(xs, y0, 'dm-lm'); L.linea(xs, y1, 'dm-l1'); L.vline(tc, 'dm-lfina');
    L.texto(L.sx(tc) + 4, L.m.t + 10, 'corte ' + f(tc), {'class': 'dm-tick'});
    var pot = potenciaT(d, n, al), n80 = nPara(d, al, 0.8);
    if (d > 0) escribir(lec, [['Potencia = ', [pct(pot, 0)], ' · beta = ', pct(1 - pot, 0), ' · alpha = ' + al],
      ['Para 80 % de potencia con d = ' + d.toFixed(2) + ' hacen falta ', [isFinite(n80) ? n80 + ' por grupo' : 'muchísimos'], ' (tamano_muestral_medias da lo mismo).']]);
    else escribir(lec, [['Sin efecto real la «potencia» es ', [pct(pot, 0)], ' = alpha: solo hay falsos positivos.']]);
  }
  pintar();
};

/* ================= 3. FDR ================= */
D.demo_fdr = function (cont) {
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var cM = control(ctr, {etq: 'Nº de contrastes', min: 20, max: 500, paso: 10, valor: 100}, nueva);
  var cP = control(ctr, {etq: '% con efecto real', min: 0, max: 50, paso: 1, valor: 10, fmt: function (v) { return v + ' %'; }}, nueva);
  var cZ = control(ctr, {etq: 'Tamaño del efecto (z)', min: 1.5, max: 5, paso: 0.1, valor: 3.5, fmt: function (v) { return v.toFixed(1); }}, nueva);
  var sA = selector(ctr, 'alpha / q', alphas(), 0.05, pintar);
  boton(ht('div', {'class': 'dm-bots'}, cont), 'Nuevo experimento', nueva);
  var L = Lienzo(cont, {h: 220, logY: true, m: {l: 44}, aria: 'p-valores ordenados con las rectas de cada criterio'});
  leyenda(cont, [['dm-p1', 'efecto real'], ['dm-pm', 'sin efecto'], ['dm-k3', 'recta BH'], ['dm-k2', 'Bonferroni'], ['dm-km', 'alpha']]);
  var tabla = ht('table', {'class': 'dm-tabla'}, cont), r = semilla(5), datos = [];
  function nueva() { var m = cM.valor(), k = Math.round(m * cP.valor() / 100), z = cZ.valor(); datos = [];
    for (var i = 0; i < m; i++) { var real = i < k, e = (real ? z : 0) + normal(r); datos.push({p: Math.max(2 * colaNormal(e), 1e-300), real: real}); }
    datos.sort(function (a, b) { return a.p - b.p; }); pintar(); }
  function pintar() {
    var m = datos.length, al = +sA.valor(), kbh = 0;
    for (var i = 0; i < m; i++) if (datos[i].p <= (i + 1) / m * al) kbh = i + 1;
    var minLog = Math.max(Math.floor(Math.log10(datos[0].p)), -10);
    L.nuevo([0, m + 1], [minLog, 0], {xl: 'rango del p-valor (1 = el menor)', yl: 'p-valor'});
    var xs = [], ys = []; for (i = 1; i <= m; i++) { xs.push(i); ys.push(i / m * al); }
    L.linea(xs, ys, 'dm-l3');
    L.linea([0.5, m + 0.5], [al / m, al / m], 'dm-l2');
    L.linea([0.5, m + 0.5], [al, al], 'dm-lm');
    var capa = L.capa();
    datos.forEach(function (d, j) { var c = sv('circle', {cx: L.sx(j + 1), cy: L.sy(Math.max(d.p, Math.pow(10, minLog))), r: 3,
      'class': d.real ? 'dm-f1' : 'dm-fm', 'fill-opacity': d.real ? 0.9 : 0.55}, capa);
      sv('title', {}, c, 'rango ' + (j + 1) + ' · p = ' + fp(d.p) + (d.real ? ' · efecto real' : ' · sin efecto')); });
    var reales = datos.filter(function (d) { return d.real; }).length;
    function fila(nombre, rech) { var desc = 0, falsos = 0, ok = 0;
      datos.forEach(function (d, j) { if (rech(d, j)) { desc++; if (d.real) ok++; else falsos++; } });
      return [nombre, desc, falsos, desc ? pct(falsos / desc, 0) : '—', ok + ' de ' + reales]; }
    var filas = [['Criterio', 'Descubrimientos', 'Falsos', '% falsos', 'Efectos reales hallados'],
      fila('Sin corregir', function (d) { return d.p < al; }),
      fila('Bonferroni', function (d) { return d.p < al / m; }),
      fila('Benjamini-Hochberg', function (d, j) { return j < kbh; })];
    while (tabla.firstChild) tabla.removeChild(tabla.firstChild);
    filas.forEach(function (fl, i) { var tr = ht('tr', {}, tabla); fl.forEach(function (c) { ht(i ? 'td' : 'th', {}, tr, String(c)); }); });
  }
  nueva();
};

/* ================= 4. Intervalos de confianza ================= */
D.demo_intervalos = function (cont) {
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var cN = control(ctr, {etq: 'n de cada muestra', min: 5, max: 200, paso: 1, valor: 20}, function () { acum = [0, 0]; nueva(); });
  var sN = selector(ctr, 'Nivel de confianza', [{v: 0.8, t: '80 %'}, {v: 0.9, t: '90 %'}, {v: 0.95, t: '95 %'}, {v: 0.99, t: '99 %'}], 0.95,
    function () { acum = [0, 0]; nueva(); });
  boton(ht('div', {'class': 'dm-bots'}, cont), 'Otras 50 muestras', nueva);
  var L = Lienzo(cont, {h: 300, m: {l: 18, b: 30}, aria: '50 intervalos de confianza frente a la media verdadera'});
  leyenda(cont, [['dm-k1', 'contiene μ'], ['dm-k2', 'no contiene μ'], ['dm-km', 'μ verdadera = 50']]);
  var lec = lectura(cont), r = semilla(3), acum = [0, 0], ivs = [];
  function nueva() { var n = cN.valor(), niv = +sN.valor(), tq = tinv(1 - (1 - niv) / 2, n - 1); ivs = [];
    for (var k = 0; k < 50; k++) { var x = []; for (var i = 0; i < n; i++) x.push(50 + 10 * normal(r));
      var m = media(x), e = tq * Math.sqrt(varianza(x, m) / n); ivs.push([m - e, m, m + e]); }
    var dentro = ivs.filter(function (v) { return v[0] <= 50 && 50 <= v[2]; }).length; acum[0] += dentro; acum[1] += 50; pintar(dentro, niv); }
  function pintar(dentro, niv) {
    var lo = 50, hi = 50; ivs.forEach(function (v) { lo = Math.min(lo, v[0]); hi = Math.max(hi, v[2]); });
    var mg = Math.max(hi - 50, 50 - lo) * 1.08; L.nuevo([50 - mg, 50 + mg], [0, 51], {y: false, xl: 'valor'});
    L.vline(50, 'dm-lm'); var capa = L.capa();
    ivs.forEach(function (v, k) { var ok = v[0] <= 50 && 50 <= v[2], y = L.sy(k + 1);
      var g = sv('g', {}, capa);
      sv('line', {x1: L.sx(v[0]), x2: L.sx(v[2]), y1: y, y2: y, 'class': ok ? 'dm-l1' : 'dm-l2', 'stroke-linecap': 'round'}, g);
      sv('circle', {cx: L.sx(v[1]), cy: y, r: 2.4, 'class': ok ? 'dm-f1' : 'dm-f2'}, g);
      sv('title', {}, g, 'media ' + f(v[1]) + ' · IC [' + f(v[0]) + ', ' + f(v[2]) + ']' + (ok ? '' : ' · NO contiene μ')); });
    escribir(lec, [[[dentro + ' de 50'], ' intervalos contienen μ (' + pct(dentro / 50) + ').'],
      ['Acumulado: ', [pct(acum[0] / acum[1], 1)], ' de ' + acum[1] + ' intervalos (nivel nominal ' + pct(niv) + ').']]);
  }
  nueva();
};

/* ================= 5. Teorema central del límite ================= */
D.demo_tcl = function (cont) {
  var gens = {
    exponencial: function (r) { return -Math.log(1 - r()); },
    uniforme: function (r) { return r(); },
    bimodal: function (r) { return (r() < 0.5 ? -2 : 2) + 0.6 * normal(r); },
    rara: function (r) { return r() < 0.05 ? 1 : 0; },
    lognormal: function (r) { return Math.exp(normal(r)); }
  };
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var sP = selector(ctr, 'Población', [{v: 'exponencial', t: 'Exponencial (asimétrica)'}, {v: 'uniforme', t: 'Uniforme'},
    {v: 'bimodal', t: 'Bimodal'}, {v: 'rara', t: 'Suceso raro (p = 0.05)'}, {v: 'lognormal', t: 'Lognormal (muy asimétrica)'}], 'exponencial', calcular);
  var cN = control(ctr, {etq: 'n (tamaño de cada muestra)', min: 1, max: 100, paso: 1, valor: 5}, calcular);
  boton(ht('div', {'class': 'dm-bots'}, cont), 'Remuestrear', calcular);
  var L1 = Lienzo(cont, {h: 100, m: {b: 22, l: 12}, aria: 'Forma de la población'});
  var L2 = Lienzo(cont, {h: 200, m: {l: 12}, aria: 'Distribución de 2000 medias muestrales'});
  leyenda(cont, [['dm-km', 'población'], ['dm-k1', 'medias de 2000 muestras'], ['dm-k2', 'normal que predice el TCL']]);
  var lec = lectura(cont), r = semilla(21);
  function hist(L, v, lo, hi, nb, cls, curva) {
    var cnt = new Array(nb).fill(0), w = (hi - lo) / nb;
    v.forEach(function (x) { var b = Math.floor((x - lo) / w); if (b >= 0 && b < nb) cnt[b]++; else if (x === hi) cnt[nb - 1]++; });
    var dens = cnt.map(function (c) { return c / (v.length * w); }), top = Math.max.apply(null, dens);
    if (curva) for (var i = 0; i <= 100; i++) top = Math.max(top, curva(lo + (hi - lo) * i / 100));
    L.nuevo([lo, hi], [0, top * 1.1], {y: false, nx: 5});
    var capa = L.capa();
    dens.forEach(function (dd, b) { var x0 = L.sx(lo + b * w) + 0.75, x1 = L.sx(lo + (b + 1) * w) - 0.75;
      sv('rect', {x: x0, y: L.sy(dd), width: Math.max(x1 - x0, 0.5), height: Math.max(L.sy(0) - L.sy(dd), 0), 'class': cls}, capa); });
    if (curva) { var xs = [], ys = []; for (i = 0; i <= 120; i++) { var x = lo + (hi - lo) * i / 120; xs.push(x); ys.push(curva(x)); } L.linea(xs, ys, 'dm-l2'); }
  }
  function calcular() {
    var g = gens[sP.valor()], n = cN.valor(), pob = [];
    for (var i = 0; i < 6000; i++) pob.push(g(r));
    var mu = media(pob), sd = Math.sqrt(varianza(pob, mu)), ord = pob.slice().sort(function (a, b) { return a - b; });
    var lo = ord[Math.floor(0.002 * ord.length)], hi = ord[Math.floor(0.995 * ord.length)];
    if (sP.valor() === 'rara') { lo = -0.5; hi = 1.5; }
    hist(L1, pob, lo, hi, sP.valor() === 'rara' ? 2 : 30, 'dm-fm dm-op60');
    var meds = [];
    for (var k = 0; k < 2000; k++) { var s = 0; for (i = 0; i < n; i++) s += g(r); meds.push(s / n); }
    var se = sd / Math.sqrt(n), mm = media(meds), m3 = 0, m2 = 0;
    meds.forEach(function (x) { m2 += (x - mm) * (x - mm); m3 += Math.pow(x - mm, 3); });
    var asim = (m3 / meds.length) / Math.pow(m2 / meds.length, 1.5);
    var lo2 = Math.min.apply(null, meds), hi2 = Math.max.apply(null, meds);
    if (hi2 - lo2 < 1e-9) { lo2 -= 0.5; hi2 += 0.5; }
    var discreta = sP.valor() === 'rara', nb = discreta ? Math.min(n + 1, 40) : 34;
    hist(L2, meds, lo2, hi2 + (discreta ? 1e-9 : 0), nb, 'dm-f1 dm-op70', function (x) { return npdf(x, mu, se); });
    escribir(lec, [['Asimetría de las medias: ', [f(asim)], ' (0 = simétrica, como la normal). Error estándar teórico σ/√n = ', f(se, 3), '.'],
      [Math.abs(asim) < 0.25 ? 'Con n = ' + n + ' la normal ya describe bien a la media.' :
        'Con n = ' + n + ' la media aún arrastra la asimetría de la población: hace falta más n' + (n >= 30 ? ' (el «n = 30» no basta aquí).' : '.')]]);
  }
  calcular();
};

/* ================= 6. Regresión lineal y atípicos ================= */
D.demo_regresion = function (cont) {
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var cB = control(ctr, {etq: 'Pendiente real', min: -2, max: 2, paso: 0.1, valor: 1, fmt: function (v) { return v.toFixed(1); }}, nueva);
  var cS = control(ctr, {etq: 'Ruido (σ)', min: 0.2, max: 4, paso: 0.1, valor: 1.5, fmt: function (v) { return v.toFixed(1); }}, nueva);
  var cN = control(ctr, {etq: 'n', min: 10, max: 200, paso: 1, valor: 40}, nueva);
  var cO = casilla(ctr, 'Añadir un punto atípico con mucho apalancamiento', pintar);
  boton(ht('div', {'class': 'dm-bots'}, cont), 'Nueva muestra', nueva);
  var L = Lienzo(cont, {h: 230, aria: 'Nube de puntos con la recta real y la recta MCO'});
  leyenda(cont, [['dm-km', 'recta real'], ['dm-k1', 'recta MCO (todos los puntos)'], ['dm-k3', 'MCO sin el atípico'], ['dm-p2', 'atípico']]);
  var lec = lectura(cont), r = semilla(8), X = [], Y = [];
  function nueva() { var b = cB.valor(), s = cS.valor(), n = cN.valor(); X = []; Y = [];
    for (var i = 0; i < n; i++) { var x = 10 * r(); X.push(x); Y.push(2 + b * x + s * normal(r)); } pintar(); }
  function mco(x, y) { var n = x.length, mx = media(x), my = media(y), sxx = 0, sxy = 0, sse = 0, sst = 0;
    for (var i = 0; i < n; i++) { sxx += (x[i] - mx) * (x[i] - mx); sxy += (x[i] - mx) * (y[i] - my); }
    var b1 = sxy / sxx, b0 = my - b1 * mx;
    for (i = 0; i < n; i++) { var e = y[i] - b0 - b1 * x[i]; sse += e * e; sst += (y[i] - my) * (y[i] - my); }
    var s2 = sse / (n - 2), se = Math.sqrt(s2 / sxx), tq = tinv(0.975, n - 2);
    return {b0: b0, b1: b1, r2: 1 - sse / sst, lo: b1 - tq * se, hi: b1 + tq * se, s2: s2, mx: mx, sxx: sxx, n: n}; }
  function pintar() {
    var b = cB.valor(), out = cO.valor(), x = X.slice(), y = Y.slice(), xo = 16, yo = 2 + b * 16 - 14;
    if (out) { x.push(xo); y.push(yo); }
    var a = mco(x, y), sin = mco(X, Y), xmax = out ? 17 : 10.5;
    var ylo = Math.min.apply(null, y), yhi = Math.max.apply(null, y), pad = (yhi - ylo) * 0.08 + 0.5;
    L.nuevo([0, xmax], [ylo - pad, yhi + pad], {xl: 'x', yl: 'y'});
    var capa = L.capa();
    if (x.length <= 60) x.forEach(function (xi, i) { sv('line', {x1: L.sx(xi), x2: L.sx(xi), y1: L.sy(y[i]), y2: L.sy(a.b0 + a.b1 * xi), 'class': 'dm-lres'}, capa); });
    X.forEach(function (xi, i) { sv('circle', {cx: L.sx(xi), cy: L.sy(Y[i]), r: 3, 'class': 'dm-f1', 'fill-opacity': 0.5}, capa); });
    L.linea([0, xmax], [2, 2 + b * xmax], 'dm-lm');
    if (out) L.linea([0, xmax], [sin.b0, sin.b0 + sin.b1 * xmax], 'dm-l3');
    L.linea([0, xmax], [a.b0, a.b0 + a.b1 * xmax], 'dm-l1');
    var lin = [['Pendiente estimada ', [f(a.b1)], ' (IC 95 %: ' + f(a.lo) + ' a ' + f(a.hi) + ') · real ' + f(b, 1) + ' · R² = ', [f(a.r2)]]];
    if (out) {
      var c = sv('circle', {cx: L.sx(xo), cy: L.sy(yo), r: 5, 'class': 'dm-f2 dm-anillo'}, capa);
      sv('title', {}, c, 'atípico: x = 16, y = ' + f(yo));
      var h = 1 / a.n + (xo - a.mx) * (xo - a.mx) / a.sxx, e = yo - a.b0 - a.b1 * xo, cook = e * e / (2 * a.s2) * h / ((1 - h) * (1 - h));
      lin.push(['Sin el atípico: ', [f(sin.b1)], '. Un solo punto mueve la pendiente ' + f(a.b1 - sin.b1) + ' · apalancamiento h = ' + f(h) + ' · Cook = ', [f(cook)],
        cook > 0.5 ? ' (> 0.5: influyente)' : '']);
    }
    escribir(lec, lin);
  }
  nueva();
};

/* ================= 7. Curva logística y odds ratio ================= */
D.demo_logistica = function (cont) {
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var c0 = control(ctr, {etq: 'Intercepto β0', min: -4, max: 4, paso: 0.1, valor: -1, fmt: function (v) { return v.toFixed(1); }}, pintar);
  var c1 = control(ctr, {etq: 'Coeficiente β1', min: -3, max: 3, paso: 0.1, valor: 1.2, fmt: function (v) { return v.toFixed(1); }}, pintar);
  var L = Lienzo(cont, {h: 220, aria: 'Probabilidad predicha según x'});
  leyenda(cont, [['dm-k1', 'p(x) = 1 / (1 + e^−(β0 + β1·x))'], ['dm-k3', 'pendiente máx. ≈ β1/4'], ['dm-pm', 'datos simulados (0/1)']]);
  var lec = lectura(cont), U = [], V = [], J = [], r = semilla(4);
  for (var i = 0; i < 160; i++) { U.push(-5 + 10 * r()); V.push(r()); J.push((r() - 0.5) * 0.06); }
  function p(b0, b1, x) { return 1 / (1 + Math.exp(-(b0 + b1 * x))); }
  function pintar() {
    var b0 = c0.valor(), b1 = c1.valor(), xs = [], ys = [];
    L.nuevo([-5, 5], [-0.08, 1.08], {xl: 'x', yl: 'probabilidad', ny: 4});
    var capa = L.capa();
    U.forEach(function (x, k) { var y = V[k] < p(b0, b1, x) ? 1 : 0;
      sv('circle', {cx: L.sx(x), cy: L.sy(y + (y ? -1 : 1) * Math.abs(J[k])), r: 2.6, 'class': 'dm-fm', 'fill-opacity': 0.55}, capa); });
    for (var k = 0; k <= 200; k++) { var x = -5 + 10 * k / 200; xs.push(x); ys.push(p(b0, b1, x)); }
    L.linea(xs, ys, 'dm-l1');
    var lin = [];
    if (Math.abs(b1) > 1e-9) {
      var x50 = -b0 / b1;
      if (x50 > -5 && x50 < 5) { L.vline(x50, 'dm-lfina');
        L.linea([x50 - 0.9, x50 + 0.9], [0.5 - 0.9 * b1 / 4, 0.5 + 0.9 * b1 / 4], 'dm-l3');
        var arriba = b1 < 0; L.texto(L.sx(x50) + 6, L.sy(arriba ? 0.7 : 0.3), 'p = 0.5 en x = ' + f(x50), {'class': 'dm-tick'}); }
      lin.push(['Odds ratio = e^β1 = ', [f(Math.exp(b1))], ': cada +1 en x multiplica las odds por ' + f(Math.exp(b1)) + '.']);
    } else lin.push(['β1 = 0: odds ratio = 1, x no cambia la probabilidad.']);
    var p0 = p(b0, b1, 0), p1 = p(b0, b1, 1), p4 = p(b0, b1, 4), p5 = p(b0, b1, 5);
    lin.push(['De x = 0 a 1 la probabilidad pasa de ' + f(p0) + ' a ' + f(p1) + ' (', [(p1 - p0 >= 0 ? '+' : '') + f(p1 - p0)],
      '); de x = 4 a 5, de ' + f(p4) + ' a ' + f(p5) + ' (', [(p5 - p4 >= 0 ? '+' : '') + f(p5 - p4)], '). Mismo OR, distinto efecto en p.']);
    lin.push(['Regla de dividir entre 4: el efecto máximo sobre p es ≈ β1/4 = ', [f(b1 / 4)], ' por unidad.']);
    escribir(lec, lin);
  }
  pintar();
};

/* ================= 8. Censura y Kaplan-Meier ================= */
D.demo_censura = function (cont) {
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var cC = control(ctr, {etq: '% de censura (aprox.)', min: 0, max: 80, paso: 5, valor: 40, fmt: function (v) { return v + ' %'; }}, nueva);
  var cN = control(ctr, {etq: 'n', min: 30, max: 400, paso: 10, valor: 150}, nueva);
  boton(ht('div', {'class': 'dm-bots'}, cont), 'Nueva muestra', nueva);
  var L = Lienzo(cont, {h: 220, aria: 'Curvas de supervivencia: verdadera, Kaplan-Meier y quitando censurados'});
  leyenda(cont, [['dm-km', 'verdadera S(t) = e^(−t/10)'], ['dm-k1', 'Kaplan-Meier'], ['dm-k2', 'quitando a los censurados']]);
  var lec = lectura(cont), r = semilla(13), datos = [];
  function nueva() { var q = cC.valor() / 100, lam = 0.1, mu = q > 0 ? lam * q / (1 - q) : 0; datos = [];
    for (var i = 0; i < cN.valor(); i++) { var t = -Math.log(1 - r()) / lam, c = mu > 0 ? -Math.log(1 - r()) / mu : Infinity;
      datos.push({t: Math.min(t, c), e: t <= c ? 1 : 0}); }
    datos.sort(function (a, b) { return a.t - b.t; }); pintar(); }
  function km(ds) { var n = ds.length, S = 1, xs = [0], ys = [1], i = 0;
    while (i < ds.length) { var t = ds[i].t, d = 0, c = 0; while (i < ds.length && ds[i].t === t) { if (ds[i].e) d++; else c++; i++; }
      if (d) { S *= 1 - d / n; xs.push(t); ys.push(S); } n -= d + c; }
    return {xs: xs, ys: ys}; }
  function mediana(c) { for (var i = 0; i < c.ys.length; i++) if (c.ys[i] <= 0.5) return c.xs[i]; return NaN; }
  function pintar() {
    var a = km(datos), ev = km(datos.filter(function (d) { return d.e; })), tmax = 40;
    L.nuevo([0, tmax], [0, 1.02], {xl: 'tiempo', yl: 'S(t)', ny: 4});
    var xs = [], ys = []; for (var k = 0; k <= 100; k++) { xs.push(tmax * k / 100); ys.push(Math.exp(-tmax * k / 1000)); }
    L.linea(xs, ys, 'dm-lm');
    function cortar(c) { var x = c.xs.slice(), y = c.ys.slice(); x.push(Math.min(tmax, Math.max(x[x.length - 1], datos[datos.length - 1].t))); y.push(y[y.length - 1]);
      return {xs: x.map(function (v) { return Math.min(v, tmax); }), ys: y}; }
    var ca = cortar(a), ce = cortar(ev);
    L.escalera(ce.xs, ce.ys, 'dm-l2'); L.escalera(ca.xs, ca.ys, 'dm-l1');
    var capa = L.capa(), j = 0;
    datos.forEach(function (d) { if (d.e || d.t > tmax) return; while (j + 1 < a.xs.length && a.xs[j + 1] <= d.t) j++;
      sv('line', {x1: L.sx(d.t), x2: L.sx(d.t), y1: L.sy(a.ys[j]) - 4, y2: L.sy(a.ys[j]) + 4, 'class': 'dm-l1 dm-fino'}, capa); });
    var cens = datos.filter(function (d) { return !d.e; }).length;
    escribir(lec, [['Mediana verdadera ', [f(10 * Math.LN2, 1)], ' · Kaplan-Meier ', [f(mediana(a), 1)], ' · quitando censurados ', [f(mediana(ev), 1)]],
      [cens + ' de ' + datos.length + ' censurados (' + pct(cens / datos.length) + '). Las marcas verticales sobre la curva azul son los censurados.']]);
  }
  nueva();
};


/* ================= 9. Explorador de distribuciones ================= */
var DISTS = {
  normal: {t: 'Normal', c: true, ps: [['μ (media)', -5, 5, 0.1, 0], ['σ (desv. típica)', 0.2, 4, 0.1, 1]],
    s: function () { return 0; },
    pdf: function (x, p) { return npdf(x, p[0], p[1]); }, m: function (p) { return [p[0], p[1] * p[1]]; },
    r: function (p) { return [p[0] - 4 * p[1], p[0] + 4 * p[1]]; }},
  t: {t: 't de Student', c: true, ps: [['gl (grados de libertad)', 1, 60, 1, 3]],
    s: function (p) { return p[0] > 3 ? 0 : NaN; },
    pdf: function (x, p) { return tpdf(x, p[0]); }, m: function (p) { return [0, p[0] > 2 ? p[0] / (p[0] - 2) : Infinity]; },
    r: function (p) { var q = Math.min(tinv(0.995, p[0]), 12); return [-q, q]; }},
  lognormal: {t: 'Lognormal', c: true, ps: [['μ del log', -1, 2, 0.1, 0], ['σ del log', 0.1, 1.5, 0.05, 0.6]],
    s: function (p) { var e = Math.exp(p[1] * p[1]); return (e + 2) * Math.sqrt(e - 1); },
    pdf: function (x, p) { return x <= 0 ? 0 : npdf(Math.log(x), p[0], p[1]) / x; },
    m: function (p) { var e = Math.exp(p[1] * p[1]); return [Math.exp(p[0] + p[1] * p[1] / 2), (e - 1) * e * Math.exp(2 * p[0])]; },
    r: function (p) { return [0, Math.exp(p[0] + 2.576 * p[1])]; }},
  gamma: {t: 'Gamma', c: true, ps: [['forma k', 0.5, 15, 0.1, 2], ['escala θ', 0.1, 5, 0.1, 1]],
    s: function (p) { return 2 / Math.sqrt(p[0]); },
    pdf: function (x, p) { return x <= 0 ? 0 : Math.exp((p[0] - 1) * Math.log(x) - x / p[1] - lgamma(p[0]) - p[0] * Math.log(p[1])); },
    m: function (p) { return [p[0] * p[1], p[0] * p[1] * p[1]]; },
    r: function (p) { return [0, p[0] * p[1] + 5 * Math.sqrt(p[0]) * p[1]]; }},
  exponencial: {t: 'Exponencial', c: true, ps: [['λ (tasa)', 0.1, 5, 0.05, 1]],
    s: function () { return 2; },
    pdf: function (x, p) { return x < 0 ? 0 : p[0] * Math.exp(-p[0] * x); }, m: function (p) { return [1 / p[0], 1 / (p[0] * p[0])]; },
    r: function (p) { return [0, 5.3 / p[0]]; }},
  invgauss: {t: 'Inversa gaussiana', c: true, ps: [['μ (media)', 0.2, 5, 0.1, 1], ['λ (forma)', 0.2, 20, 0.1, 3]],
    s: function (p) { return 3 * Math.sqrt(p[0] / p[1]); },
    pdf: function (x, p) { return x <= 0 ? 0 : Math.sqrt(p[1] / (2 * Math.PI * x * x * x)) * Math.exp(-p[1] * (x - p[0]) * (x - p[0]) / (2 * p[0] * p[0] * x)); },
    m: function (p) { return [p[0], p[0] * p[0] * p[0] / p[1]]; },
    r: function (p) { return [0, p[0] + 6 * Math.sqrt(p[0] * p[0] * p[0] / p[1])]; }},
  chi2: {t: 'Chi-cuadrado', c: true, ps: [['gl', 1, 40, 1, 4]],
    s: function (p) { return Math.sqrt(8 / p[0]); },
    pdf: function (x, p) { var k = p[0] / 2; return x <= 0 ? 0 : Math.exp((k - 1) * Math.log(x) - x / 2 - lgamma(k) - k * Math.log(2)); },
    m: function (p) { return [p[0], 2 * p[0]]; }, r: function (p) { return [0, p[0] + 5 * Math.sqrt(2 * p[0])]; }},
  beta: {t: 'Beta', c: true, ps: [['α', 0.3, 10, 0.1, 2], ['β', 0.3, 10, 0.1, 5]],
    s: function (p) { var a = p[0], b = p[1]; return 2 * (b - a) * Math.sqrt(a + b + 1) / ((a + b + 2) * Math.sqrt(a * b)); },
    pdf: function (x, p) { return x <= 0 || x >= 1 ? 0 : Math.exp((p[0] - 1) * Math.log(x) + (p[1] - 1) * Math.log(1 - x) + lgamma(p[0] + p[1]) - lgamma(p[0]) - lgamma(p[1])); },
    m: function (p) { var s = p[0] + p[1]; return [p[0] / s, p[0] * p[1] / (s * s * (s + 1))]; }, r: function () { return [0, 1]; }},
  pareto: {t: 'Pareto (cola pesada)', c: true, ps: [['α (cola)', 0.8, 6, 0.1, 2.5], ['xm (mínimo)', 0.5, 5, 0.1, 1]],
    s: function (p) { var a = p[0]; return a > 3 ? 2 * (1 + a) / (a - 3) * Math.sqrt((a - 2) / a) : Infinity; },
    pdf: function (x, p) { return x < p[1] ? 0 : p[0] * Math.pow(p[1], p[0]) / Math.pow(x, p[0] + 1); },
    m: function (p) { var a = p[0], x = p[1]; return [a > 1 ? a * x / (a - 1) : Infinity, a > 2 ? x * x * a / ((a - 1) * (a - 1) * (a - 2)) : Infinity]; },
    r: function (p) { return [0, Math.min(p[1] * Math.pow(0.01, -1 / p[0]), p[1] * 60)]; }},
  uniforme: {t: 'Uniforme', c: true, ps: [['a', -5, 4, 0.1, 0], ['ancho (b − a)', 0.2, 10, 0.1, 1]],
    s: function () { return 0; },
    pdf: function (x, p) { return x >= p[0] && x <= p[0] + p[1] ? 1 / p[1] : 0; }, m: function (p) { return [p[0] + p[1] / 2, p[1] * p[1] / 12]; },
    r: function (p) { return [p[0] - p[1] * 0.25, p[0] + p[1] * 1.25]; }},
  binomial: {t: 'Binomial', c: false, ps: [['n (ensayos)', 1, 60, 1, 10], ['p (éxito)', 0.01, 0.99, 0.01, 0.3]],
    s: function (p) { return (1 - 2 * p[1]) / Math.sqrt(p[0] * p[1] * (1 - p[1])); },
    pdf: function (k, p) { return Math.exp(lgamma(p[0] + 1) - lgamma(k + 1) - lgamma(p[0] - k + 1) + k * Math.log(p[1]) + (p[0] - k) * Math.log(1 - p[1])); },
    m: function (p) { return [p[0] * p[1], p[0] * p[1] * (1 - p[1])]; }, r: function (p) { return [0, p[0]]; }},
  poisson: {t: 'Poisson', c: false, ps: [['λ (media)', 0.1, 30, 0.1, 3]],
    s: function (p) { return 1 / Math.sqrt(p[0]); },
    pdf: function (k, p) { return Math.exp(k * Math.log(p[0]) - p[0] - lgamma(k + 1)); }, m: function (p) { return [p[0], p[0]]; },
    r: function (p) { return [0, Math.ceil(p[0] + 5 * Math.sqrt(p[0]) + 3)]; }},
  nbinom: {t: 'Binomial negativa', c: false, ps: [['r (tamaño)', 0.5, 30, 0.5, 3], ['media', 0.5, 30, 0.5, 4]],
    s: function (p) { var q = p[0] / (p[0] + p[1]); return (2 - q) / Math.sqrt(p[0] * (1 - q)); },
    pdf: function (k, p) { var r = p[0], q = r / (r + p[1]); return Math.exp(lgamma(k + r) - lgamma(k + 1) - lgamma(r) + r * Math.log(q) + k * Math.log(1 - q)); },
    m: function (p) { return [p[1], p[1] + p[1] * p[1] / p[0]]; }, r: function (p) { return [0, Math.ceil(p[1] + 5 * Math.sqrt(p[1] + p[1] * p[1] / p[0]) + 3)]; }},
  bernoulli: {t: 'Bernoulli', c: false, ps: [['p (éxito)', 0.01, 0.99, 0.01, 0.5]],
    s: function (p) { return (1 - 2 * p[0]) / Math.sqrt(p[0] * (1 - p[0])); },
    pdf: function (k, p) { return k === 0 ? 1 - p[0] : k === 1 ? p[0] : 0; }, m: function (p) { return [p[0], p[0] * (1 - p[0])]; },
    r: function () { return [0, 1]; }},
  geometrica: {t: 'Geométrica', c: false, ps: [['p (éxito)', 0.05, 0.95, 0.01, 0.3]],
    s: function (p) { return (2 - p[0]) / Math.sqrt(1 - p[0]); },
    pdf: function (k, p) { return p[0] * Math.pow(1 - p[0], k); }, m: function (p) { return [(1 - p[0]) / p[0], (1 - p[0]) / (p[0] * p[0])]; },
    r: function (p) { return [0, Math.min(60, Math.ceil(Math.log(0.002) / Math.log(1 - p[0])))]; }},
  weibull: {t: 'Weibull', c: true, ps: [['forma k', 0.5, 6, 0.1, 1.5], ['escala λ', 0.2, 5, 0.1, 1]],
    s: function (p) { var g = function (a) { return Math.exp(lgamma(1 + a / p[0])); }, mu = g(1), v = g(2) - mu * mu;
      return (g(3) - 3 * mu * v - mu * mu * mu) / Math.pow(v, 1.5); },
    pdf: function (x, p) { return x <= 0 ? 0 : p[0] / p[1] * Math.pow(x / p[1], p[0] - 1) * Math.exp(-Math.pow(x / p[1], p[0])); },
    m: function (p) { var g1 = Math.exp(lgamma(1 + 1 / p[0])), g2 = Math.exp(lgamma(1 + 2 / p[0])); return [p[1] * g1, p[1] * p[1] * (g2 - g1 * g1)]; },
    r: function (p) { return [0, p[1] * Math.pow(-Math.log(0.003), 1 / p[0])]; }}
};
var DIST_DE_CONCEPTO = {c_distribucion_normal: 'normal', c_distribucion_t_de_student: 't', c_distribucion_lognormal: 'lognormal',
  c_distribucion_gamma: 'gamma', c_distribucion_inversa_gaussiana: 'invgauss', c_distribucion_binomial: 'binomial',
  c_distribucion_de_poisson: 'poisson', c_distribucion_binomial_negativa: 'nbinom', c_distribucion_compuesta_poisson_gamma: 'nbinom',
  c_distribuciones_de_la_clase_a_b_0_y_a_b_1: 'poisson', c_distribuciones_con_colas_pesadas: 'pareto',
  c_familias_parametricas: 'gamma', c_variables_aleatorias_y_distribuciones: 'normal', c_glm_de_conteo_poisson_y_binomial_negativa: 'nbinom',
  c_glm_de_variable_continua_gamma_e_inversa_gaussiana: 'gamma', c_sobredispersion: 'nbinom', c_value_at_risk_var: 'lognormal',
  c_tvar_y_medidas_coherentes_de_riesgo: 'pareto', c_teoria_de_valores_extremos: 'pareto', c_siniestralidad_agregada: 'lognormal',
  c_distribucion_uniforme: 'uniforme', c_distribucion_exponencial: 'exponencial', c_distribucion_de_weibull: 'weibull',
  c_distribucion_de_bernoulli: 'bernoulli', c_distribucion_geometrica: 'geometrica', c_distribuciones_chi_cuadrado_y_f: 'chi2',
  c_ley_de_los_grandes_numeros: 'normal'};
D.demo_distribuciones = function (cont, op) {
  var ini = (op && DIST_DE_CONCEPTO[op.concepto]) || 'normal';
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var sD = selector(ctr, 'Distribución', Object.keys(DISTS).map(function (k) { return {v: k, t: DISTS[k].t}; }), ini, function () { montar(); });
  var cajaP = ht('div', {'class': 'dm-ctrls'}, cont), cajaX = ht('div', {'class': 'dm-ctrls'}, cont);
  var cN = casilla(cont, 'Comparar con la normal de igual media y varianza', pintar);
  var L1 = Lienzo(cont, {h: 200, aria: 'Función de densidad o de probabilidad'});
  var L2 = Lienzo(cont, {h: 120, aria: 'Función de distribución acumulada'});
  leyenda(cont, [['dm-k1', 'densidad / probabilidad'], ['dm-k3', 'P(X ≤ x)'], ['dm-km', 'media'], ['dm-k2', 'normal equivalente']]);
  var lec = lectura(cont), ctrls = [], cx = null;
  function montar() {
    while (cajaP.firstChild) cajaP.removeChild(cajaP.firstChild);
    ctrls = DISTS[sD.valor()].ps.map(function (q) { return control(cajaP, {etq: q[0], min: q[1], max: q[2], paso: q[3], valor: q[4],
      fmt: function (v) { return q[3] >= 1 ? String(v) : v.toFixed(2); }}, pintar); });
    while (cajaX.firstChild) cajaX.removeChild(cajaX.firstChild);
    cx = control(cajaX, {etq: 'x para P(X ≤ x) (% del rango)', min: 0, max: 100, paso: 1, valor: 50, fmt: function (v) { return v + ' %'; }}, pintar);
    pintar();
  }
  function pintar() {
    var d = DISTS[sD.valor()], p = ctrls.map(function (c) { return c.valor(); }), rg = d.r(p), mv = d.m(p), xs = [], ys = [];
    if (!d.c) { rg = [Math.max(0, Math.floor(rg[0])), Math.ceil(rg[1])]; for (var k = rg[0]; k <= rg[1]; k++) { xs.push(k); ys.push(d.pdf(k, p)); } }
    else for (var i = 0; i <= 400; i++) { var x = rg[0] + (rg[1] - rg[0]) * i / 400; xs.push(x); ys.push(d.pdf(x, p)); }
    var acum = [], s = 0;                                         /* CDF numérica */
    for (i = 0; i < xs.length; i++) { s += d.c ? (i ? (ys[i] + ys[i - 1]) / 2 * (xs[i] - xs[i - 1]) : 0) : ys[i]; acum.push(Math.min(s, 1)); }
    var xsel = d.c ? rg[0] + (rg[1] - rg[0]) * cx.valor() / 100 : Math.round(rg[0] + (rg[1] - rg[0]) * cx.valor() / 100);
    var idx = 0; while (idx + 1 < xs.length && xs[idx + 1] <= xsel + 1e-9) idx++;
    var top = Math.max.apply(null, ys.filter(isFinite)) || 1;
    var nor = cN.valor() && isFinite(mv[1]) ? function (x) { return npdf(x, mv[0], Math.sqrt(mv[1])); } : null;
    if (nor && d.c) for (i = 0; i < xs.length; i += 10) top = Math.max(top, nor(xs[i]));
    top = Math.min(top, (d.c ? 6 : 1.1) * (ys.slice().sort(function (a, b) { return a - b; })[Math.floor(ys.length * 0.98)] || top));
    var xpad = d.c ? 0 : 0.6;
    L1.nuevo([rg[0] - xpad, rg[1] + xpad], [0, top * 1.08], {xl: 'x', ny: 3});
    if (d.c) {
      L1.area(xs, ys.map(function (y) { return Math.min(y, top * 1.08); }), 'dm-f3 dm-op35', function (x) { return x <= xsel; });
      L1.linea(xs, ys.map(function (y) { return Math.min(y, top * 1.08); }), 'dm-l1');
    } else {
      var capa = L1.capa(), bw = Math.max(1.5, Math.min(14, (L1.sx(1) - L1.sx(0)) * 0.7));
      xs.forEach(function (k, j) { var r = sv('rect', {x: L1.sx(k) - bw / 2, y: L1.sy(ys[j]), width: bw, height: Math.max(L1.sy(0) - L1.sy(ys[j]), 0),
        'class': k <= xsel ? 'dm-f3' : 'dm-f1', rx: 1.5}, capa); sv('title', {}, r, 'P(X = ' + k + ') = ' + ys[j].toFixed(4)); });
    }
    if (nor) { var nx = [], ny = []; for (i = 0; i <= 200; i++) { var x2 = rg[0] + (rg[1] - rg[0]) * i / 200; nx.push(x2); ny.push(Math.min(nor(x2), top * 1.08)); } L1.linea(nx, ny, 'dm-l2'); }
    if (isFinite(mv[0]) && mv[0] >= rg[0] && mv[0] <= rg[1]) { L1.vline(mv[0], 'dm-lm'); L1.texto(L1.sx(mv[0]) + 4, L1.m.t + 10, 'media ' + f(mv[0]), {'class': 'dm-tick'}); }
    L2.nuevo([rg[0] - xpad, rg[1] + xpad], [0, 1.02], {xl: 'P(X ≤ x)', ny: 2});
    if (d.c) L2.linea(xs, acum, 'dm-l3'); else L2.escalera(xs, acum, 'dm-l3');
    L2.vline(xsel, 'dm-lfina');
    var asim = d.s(p);
    escribir(lec, [['Media ', [isFinite(mv[0]) ? f(mv[0], 3) : '∞ (no existe)'], ' · varianza ', [isFinite(mv[1]) ? f(mv[1], 3) : '∞ (no existe)'],
      ' · desv. típica ', isFinite(mv[1]) ? f(Math.sqrt(mv[1]), 3) : '∞', ' · asimetría ', isFinite(asim) ? f(asim) : (asim === Infinity ? '∞ (no existe)' : '—')],
      ['P(X ≤ ' + (d.c ? f(xsel) : xsel) + ') ≈ ', [f(acum[idx], 3)], d.c ? ' (área sombreada)' : ' (barras verdes)']]);
  }
  montar();
};


/* ================= 10. Distribuciones básicas: se dibujan al añadir muestras ================= */
var BASICAS = ['uniforme', 'normal', 'exponencial', 'bernoulli', 'binomial', 'geometrica', 'poisson', 'gamma', 'beta', 'chi2', 't', 'lognormal', 'weibull'];
function gammaMuestra(r, k) {                       /* Marsaglia-Tsang (k < 1 se reduce a k + 1) */
  if (k < 1) return gammaMuestra(r, k + 1) * Math.pow(r(), 1 / k);
  var d = k - 1 / 3, c = 1 / Math.sqrt(9 * d);
  for (;;) { var x = normal(r), v = 1 + c * x; if (v <= 0) continue; v = v * v * v; var u = r();
    if (u < 1 - 0.0331 * x * x * x * x || Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v; } }
var MUESTRA = {
  uniforme: function (r, p) { return p[0] + p[1] * r(); },
  normal: function (r, p) { return p[0] + p[1] * normal(r); },
  exponencial: function (r, p) { return -Math.log(1 - r()) / p[0]; },
  bernoulli: function (r, p) { return r() < p[0] ? 1 : 0; },
  binomial: function (r, p) { var s = 0; for (var i = 0; i < p[0]; i++) if (r() < p[1]) s++; return s; },
  geometrica: function (r, p) { return Math.floor(Math.log(1 - r()) / Math.log(1 - p[0])); },
  poisson: function (r, p) { var L = Math.exp(-p[0]), k = 0, q = 1; do { k++; q *= r(); } while (q > L); return k - 1; },
  gamma: function (r, p) { return gammaMuestra(r, p[0]) * p[1]; },
  beta: function (r, p) { var a = gammaMuestra(r, p[0]), b = gammaMuestra(r, p[1]); return a / (a + b); },
  chi2: function (r, p) { return 2 * gammaMuestra(r, p[0] / 2); },
  t: function (r, p) { return normal(r) / Math.sqrt(2 * gammaMuestra(r, p[0] / 2) / p[0]); },
  lognormal: function (r, p) { return Math.exp(p[0] + p[1] * normal(r)); },
  weibull: function (r, p) { return p[1] * Math.pow(-Math.log(1 - r()), 1 / p[0]); }
};
var USO = {
  uniforme: 'Todos los valores de un intervalo son igual de probables. Base de los generadores de azar: casi todo se simula a partir de una uniforme(0,1).',
  normal: 'Suma de muchos efectos pequeños (teorema central del límite). Errores de medida, alturas, medias muestrales.',
  exponencial: 'Tiempo hasta el próximo suceso cuando ocurren al azar y sin memoria: llamadas, siniestros, averías.',
  bernoulli: 'Un solo ensayo con dos resultados (éxito 1 / fracaso 0): ¿renueva el cliente? ¿hay siniestro? Es la pieza de la binomial y de la regresión logística.',
  binomial: 'Nº de éxitos en n ensayos independientes con la misma probabilidad p: 10 pólizas, cuántas tienen siniestro.',
  geometrica: 'Nº de fracasos antes del primer éxito: años sin siniestro antes del primero, tiradas hasta un 6.',
  poisson: 'Nº de sucesos raros en un periodo fijo con tasa λ: siniestros al mes, llegadas por hora. Media = varianza.',
  nbinom: 'Conteos con sobredispersión (varianza > media): siniestros cuando unos asegurados son más arriesgados que otros.',
  gamma: 'Valores positivos y asimétricos: importes de siniestros, tiempo hasta que ocurren k sucesos.',
  beta: 'Una probabilidad o proporción entre 0 y 1; incertidumbre sobre p en Bayes.',
  chi2: 'Suma de k normales al cuadrado: varianzas muestrales y contrastes chi-cuadrado.',
  t: 'La normal con colas más pesadas cuando se estima σ con pocos datos (t-test). Con gl = 1 es la Cauchy y no tiene media.',
  lognormal: 'El logaritmo es normal: rentas, precios, importes con asimetría fuerte.',
  weibull: 'Tiempos de vida y fallos: k < 1 el riesgo baja con el tiempo, k = 1 es constante (exponencial), k > 1 sube.',
  pareto: 'Cola muy pesada: unos pocos valores enormes dominan (siniestros extremos, riqueza).'
};
D.demo_dist_animada = function (cont, op) {
  var ini = (op && DIST_DE_CONCEPTO[op.concepto]) || 'normal'; if (BASICAS.indexOf(ini) < 0) ini = 'normal';
  var NMAX = 5000, NB = 30;
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var sD = selector(ctr, 'Distribución', BASICAS.map(function (k) { return {v: k, t: DISTS[k].t}; }), ini, function () { montar(); });
  var cajaP = ht('div', {'class': 'dm-ctrls'}, cont), bots = ht('div', {'class': 'dm-bots'}, cont);
  var L1 = Lienzo(cont, {h: 210, aria: 'Histograma de la muestra y distribución teórica'});
  var L2 = Lienzo(cont, {h: 125, aria: 'Media muestral frente a la media teórica según crece n'});
  leyenda(cont, [['dm-k1', 'muestra (histograma)'], ['dm-k2', 'distribución teórica'], ['dm-km', 'media teórica'], ['dm-k3', 'media muestral']]);
  var nota = ht('div', {'class': 'dm-nota'}, cont, USO[ini] || '');
  var lec = lectura(cont), ctrls = [], d, p, rg, rnd, n, suma, suma2, cuentas, medias, tTop, timer = null, bPlay;
  function parar() { if (timer) { clearInterval(timer); timer = null; } if (bPlay) bPlay.textContent = '▶ Reproducir'; }
  function añadir(k) {
    k = Math.min(k, NMAX - n);
    for (var i = 0; i < k; i++) { var x = MUESTRA[sD.valor()](rnd, p); n++; suma += x; suma2 += x * x; medias.push(suma / n);
      var j = d.c ? Math.floor((x - rg[0]) / (rg[1] - rg[0]) * NB) : Math.round(x) - rg[0];
      if (j >= 0 && j < cuentas.length) cuentas[j]++; }
    pintar();
    if (n >= NMAX) parar();
  }
  function montar() {
    parar(); while (cajaP.firstChild) cajaP.removeChild(cajaP.firstChild);
    d = DISTS[sD.valor()]; nota.textContent = USO[sD.valor()] || '';
    ctrls = d.ps.map(function (q) { return control(cajaP, {etq: q[0], min: q[1], max: q[2], paso: q[3], valor: q[4],
      fmt: function (v) { return q[3] >= 1 ? String(v) : v.toFixed(2); }}, reiniciar); });
    reiniciar();
  }
  function reiniciar() {
    parar(); d = DISTS[sD.valor()]; p = ctrls.map(function (c) { return c.valor(); }); rg = d.r(p);
    if (!d.c) rg = [Math.max(0, Math.floor(rg[0])), Math.ceil(rg[1])];
    rnd = semilla(42); n = 0; suma = 0; suma2 = 0; medias = []; cuentas = []; var i;
    for (i = 0; i < (d.c ? NB : rg[1] - rg[0] + 1); i++) cuentas.push(0);
    var ys = []; if (d.c) for (i = 0; i <= 200; i++) ys.push(d.pdf(rg[0] + (rg[1] - rg[0]) * i / 200, p)); else for (i = rg[0]; i <= rg[1]; i++) ys.push(d.pdf(i, p));
    var fin = ys.filter(isFinite), mx = Math.max.apply(null, fin) || 1;
    tTop = Math.min(mx, 6 * (fin.slice().sort(function (a, b) { return a - b; })[Math.floor(fin.length * 0.9)] || mx));
    pintar();
  }
  function pintar() {
    var mv = d.m(p), sd = isFinite(mv[1]) ? Math.sqrt(mv[1]) : NaN, xpad = d.c ? 0 : 0.6, bw = (rg[1] - rg[0]) / NB, i, k;
    var h = cuentas.map(function (c) { return n ? c / (d.c ? n * bw : n) : 0; });
    var top = Math.max(tTop, 1.1 * Math.max.apply(null, h));
    L1.nuevo([rg[0] - xpad, rg[1] + xpad], [0, top * 1.08], {xl: 'x', ny: 3});
    var capa = L1.capa();
    if (d.c) h.forEach(function (v, j) { var x0 = L1.sx(rg[0] + j * bw), x1 = L1.sx(rg[0] + (j + 1) * bw), vv = Math.min(v, top * 1.08);
      sv('rect', {x: x0, y: L1.sy(vv), width: Math.max(x1 - x0 - 1, 0.5), height: Math.max(L1.sy(0) - L1.sy(vv), 0), 'class': 'dm-f1 dm-op60'}, capa); });
    else { var ancho = Math.max(2, Math.min(16, (L1.sx(1) - L1.sx(0)) * 0.6));
      h.forEach(function (v, j) { sv('rect', {x: L1.sx(rg[0] + j) - ancho / 2, y: L1.sy(v), width: ancho, height: Math.max(L1.sy(0) - L1.sy(v), 0), 'class': 'dm-f1 dm-op60', rx: 1.5}, capa); }); }
    if (d.c) { var xs = [], ys = []; for (i = 0; i <= 300; i++) { var x = rg[0] + (rg[1] - rg[0]) * i / 300; xs.push(x); ys.push(Math.min(d.pdf(x, p), top * 1.08)); } L1.linea(xs, ys, 'dm-l2'); }
    else for (k = rg[0]; k <= rg[1]; k++) sv('circle', {cx: L1.sx(k), cy: L1.sy(d.pdf(k, p)), r: 3.2, 'class': 'dm-f2 dm-anillo'}, capa);
    if (isFinite(mv[0]) && mv[0] >= rg[0] && mv[0] <= rg[1]) L1.vline(mv[0], 'dm-lm');
    L1.texto(L1.m.l + 6, L1.m.t + 11, 'n = ' + n, {'class': 'dm-txt'});
    /* convergencia de la media (eje x logarítmico) */
    var ex = isFinite(sd) ? 2.5 * sd : 3, c0 = isFinite(mv[0]) ? mv[0] : 0;
    L2.nuevo([0, Math.log10(NMAX)], [c0 - ex, c0 + ex], {x: false, ny: 3, xl: 'n (escala logarítmica)'});
    [1, 10, 100, 1000].forEach(function (v) { L2.texto(L2.sx(Math.log10(v)), L2.H - L2.m.b + 13, String(v), {'class': 'dm-tick', 'text-anchor': 'middle'}); });
    if (isFinite(mv[0])) L2.linea([0, Math.log10(NMAX)], [mv[0], mv[0]], 'dm-lm');
    if (n) { var paso = Math.max(1, Math.floor(n / 400)), px = [], py = [];
      for (i = 0; i < n; i += paso) { px.push(Math.log10(i + 1)); py.push(Math.max(c0 - ex, Math.min(c0 + ex, medias[i]))); }
      px.push(Math.log10(n)); py.push(Math.max(c0 - ex, Math.min(c0 + ex, medias[n - 1]))); L2.linea(px, py, 'dm-l3'); }
    var m = n ? suma / n : NaN, sm = n > 1 ? Math.sqrt(Math.max(suma2 / n - m * m, 0) * n / (n - 1)) : NaN;
    escribir(lec, [
      ['n = ', [String(n)], ' · media muestral ', [n ? f(m, 3) : '—'], ' (teórica ', isFinite(mv[0]) ? f(mv[0], 3) : 'no existe', ') · desv. típica muestral ', [n > 1 ? f(sm, 3) : '—'], ' (teórica ', isFinite(sd) ? f(sd, 3) : '∞', ')'],
      [isFinite(sd) ? 'Error típico de la media = σ/√n ≈ ' + (n ? f(sd / Math.sqrt(n), 3) : '—') + ': se reduce a la mitad cada vez que n se multiplica por 4.'
        : 'Esta distribución no tiene varianza (o media) finita: la media muestral NO se estabiliza por mucho que aumente n.']]);
  }
  boton(bots, '+1', function () { parar(); añadir(1); }); boton(bots, '+10', function () { parar(); añadir(10); });
  boton(bots, '+100', function () { parar(); añadir(100); }); boton(bots, '+1000', function () { parar(); añadir(1000); });
  bPlay = boton(bots, '▶ Reproducir', function () {
    if (timer) { parar(); return; } if (n >= NMAX) reiniciar();
    bPlay.textContent = '❚❚ Pausar';
    timer = setInterval(function () { if (!cont.isConnected) { parar(); return; } añadir(Math.ceil(1 + n * 0.05)); }, 90); });
  boton(bots, 'Reiniciar', reiniciar);
  montar();
};

/* ================= 11. Galería de distribuciones básicas (estática) ================= */
D.demo_dist_galeria = function (cont) {
  var GRUPOS = [['Continuas', ['uniforme', 'normal', 'exponencial', 'gamma', 'beta', 'chi2', 't', 'lognormal', 'weibull', 'pareto']],
    ['Discretas', ['bernoulli', 'binomial', 'geometrica', 'poisson', 'nbinom']]];
  GRUPOS.forEach(function (g) {
    ht('h4', {'class': 'dm-sub'}, cont, g[0]); var rej = ht('div', {'class': 'dm-galeria'}, cont);
    g[1].forEach(function (k) {
      var d = DISTS[k], p = d.ps.map(function (q) { return q[4]; }), tj = ht('div', {'class': 'dm-tarj'}, rej);
      ht('b', {}, tj, d.t + ' (' + d.ps.map(function (q, i) { return q[0].split(' ')[0] + '=' + p[i]; }).join(', ') + ')');
      var L = Lienzo(tj, {w: 230, h: 120, m: {t: 8, r: 8, b: 20, l: 30}, aria: 'Forma de la distribución ' + d.t}), rg = d.r(p), mv = d.m(p), xs = [], ys = [], i;
      if (!d.c) rg = [Math.max(0, Math.floor(rg[0])), Math.ceil(rg[1])];
      if (d.c) for (i = 0; i <= 200; i++) { var x = rg[0] + (rg[1] - rg[0]) * i / 200; xs.push(x); ys.push(d.pdf(x, p)); }
      else for (i = rg[0]; i <= rg[1]; i++) { xs.push(i); ys.push(d.pdf(i, p)); }
      var fin = ys.filter(isFinite), top = Math.min(Math.max.apply(null, fin), 6 * (fin.slice().sort(function (a, b) { return a - b; })[Math.floor(fin.length * 0.9)] || 1));
      var xp = d.c ? 0 : 0.6; L.nuevo([rg[0] - xp, rg[1] + xp], [0, top * 1.1], {ny: 2, nx: 4});
      if (d.c) { var yc = ys.map(function (y) { return Math.min(y, top * 1.1); }); L.area(xs, yc, 'dm-f1 dm-op35'); L.linea(xs, yc, 'dm-l1'); }
      else { var capa = L.capa(), bw = Math.max(2, Math.min(14, (L.sx(1) - L.sx(0)) * 0.7));
        xs.forEach(function (kk, j) { sv('rect', {x: L.sx(kk) - bw / 2, y: L.sy(ys[j]), width: bw, height: Math.max(L.sy(0) - L.sy(ys[j]), 0), 'class': 'dm-f1', rx: 1.5}, capa); }); }
      if (isFinite(mv[0]) && mv[0] >= rg[0] && mv[0] <= rg[1]) L.vline(mv[0], 'dm-lm');
      ht('div', {'class': 'dm-pie'}, tj, 'Media ' + (isFinite(mv[0]) ? f(mv[0], 2) : '—') + ' · varianza ' + (isFinite(mv[1]) ? f(mv[1], 2) : '∞'));
      ht('div', {'class': 'dm-uso'}, tj, USO[k] || '');
    });
  });
  ht('div', {'class': 'dm-nota'}, cont, 'La línea vertical es la media. Para ver cómo cada una se va dibujando al acumular datos usa «Se dibujan al añadir datos», y para mover sus parámetros el «Explorador de distribuciones».');
};


/* ================= 12. MCMC: el algoritmo de Metropolis ================= */
D.demo_mcmc = function (cont) {
  var NMAX = 20000, NB = 40, R = 10;
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont), bots = ht('div', {'class': 'dm-bots'}, cont);
  var cD = control(ctr, {etq: 'Separación de los dos picos', min: 0, max: 8, paso: 0.5, valor: 5, fmt: function (v) { return v.toFixed(1); }}, reiniciar);
  var cS = control(ctr, {etq: 'Tamaño del salto (desv. típica)', min: 0.05, max: 6, paso: 0.05, valor: 0.6, fmt: function (v) { return v.toFixed(2); }}, reiniciar);
  var cX = control(ctr, {etq: 'Punto de partida', min: -8, max: 8, paso: 0.5, valor: -4, fmt: function (v) { return v.toFixed(1); }}, reiniciar);
  var L1 = Lienzo(cont, {h: 190, aria: 'Histograma de la cadena y distribución objetivo'});
  var L2 = Lienzo(cont, {h: 120, aria: 'Traza de la cadena'});
  leyenda(cont, [['dm-k1', 'cadena (histograma)'], ['dm-k2', 'distribución objetivo'], ['dm-km', 'centro de cada pico']]);
  var lec = lectura(cont), d, s, rnd, x, n, acep, cuentas, traza, timer = null, bPlay;
  function objetivo(v) { return 0.5 * npdf(v, -d / 2, 1) + 0.5 * npdf(v, d / 2, 1); }
  function parar() { if (timer) { clearInterval(timer); timer = null; } if (bPlay) bPlay.textContent = '▶ Reproducir'; }
  function reiniciar() {
    parar(); d = cD.valor(); s = cS.valor(); rnd = semilla(42); x = cX.valor(); n = 0; acep = 0; traza = [];
    cuentas = []; for (var i = 0; i < NB; i++) cuentas.push(0); pintar();
  }
  function añadir(k) {
    k = Math.min(k, NMAX - n);
    for (var i = 0; i < k; i++) {
      var y = x + s * normal(rnd);
      if (rnd() < objetivo(y) / objetivo(x)) { x = y; acep++; }
      n++; traza.push(x);
      var j = Math.floor((x + R) / (2 * R) * NB); if (j >= 0 && j < NB) cuentas[j]++;
    }
    pintar(); if (n >= NMAX) parar();
  }
  function pintar() {
    var bw = 2 * R / NB, i, h = cuentas.map(function (c) { return n ? c / (n * bw) : 0; });
    var xs = [], ys = []; for (i = 0; i <= 300; i++) { var v = -R + 2 * R * i / 300; xs.push(v); ys.push(objetivo(v)); }
    var top = Math.max(Math.max.apply(null, ys), Math.max.apply(null, h)) * 1.1;
    L1.nuevo([-R, R], [0, top], {xl: 'x', ny: 3});
    var capa = L1.capa();
    h.forEach(function (hv, j) { var x0 = L1.sx(-R + j * bw), x1 = L1.sx(-R + (j + 1) * bw);
      sv('rect', {x: x0, y: L1.sy(hv), width: Math.max(x1 - x0 - 1, 0.5), height: Math.max(L1.sy(0) - L1.sy(hv), 0), 'class': 'dm-f1 dm-op60'}, capa); });
    L1.linea(xs, ys, 'dm-l2'); L1.vline(-d / 2, 'dm-lm'); if (d > 0) L1.vline(d / 2, 'dm-lm');
    L1.texto(L1.m.l + 6, L1.m.t + 11, 'n = ' + n, {'class': 'dm-txt'});
    L2.nuevo([0, Math.max(n, 100)], [-R, R], {xl: 'iteración', ny: 4});
    L2.linea([0, Math.max(n, 100)], [-d / 2, -d / 2], 'dm-lm'); if (d > 0) L2.linea([0, Math.max(n, 100)], [d / 2, d / 2], 'dm-lm');
    if (n) { var paso = Math.max(1, Math.floor(n / 500)), px = [], py = []; for (i = 0; i < n; i += paso) { px.push(i); py.push(traza[i]); } L2.linea(px, py, 'dm-l3'); }
    var m = 0, der = 0; for (i = 0; i < n; i++) { m += traza[i]; if (traza[i] > 0) der++; } m = n ? m / n : NaN;
    var rho = 0; if (n > 10) { var c0 = 0, c1 = 0; for (i = 0; i < n; i++) { c0 += (traza[i] - m) * (traza[i] - m); if (i + 1 < n) c1 += (traza[i] - m) * (traza[i + 1] - m); } rho = c0 > 0 ? c1 / c0 : 0; }
    var ess = n > 10 && rho > 0 ? n * (1 - rho) / (1 + rho) : n, ta = n ? acep / n : NaN, aviso = '';
    if (n > 50 && ta < 0.15) aviso = 'El salto es demasiado grande: casi todas las propuestas se rechazan y la cadena se queda quieta.';
    else if (n > 50 && ta > 0.8) aviso = 'El salto es muy pequeño: se acepta casi todo, pero la cadena avanza despacio (autocorrelación alta, pocas muestras efectivas).';
    if (d >= 4 && n > 500 && (der / n < 0.1 || der / n > 0.9)) aviso = 'La cadena se ha quedado en un solo pico: parece que todo va bien, pero no ha explorado la distribución. Prueba con más saltos, otro punto de partida o varias cadenas.';
    escribir(lec, [['n = ', [String(n)], ' · aceptación ', [n ? pct(ta, 0) : '—'], ' · muestras efectivas ≈ ', [n > 10 ? f(ess, 0) : '—'], ' · en el pico derecho ', [n ? pct(der / n, 0) : '—'], ' (teórico 50 %)'],
      [aviso || 'Aceptación entre el 20 % y el 50 % suele ser un buen equilibrio. Con n grande, el histograma se parece a la curva naranja.']]);
  }
  boton(bots, '+10', function () { parar(); añadir(10); }); boton(bots, '+100', function () { parar(); añadir(100); });
  boton(bots, '+1000', function () { parar(); añadir(1000); });
  bPlay = boton(bots, '▶ Reproducir', function () {
    if (timer) { parar(); return; } if (n >= NMAX) reiniciar();
    bPlay.textContent = '❚❚ Pausar';
    timer = setInterval(function () { if (!cont.isConnected) { parar(); return; } añadir(Math.ceil(5 + n * 0.04)); }, 90); });
  boton(bots, 'Reiniciar', reiniciar);
  reiniciar();
};

/* ================= 13. Cadenas de Markov ================= */
D.demo_markov = function (cont) {
  var PRESETS = {
    clima: {t: 'Tiempo: soleado / nublado / lluvia', e: ['Soleado', 'Nublado', 'Lluvia'], B: [[.7, .2, .1], [.3, .4, .3], [.2, .3, .5]]},
    bonus: {t: 'Bonus-malus (3 niveles)', e: ['Bonus', 'Medio', 'Malus'], B: [[.9, .1, 0], [.9, 0, .1], [0, .9, .1]]},
    absorbente: {t: 'Con un estado absorbente', e: ['Absorbente', 'A', 'B'], B: [[1, 0, 0], [.3, .4, .3], [.1, .4, .5]]}
  };
  var T = 40;
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont), bots = ht('div', {'class': 'dm-bots'}, cont);
  var sP = selector(ctr, 'Cadena', Object.keys(PRESETS).map(function (k) { return {v: k, t: PRESETS[k].t}; }), 'clima', function () { pintar(); });
  var sI = selector(ctr, 'Estado inicial', [{v: 0, t: 'estado 1'}, {v: 1, t: 'estado 2'}, {v: 2, t: 'estado 3'}], 0, function () { pintar(); });
  var cQ = control(ctr, {etq: 'Persistencia (prob. extra de quedarse)', min: 0, max: 0.95, paso: 0.05, valor: 0, fmt: function (v) { return v.toFixed(2); }}, pintar);
  var cT = control(ctr, {etq: 'Paso t', min: 0, max: T, paso: 1, valor: 5, fmt: function (v) { return String(v); }}, pintar);
  var L1 = Lienzo(cont, {h: 170, aria: 'Probabilidad de cada estado según el paso'});
  var L2 = Lienzo(cont, {h: 110, aria: 'Distribución en el paso t frente a la estacionaria'});
  leyenda(cont, [['dm-k1', 'estado 1'], ['dm-k2', 'estado 2'], ['dm-k3', 'estado 3'], ['dm-km', 'paso t']]);
  var lec = lectura(cont), emp = null, rnd = semilla(42), CL = ['dm-f1', 'dm-f2', 'dm-f3'], LN = ['dm-l1', 'dm-l2', 'dm-l3'];
  function matriz() { var B = PRESETS[sP.valor()].B, q = cQ.valor();
    return B.map(function (fila, i) { return fila.map(function (v, j) { return q * (i === j ? 1 : 0) + (1 - q) * v; }); }); }
  function paso(p, P) { var r = [0, 0, 0]; for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) r[j] += p[i] * P[i][j]; return r; }
  function pintar() {
    var P = matriz(), e0 = [0, 0, 0]; e0[+sI.valor()] = 1; var tray = [e0], i, j;
    for (i = 1; i <= 400; i++) tray.push(paso(tray[i - 1], P));
    var pi = tray[400], t = cT.valor(), hasta = null;
    for (i = 0; i <= 400 && hasta === null; i++) if (Math.max(Math.abs(tray[i][0] - pi[0]), Math.abs(tray[i][1] - pi[1]), Math.abs(tray[i][2] - pi[2])) < 0.01) hasta = i;
    L1.nuevo([0, T], [0, 1.02], {xl: 'paso', ny: 4});
    for (j = 0; j < 3; j++) { var xs = [], ys = []; for (i = 0; i <= T; i++) { xs.push(i); ys.push(tray[i][j]); } L1.linea(xs, ys, LN[j]);
      sv('circle', {cx: L1.sx(T), cy: L1.sy(pi[j]), r: 3.5, 'class': CL[j] + ' dm-anillo'}, L1.svg); }
    L1.vline(t, 'dm-lm');
    L2.nuevo([-0.6, 2.6], [0, 1.02], {ny: 2, nx: 3, x: false});
    var capa = L2.capa();
    for (j = 0; j < 3; j++) { var v = tray[t][j], x0 = L2.sx(j - 0.3), x1 = L2.sx(j + 0.3);
      sv('rect', {x: x0, y: L2.sy(v), width: x1 - x0, height: Math.max(L2.sy(0) - L2.sy(v), 0), 'class': CL[j] + ' dm-op60'}, capa);
      sv('circle', {cx: L2.sx(j), cy: L2.sy(pi[j]), r: 4, 'class': 'dm-fm dm-anillo'}, capa);
      L2.texto(L2.sx(j), L2.H - L2.m.b + 13, PRESETS[sP.valor()].e[j], {'class': 'dm-tick', 'text-anchor': 'middle'}); }
    var fila = function (r) { return r.map(function (v) { return v.toFixed(2); }).join('  '); };
    escribir(lec, [['Paso ', [String(t)], ': ', [fila(tray[t])], '  ·  estacionaria π (puntos grises): ', [fila(pi)]],
      ['Filas de P: ' + P.map(fila).join('  |  ')],
      [hasta === null ? 'La cadena no converge a una distribución única desde ese estado.' : 'Llega a menos de 0,01 de π en ' + hasta + ' pasos. La persistencia solo cambia la VELOCIDAD: π es la misma.']]);
  }
  boton(bots, 'Simular 1000 pasos', function () {
    var P = matriz(), s = +sI.valor(), c = [0, 0, 0];
    for (var k = 0; k < 1000; k++) { c[s]++; var u = rnd(), a = 0, nx = 2; for (var j = 0; j < 3; j++) { a += P[s][j]; if (u < a) { nx = j; break; } } s = nx; }
    pintar(); emp = c.map(function (v) { return v / 1000; });
    var linea = ht('div', {}, lec); linea.textContent = 'Frecuencia observada en 1000 pasos: ' + emp.map(function (v) { return v.toFixed(2); }).join('  ') + ' (≈ π: la cadena pasa en cada estado la fracción de tiempo que dice π).'; });
  pintar();
};

/* ================= 14. PCA ================= */
D.demo_pca = function (cont) {
  var N = 300, ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var cR = control(ctr, {etq: 'Correlación entre X1 y X2', min: -0.95, max: 0.95, paso: 0.05, valor: 0.8, fmt: function (v) { return v.toFixed(2); }}, pintar);
  var cS = control(ctr, {etq: 'Desviación de X2 / X1', min: 0.2, max: 2, paso: 0.1, valor: 1, fmt: function (v) { return v.toFixed(1); }}, pintar);
  var L1 = Lienzo(cont, {h: 230, aria: 'Nube de puntos con los ejes de componentes principales'});
  var L2 = Lienzo(cont, {h: 90, aria: 'Varianza explicada por componente'});
  leyenda(cont, [['dm-k1', 'PC1 (más varianza)'], ['dm-k2', 'PC2']]);
  var lec = lectura(cont), rnd = semilla(42), z1 = [], z2 = [], i;
  for (i = 0; i < N; i++) { z1.push(normal(rnd)); z2.push(normal(rnd)); }
  function pintar() {
    var r = cR.valor(), sg = cS.valor(), X = [], Y = [], mx = 0, my = 0;
    for (i = 0; i < N; i++) { X.push(z1[i]); Y.push(sg * (r * z1[i] + Math.sqrt(1 - r * r) * z2[i])); mx += X[i]; my += Y[i]; } mx /= N; my /= N;
    var a = 0, b = 0, c = 0; for (i = 0; i < N; i++) { a += (X[i] - mx) * (X[i] - mx); b += (X[i] - mx) * (Y[i] - my); c += (Y[i] - my) * (Y[i] - my); } a /= N - 1; b /= N - 1; c /= N - 1;
    var tr = a + c, dt = Math.sqrt((a - c) * (a - c) / 4 + b * b), l1 = tr / 2 + dt, l2 = tr / 2 - dt, ang = 0.5 * Math.atan2(2 * b, a - c);
    var lim = 4.2; L1.nuevo([-lim, lim], [-lim, lim], {xl: 'X1', yl: 'X2', ny: 4, nx: 4});
    var capa = L1.capa(); for (i = 0; i < N; i++) sv('circle', {cx: L1.sx(X[i]), cy: L1.sy(Y[i]), r: 2, 'class': 'dm-f1 dm-op35'}, capa);
    var e1 = 2 * Math.sqrt(l1), e2 = 2 * Math.sqrt(Math.max(l2, 0));
    L1.linea([mx - e1 * Math.cos(ang), mx + e1 * Math.cos(ang)], [my - e1 * Math.sin(ang), my + e1 * Math.sin(ang)], 'dm-l2');
    L1.linea([mx + e2 * Math.sin(ang), mx - e2 * Math.sin(ang)], [my - e2 * Math.cos(ang), my + e2 * Math.cos(ang)], 'dm-l3');
    L2.nuevo([-0.6, 1.6], [0, 1.05], {ny: 2, nx: 2, x: false}); var cp = L2.capa();
    [l1 / tr, l2 / tr].forEach(function (v, j) { var x0 = L2.sx(j - 0.3), x1 = L2.sx(j + 0.3);
      sv('rect', {x: x0, y: L2.sy(v), width: x1 - x0, height: Math.max(L2.sy(0) - L2.sy(v), 0), 'class': j ? 'dm-f3' : 'dm-f2'}, cp);
      L2.texto(L2.sx(j), L2.sy(v) - 4, pct(v, 0), {'class': 'dm-txt', 'text-anchor': 'middle'}, cp);
      L2.texto(L2.sx(j), L2.H - L2.m.b + 13, 'PC' + (j + 1), {'class': 'dm-tick', 'text-anchor': 'middle'}, cp); });
    escribir(lec, [['PC1 explica ', [pct(l1 / tr, 1)], ' de la varianza total y PC2 ', [pct(l2 / tr, 1)], ' · ángulo de PC1: ', [f(ang * 180 / Math.PI, 0) + '°']],
      [l1 / tr > 0.9 ? 'Casi toda la información está en una dirección: una sola componente resume bien las dos variables.'
        : l1 / tr < 0.6 ? 'Las dos direcciones pesan parecido: reducir a una componente perdería mucha información.' : 'Una componente conserva la mayor parte, pero no todo.'],
      ['PCA busca los ejes de máxima varianza: con correlación alta la nube se alarga y PC1 la sigue; con correlación 0 y desviaciones iguales no hay dirección preferente.']]);
  }
  pintar();
};

/* ================= 15. K-means ================= */
D.demo_kmeans = function (cont) {
  var N = 240, KMAX = 6, COL = ['#3987e5', '#d95926', '#199e70', '#c8a415', '#9b59b6', '#e0457b'];
  var ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var cK = control(ctr, {etq: 'Número de grupos k', min: 1, max: KMAX, paso: 1, valor: 3, fmt: function (v) { return String(v); }}, pintar);
  var cS = control(ctr, {etq: 'Separación de los 3 grupos reales', min: 0.5, max: 6, paso: 0.25, valor: 4, fmt: function (v) { return v.toFixed(2); }}, pintar);
  var L1 = Lienzo(cont, {h: 220, aria: 'Puntos coloreados por grupo y centroides'});
  var L2 = Lienzo(cont, {h: 110, aria: 'Inercia y silhouette según k'});
  leyenda(cont, [['dm-k1', 'inercia (relativa a k = 1)'], ['dm-k2', 'silhouette medio']]);
  var lec = lectura(cont), rnd = semilla(42), Z = [], i;
  for (i = 0; i < N; i++) Z.push([normal(rnd), normal(rnd), i % 3]);
  function datos(s) { var C = [[0, 0], [s, 0], [s / 2, s * 0.87]]; return Z.map(function (z) { return [z[0] + C[z[2]][0], z[1] + C[z[2]][1]]; }); }
  function d2(a, b) { return (a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]); }
  function kmeans(X, k) {                       /* k-means++ determinista + Lloyd */
    var r = semilla(42), cen = [X[Math.floor(r() * X.length)]], j, e;
    while (cen.length < k) { var w = X.map(function (p) { return Math.min.apply(null, cen.map(function (c) { return d2(p, c); })); }), tot = w.reduce(function (a, b) { return a + b; }, 0), u = r() * tot, acu = 0, el = 0;
      for (j = 0; j < w.length; j++) { acu += w[j]; if (acu >= u) { el = j; break; } } cen.push(X[el]); }
    var lab = X.map(function () { return 0; });
    for (var it = 0; it < 60; it++) {
      var cambio = false; X.forEach(function (p, m) { var mj = 0, md = Infinity; cen.forEach(function (c, q) { var dd = d2(p, c); if (dd < md) { md = dd; mj = q; } }); if (lab[m] !== mj) { lab[m] = mj; cambio = true; } });
      cen = cen.map(function (c, q) { var sx = 0, sy = 0, nn = 0; X.forEach(function (p, m) { if (lab[m] === q) { sx += p[0]; sy += p[1]; nn++; } }); return nn ? [sx / nn, sy / nn] : c; });
      if (!cambio) break; }
    var ine = 0; X.forEach(function (p, m) { ine += d2(p, cen[lab[m]]); });
    return {lab: lab, cen: cen, ine: ine};
  }
  function silhouette(X, lab, k) {
    if (k < 2) return NaN; var s = 0;
    for (var m = 0; m < X.length; m++) { var sum = [], cnt = []; for (var q = 0; q < k; q++) { sum.push(0); cnt.push(0); }
      for (var o = 0; o < X.length; o++) if (o !== m) { sum[lab[o]] += Math.sqrt(d2(X[m], X[o])); cnt[lab[o]]++; }
      var a = cnt[lab[m]] ? sum[lab[m]] / cnt[lab[m]] : 0, b = Infinity; for (q = 0; q < k; q++) if (q !== lab[m] && cnt[q]) b = Math.min(b, sum[q] / cnt[q]);
      s += isFinite(b) ? (b - a) / Math.max(a, b) : 0; }
    return s / X.length;
  }
  function pintar() {
    var X = datos(cS.valor()), k = cK.valor(), res = [], sil = [], j;
    for (j = 1; j <= KMAX; j++) { var r = kmeans(X, j); res.push(r); sil.push(silhouette(X, r.lab, j)); }
    var lim = 10; L1.nuevo([-4, lim], [-4, lim], {ny: 4, nx: 5}); var capa = L1.capa(), a = res[k - 1];
    X.forEach(function (p, m) { sv('circle', {cx: L1.sx(p[0]), cy: L1.sy(p[1]), r: 2.4, fill: COL[a.lab[m]], 'fill-opacity': 0.6}, capa); });
    a.cen.forEach(function (c) { sv('circle', {cx: L1.sx(c[0]), cy: L1.sy(c[1]), r: 6, fill: '#ffffff', stroke: '#000000', 'stroke-width': 2}, capa); });
    L2.nuevo([0.5, KMAX + 0.5], [0, 1.05], {ny: 2, nx: KMAX, xl: 'k'});
    L2.linea(res.map(function (_, q) { return q + 1; }), res.map(function (q) { return q.ine / res[0].ine; }), 'dm-l1');
    var xs2 = [], ys2 = []; for (j = 2; j <= KMAX; j++) { xs2.push(j); ys2.push(Math.max(sil[j - 1], 0)); } L2.linea(xs2, ys2, 'dm-l2'); L2.vline(k, 'dm-lm');
    var mejor = 2; for (j = 3; j <= KMAX; j++) if (sil[j - 1] > sil[mejor - 1]) mejor = j;
    escribir(lec, [['k = ', [String(k)], ' · inercia ', [pct(a.ine / res[0].ine, 0)], ' de la de k = 1 · silhouette ', [k > 1 ? f(sil[k - 1], 2) : '—'], ' · mejor k por silhouette: ', [String(mejor)]],
      [sil[mejor - 1] < 0.4 ? 'Grupos poco separados: el silhouette es bajo y la inercia baja sin «codo». K-means siempre devuelve k grupos, haya o no estructura real.'
        : 'Con grupos separados, la inercia deja de bajar de golpe en k = 3 (el «codo») y el silhouette tiene su máximo ahí.']]);
  }
  pintar();
};

/* ================= 16. Bandidos multibrazo ================= */
D.demo_bandido = function (cont) {
  var NMAX = 3000, ctr = ht('div', {'class': 'dm-ctrls'}, cont), bots = ht('div', {'class': 'dm-bots'}, cont);
  var cp = [0.3, 0.5, 0.6].map(function (v, q) { return control(ctr, {etq: 'Probabilidad real del brazo ' + (q + 1), min: 0.05, max: 0.95, paso: 0.05, valor: v, fmt: function (x) { return x.toFixed(2); }}, reiniciar); });
  var L1 = Lienzo(cont, {h: 170, aria: 'Arrepentimiento acumulado (regret) de cada estrategia'});
  var L2 = Lienzo(cont, {h: 100, aria: 'Porcentaje de tiradas en el mejor brazo'});
  leyenda(cont, [['dm-k1', 'al azar'], ['dm-k2', 'ε-greedy (10 %)'], ['dm-k3', 'Thompson']]);
  var lec = lectura(cont), NOM = ['al azar', 'ε-greedy', 'Thompson'], p, rnd, E, n, timer = null, bPlay;
  function parar() { if (timer) { clearInterval(timer); timer = null; } if (bPlay) bPlay.textContent = '▶ Reproducir'; }
  function reiniciar() {
    parar(); p = cp.map(function (c) { return c.valor(); }); rnd = semilla(42); n = 0;
    E = [0, 1, 2].map(function () { return {s: [0, 0, 0], f: [0, 0, 0], tir: [0, 0, 0], reg: [0], mej: [0]}; }); pintar();
  }
  function elegir(q, e) {
    if (q === 0) return Math.floor(rnd() * 3);
    if (q === 1) { if (rnd() < 0.1) return Math.floor(rnd() * 3); var m = 0, best = -1; for (var j = 0; j < 3; j++) { var t = e.tir[j] ? e.s[j] / e.tir[j] : 1; if (t > best) { best = t; m = j; } } return m; }
    var m2 = 0, bv = -1; for (var j2 = 0; j2 < 3; j2++) { var v = MUESTRA.beta(rnd, [1 + e.s[j2], 1 + e.f[j2]]); if (v > bv) { bv = v; m2 = j2; } } return m2;
  }
  function añadir(k) {
    k = Math.min(k, NMAX - n); var pm = Math.max.apply(null, p), mejor = p.indexOf(pm);
    for (var i = 0; i < k; i++) { for (var q = 0; q < 3; q++) { var e = E[q], a = elegir(q, e), exito = rnd() < p[a];
      e.tir[a]++; if (exito) e.s[a]++; else e.f[a]++; e.reg.push(e.reg[e.reg.length - 1] + pm - p[a]); e.mej.push(e.tir[mejor] / (e.reg.length - 1)); } n++; }
    pintar(); if (n >= NMAX) parar();
  }
  function pintar() {
    var T = Math.max(n, 100), top = Math.max(1, Math.max.apply(null, E.map(function (e) { return e.reg[e.reg.length - 1]; })) * 1.1), cls = ['dm-l1', 'dm-l2', 'dm-l3'];
    L1.nuevo([0, T], [0, top], {xl: 'tirada', yl: 'arrepentimiento', ny: 3});
    L2.nuevo([0, T], [0, 1.02], {xl: 'tirada', yl: '% mejor brazo', ny: 2});
    E.forEach(function (e, q) { var paso = Math.max(1, Math.floor(n / 400)), xs = [], ys = [], zs = [];
      for (var i = 0; i <= n; i += paso) { xs.push(i); ys.push(e.reg[i]); zs.push(i ? e.mej[i] : 0); } if (xs.length > 1) { L1.linea(xs, ys, cls[q]); L2.linea(xs, zs, cls[q]); } });
    var pm = Math.max.apply(null, p), mejor = p.indexOf(pm);
    escribir(lec, [['Tiradas: ', [String(n)], ' · mejor brazo: el ', [String(mejor + 1)], ' (p = ' + pm.toFixed(2) + ')'],
      [E.map(function (e, q) { return NOM[q] + ': arrepentimiento ' + f(e.reg[e.reg.length - 1], 1) + ', ' + (n ? pct(e.tir[mejor] / n, 0) : '—') + ' en el mejor'; }).join('  ·  ')],
      ['El arrepentimiento (regret) es lo que se pierde por no tirar siempre del mejor brazo. Al azar crece en línea recta; ε-greedy sigue explorando un 10 % para siempre; Thompson explora mucho al principio y luego casi solo explota.']]);
  }
  boton(bots, '+100', function () { parar(); añadir(100); }); boton(bots, '+1000', function () { parar(); añadir(1000); });
  bPlay = boton(bots, '▶ Reproducir', function () {
    if (timer) { parar(); return; } if (n >= NMAX) reiniciar();
    bPlay.textContent = '❚❚ Pausar';
    timer = setInterval(function () { if (!cont.isConnected) { parar(); return; } añadir(Math.ceil(2 + n * 0.03)); }, 90); });
  boton(bots, 'Reiniciar', reiniciar);
  reiniciar();
};

/* ================= 17. VaR y TVaR: la cola importa ================= */
D.demo_var = function (cont) {
  var M = 100, ctr = ht('div', {'class': 'dm-ctrls'}, cont);
  var sD = selector(ctr, 'Distribución de la pérdida', [{v: 'normal', t: 'Normal'}, {v: 'lognormal', t: 'Lognormal'}, {v: 'pareto', t: 'Pareto (cola pesada)'}], 'normal', function () { pintar(); });
  var cA = control(ctr, {etq: 'Nivel de confianza', min: 0.9, max: 0.999, paso: 0.001, valor: 0.99, fmt: function (v) { return (100 * v).toFixed(1) + ' %'; }}, pintar);
  var cC = control(ctr, {etq: 'Coef. de variación (σ / media)', min: 0.2, max: 0.8, paso: 0.05, valor: 0.4, fmt: function (v) { return v.toFixed(2); }}, pintar);
  var L1 = Lienzo(cont, {h: 190, aria: 'Densidad de la pérdida con VaR y TVaR'});
  leyenda(cont, [['dm-k1', 'densidad (misma media y desviación)'], ['dm-km', 'VaR'], ['dm-k2', 'TVaR (media de la cola)']]);
  var lec = lectura(cont);
  function modelo(k, cv) {
    var sd = M * cv;
    if (k === 'normal') return {pdf: function (x) { return npdf(x, M, sd); }, q: function (u) { return M + sd * qnorm(u); }};
    if (k === 'lognormal') { var s2 = Math.log(1 + cv * cv), mu = Math.log(M) - s2 / 2, sl = Math.sqrt(s2);
      return {pdf: function (x) { return x <= 0 ? 0 : npdf(Math.log(x), mu, sl) / x; }, q: function (u) { return Math.exp(mu + sl * qnorm(u)); }}; }
    var a = 1 + Math.sqrt(1 + 1 / (cv * cv)), xm = M * (a - 1) / a;
    return {pdf: function (x) { return x < xm ? 0 : a * Math.pow(xm, a) / Math.pow(x, a + 1); }, q: function (u) { return xm * Math.pow(1 - u, -1 / a); }, a: a};
  }
  function qnorm(u) { var lo = -9, hi = 9; for (var i = 0; i < 45; i++) { var m = (lo + hi) / 2; if (Phi(m) < u) lo = m; else hi = m; } return (lo + hi) / 2; }
  function pintar() {
    var cv = cC.valor(), al = cA.valor(), md = modelo(sD.valor(), cv), var_ = md.q(al), tv = 0, N = 2000, i;
    for (i = 0; i < N; i++) tv += md.q(1 - (1 - al) * (i + 0.5) / N); tv /= N;
    var xmax = Math.max(M * (1 + 6 * cv), tv * 1.15), xs = [], ys = [];
    for (i = 0; i <= 400; i++) { var x = xmax * i / 400; xs.push(x); ys.push(md.pdf(x)); }
    var top = Math.max.apply(null, ys.filter(isFinite)) * 1.1; L1.nuevo([0, xmax], [0, top], {xl: 'pérdida', ny: 3});
    var yc = ys.map(function (y) { return Math.min(y, top); });
    L1.area(xs, yc, 'dm-f1 dm-op35'); L1.area(xs, yc, 'dm-f2 dm-op60', function (x) { return x >= var_; }); L1.linea(xs, yc, 'dm-l1');
    L1.vline(var_, 'dm-lm'); L1.vline(tv, 'dm-l2');
    escribir(lec, [['VaR ', [pct(al, 1)], ' = ', [f(var_, 1)], ' · TVaR = ', [f(tv, 1)], ' · TVaR / VaR = ', [f(tv / var_, 2)]],
      ['Las tres familias tienen la misma media (100) y casi la misma dispersión, pero la cola cambia el riesgo: el VaR solo dice «a partir de aquí», el TVaR dice cuánto se pierde de media cuando se supera. Con cola pesada la diferencia es mayor' + (md.a ? ' (α = ' + f(md.a, 2) + ').' : '.')]]);
  }
  pintar();
};

/* utilidades expuestas para las pruebas automáticas */
D._estad = {tcdf: tcdf, tinv: tinv, Phi: Phi, colaNormal: colaNormal, potenciaT: potenciaT, nPara: nPara};
return D;
})();
