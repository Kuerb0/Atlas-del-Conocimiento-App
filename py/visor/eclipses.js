/* eclipses.js — pestaña «Eclipses»: el Sol es el límite de GitHub y cada galaxia / tipo de archivo es una luna de su color que lo tapa.
   Todo es estático: el área de cada luna es proporcional a lo que ocupa (radio = R·√(bytes/límite)), así que el Sol queda tapado en la misma proporción que el repositorio está lleno.
   Las lunas se reparten alrededor del Sol, cada una en su ángulo, para que cada eclipse se vea por separado. Canvas 2D sin librerías.
   API: crearEclipses({canvas, alPasar(id|null)}) -> {medir, mostrar, ocultar, datos(items, limite), resaltar(id|null)}
   items = [{id, nombre, bytes, color:[r,g,b]}] */
(function () {
'use strict';
window.crearEclipses = function (o) {
  var cv = o.canvas, ctx = cv.getContext('2d'), W = 800, H = 460, DPR = 1, lunas = [], resal = null, estrellas = [];
  for (var i = 0, a = 7; i < 220; i++) { a = (a * 16807) % 2147483647; var x = a / 2147483647; a = (a * 16807) % 2147483647; var y = a / 2147483647; estrellas.push([x, y, .5 + 1.4 * x * y]); }

  function geom() { return {cx: W * .5, cy: H * .5, R: Math.min(W * .24, H * .36)}; }
  function dibujar() {
    var g = geom(), cx = g.cx, cy = g.cy, R = g.R, n = lunas.length;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1; ctx.fillStyle = '#02030a'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#fff'; estrellas.forEach(function (e) { ctx.globalAlpha = .12 + .5 * e[2] / 2; ctx.fillRect(e[0] * W, e[1] * H, e[2], e[2]); }); ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'lighter';                                                             /* corona */
    var co = ctx.createRadialGradient(cx, cy, R * .9, cx, cy, R * 2.1); co.addColorStop(0, 'rgba(255,170,70,.45)'); co.addColorStop(.4, 'rgba(255,120,40,.12)'); co.addColorStop(1, 'rgba(255,100,30,0)');
    ctx.fillStyle = co; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'source-over';
    var so = ctx.createRadialGradient(cx, cy, 0, cx, cy, R); so.addColorStop(0, '#fff6d8'); so.addColorStop(.7, '#ffc864'); so.addColorStop(1, '#ff9a3c');
    ctx.fillStyle = so; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.2832); ctx.fill();
    ctx.strokeStyle = 'rgba(255,220,150,.55)'; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.2832); ctx.stroke();
    lunas.slice().sort(function (p, q) { return q.k - p.k; }).forEach(function (l) {                         /* las grandes debajo, las pequeñas encima: ninguna queda escondida */
      var rr = R * l.k, ang = -Math.PI / 2 + 2 * Math.PI * l.pos / n, d = R * .72, c = l.color.join(','), hot = resal === l.id;
      l.px = cx + Math.cos(ang) * d; l.py = cy + Math.sin(ang) * d; l.pr = rr;
      ctx.fillStyle = 'rgba(' + c + ',' + (hot ? .98 : .88) + ')'; ctx.beginPath(); ctx.arc(l.px, l.py, rr, 0, 6.2832); ctx.fill();
      ctx.strokeStyle = hot ? '#fff' : 'rgba(255,255,255,.55)'; ctx.lineWidth = hot ? 2.6 : 1.2; ctx.stroke();
      if (rr > 22 || hot) { ctx.fillStyle = '#fff'; ctx.shadowColor = 'rgba(0,0,0,.8)'; ctx.shadowBlur = 4; ctx.font = (hot ? 13 : 11) + 'px system-ui,sans-serif'; ctx.textAlign = 'center'; ctx.fillText(l.nombre, l.px, l.py + 4); ctx.shadowBlur = 0; }
    });
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
  cv.addEventListener('mousemove', function (e) { var l = bajo(e), id = l ? l.id : null; if (id !== resal) { resal = id; dibujar(); if (o.alPasar) o.alPasar(id); } });
  cv.addEventListener('mouseleave', function () { if (resal !== null) { resal = null; dibujar(); if (o.alPasar) o.alPasar(null); } });
  return {
    medir: medir,
    mostrar: medir,
    ocultar: function () {},
    resaltar: function (id) { if (id !== resal) { resal = id; dibujar(); } },
    datos: function (items, lim) {
      lunas = items.map(function (it, i) { return {id: it.id, nombre: it.nombre, color: it.color, k: Math.max(.035, Math.min(1.5, Math.sqrt(it.bytes / (lim || 1)))), pos: i}; });
      dibujar();
    }
  };
};
})();
