/* cerebro.js — primera capa del visor: un cerebro 3D (el gestor de conocimiento) con galaxias pequeñas dentro.
   Cada galaxia es una colección: «Estadística» es el mapa 3D de siempre (el árbol); las demás (libros, finanzas, notas) son ámbitos de búsqueda.
   Canvas 2D con perspectiva escrita a mano, como mapa3d.js: sin librerías ni WebGL. Lo incrusta construir_visor.py en la plantilla.
   Navegación: arrastrar = girar · rueda = acercar · clic en una galaxia = entrar.
   API: crearCerebro({canvas, galaxias:[{id, nombre, color:[r,g,b], sub}], alGalaxia(g), reducir}) -> {mostrar, ocultar, medir, resaltar({id: nº}), datos({id: texto})} */
(function () {
'use strict';
function azar(sem) { var a = sem >>> 0; return function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
var SANS = 'system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
var spr = {};
function sprite(c) {                                  /* mancha de luz de 32 px */
  var k = c.join(','); if (spr[k]) return spr[k];
  var cv = document.createElement('canvas'); cv.width = cv.height = 32; var g = cv.getContext('2d'), gr = g.createRadialGradient(16, 16, 0, 16, 16, 16);
  gr.addColorStop(0, 'rgba(255,255,255,.95)'); gr.addColorStop(.2, 'rgba(' + k + ',.85)'); gr.addColorStop(.55, 'rgba(' + k + ',.18)'); gr.addColorStop(1, 'rgba(' + k + ',0)');
  g.fillStyle = gr; g.fillRect(0, 0, 32, 32); return spr[k] = cv;
}
var CEREBRO = [[240, 140, 192], [210, 130, 235], [170, 140, 250], [130, 160, 255]];   /* rosa → violeta → azul */
var SITIOS = [[-56, 26, 56], [56, 22, 40], [-58, -10, -30], [56, -4, -48], [0, 54, -6], [0, -30, 74], [0, 8, 6], [-20, 46, -50]];
function suave(x) { return x < 0 ? 0 : x > 1 ? 1 : x * x * (3 - 2 * x); }

window.crearCerebro = function (o) {
  var cv = o.canvas, ctx = cv.getContext('2d'), G = o.galaxias, rnd = azar(11), gauss = function () { return (rnd() + rnd() + rnd() - 1.5) * 1.15; };
  var W = 800, H = 600, DPR = 1, yaw = .5, pitch = .42, zoom = 1, t = 0, tPrev = 0, raf = 0, vivo = false, hover = -1, arr = null, res = {};
  var P = [], L = [], mundo = [];

  /* ---- el cerebro: dos hemisferios con circunvoluciones, cerebelo, tronco y algunas conexiones ---- */
  function lobulo(cx, cy, cz, rx, ry, rz, n, fr, lado) {
    for (var i = 0; i < n; i++) {
      var u = 2 * Math.PI * rnd(), v = Math.acos(2 * rnd() - 1), dx = Math.sin(v) * Math.cos(u), dy = Math.cos(v), dz = Math.sin(v) * Math.sin(u);
      var f = 1 + .12 * Math.sin(fr * u + 3 * Math.cos(5 * v)) * Math.sin((fr - 1) * v + 2 * Math.sin(3 * u));
      var k = rnd() < .8 ? 1 : Math.cbrt(rnd()) * .9, r = k * f;
      var x = cx + dx * rx * r, y = cy + dy * ry * r * (dy < 0 ? .6 : 1), z = cz + dz * rz * r;
      if (lado < 0) x = Math.min(x, -3 - 3 * rnd()); else if (lado > 0) x = Math.max(x, 3 + 3 * rnd());
      P.push({x: x, y: y, z: z, c: Math.min(3, Math.floor(((y + 70) / 150 + (z + 130) / 520) * 2.2 + rnd() * .5)), s: .8 + .8 * rnd(), a: .35 + .5 * rnd()});
    }
  }
  lobulo(-36, 8, 6, 60, 62, 118, 2400, 7, -1); lobulo(36, 8, 6, 60, 62, 118, 2400, 7, 1);
  lobulo(0, -56, -88, 44, 22, 30, 420, 13, 0);
  for (var i = 0; i < 70; i++) { var q = rnd(); P.push({x: gauss() * 3, y: -48 - 75 * q, z: -46 - 12 * q + gauss() * 3, c: 3, s: .8 + .6 * rnd(), a: .4 + .4 * rnd()}); }
  for (var tries = 0; tries < 6000 && L.length < 240; tries++) {     /* conexiones entre puntos cercanos */
    var a = P[Math.floor(rnd() * P.length)], b = P[Math.floor(rnd() * P.length)], d = Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
    if (d > 14 && d < 42) L.push([a, b]);
  }
  /* ---- las galaxias: dos brazos en espiral logarítmica, inclinadas y girando ---- */
  G.forEach(function (g, i) {
    var s = SITIOS[i] || [0, 0, 0], R = 30 + 18 * (g.peso || 0), pts = [], N = 170 + Math.round(150 * (g.peso || 0)), tilt = (rnd() - .5) * 1.1;
    for (var k = 0; k < N; k++) { var r = 3 + R * Math.pow(rnd(), .75), brazo = k % 2 ? Math.PI : 0;
      pts.push({r: r, a: r * .17 + brazo + gauss() * .22, y: gauss() * 2.2 * (1 - r / R * .6), s: .7 + 1.1 * rnd(), al: .35 + .6 * rnd()}); }
    mundo.push({g: g, s: s, R: R, pts: pts, tilt: tilt, w: .25 + .2 * rnd(), sx: 0, sy: 0, sr: 40, rgb: g.color});
  });

  /* ---- proyección ---- */
  var cY, sY, cP, sP, CX, CY, F, DIST = 470, dist = DIST, foco = {x: 0, y: 0, z: 0}, an = null, vel = 1;
  function prep() { cY = Math.cos(yaw); sY = Math.sin(yaw); cP = Math.cos(pitch); sP = Math.sin(pitch); CX = W / 2; CY = H / 2 + 10; F = 760 * Math.min(W / 800, H / 600) * zoom; }
  function pr(x, y, z, out) {
    x -= foco.x; y -= foco.y; z -= foco.z;
    var x1 = x * cY + z * sY, z1 = -x * sY + z * cY, y2 = y * cP - z1 * sP, z2 = y * sP + z1 * cP, d = z2 + dist; if (d < 30) return false;
    var s = F / d; out.x = CX + x1 * s; out.y = CY - y2 * s; out.s = s; out.d = d; return true;
  }
  var O = {};
  function luz(c, x, y, tam, al) { ctx.globalAlpha = al > 1 ? 1 : al; ctx.drawImage(sprite(c), x - tam / 2, y - tam / 2, tam, tam); }

  function dibujar() {
    prep(); ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1; ctx.fillStyle = '#03040a'; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'lighter';
    ctx.lineWidth = 1; ctx.strokeStyle = "rgba(190,150,255,.07)"; ctx.beginPath();
    L.forEach(function (e) { var A = {}, B = {}; if (pr(e[0].x, e[0].y, e[0].z, A) && pr(e[1].x, e[1].y, e[1].z, B)) { ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); } });
    ctx.stroke();
    for (var i = 0; i < P.length; i++) { var p = P[i]; if (!pr(p.x, p.y, p.z, O)) continue;
      var prof = 1.15 - (O.d - dist + 130) / 520; luz(CEREBRO[p.c < 0 ? 0 : p.c], O.x, O.y, (1.2 + 1.5 * p.s) * O.s * 1.5, p.a * .55 * (prof < .3 ? .3 : prof)); }
    mundo.forEach(function (m, gi) {
      var hot = gi === hover || res[m.g.id], ct = Math.cos(m.tilt), st = Math.sin(m.tilt), c0 = [255, 255, 255];
      m.pts.forEach(function (p) { var a = p.a + t * m.w, x = p.r * Math.cos(a), z = p.r * Math.sin(a), y = p.y * ct - z * st, z2 = p.y * st + z * ct;
        if (pr(m.s[0] + x, m.s[1] + y, m.s[2] + z2, O)) luz(m.rgb, O.x, O.y, (3 + 4 * p.s) * O.s * (hot ? 1.5 : 1.15), p.al * (hot ? 1 : .8)); });
      if (pr(m.s[0], m.s[1], m.s[2], O)) { m.sx = O.x; m.sy = O.y; m.sr = (m.R + 6) * O.s; luz(m.rgb, O.x, O.y, m.R * 1.5 * O.s * (hot ? 1.6 : 1.1), hot ? .9 : .55); luz(c0, O.x, O.y, 9 * O.s, .9); }
    });
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; ctx.textAlign = 'center';
    if (an) { var ov = an.sale ? 1 - suave(an.p / .4) : suave((an.p - .72) / .28); ctx.fillStyle = 'rgba(3,4,10,' + ov.toFixed(3) + ')'; ctx.fillRect(0, 0, W, H); return; }
    var puestas = [];                               /* etiquetas: de arriba abajo, bajando la que se pise con otra */
    mundo.map(function (m, gi) { return {m: m, gi: gi, y: m.sy + m.sr + 14}; }).sort(function (a, b) { return a.y - b.y; }).forEach(function (e) {
      puestas.forEach(function (q) { if (Math.abs(e.m.sx - q.m.sx) < 130 && e.y < q.y + 28) e.y = q.y + 28; });
      puestas.push(e);
      var m = e.m, hot = e.gi === hover, n = res[m.g.id], col = 'rgb(' + m.rgb.join(',') + ')';
      ctx.strokeStyle = 'rgba(' + m.rgb.join(',') + ',' + (hot ? .85 : .45) + ')'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(m.sx, m.sy + 4); ctx.lineTo(m.sx, e.y - 12); ctx.stroke();   /* línea guía: de la galaxia a su título */
      var txt = m.g.nombre + (n ? '  · ' + n + ' ✓' : ''), yy = e.y - 2;
      ctx.lineJoin = 'round'; ctx.lineWidth = 3.5; ctx.strokeStyle = 'rgba(3,4,10,.95)';
      ctx.font = '700 11px ' + SANS; var tw = ctx.measureText(txt).width;
      ctx.strokeText(txt, m.sx + 6, yy); ctx.fillStyle = hot ? '#fff' : 'rgba(255,255,255,.95)'; ctx.fillText(txt, m.sx + 6, yy);
      ctx.beginPath(); ctx.arc(m.sx - tw / 2 - 2, yy - 4, 3.5, 0, 6.2832); ctx.fillStyle = col; ctx.fill();                                                                     /* punto del color de la galaxia */
      if (m.g.sub) { ctx.font = '600 9.5px ' + SANS; ctx.strokeText(m.g.sub, m.sx + 6, yy + 12); ctx.fillStyle = 'rgba(190,204,230,.92)'; ctx.fillText(m.g.sub, m.sx + 6, yy + 12); }
    });
    ctx.font = '500 12px ' + SANS; ctx.fillStyle = 'rgba(160,176,205,.7)'; ctx.fillText('Clic en una galaxia para entrar · arrastra para girar · rueda para acercar', W / 2, H - 14);
  }
  function frame(ahora) {
    var dt = Math.min(.05, (ahora - (tPrev || ahora)) / 1000); tPrev = ahora;
    if (an) {                                               /* vuelo: la cámara se acerca a la galaxia (o se aleja de ella al volver) */
      an.p = Math.min(1, (ahora - an.t0) / an.dur); var e = suave(an.p), k = an.sale ? 1 - e : e;
      foco = {x: an.s[0] * k, y: an.s[1] * k, z: an.s[2] * k}; dist = DIST + (95 - DIST) * k; pitch += (an.pitch0 - pitch) * .04 * (1 - k);
      if (an.p >= 1) { var fin = an.fin; an = null; foco = {x: 0, y: 0, z: 0}; dist = DIST; if (fin) fin(); }
    } else if (!o.reducir && !arr) yaw += dt * .13 * vel;
    t += dt; dibujar(); raf = vivo && (!o.reducir || an) ? requestAnimationFrame(frame) : 0;
  }
  function ocupado() {                                    /* ¿hay un vuelo en curso? (uno que lleva mucho más de su duración se da por muerto: pestaña sin fotogramas) */
    if (an && performance.now() - an.t0 > an.dur + 500) { var fin = an.fin; an = null; foco = {x: 0, y: 0, z: 0}; dist = DIST; if (fin) fin(); }
    return !!an;
  }
  function pintar() { if (vivo && !raf) raf = requestAnimationFrame(frame); }
  function medir() { var r = cv.getBoundingClientRect(); if (!r.width) return; DPR = Math.min(window.devicePixelRatio || 1, 2); W = r.width; H = r.height; cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); pintar(); }

  /* ---- ratón ---- */
  function lugar(ev) { var r = cv.getBoundingClientRect(); return {x: ev.clientX - r.left, y: ev.clientY - r.top}; }
  function bajo(p) { var mejor = -1, md = 1e9; mundo.forEach(function (m, i) { var d = Math.hypot(p.x - m.sx, p.y - m.sy); if (d < m.sr * 1.15 && d < md) { md = d; mejor = i; } }); return mejor; }
  cv.addEventListener('pointerdown', function (ev) { if (ocupado()) return; cv.setPointerCapture(ev.pointerId); arr = {x: ev.clientX, y: ev.clientY, mov: 0}; });
  cv.addEventListener('pointermove', function (ev) {
    if (ocupado()) return;
    if (arr) { var dx = ev.clientX - arr.x, dy = ev.clientY - arr.y; arr.mov += Math.abs(dx) + Math.abs(dy); arr.x = ev.clientX; arr.y = ev.clientY;
      yaw -= dx * .006; pitch = Math.max(-1.2, Math.min(1.2, pitch + dy * .006)); cv.style.cursor = 'grabbing'; }
    else { var h = bajo(lugar(ev)); if (h !== hover) { hover = h; cv.style.cursor = h >= 0 ? 'pointer' : 'grab'; } }
    pintar();
  });
  cv.addEventListener('pointerup', function (ev) { var clic = arr && arr.mov < 5; arr = null; cv.style.cursor = 'grab'; if (clic) { var h = bajo(lugar(ev)); if (h >= 0) o.alGalaxia(mundo[h].g); } pintar(); });
  cv.addEventListener('pointerleave', function () { if (!arr) { hover = -1; pintar(); } });
  cv.addEventListener('wheel', function (ev) { ev.preventDefault(); if (ocupado()) return; zoom = Math.max(.6, Math.min(2.6, zoom * (ev.deltaY < 0 ? 1.1 : 1 / 1.1))); pintar(); }, {passive: false});
  cv.style.cursor = 'grab'; cv.style.touchAction = 'none';

  return {
    mostrar: function (desde) {                             /* desde = id de la galaxia de la que se vuelve: la cámara se aleja de ella */
      vivo = true; an = null; foco = {x: 0, y: 0, z: 0}; dist = DIST; medir();
      var m = desde && !o.reducir ? mundo.filter(function (q) { return q.g.id === desde; })[0] : null;
      if (m) { an = {s: m.s, sale: true, t0: performance.now(), dur: 900, p: 0, pitch0: pitch}; pintar(); }
    },
    volar: function (id, fin) {                             /* acerca la cámara a la galaxia y llama a fin() al llegar */
      var m = mundo.filter(function (q) { return q.g.id === id; })[0];
      if (!m || o.reducir || ocupado()) { if (fin) fin(); return; }
      hover = -1; an = {s: m.s, sale: false, t0: performance.now(), dur: 1150, p: 0, fin: fin, pitch0: pitch}; if (!vivo) vivo = true; pintar();
    },
    ocultar: function () { vivo = false; if (raf) cancelAnimationFrame(raf); raf = 0; },
    medir: medir,
    resaltar: function (m) { res = m || {}; pintar(); },
    datos: function (m) { G.forEach(function (g) { if (m[g.id] !== undefined) g.sub = m[g.id]; }); pintar(); }
  };
};
})();
