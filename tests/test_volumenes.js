/* Ejecutar: node tests/test_volumenes.js */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
require(path.join(root, 'web/js/tramos_volumen.js'));
const {clasificar} = globalThis.distribucionVolumen;
for (const [v, expected] of [[0,'menor_10'],[9.9999,'menor_10'],[10,'10_20'],
  [19.9999,'10_20'],[20,'20_30'],[30,'20_30'],[30.0001,'mayor_30'],
  [null,'sin_volumen'],[-1,'sin_volumen'],[NaN,'sin_volumen'],[Infinity,'sin_volumen']]) {
  assert.equal(clasificar(v), expected, String(v));
}
class Element {
  constructor() {this.value = ''; this.options = [{textContent:'Todos',value:''}]; this.listeners = {}; this.rows = [];}
  set innerHTML(value) {
    this.html = value;
    this.rows = [...value.matchAll(/<tr>/g)].map(() => ({cells:[{}], insertCell:() => ({})}));
  }
  get innerHTML() {return this.html || '';}
  replaceChildren(...children) {this.options = children; this.html = '';}
  add(option) {this.options.push(option);}
  addEventListener(event, callback) {this.listeners[event] = callback;}
  closest() {return {after:() => {}};}
}
const html = fs.readFileSync(path.join(root,'web/pages/Panel_Volumenes.html'),'utf8');
const elements = new Map([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1],new Element()]));
elements.set('paginacion',new Element());
elements.get('unidad').value = 'El Salvador';
const tickets = [0,10,20,30,31,null].map((volumen_m3,i) => ({
  volumen_m3, unidad:'El Salvador', anio:2026, mes:i === 0 ? 1 : 5, periodo:'2026-05',
  edp:47, fila:i+1, ticket:i, residuo:'Madera', residuo_original:'Madera',
  referencia_maestra:{hoja:'AUX',celda_inferior:'B2',celda_superior:'C2'},
  estado:volumen_m3 == null ? 'sin_evaluar' : 'coincide', motivo:'',
  capacidades_compatibles:[], volumen_tipo:20, peso_kg:1000, densidad_kg_m3:200
}));
const context = {
  document:{body:{dataset:{panel:'volumenes'}}, getElementById:id => elements.get(id),
    createElement:() => ({click:() => {}}), createTextNode:value => value},
  Option:class {constructor(textContent,value) {this.textContent=textContent;this.value=value;}},
  URLSearchParams, Intl, Date, console, Blob,
  URL:{createObjectURL:blob => {downloads.push(blob); return 'blob:test';},revokeObjectURL:() => {}},
  setTimeout:() => {},
  distribucionVolumen:globalThis.distribucionVolumen,
  fetch:async url => {
    requests.push(url);
    return {ok:true,blob:async () => new Blob(['PDF']),headers:{get:() => "attachment; filename*=UTF-8''test.pdf"},json:async () => ({unidad:'El Salvador',tickets,
    volumenes:[15,20,30],tolerancia_m3:3,umbral_m3:15,actualizado:'2026-10-07',
    avisos_edp:[],maestra:{archivo:'maestra.xlsx',materiales:[],avisos:[]}})};
  }
};
const requests = [], downloads = [];
vm.runInNewContext(fs.readFileSync(path.join(root,'web/js/densidades.js'),'utf8'),context);
setImmediate(async () => {
  const value = id => elements.get(id).textContent;
  assert.match(value('kpi-total'), /^1 .*16,7%$/);
  assert.match(value('kpi-amarillos'), /^2 .*33,3%$/);
  assert.match(value('kpi-pendientes'), /^1 .*16,7%$/);
  assert.match(value('cobertura'), /91,00 m³/);
  elements.get('tramo_volumen').value = '20_30';
  elements.get('tramo_volumen').listeners.change();
  assert.match(value('kpi-amarillos'), /^2 .*100,0%$/);
  assert.match(value('cobertura'), /50,00 m³/);
  await elements.get('generar-pdf').listeners.click();
  assert.match(requests.at(-1), /^\/api\/volumenes\/reporte.pdf\?/);
  assert.match(requests.at(-1), /tramo_volumen=20_30/);
  await elements.get('descargar-compilado').listeners.click();
  assert.match(requests.at(-1), /^\/api\/volumenes\/compilado.zip\?/);
  assert.match(requests.at(-1), /tramo_volumen=20_30/);
  elements.get('exportar').listeners.click();
  const csv = await downloads.at(-1).text();
  assert.match(csv, /"tramo_volumen"/);
  assert.equal(csv.split('\r\n').length,3);
  assert.match(csv, /20 a 30 m³/);
  elements.get('trimestre').value = '1';
  elements.get('trimestre').listeners.change();
  assert.match(value('cobertura'), /^0 tickets/);
  elements.get('limpiar').onclick();
  assert.match(value('cobertura'), /^6 tickets/);
  elements.get('trimestre').value = '1';
  elements.get('trimestre').listeners.change();
  assert.match(value('cobertura'), /^1 tickets/);
  assert.match(value('kpi-total'), /^1 .*100,0%$/);
  console.log('Distribución: límites, porcentajes, sumas, filtros combinados y selección vacía correctos.');
});
