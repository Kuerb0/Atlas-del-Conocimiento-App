/* agujero.js — el agujero negro de la pestaña «Importar»: disco de acreción en órbita, anillo de luz y halo curvado por la gravedad (como en Interstellar).
   Canvas 2D sin librerías. Clic (o soltar archivos encima) = añadir archivos; al importar «traga» los archivos y lanza un destello del color de su galaxia.
   API: crearAgujero({canvas, alClic()}) -> {medir, mostrar, ocultar, tragar([r,g,b]), ocupado(bool)} */
(function () {
'use strict';
function azar(sem) { var a = sem >>> 0; return function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
var spr = {};
function sprite(c) {
  var k = c.join(','); if (spr[k]) return spr[k];
  var cv = document.createElement('canvas'); cv.width = cv.height = 32; var g = cv.getContext('2d'), gr = g.createRadialGradient(16, 16, 0, 16, 16, 16);
  gr.addColorStop(0, 'rgba(255,255,255,.95)'); gr.addColorStop(.25, 'rgba(' + k + ',.8)'); gr.addColorStop(.6, 'rgba(' + k + ',.15)'); gr.addColorStop(1, 'rgba(' + k + ',0)');
  g.fillStyle = gr; g.fillRect(0, 0, 32, 32); return spr[k] = cv;
}
function color(k) {            /* de blanco caliente (dentro) a naranja y a rojo oscuro (fuera) */
  return k < .35 ? [255, Math.round(245 - 70 * k / .35), Math.round(220 - 130 * k / .35)] : [255, Math.round(175 - 95 * (k - .35) / .65), Math.round(90 - 70 * (k - .35) / .65)];
}

window.crearAgujero = function (o) {
  var cv = o.canvas, ctx = cv.getContext('2d'), rnd = azar(5), W = 800, H = 500, DPR = 1, vivo = false, raf = 0, tPrev = 0, t = 0, hover = false, rapido = 0, ocup = false;
  var disco = [], halo = [], estrellas = [], tragados = [];
  for (var i = 0; i < 1500; i++) {                                /* disco: más denso hacia dentro, velocidad kepleriana */
    var k = Math.pow(rnd(), 1.6), r = 1.35 + 2.6 * k;
    disco.push({r: r, a: 2 * Math.PI * rnd(), w: 1.7 / Math.pow(r, 1.5), k: k, s: .8 + 1.6 * rnd(), al: .35 + .6 * rnd(), y: (rnd() - .5) * .04});
  }
  for (i = 0; i < 700; i++) { var kk = Math.pow(rnd(), 1.4); halo.push({r: 1.12 + 1.3 * kk, a: 2 * Math.PI * rnd(), w: 1.2 / Math.pow(1.12 + 1.3 * kk, 1.5), k: kk * .8, s: .7 + 1.2 * rnd(), al: .25 + .5 * rnd()}); }
  for (i = 0; i < 260; i++) estrellas.push({x: rnd(), y: rnd(), s: .6 + 1.6 * rnd() * rnd(), a: .15 + .7 * rnd()});

  function luz(c, x, y, tam, al) { ctx.globalAlpha = al > 1 ? 1 : al; ctx.drawImage(sprite(c), x - tam / 2, y - tam / 2, tam, tam); }
  function dibujar() {
    var cx = W / 2, cy = H / 2, R = Math.min(W * .17, H * .27), inc = .26;     /* R: radio del horizonte; inc: inclinación del disco */
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1; ctx.fillStyle = '#02030a'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#fff'; estrellas.forEach(function (e) { ctx.globalAlpha = e.a; ctx.fillRect(e.x * W, e.y * H, e.s, e.s); });
    ctx.globalCompositeOperation = 'lighter'; var hot = hover ? 1.25 : 1, giro = t * (1 + rapido * 2.5);
    var rad = Math.min(W, H) * .5, rg = ctx.createRadialGradient(cx, cy, R * .9, cx, cy, rad); rg.addColorStop(0, 'rgba(255,150,60,' + (.26 * hot) + ')'); rg.addColorStop(.55, 'rgba(255,110,40,' + (.07 * hot) + ')'); rg.addColorStop(1, 'rgba(255,100,30,0)');
    ctx.globalAlpha = 1; ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H);
    /* 1) mitad trasera del disco y halo curvado: la luz de detrás del agujero se ve por encima y por debajo */
    disco.forEach(function (p) { var a = p.a + p.w * giro, z = Math.sin(a); if (z > 0) return;
      luz(color(p.k), cx + Math.cos(a) * p.r * R, cy + (z * inc * p.r + p.y) * R, p.s * 4 * hot, p.al * .85); });
    halo.forEach(function (p) { var a = p.a + p.w * giro, rr = p.r * R;
      luz(color(p.k), cx + Math.cos(a) * rr * .98, cy + Math.sin(a) * rr * .98 - (Math.sin(a) > 0 ? 0 : 0), p.s * 3.4 * hot, p.al * (Math.sin(a) < 0 ? .75 : .42)); });
    /* 2) el horizonte de sucesos: negro, y el anillo de fotones alrededor */
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1; ctx.fillStyle = '#000'; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.2832); ctx.fill();
    ctx.globalCompositeOperation = 'lighter'; ctx.lineWidth = 3 * hot; ctx.strokeStyle = 'rgba(255,225,170,' + (.8 * Math.min(1, hot)) + ')'; ctx.beginPath(); ctx.arc(cx, cy, R * 1.03, 0, 6.2832); ctx.stroke();
    ctx.lineWidth = 9; ctx.strokeStyle = 'rgba(255,170,80,.16)'; ctx.beginPath(); ctx.arc(cx, cy, R * 1.07, 0, 6.2832); ctx.stroke();
    /* 3) mitad delantera del disco, por delante del agujero */
    disco.forEach(function (p) { var a = p.a + p.w * giro, z = Math.sin(a); if (z <= 0) return;
      luz(color(p.k), cx + Math.cos(a) * p.r * R, cy + (z * inc * p.r + p.y) * R, p.s * 4.4 * hot, Math.min(1, p.al * 1.15)); });
    /* 4) lo que se está tragando: espirales que caen al centro */
    tragados = tragados.filter(function (q) { return q.r > .12; });
    tragados.forEach(function (q) { q.a += q.w; q.r -= q.v; q.w *= 1.012; luz(q.c, cx + Math.cos(q.a) * q.r * R * 4, cy + Math.sin(q.a) * q.r * R * 4 * (.55 + .45 * q.r / 1.1), 6 + 8 * q.r, Math.min(1, q.r + .2)); });
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  }
  function frame(ahora) {
    var dt = Math.min(.05, (ahora - (tPrev || ahora)) / 1000); tPrev = ahora; t += dt;
    rapido += ((ocup ? 1 : 0) - rapido) * Math.min(1, dt * 3);
    dibujar(); raf = vivo ? requestAnimationFrame(frame) : 0;
  }
  function pintar() { if (vivo && !raf) { tPrev = 0; raf = requestAnimationFrame(frame); } }
  function medir() { var r = cv.getBoundingClientRect(); if (!r.width) return; DPR = Math.min(window.devicePixelRatio || 1, 2); W = r.width; H = r.height; cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); pintar(); }
  function dentro(ev) { var r = cv.getBoundingClientRect(), x = ev.clientX - r.left - W / 2, y = ev.clientY - r.top - H / 2; return Math.hypot(x, y) < Math.min(W * .17, H * .27) * 4; }
  cv.addEventListener('pointermove', function (ev) { var h = dentro(ev); if (h !== hover) { hover = h; cv.style.cursor = h ? 'pointer' : 'default'; } });
  cv.addEventListener('pointerleave', function () { hover = false; });
  cv.addEventListener('click', function (ev) { if (dentro(ev) && o.alClic) o.alClic(); });
  cv.addEventListener('keydown', function (ev) { if ((ev.key === 'Enter' || ev.key === ' ') && o.alClic) { ev.preventDefault(); o.alClic(); } });
  return {
    medir: medir, mostrar: function () { vivo = true; medir(); }, ocultar: function () { vivo = false; if (raf) cancelAnimationFrame(raf); raf = 0; },
    ocupado: function (b) { ocup = !!b; pintar(); },
    tragar: function (c) { for (var i = 0; i < 70; i++) tragados.push({c: c, a: 6.2832 * rnd(), r: .9 + .35 * rnd(), v: .004 + .006 * rnd(), w: .02 + .03 * rnd()}); pintar(); }
  };
};
})();
