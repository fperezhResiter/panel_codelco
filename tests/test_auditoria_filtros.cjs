// Ejecuta el código real de la página con un DOM de prueba, sin abrir un navegador.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const html = fs.readFileSync('web/pages/Panel_Auditoria_EDP.html', 'utf8');
const elementos = new Map(), consultas = [], descargas = [];
class Elemento {
  constructor(id) { this.id = id; this.options = []; this.listeners = {}; this._value = ''; }
  get value() {
    return this.options.length ? (this.options.some(o => o.value === this._value) ? this._value : this.options[0].value) : this._value;
  }
  set value(v) { this._value = String(v); }
  replaceChildren(...opciones) { this.options = opciones; this._value = opciones[0]?.value || ''; }
  add(opcion) { this.options.push(opcion); }
  addEventListener(evento, callback) { this.listeners[evento] = callback; }
  click() { if (this.id === 'a') descargas.push(this.download); }
  remove() {}
}
for (const [, id] of html.matchAll(/\bid="([^"]+)"/g)) elementos.set(id, new Elemento(id));
for (const [, id] of html.matchAll(/<(?:button|input|select)\b[^>]*\bid="([^"]+)"[^>]*\bdisabled\b[^>]*>/g)) elementos.get(id).disabled = true;
const controlesEn = fragmento => [...fragmento.matchAll(/<(?:button|input|select)\b[^>]*\bid="([^"]+)"/g)].map(([, id]) => elementos.get(id));
const controlesAuditoria = controlesEn(html.match(/<main class="auditoria">([\s\S]*?)<\/main>/)[1]);
const controlesChequeo = controlesEn(html.match(/<section class="filtros filtros-chequeo"[^>]*>([\s\S]*?)<\/section>/)[1]);
for (const [, id, contenido] of html.matchAll(/<select id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)) {
  elementos.get(id).options = [...contenido.matchAll(/<option value="([^"]*)"[^>]*>([^<]*)<\/option>/g)]
    .map(([, value, text]) => ({value, text}));
}
const $ = id => { assert(elementos.has(id), 'Falta el elemento ' + id); return elementos.get(id); };
const document = {
  getElementById: $,
  querySelectorAll: selector => selector.startsWith('.auditoria') ? [...controlesAuditoria, ...(selector.includes('.filtros-chequeo') ? controlesChequeo : [])] : [],
  createElement: id => new Elemento(id), body: {appendChild() {}}, addEventListener() {},
};
const estados = [
  ['Andina', 2025, 5, 39, 'completo', 'verde', 'Chequeo completo'],
  ['Andina', 2026, 6, 40, 'parcial', 'amarillo', 'Chequeo parcial'],
  ['Andina', 2026, 5, 41, 'sin_revision', 'rojo', 'Sin revisión'],
  ['El Salvador', 2026, 5, 47, 'completo', 'verde', 'Chequeo completo'],
].map(([unidad, anio, mes, edp, estado_codigo, color, estado]) => ({
  unidad, anio, mes, edp, periodo: `${anio}-${String(mes).padStart(2, '0')}`,
  estado_codigo, color, estado, revisiones: 1, comprobados: 1, pendientes: 0,
}));
const catalogo = {unidades: ['Andina', 'El Salvador'], estados_pago: estados, muestras: [], avisos: [],
  fuentes: estados.map((e, i) => ({...e, id: 'fuente-' + i, nombre: 'EDP.xlsx', origen: 'Fuentes'}))};
