/* Límites aplicados al volumen completo, antes de redondear. */
(() => {
  'use strict';
  const tramos = [
    {id:'menor_10', nombre:'Menor a 10 m³', color:'#0E81C5'},
    {id:'10_20', nombre:'10 a menos de 20 m³', color:'#2E9E6B'},
    {id:'20_30', nombre:'20 a 30 m³', color:'#997000'},
    {id:'mayor_30', nombre:'Mayor a 30 m³', color:'#a12424'},
    {id:'sin_volumen', nombre:'Sin volumen calculable', color:'#5B6B7C'}
  ];
  function clasificar(volumen) {
    if (typeof volumen !== 'number' || !Number.isFinite(volumen) || volumen < 0) return 'sin_volumen';
    return volumen < 10 ? 'menor_10' : volumen < 20 ? '10_20' : volumen <= 30 ? '20_30' : 'mayor_30';
  }
  globalThis.distribucionVolumen = {tramos, clasificar};
})();
