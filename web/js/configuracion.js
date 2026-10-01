'use strict';
// Única fuente de preferencias para todos los reportes del portal.
(() => {
  const clave = 'resiter.portal.config.v1';
  const normalizar = s => String(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().replace(/\s+/g, ' ').toUpperCase();
  let aviso = '';
  const leer = key => { try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch { aviso = 'No se pudo leer el almacenamiento del navegador.'; return null; } };
  const lista = v => Array.isArray(v) ? v.filter(x => typeof x === 'string') : [];
  function cargar() {
    const c = leer(clave);
    if (c && typeof c === 'object') return {regiones: lista(c.regiones), cecos: lista(c.cecos), catalogo: lista(c.catalogo), centros: lista(c.centros), ocultos: lista(c.ocultos)};
    const r = leer('resiter.reportabilidad.config.v1') || {}, m = leer('resiter.mantenciones.config.v1') || {};
    return {regiones: [...new Set([...lista(r.regiones), ...lista(m.regiones), ...lista(leer('resiter.programa.config.v1'))].map(normalizar))], cecos: lista(r.cecos), catalogo: [], centros: [], ocultos: []};
  }
  let estado = cargar();
  const paneles = {
    reportabilidad: ['Reportabilidad', [['evolucion','Evolución semanal'],['barras','Cumplimiento por región / CeCo'],['tabla','Detalle por región y CeCo']]],
    seguimiento: ['Seguimiento KM-HR', [['lecturas','Lecturas semanales'],['ritmo','Uso diario'],['tabla','Detalle de equipos']]],
    resumen: ['Resumen de mantención', [['tabla','Resumen por región y CeCo'],['patentes','Detalle de patentes']]],
    calendario: ['Calendario de mantención', [['calendario','Calendario mensual'],['agenda','Tabla de agenda']]],
    programa: ['Programa Mantención', [['cumplimiento','Cumplimiento mensual'],['cantidades','Programadas y realizadas'],['estados','Distribución de estados'],['tabla','Detalle por región y CeCo']]]
  };
  function persistir() {
    try { localStorage.setItem(clave, JSON.stringify(estado)); aviso = 'Configuración guardada en este navegador.'; }
    catch { aviso = 'No se pudo guardar. Los cambios solo se conservan en esta página; permite el almacenamiento para aplicarlos entre paneles.'; }
  }
  function aplicar() {
    document.querySelectorAll('[data-vista]').forEach(el => el.classList.toggle('vista-oculta', estado.ocultos.includes(el.dataset.vista)));
    document.querySelectorAll('[data-grupo-vistas]').forEach(el => el.classList.toggle('vista-oculta', [...el.querySelectorAll('[data-vista]')].every(n => n.classList.contains('vista-oculta'))));
  }
  function cambiar() { persistir(); aplicar(); window.dispatchEvent(new Event('portal-config')); }
  window.PortalConfig = {
    paneles, normalizar,
    incluida: region => !estado.regiones.includes(normalizar(region)),
    cecoIncluido: ceco => !estado.cecos.includes(ceco),
    estado: () => JSON.parse(JSON.stringify(estado)),
    aviso: () => aviso,
    registrar(regiones, centros = []) {
      const nuevas = [...new Set([...estado.catalogo, ...regiones].filter(x => typeof x === 'string').map(normalizar))].sort();
      const cecos = [...new Set([...estado.centros, ...centros])].sort();
      if (JSON.stringify(nuevas) !== JSON.stringify(estado.catalogo) || JSON.stringify(cecos) !== JSON.stringify(estado.centros)) { estado.catalogo = nuevas; estado.centros = cecos; persistir(); }
    },
    seleccionar(tipo, valor, incluir) { const claveValor = tipo === 'regiones' ? normalizar(valor) : valor; estado[tipo] = estado[tipo].filter(x => x !== claveValor); if (!incluir) estado[tipo].push(claveValor); cambiar(); },
    regionesTodas(incluir) { estado.regiones = incluir ? [] : [...estado.catalogo]; cambiar(); },
    restaurarVistas() { estado.ocultos = []; cambiar(); }
  };
  window.addEventListener('storage', e => { if (e.key === clave || e.key === null) { estado = cargar(); aplicar(); window.dispatchEvent(new Event('portal-config')); } });
  aplicar();
})();