const fetch = async ruta => {
  consultas.push(ruta);
  return {ok: true, json: async () => structuredClone(catalogo), blob: async () => new Blob(['PDF']),
    headers: {get: () => "attachment; filename*=UTF-8''compilado.zip"}};
};
vm.runInNewContext(fs.readFileSync('web/js/auditoria.js', 'utf8'), {
  window: {PanelSesion: {usuario: {rol: 'administrador'}, permite: () => true, listo: Promise.resolve()}}, document, fetch, Blob, URL, URLSearchParams,
  Option: class {constructor(text, value) {this.text = text; this.value = String(value);}},
  setTimeout() {}, setInterval() {}, console,
});
const filas = () => ($('estados-pago').innerHTML.match(/<tr>/g) || []).length;
const cambiar = async (id, valor) => {$(id).value = valor; await $(id).listeners.change();};
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  assert(html.indexOf('id="chequeo-unidad"') < html.indexOf('id="estados-pago"'));
  assert.equal(filas(), 4);
  for (const id of ['chequeo-unidad', 'chequeo-anio', 'chequeo-trimestre', 'chequeo-mes', 'chequeo-edp', 'chequeo-estado', 'chequeo-limpiar', 'chequeo-este-mes']) {
    assert.equal($(id).disabled, false, `${id}: disponible después de cargar el catálogo`);
  }
  assert.equal($('descargar-compilado').disabled, true);
  await cambiar('unidad', 'El Salvador');
  assert.equal(filas(), 4, 'La selección del sorteo no filtra la tabla de chequeo');
  await cambiar('chequeo-unidad', 'Andina');
  assert.equal(filas(), 3);
  assert.equal($('unidad').value, 'El Salvador', 'Los filtros de chequeo no cambian el sorteo');
  await cambiar('chequeo-anio', '2026');
  assert.equal(filas(), 2);
  await cambiar('chequeo-mes', '6');
  await cambiar('chequeo-edp', '40');
  await cambiar('chequeo-estado', 'parcial');
  assert.equal(filas(), 1);
  assert.match($('estados-pago').innerHTML, /Chequeo parcial/);
  assert.match($('grafico-chequeos').innerHTML, /Chequeo parcial, 1 EDP/);
  assert.equal($('pdf-unidad').disabled, false);
  await $('pdf-unidad').listeners.click();
  assert.equal(consultas.at(-1), '/api/auditoria/unidad.zip?unidad=Andina&anio=2026&mes=6&edp=40');
  await cambiar('chequeo-estado', 'completo');
  assert.match($('estados-pago').innerHTML, /Sin EDP que coincidan/);
  assert.equal($('pdf-unidad').disabled, true);
  assert.equal($('descargar-compilado').disabled, true, 'No se compila cuando ningún EDP coincide con los filtros');
  await cambiar('chequeo-estado', 'parcial');
  assert.equal($('descargar-compilado').disabled, false);
  await $('descargar-compilado').listeners.click();
  assert.equal(consultas.at(-1), '/api/auditoria/compilado.zip?unidad=Andina&anio=2026&mes=6&edp=40&estado=parcial');
  assert.equal(descargas.at(-1), 'compilado.zip');
  await cambiar('chequeo-anio', '');
  await cambiar('chequeo-mes', '');
  await cambiar('chequeo-edp', '');
  await cambiar('chequeo-estado', '');
  await cambiar('chequeo-trimestre', '2');
  await $('descargar-compilado').listeners.click();
  assert.equal(consultas.at(-1), '/api/auditoria/compilado.zip?unidad=Andina&trimestre=2');
  await cambiar('chequeo-trimestre', '');
  await cambiar('chequeo-estado', 'sin_revision');
  assert.equal(filas(), 1);
  assert.match($('estados-pago').innerHTML, /Sin revisión/);
  await $('actualizar').listeners.click();
  assert.equal($('chequeo-unidad').value, 'Andina');
  assert.equal($('chequeo-estado').value, 'sin_revision');
  assert.equal(filas(), 1, 'La recarga conserva los filtros de chequeo');
  await cambiar('chequeo-unidad', '');
  assert.equal($('descargar-compilado').disabled, true);
  console.log('OK: filtros independientes, estados, selección PDF, recarga y compilado por filtros con trimestre sin año.');
})().catch(error => {console.error(error); process.exitCode = 1;});
