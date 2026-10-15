// Verifica los scripts reales de los tres paneles y sus exportaciones.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
require('../web/js/tramos_volumen.js');

class Elemento {
  constructor(id) { this.id = id; this.options = []; this.listeners = {}; this._value = ''; this.innerHTML = ''; }
  get value() { return this.options.length ? (this.options.some(o => o.value === this._value) ? this._value : this.options[0].value) : this._value; }
  set value(v) { this._value = String(v); }
  get selectedOptions() { return this.options.filter(o => o.value === this.value); }
  replaceChildren(...opciones) { this.options = opciones; this._value = opciones[0]?.value || ''; }
  add(opcion) { this.options.push(opcion); }
  addEventListener(evento, callback) { this.listeners[evento] = callback; }
  append() {}
  click() {}
  remove() {}
  close() {}
  closest() { return {after() {}}; }
}
const registros = [];
for (const unidad of ['Andina', 'El Salvador']) {
  for (const anio of [2025, 2026]) {
    for (let mes = 1; mes <= 12; mes++) registros.push({
      unidad, anio, mes, edp: mes, periodo: `${anio}-${String(mes).padStart(2, '0')}`,
      mes_nombre: `Mes ${mes}`, estado: 'cuadra', estado_codigo: 'completo', color: 'verde',
      revisiones: 1, comprobados: 1, pendientes: 0, tickets: [], avisos: [], errores: [],
      peso_kg: 1000, ton_tickets: 1, ton_edp: 1, monto_edp: 1, monto_esperado: 1, diferencia: 0,
    });
  }
}
async function cargarPanel(nombre, script, datos) {
  let ahora = '2026-10-08T15:00:00Z';
  const html = fs.readFileSync(`web/pages/${nombre}.html`, 'utf8');
  const elementos = new Map(), consultas = [];
  for (const [, id] of html.matchAll(/\bid="([^"]+)"/g)) elementos.set(id, new Elemento(id));
  for (const [, id, contenido] of html.matchAll(/<select id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)) {
    elementos.get(id).options = [...contenido.matchAll(/<option value="([^"]*)"[^>]*>([^<]*)<\/option>/g)]
      .map(([, value, textContent]) => ({value, textContent}));
  }
  const $ = id => { assert(elementos.has(id), `Falta ${id} en ${nombre}`); return elementos.get(id); };
  const document = {getElementById: id => elementos.get(id) || null,
    querySelectorAll: selector => selector.startsWith('.auditoria') ? [...elementos.values()] : [],
    createElement: id => new Elemento(id), createTextNode: texto => texto,
    body: {dataset: {panel: nombre === 'Panel_Volumenes' ? 'volumenes' : ''}, appendChild() {}}, addEventListener() {}};
  const fetch = async (ruta, opciones) => {
    consultas.push({ruta, opciones});
    return {ok: true, json: async () => structuredClone(datos), blob: async () => new Blob(['PDF']),
      headers: {get: () => "attachment; filename*=UTF-8''reporte.pdf"}};
  };
  vm.runInNewContext(fs.readFileSync(`web/js/${script}.js`, 'utf8'), {
    window: {PanelSesion: {usuario: {rol: 'administrador'}, permite: () => true, listo: Promise.resolve()}}, document, fetch, Blob, URL, URLSearchParams, console,
    Option: class {constructor(textContent, value) {this.textContent = textContent; this.value = String(value);}},
    Date: class extends Date { constructor(...args) { super(...(args.length ? args : [ahora])); } },
    distribucionVolumen: globalThis.distribucionVolumen,
    setTimeout() {}, setInterval() {},
  });
  await new Promise(resolve => setImmediate(resolve));
  const cambiar = async (id, valor) => {$(id).value = valor; await $(id).listeners.change();};
  return {$, cambiar, consultas, fijarFecha: fecha => {ahora = fecha;}, filas: id => ($(id).innerHTML.match(/<tr>(?!<td colspan=)/g) || []).length};
}
async function probarConciliacion(sufijo) {
  const {$, cambiar, consultas, filas, fijarFecha} = await cargarPanel('Panel_Conciliacion' + sufijo, 'conciliacion', {
    registros, unidades: ['Andina', 'El Salvador'], avisos: [], omitidos: [], actualizado: '2026-01-01', fuentes: '',
  });
  assert.equal(filas('filas'), 48);
  for (let trimestre = 1; trimestre <= 4; trimestre++) {
    await cambiar('trimestre', trimestre);
    assert.equal(filas('filas'), 12);
    await $('generar-pdf').listeners.click();
    const reporte = JSON.parse(consultas.at(-1).opciones.body);
    assert.equal(reporte.registros.length, 12);
    assert(reporte.registros.every(r => Math.ceil(r.mes / 3) === trimestre));
    assert.match(reporte.filtros.Trimestre, /trimestre/);
  }
  await cambiar('unidad', 'Andina'); await cambiar('anio', '2026');
  assert.equal(filas('filas'), 3);
  await cambiar('mes', '10'); assert.equal(filas('filas'), 1);
  await cambiar('mes', '9'); assert.equal($('generar-pdf').disabled, true);
  await $('limpiar').listeners.click(); assert.equal(filas('filas'), 48);
  await cambiar('trimestre', '2'); await $('actualizar').listeners.click();
  assert.equal($('trimestre').value, '2'); assert.equal(filas('filas'), 12);
  await cambiar('unidad', 'Andina'); await cambiar('edp', '1'); await cambiar('filtro-estado', 'diferencia');
  await $('este-mes').listeners.click();
  assert.equal($('unidad').value, 'Andina'); assert.equal($('anio').value, '2026'); assert.equal($('mes').value, '10');
  assert.equal($('trimestre').value, ''); assert.equal($('edp').value, ''); assert.equal($('filtro-estado').value, '');
  assert.equal(filas('filas'), 1);
  await $('generar-pdf').listeners.click();
  assert(JSON.parse(consultas.at(-1).opciones.body).registros.every(r => r.anio === 2026 && r.mes === 10));
  fijarFecha('2030-01-01T02:00:00Z'); // En Santiago todavía es diciembre de 2029.
  await $('este-mes').listeners.click();
  assert.equal($('anio').value, '2029'); assert.equal($('mes').value, '12'); assert.equal(filas('filas'), 0);
  await $('actualizar').listeners.click(); assert.equal(filas('filas'), 0); assert.equal($('anio').value, '2029');
  await $('limpiar').listeners.click(); assert.equal(filas('filas'), 48);
}
async function probarDensidades(sufijo, nombre = 'Panel_Densidades') {
  const tickets = registros.filter(r => r.unidad === 'El Salvador').map(r => ({...r, estado: 'sin_evaluar',
    residuo: 'Madera', residuo_original: 'Madera', ticket: 'T', fila: 1, referencia_maestra: {},
    volumen_m3: null, volumen_tipo: null, capacidades_compatibles: [], motivo: '', archivo: 'EDP.xlsx'}));
  const {$, cambiar, consultas, filas, fijarFecha} = await cargarPanel(nombre + sufijo, 'densidades', {
    tickets, unidad: 'El Salvador', volumenes: [15], tolerancia_m3: 3, umbral_m3: 15,
    maestra: {avisos: [], materiales: []}, avisos_edp: [{anio: 2026, mes: 1, edp: 1, mensaje: 'Aviso de enero'}],
    actualizado: '2026-01-01',
  });
  assert.equal(filas('filas'), 24);
  for (let trimestre = 1; trimestre <= 4; trimestre++) {
    await cambiar('trimestre', trimestre); assert.equal(filas('filas'), 6);
    await $('generar-pdf').listeners.click();
    assert.equal(new URL(consultas.at(-1).ruta, 'http://localhost').searchParams.get('trimestre'), String(trimestre));
    assert.equal($('avisos').hidden, trimestre !== 1);
  }
  await cambiar('anio', '2026'); assert.equal(filas('filas'), 3);
  await cambiar('mes', '12'); assert.equal(filas('filas'), 1);
  await $('descargar-compilado').listeners.click();
  assert.match(consultas.at(-1).ruta, /compilado.zip\?unidad=El\+Salvador&anio=2026&trimestre=4&mes=12/);
  await cambiar('mes', '9'); assert.equal($('generar-pdf').disabled, true);
  $('limpiar').onclick(); assert.equal(filas('filas'), 24); assert.equal($('trimestre').value, '');
  await cambiar('trimestre', '2'); await $('actualizar').onclick();
  assert.equal($('trimestre').value, '2'); assert.equal(filas('filas'), 6);
  $('buscar').value = 'sin coincidencias'; $('edp').value = '1';
  if (nombre === 'Panel_Volumenes') $('tramo_volumen').value = 'mayor_30';
  $('este-mes').onclick();
  assert.equal($('anio').value, '2026'); assert.equal($('mes').value, '10'); assert.equal($('unidad').value, 'El Salvador');
  assert.equal($('buscar').value, ''); assert.equal($('trimestre').value, ''); assert.equal(filas('filas'), 1);
  await $('generar-pdf').listeners.click();
  const parametros = new URL(consultas.at(-1).ruta, 'http://localhost').searchParams;
  assert.equal(parametros.get('anio'), '2026'); assert.equal(parametros.get('mes'), '10'); assert.equal(parametros.get('trimestre'), null);
  fijarFecha('2030-01-01T02:00:00Z'); $('este-mes').onclick();
  assert.equal($('anio').value, '2029'); assert.equal($('mes').value, '12'); assert.equal(filas('filas'), 0);
  await $('actualizar').onclick(); assert.equal(filas('filas'), 0); assert.equal($('anio').value, '2029');
  $('limpiar').onclick(); assert.equal(filas('filas'), 24);
}
async function probarAuditoria(sufijo) {
  const {$, cambiar, filas, fijarFecha} = await cargarPanel('Panel_Auditoria_EDP' + sufijo, 'auditoria', {
    unidades: ['Andina', 'El Salvador'], estados_pago: registros, muestras: [], avisos: [],
    fuentes: registros.map((r, i) => ({...r, id: 'fuente-' + i, nombre: 'EDP.xlsx', origen: 'Fuentes'})),
  });
  assert.equal(filas('estados-pago'), 48);
  for (let trimestre = 1; trimestre <= 4; trimestre++) {
    await cambiar('chequeo-trimestre', trimestre); assert.equal(filas('estados-pago'), 12);
    await cambiar('trimestre', trimestre);
    const meses = $('mes').options.filter(o => o.value).map(o => Number(o.value));
    assert.deepEqual(meses, [trimestre * 3 - 2, trimestre * 3 - 1, trimestre * 3]);
    assert.equal(filas('estados-pago'), 12, 'El trimestre de selección no cambia el chequeo');
    assert.equal($('fuente').options.length, trimestre === 1 ? 1 : 3);
  }
  await cambiar('chequeo-unidad', 'Andina'); await cambiar('chequeo-anio', '2026');
  assert.equal(filas('estados-pago'), 3);
  await cambiar('chequeo-mes', '12'); assert.equal(filas('estados-pago'), 1);
  await cambiar('chequeo-trimestre', '1');
  assert.equal($('chequeo-mes').value, '', 'El mes incompatible se restablece en los filtros dependientes');
  assert.equal(filas('estados-pago'), 3);
  await $('actualizar').listeners.click();
  assert.equal($('chequeo-trimestre').value, '1'); assert.equal(filas('estados-pago'), 3);
  await cambiar('chequeo-trimestre', ''); assert.equal(filas('estados-pago'), 12);
  await cambiar('chequeo-edp', '1'); await cambiar('chequeo-estado', 'parcial');
  await $('chequeo-este-mes').listeners.click();
  assert.equal($('chequeo-unidad').value, 'Andina'); assert.equal($('chequeo-anio').value, '2026'); assert.equal($('chequeo-mes').value, '10');
  assert.equal($('chequeo-edp').value, ''); assert.equal($('chequeo-estado').value, ''); assert.equal(filas('estados-pago'), 1);
  await $('este-mes').listeners.click(); await new Promise(resolve => setImmediate(resolve));
  assert.equal($('anio').value, '2026'); assert.equal($('mes').value, '10'); assert.equal($('trimestre').value, '');
  assert.equal($('fuente').options.length, 1); assert($('fuente').value);
  fijarFecha('2030-01-01T02:00:00Z');
  await $('chequeo-este-mes').listeners.click(); await $('este-mes').listeners.click(); await new Promise(resolve => setImmediate(resolve));
  assert.equal($('chequeo-anio').value, '2029'); assert.equal($('anio').value, '2029');
  assert.equal($('chequeo-mes').value, '12'); assert.equal($('mes').value, '12');
  assert.equal(filas('estados-pago'), 0); assert.equal($('fuente').value, ''); assert.equal($('sortear').disabled, true);
  await $('actualizar').listeners.click(); await new Promise(resolve => setImmediate(resolve));
  assert.equal(filas('estados-pago'), 0); assert.equal($('anio').value, '2029'); assert.equal($('mes').value, '12');
  await $('chequeo-limpiar').listeners.click(); assert.equal(filas('estados-pago'), 48);
  await $('limpiar').listeners.click(); await new Promise(resolve => setImmediate(resolve));
  assert.equal($('unidad').value, ''); assert.equal($('anio').value, ''); assert.equal($('mes').value, '');
  assert.equal($('fuente').options.length, 48);
}
(async () => {
  for (const sufijo of ['']) {
    await probarConciliacion(sufijo); await probarDensidades(sufijo); await probarAuditoria(sufijo);
  }
  await probarDensidades('', 'Panel_Volumenes');
  console.log('OK: trimestres, Este Mes, limpieza, exportaciones, recarga sin datos y cambio de año en Santiago en los cuatro paneles.');
})().catch(error => {console.error(error); process.exitCode = 1;});
