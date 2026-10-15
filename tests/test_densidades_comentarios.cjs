'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'web/pages/Panel_Densidades.html'), 'utf8');
const source = fs.readFileSync(path.join(root, 'web/js/densidades.js'), 'utf8');
class Element {
  constructor() { this.value = ''; this.options = [{textContent:'Todos', value:''}]; this.listeners = {}; }
  replaceChildren(...children) { this.options = children; }
  add(option) { this.options.push(option); }
  addEventListener(event, callback) { this.listeners[event] = callback; }
}
const tickets = ['coincide','no_coincide_menor','no_coincide_mayor','sin_evaluar'].map((estado,i) => ({
  id:String(i), unidad:'Andina', anio:2026, mes:5, periodo:'2026-05', edp:47, fila:i+2,
  ticket:String(i), residuo:'Madera', residuo_original:'Madera', peso_kg:1000,
  volumen_m3:20, densidad_kg_m3:200, volumen_tipo:20, capacidades_compatibles:[],
  referencia_maestra:{}, estado, motivo:'Motivo calculado', comentario:'<script>texto</script>'
}));
async function comprobar(rol) {
  const elements = new Map([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], new Element()]));
  elements.set('paginacion', new Element()); elements.get('unidad').value = 'Andina';
  const datos = {unidad:'Andina', tickets:structuredClone(tickets), volumenes:[13,20,40], tolerancia_m3:3,
    umbral_m3:13, actualizado:'2026-10-08', avisos_edp:[], maestra:{materiales:[], avisos:[]}};
  const llamadas = [], downloads = [];
  const context = {document:{body:{dataset:{}}, getElementById:id => elements.get(id), createElement:() => ({click(){}})},
    window:{PanelSesion:{permite:permiso => permiso === 'revisar' && rol !== 'general', listo:Promise.resolve()}},
    Option:class {constructor(textContent,value) {this.textContent=textContent; this.value=value;}},
    Intl, Date, URLSearchParams, Blob, setTimeout:() => {},
    URL:{createObjectURL:blob => {downloads.push(blob); return 'blob:test';}, revokeObjectURL(){}},
    fetch:async (url, opciones) => {
      llamadas.push([url, opciones]);
      return {ok:true,json:async () => opciones?.method === 'POST' ? {id:'2',comentario:JSON.parse(opciones.body).comentario,
        comentario_autor:'auditor@prueba.cl',comentario_actualizado:'2026-10-08T12:00:00Z'} : datos};
    }};
  vm.runInNewContext(source,context);
  await new Promise(resolve => setImmediate(resolve));
  const filas = elements.get('filas').innerHTML;
  for (const texto of ['Transacción es Consistente con las tolvas en Faena',
    'Transacción No es Consistente con las tolvas en Faena', 'Transacción No óptima con las tolvas en Faena', 'Sin evaluar']) assert.ok(filas.includes(texto));
  assert.equal((filas.match(/<textarea/g) || []).length, rol === 'general' ? 0 : 1);
  assert.ok(!filas.includes('<script>'));
  if (rol !== 'general') {
    assert.match(filas, /data-comentario-id="2"/);
    const campo = {value:'Peso requiere revisión'}, boton = {}, mensaje = {};
    const formulario = {dataset:{comentarioId:'2'}, querySelector:selector => ({textarea:campo,button:boton,'[role="status"]':mensaje})[selector]};
    await elements.get('filas').listeners.submit({preventDefault(){}, target:{closest:() => formulario}});
    assert.equal(llamadas.at(-1)[0],'/api/densidades/comentario');
    assert.equal(JSON.parse(llamadas.at(-1)[1].body).id,'2');
    assert.equal(mensaje.textContent,'Comentario guardado.');
    assert.equal(campo.disabled,false);
    elements.get('exportar').listeners.click();
    assert.match(await downloads.at(-1).text(), /Peso requiere revisión/);
  }
}
(async () => {
  for (const rol of ['general','auditor','administrador']) await comprobar(rol);
  assert.match(html, /<th>Comentario<\/th>/);
  console.log('OK: estados, comentarios por rol, texto escapado, guardado y exportación.');
})().catch(error => {console.error(error); process.exitCode=1;});
