/* eclipses.js — pestaña «Eclipses»: un eclipse total. El Sol es el límite de GitHub y UNA luna lo cubre entero; la luna es un gráfico de sectores (pie): cada galaxia / tipo de archivo es una porción de su color, proporcional a lo que pesa.
   Cuánto del límite está lleno se lee en el anillo de la corona (un arco que se va completando; ámbar y luego rojo al acercarse al 100 %) y en el texto del centro. Estático, sin animación. Canvas 2D sin librerías.
   API: crearEclipses({canvas, alPasar(id|null)}) -> {medir, mostrar, ocultar, datos(items, limite, total), resaltar(id|null)}
   items = [{id, nombre, bytes, color:[r,g,b]}] (los que no entren en la lista se suman en un item «Otros» antes de llamar); total = bytes de todo (la luna se reparte entre los items). */
(function () {
'use strict';
var TAU = 2 * Math.PI, INI = -Math.PI / 2;
window.crearEclipses = function (o) {
  var cv = o.canvas, ctx = cv.getContext('2d'), W = 800, H = 460, DPR = 1, trozos = [], total = 0, lim = 1, resal = null, estrellas = [];
  for (var i = 0, a = 7; i < 220; i++) { a = (a * 16807) % 2147483647; var x = a / 2147483647; a = (a * 16807) % 2147483647; var y = a / 2147483647; estrellas.push([x, y, .5 + 1.4 * x * y]); }

  function geom() { return {cx: W * .5, cy: H * .5, R: Math.min(W * .3, H * .36)}; }
  function mb(b) { return b >= 1073741824 ? (b / 1073741824).toFixed(2) + ' GB' : b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB'; }
  function dibujar() {
    var g = geom(), cx = g.cx, cy = g.cy, R = g.R, sombra = '#02030a';
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1; ctx.fillStyle = sombra; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#fff'; estrellas.forEach(function (e) { ctx.globalAlpha = .12 + .5 * e[2] / 2; ctx.fillRect(e[0] * W, e[1] * H, e[2], e[2]); }); ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'lighter';                                                             /* corona: el Sol queda tapado y solo asoma su luz alrededor */
    var co = ctx.createRadialGradient(cx, cy, R * .96, cx, cy, R * 2.2); co.addColorStop(0, 'rgba(255,190,90,.85)'); co.addColorStop(.25, 'rgba(255,140,50,.28)'); co.addColorStop(1, 'rgba(255,100,30,0)');
    ctx.fillStyle = co; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'source-over';
    var f = Math.max(0, total / lim), fr = Math.min(1, f), col = f >= 1 ? '#ff4d4d' : f >= .8 ? '#ff9a3c' : '#ffd37a', rr = R * 1.2;
    ctx.lineWidth = 7; ctx.lineCap = 'round'; ctx.strokeStyle = 'rgba(255,255,255,.12)'; ctx.beginPath(); ctx.arc(cx, cy, rr, 0, TAU); ctx.stroke();   /* anillo = lo lleno del límite */
    if (fr > 0) { ctx.strokeStyle = col; ctx.beginPath(); ctx.arc(cx, cy, rr, INI, INI + TAU * fr); ctx.stroke(); }
    ctx.lineCap = 'butt';
    ctx.fillStyle = '#05060e'; ctx.beginPath(); ctx.arc(cx, cy, R * 1.02, 0, TAU); ctx.fill();            /* la luna, algo mayor que el Sol: eclipse total */
    var ang = INI;
    trozos.forEach(function (t) {
      var a1 = ang + TAU * t.frac, hot = resal === t.id;
      t.a0 = ang; t.a1 = a1; ang = a1;
      if (t.frac <= 0) return;
      ctx.fillStyle = 'rgba(' + t.color.join(',') + ',' + (hot ? 1 : .86) + ')';
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, R * (hot ? 1.04 : 1), t.a0, t.a1); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = hot ? '#fff' : 'rgba(2,3,10,.9)'; ctx.lineWidth = hot ? 2.4 : 1.4; ctx.stroke();
      if (t.frac > .06) {                                                                                  /* etiqueta dentro de la porción si cabe */
        var m = (t.a0 + t.a1) / 2, px = cx + Math.cos(m) * R * .66, py = cy + Math.sin(m) * R * .66;
        ctx.fillStyle = '#fff'; ctx.shadowColor = 'rgba(0,0,0,.85)'; ctx.shadowBlur = 4; ctx.textAlign = 'center';
        ctx.font = '11px system-ui,sans-serif'; ctx.fillText(t.nombre, px, py - 2); ctx.font = '10px system-ui,sans-serif'; ctx.fillText((100 * t.frac).toFixed(t.frac < .1 ? 1 : 0) + ' %', px, py + 11); ctx.shadowBlur = 0;
      }
    });
    ctx.strokeStyle = 'rgba(255,225,160,.5)'; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(cx, cy, R * 1.02, 0, TAU); ctx.stroke();
    var h = trozos.filter(function (t) { return t.id === resal; })[0];                                     /* centro de la luna: lo señalado, o el total */
    ctx.fillStyle = 'rgba(2,3,10,.82)'; ctx.beginPath(); ctx.arc(cx, cy, R * .3, 0, TAU); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.textAlign = 'center';
    if (h) { ctx.font = '600 12px system-ui,sans-serif'; ctx.fillText(h.nombre, cx, cy - 6); ctx.font = '11px system-ui,sans-serif'; ctx.fillText(mb(h.bytes) + ' · ' + (100 * h.frac).toFixed(1) + ' %', cx, cy + 11); }
    else { ctx.font = '600 13px system-ui,sans-serif'; ctx.fillText(mb(total), cx, cy - 4); ctx.font = '11px system-ui,sans-serif'; ctx.fillStyle = '#c9d4ee'; ctx.fillText((100 * f).toFixed(f < .1 ? 1 : 0) + ' % del límite', cx, cy + 12); }
  }
  function medir() {
    var r = cv.getBoundingClientRect(); if (!r.width) return; DPR = Math.min(2, window.devicePixelRatio || 1);
    W = r.width; H = r.height; cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); dibujar();
  }
  function bajo(e) {                                                                                             /* porción bajo el ratón (por el ángulo respecto al centro) */
    var r = cv.getBoundingClientRect(), g = geom(), x = e.clientX - r.left - g.cx, y = e.clientY - r.top - g.cy;
    if (Math.hypot(x, y) > g.R * 1.04 || Math.hypot(x, y) < g.R * .3) return null;
    var a = Math.atan2(y, x); if (a < INI) a += TAU;
    return trozos.filter(function (t) { return t.frac > 0 && a >= t.a0 && a < t.a1; })[0] || null;
  }
  cv.addEventListener('mousemove', function (e) { var t = bajo(e), id = t ? t.id : null; if (id !== resal) { resal = id; dibujar(); if (o.alPasar) o.alPasar(id); } });
  cv.addEventListener('mouseleave', function () { if (resal !== null) { resal = null; dibujar(); if (o.alPasar) o.alPasar(null); } });
  return {
    medir: medir,
    mostrar: medir,
    ocultar: function () {},
    resaltar: function (id) { if (id !== resal) { resal = id; dibujar(); } },
    datos: function (items, limite, tot) {
      var suma = items.reduce(function (s, it) { return s + it.bytes; }, 0) || 1;
      lim = limite || 1; total = tot == null ? suma : tot;
      trozos = items.map(function (it) { return {id: it.id, nombre: it.nombre, color: it.color, bytes: it.bytes, frac: it.bytes / suma, a0: 0, a1: 0}; });
      dibujar();
    }
  };
};
})();
