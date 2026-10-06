/* eclipses.js — pestaña «Eclipses»: el Sol es el límite de GitHub y cada galaxia / tipo de archivo es una luna que lo eclipsa.
   El área de cada luna es proporcional a lo que ocupa (radio = R·√(bytes/límite)), así que el Sol queda tapado en la misma proporción que el repositorio está lleno.
   Canvas 2D sin librerías. API: crearEclipses({canvas, alPasar(id|null)}) -> {medir, mostrar, ocultar, datos(items, limite), resaltar(id|null)}
   items = [{id, nombre, bytes, color:[r,g,b]}] */
(function () {
'use strict';
window.crearEclipses = function (o) {
  var cv = o.canvas, ctx = cv.getContext('2d'), W = 800, H = 460, DPR = 1, vivo = false, raf = 0, tPrev = 0, t = 0;
  var lunas = [], limite = 1, resal = null, mx = -1, my = -1, estrellas = [];
  for (var i = 0, a = 7; i < 220; i++) { a = (a * 16807) % 2147483647; var x = a / 2147483647; a = (a * 16807) % 2147483647; var y = a / 2147483647; estrellas.push([x, y, .5 + 1.4 * x * y]); }

  function geom() { return {cx: W * .5, cy: H * .5, R: Math.min(W * .24, H * .36)}; }
  function posicion(l, g) {                     /* cada luna cruza el Sol por su propio carril, con su propia velocidad y fase */
    var rr = g.R * l.k, amp = g.R + rr * .9;
    return {x: g.cx + Math.sin(t * l.w + l.fase) * amp, y: g.cy + l.carril * g.R * 1.05, r: rr};
  }
  function dibujar() {
    var g = geom(), cx = g.cx, cy = g.cy, R = g.R;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1; ctx.fillStyle = '#02030a'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#fff'; estrellas.forEach(function (e) { ctx.globalAlpha = .12 + .5 * e[2] / 2; ctx.fillRect(e[0] * W, e[1] * H, e[2], e[2]); }); ctx.globalAlpha = 1;
    var lleno = lunas.reduce(function (s, l) { return s + l.k * l.k; }, 0), brillo = Math.max(.25, 1 - Math.min(1, lleno) * .55);   /* el Sol se apaga un poco cuanto más lleno */
    ctx.globalCompositeOperation = 'lighter';                                                             /* corona */
    var co = ctx.createRadialGradient(cx, cy, R * .9, cx, cy, R * 2.1); co.addColorStop(0, 'rgba(255,170,70,' + (.45 * brillo) + ')'); co.addColorStop(.4, 'rgba(255,120,40,' + (.12 * brillo) + ')'); co.addColorStop(1, 'rgba(255,100,30,0)');
    ctx.fillStyle = co; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'source-over';
    var so = ctx.createRadialGradient(cx, cy, 0, cx, cy, R); so.addColorStop(0, '#fff6d8'); so.addColorStop(.7, '#ffc864'); so.addColorStop(1, '#ff9a3c');
    ctx.globalAlpha = .55 + .45 * brillo; ctx.fillStyle = so; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.2832); ctx.fill(); ctx.globalAlpha = 1;
    ctx.strokeStyle = 'rgba(255,220,150,.55)'; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.2832); ctx.stroke();
    lunas.forEach(function (l) {                                                                                 /* pequeñas debajo, grandes encima no: las pequeñas arriba para verlas */
      var p = posicion(l, g), c = l.color.join(','), hot = resal === l.id;
      l.px = p.x; l.py = p.y; l.pr = p.r;
      ctx.fillStyle = hot ? 'rgba(18,16,26,.97)' : 'rgba(6,7,14,.94)'; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.2832); ctx.fill();
      ctx.fillStyle = 'rgba(' + c + ',' + (hot ? .3 : .14) + ')'; ctx.fill();
      ctx.strokeStyle = 'rgba(' + c + ',' + (hot ? 1 : .8) + ')'; ctx.lineWidth = hot ? 2.6 : 1.5; ctx.stroke();
      if (p.r > 22 || hot) { ctx.fillStyle = 'rgba(235,240,255,.95)'; ctx.font = (hot ? 13 : 11) + 'px system-ui,sans-serif'; ctx.textAlign = 'center'; ctx.fillText(l.nombre, p.x, p.y + 4); }
    });
  }
  function bucle(ts) {
    if (!vivo) return; t += Math.min(.05, (ts - tPrev) / 1000 || 0); tPrev = ts; dibujar(); raf = requestAnimationFrame(bucle);
  }
  function medir() {
    var r = cv.getBoundingClientRect(); if (!r.width) return; DPR = Math.min(2, window.devicePixelRatio || 1);
    W = r.width; H = r.height; cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); dibujar();
  }
  function bajo(e) {                                                                                             /* luna bajo el ratón (la más pequeña si se solapan) */
    var r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top, mejor = null;
    lunas.forEach(function (l) { if (Math.hypot(x - l.px, y - l.py) <= l.pr && (!mejor || l.pr < mejor.pr)) mejor = l; });
    return mejor;
  }
  cv.addEventListener('mousemove', function (e) { var l = bajo(e), id = l ? l.id : null; if (id !== resal) { resal = id; if (o.alPasar) o.alPasar(id); } });
  cv.addEventListener('mouseleave', function () { if (resal !== null) { resal = null; if (o.alPasar) o.alPasar(null); } });
  return {
    medir: medir,
    mostrar: function () { medir(); if (!vivo) { vivo = true; tPrev = performance.now(); raf = requestAnimationFrame(bucle); } },
    ocultar: function () { vivo = false; cancelAnimationFrame(raf); },
    resaltar: function (id) { resal = id; },
    datos: function (items, lim) {
      limite = lim || 1; var n = items.length;
      lunas = items.map(function (it, i) {
        var k = Math.min(1.5, Math.sqrt(it.bytes / limite));
        return {id: it.id, nombre: it.nombre, color: it.color, k: Math.max(.035, k), w: .35 + .5 * ((i * 37) % 11) / 11, fase: i * 2.399, carril: n > 1 ? (i / (n - 1) - .5) * 1.5 : 0};
      });
      dibujar();
    }
  };
};
})();
