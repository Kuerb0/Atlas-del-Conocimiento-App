// Prueba sin navegador de las demos del visor: carga visor/demos.js con un DOM mínimo, ejecuta cada demo,
// pulsa todos los botones, mueve todos los deslizadores y cambia todos los selectores.
// Falla si algo lanza una excepción o si se pinta NaN / undefined / Infinity. Uso: node demos_stub.js <ruta a demos.js>
const fs = require('fs'), vm = require('vm');

const temporizadores = [];
function El(tag) {
  const e = {tag, children: [], attrs: {}, listeners: {}, style: {}, isConnected: true, _text: '', _v: undefined, checked: false};
  e.setAttribute = (k, v) => { e.attrs[k] = String(v); };
  e.getAttribute = (k) => e.attrs[k];
  e.appendChild = (c) => { e.children.push(c); return c; };
  e.removeChild = (c) => { e.children = e.children.filter((x) => x !== c); return c; };
  e.addEventListener = (t, f) => { (e.listeners[t] = e.listeners[t] || []).push(f); };
  e.close = () => {};
  Object.defineProperty(e, 'firstChild', {get: () => e.children[0] || null});
  Object.defineProperty(e, 'lastChild', {get: () => e.children[e.children.length - 1] || null});
  Object.defineProperty(e, 'textContent', {get: () => e._text, set: (v) => { e._text = String(v); e.children = []; }});
  Object.defineProperty(e, 'value', {
    get: () => (e._v !== undefined ? e._v : (tag === 'select' ? (e.children[0] || {attrs: {}}).attrs.value : e.attrs.value)),
    set: (v) => { e._v = String(v); }});
  return e;
}
const documento = {createElement: El, createElementNS: (ns, t) => El(t), createTextNode: (t) => ({text: String(t)})};
const ctx = vm.createContext({document: documento, window: {}, console, Math, Date, Object, Array, String, Number, isFinite, isNaN, parseInt, parseFloat, JSON,
  Float32Array, Float64Array, Int16Array, Uint8Array, Uint32Array,
  setInterval: (f) => { temporizadores.push(f); return temporizadores.length; }, clearInterval: () => {}});
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8') + '\n;this.DEMOS = DEMOS;', ctx);
const DEMOS = ctx.DEMOS;

function recorrer(e, f) { f(e); (e.children || []).forEach((c) => c.tag && recorrer(c, f)); }
function disparar(e, tipo) { (e.listeners[tipo] || []).forEach((f) => f({target: e, preventDefault() {}})); }
function malos(raiz, nombre) {
  const out = [];
  recorrer(raiz, (e) => { for (const k in e.attrs) if (/NaN|undefined|Infinity/.test(e.attrs[k])) out.push(`${nombre}: <${e.tag} ${k}="${e.attrs[k].slice(0, 60)}">`);
    if (/NaN|undefined/.test(e._text)) out.push(`${nombre}: texto «${e._text.slice(0, 60)}»`);
    (e.children || []).forEach((c) => { if (c.text && /NaN|undefined/.test(c.text)) out.push(`${nombre}: texto «${c.text.slice(0, 60)}»`); }); });
  return out;
}

const problemas = [];
const nombres = Object.keys(DEMOS).filter((k) => k[0] !== '_');
for (const nombre of nombres) {
  const cont = El('div');
  try {
    DEMOS[nombre](cont, {});
    const todos = [];
    recorrer(cont, (e) => todos.push(e));
    todos.filter((e) => e.tag === 'button').forEach((b) => { disparar(b, 'click'); temporizadores.splice(0).slice(0, 1).forEach((f) => { for (let i = 0; i < 5; i++) f(); }); disparar(b, 'click'); });
    todos.filter((e) => e.tag === 'input' && e.attrs.type === 'range').forEach((i) => {
      const mn = +i.attrs.min, mx = +i.attrs.max, st = +i.attrs.step || 1, ajusta = (v) => mn + Math.round((v - mn) / st) * st;
      for (const v of [mn, mx, ajusta((mn + mx) / 2)]) { i._v = String(v); disparar(i, 'input'); } });
    todos.filter((e) => e.tag === 'input' && e.attrs.type === 'checkbox').forEach((i) => { i.checked = true; disparar(i, 'change'); });
    todos.filter((e) => e.tag === 'select').forEach((s) => s.children.forEach((o) => { s._v = o.attrs.value; disparar(s, 'change'); }));
    problemas.push(...malos(cont, nombre));
  } catch (err) { problemas.push(`${nombre}: EXCEPCIÓN ${err.stack.split('\n').slice(0, 3).join(' | ')}`); }
}
// Con un tercer argumento (nombres separados por comas) imprime la lectura numérica de esas demos con sus valores iniciales.
if (process.argv[3]) for (const n of process.argv[3].split(',')) {
  const c = El('div'); DEMOS[n](c, {}); const out = [];
  (function pulsa(e) { if (e.tag === 'button' && e._text === '+1000') for (let i = 0; i < 5; i++) disparar(e, 'click'); e.children.forEach((x) => x.tag && pulsa(x)); })(c);   // 5000 pasos
  (function rec(e) { if (e.attrs.class === 'dm-lect') e.children.forEach((ln) => out.push(ln.children.map((x) => (x.text !== undefined ? x.text : x._text)).join('')));
    e.children.forEach((x) => x.tag && rec(x)); })(c);
  console.log(n + ' =>', out);
}
console.log(`${nombres.length} demos ejecutadas`);
if (problemas.length) { console.log(problemas.slice(0, 15).join('\n')); process.exit(1); }
