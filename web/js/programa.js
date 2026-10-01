'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const campos = ['total', 'realizadas', 'regularizadas', 'no_realizadas', 'na'];
  const numero = new Intl.NumberFormat('es-CL', {maximumFractionDigits: 1});
  const hoy = new Date();
  const colores = ['#2E9E6B', '#C43C39', '#D98A1E', '#7C8998'];
  function svgNodo(tipo, atributos = {}, texto) {
    const nodo = document.createElementNS('http://www.w3.org/2000/svg', tipo);
    Object.entries(atributos).forEach(([k, v]) => nodo.setAttribute(k, v));
    if (texto !== undefined) nodo.textContent = texto;
    return nodo;
  }
  function lienzo(id, ancho, alto, titulo) {
    const svg = svgNodo('svg', {viewBox: `0 0 ${ancho} ${alto}`, role: 'img', 'aria-label': titulo});
    svg.append(svgNodo('title', {}, titulo));
    $(id).replaceChildren(svg);
    return svg;
  }
  let seleccion = {nivel: 'total'};
  let datosActuales = null;
  function nombresRegiones(datos) {
    return [...new Set([...datos.regiones.map(r => r.region), ...(datos.historico || []).flatMap(m => (m.regiones || []).map(r => r.region))])].sort();
  }
  function aplicarConfiguracion(datos) {
    function filtrar(resumen) {
      const regiones = (resumen.regiones || []).filter(r => PortalConfig.incluida(r.region));
      const totales = {};
      for (const campo of [...campos, 'sin_clasificar']) totales[campo] = regiones.reduce((s,r) => s + (r[campo] || 0), 0);
      const aplicables = totales.total - totales.na;
      return {...resumen, ...totales, regiones, porcentaje: aplicables ? totales.realizadas / aplicables * 100 : null};
    }
    return {...filtrar(datos), historico: (datos.historico || []).map(filtrar)};
  }
  function configurar(){if(datosActuales)PortalConfig.registrar(nombresRegiones(datosActuales));}
  window.addEventListener('portal-config',()=>{if(datosActuales){prepararRegiones(aplicarConfiguracion(datosActuales));renderizar(datosActuales);}});
  const nombreMes = mes => new Intl.DateTimeFormat('es-CL', {month: 'long', timeZone: 'UTC'}).format(new Date(mes + '-01T00:00:00Z'));
  function cambiarSeleccion(nueva) {
    seleccion = nueva;
    $('region-programa').value = seleccion.region || '';
    if (datosActuales) renderizar(datosActuales);
  }
  function datosRegion(datos) {
    if (!seleccion.region) return datos;
    const region = datos.regiones.find(r => r.region === seleccion.region);
    return {...datos, ...(region || {total: 0, realizadas: 0, regularizadas: 0, no_realizadas: 0, na: 0, sin_clasificar: 0, porcentaje: null}), regiones: region ? [region] : []};
  }
  function prepararRegiones(datos) {
    const nombres = nombresRegiones(datos);
    $('region-programa').replaceChildren();
    for (const nombre of ['', ...nombres]) {
      const opcion = document.createElement('option'); opcion.value = nombre;
      opcion.textContent = nombre || 'Todas las regiones'; $('region-programa').append(opcion);
    }
    if (seleccion.region && !nombres.includes(seleccion.region)) seleccion = {nivel: 'total'};
    $('region-programa').value = seleccion.region || '';
  }
  function historial(datos, porcentaje) {
    const clave = porcentaje ? 'cumplimiento' : 'cantidades';
    const id = 'grafico-' + clave;
    const estado = seleccion;
    const registros = datos.historico || [];
    $(id).replaceChildren();
    if (!registros.length) { $(id).textContent = 'Sin datos históricos disponibles.'; return; }
    const detalleDisponible = registros.every(r => Array.isArray(r.regiones));
    const regiones = [...new Set(registros.flatMap(r => (r.regiones || []).map(g => g.region)))].sort();
    const entidades = estado.nivel === 'total' ? ['Total general'] : estado.nivel === 'regiones' ? regiones :
      [...new Set(registros.flatMap(r => (r.regiones || []).filter(g => g.region === estado.region).flatMap(g => g.cecos.map(c => c.ceco))))].sort();
    const controles = document.createElement('div');
    controles.className = 'config-acciones';
    const ruta = document.createElement('strong');
    ruta.textContent = estado.nivel === 'total' ? 'Total general' : estado.nivel === 'regiones' ? 'Todas las regiones' : 'CeCo · ' + estado.region;
    controles.append(ruta);
    function boton(nombre, accion) {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = nombre;
      b.addEventListener('click', accion); controles.append(b);
    }
    if (estado.nivel !== 'total') boton('← Total general', () => { cambiarSeleccion({nivel: 'total'}); });
    if (estado.nivel === 'cecos') boton('← Todas las regiones', () => { cambiarSeleccion({nivel: 'regiones'}); });
    const ayuda = document.createElement('p'); ayuda.className = 'nota';
    ayuda.textContent = !detalleDisponible ? 'Reinicia el servidor para habilitar el desglose por región y CeCo.' : estado.nivel === 'total' ? 'Pulsa una línea, un punto o su leyenda para ver todas las regiones.' : estado.nivel === 'regiones' ? 'Pulsa una región para ver todos sus CeCo.' : 'Detalle de todos los CeCo de la región. Línea continua: programadas; discontinua: realizadas.';
    const series = [];
    entidades.forEach((nombre, indice) => {
      const color = estado.nivel === 'total' ? '#166887' : 'hsl(' + ((indice * 137.508) % 360) + ',65%,36%)';
      (porcentaje ? ['porcentaje'] : ['total', 'realizadas']).forEach(campo => {
        const valores = registros.map(r => {
          let dato = r;
          if (estado.nivel !== 'total') {
            dato = (r.regiones || []).find(g => g.region === (estado.nivel === 'regiones' ? nombre : estado.region));
            if (estado.nivel === 'cecos') dato = dato?.cecos.find(c => c.ceco === nombre);
          }
          return dato ? dato[campo] : (porcentaje ? null : 0);
        });
        series.push({nombre, campo, valores, color: estado.nivel === 'total' && campo === 'realizadas' ? '#2E9E6B' : color});
      });
    });
    const ancho = Math.max(560, registros.length * 110 + 110), alto = 310;
    const svg = svgNodo('svg', {viewBox: '0 0 ' + ancho + ' ' + alto, role: 'group', 'aria-label': (porcentaje ? 'Cumplimiento' : 'Programadas y realizadas') + ' · ' + ruta.textContent});
    svg.style.minWidth = ancho + 'px';
    const scroll = document.createElement('div'); scroll.style.overflowX = 'auto'; scroll.append(svg);
    const maximo = porcentaje ? 100 : Math.max(1, ...series.flatMap(s => s.valores));
    const y = v => 245 - v / maximo * 200;
    const x = i => 85 + i * (ancho - 150) / Math.max(1, registros.length - 1);
    for (let i = 0; i <= 5; i++) {
      const valor = maximo * i / 5;
      svg.append(svgNodo('line', {x1: 55, x2: ancho - 20, y1: y(valor), y2: y(valor), stroke: '#DDE4EC'}));
      svg.append(svgNodo('text', {x: 48, y: y(valor) + 4, 'text-anchor': 'end', fill: '#5B6B7C'}, numero.format(valor) + (porcentaje ? '%' : '')));
    }
    registros.forEach((r,i) => {
      const etiqueta = svgNodo('text', {x: x(i), y: 275, 'text-anchor': 'middle', fill: '#1B2A3A'});
      etiqueta.append(svgNodo('tspan', {x: x(i)}, nombreMes(r.mes)), svgNodo('tspan', {x: x(i), dy: 17, fill: '#5B6B7C'}, r.mes.slice(0,4)));
      svg.append(etiqueta);
    });
    const leyenda = document.createElement('div'); leyenda.className = 'leyenda';
    series.forEach(s => {
      const etiqueta = s.nombre + (porcentaje ? '' : s.campo === 'total' ? ' · Programadas' : ' · Realizadas');
      const avanzar = () => {
        if (!detalleDisponible || estado.nivel === 'cecos') return;
        cambiarSeleccion(estado.nivel === 'total' ? {nivel: 'regiones'} : {nivel: 'cecos', region: s.nombre});
      };
      const grupo = svgNodo('g', {'aria-label': etiqueta});
      if (detalleDisponible && estado.nivel !== 'cecos') {
        grupo.setAttribute('role', 'button'); grupo.setAttribute('tabindex', '0'); grupo.style.cursor = 'pointer';
        grupo.addEventListener('click', avanzar);
        grupo.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); avanzar(); } });
      }
      let d = '', anterior = false;
      s.valores.forEach((v,i) => { if (v === null) { anterior = false; return; } d += (anterior ? ' L' : ' M') + x(i) + ' ' + y(v); anterior = true; });
      grupo.append(svgNodo('path', {d, fill: 'none', stroke: s.color, 'stroke-width': 3, 'stroke-dasharray': s.campo === 'realizadas' ? '7 4' : 'none'}));
      grupo.append(svgNodo('path', {d, fill: 'none', stroke: 'transparent', 'stroke-width': 16}));
      s.valores.forEach((v,i) => {
        if (v === null) return;
        const punto = svgNodo('circle', {cx: x(i), cy: y(v), r: 5, fill: s.color, stroke: '#fff', 'stroke-width': 1});
        punto.append(svgNodo('title', {}, etiqueta + ' · ' + registros[i].mes + ': ' + numero.format(v) + (porcentaje ? '%' : '')));
        grupo.append(punto);
        if (series.length <= 2) grupo.append(svgNodo('text', {x: x(i), y: y(v) + (s.campo === 'realizadas' ? 20 : -12), 'text-anchor': 'middle', fill: s.color}, numero.format(v) + (porcentaje ? '%' : '')));
      });
      svg.append(grupo);
      const b = document.createElement('button'); b.type = 'button'; b.style.color = s.color;
      b.textContent = (s.campo === 'realizadas' ? '┄ ' : '━ ') + etiqueta;
      b.addEventListener('click', avanzar); leyenda.append(b);
    });
    $(id).append(controles, ayuda, scroll, leyenda);
  }
  function graficos(datos) {
    historial(datos, true);
    historial(datos, false);
    datos = datosRegion(datos);
    $('titulo-torta').textContent = `Estados · ${nombreMes(datos.mes)} ${datos.mes.slice(0,4)} · ${seleccion.region || 'Todas las regiones'}`;
    const estados = [['Realizadas', datos.realizadas], ['No realizadas', datos.no_realizadas], ['Regularizadas', datos.regularizadas], ['N/A', datos.na]];
    const total = estados.reduce((s, e) => s + e[1], 0);
    $('leyenda-estados').replaceChildren();
    estados.forEach(([nombre, cantidad], i) => {
      const p = document.createElement('p');
      const marca = document.createElement('span');
      marca.textContent = '● ';
      marca.style.color = colores[i];
      p.append(marca, `${nombre}: ${numero.format(cantidad)} (${total ? numero.format(cantidad / total * 100) : '0'}%)`);
      $('leyenda-estados').append(p);
    });
    const nota = document.createElement('p');
    nota.className = 'nota';
    nota.textContent = `Distribución sobre ${total} patentes con uno de los cuatro estados.${datos.sin_clasificar ? ` ${datos.sin_clasificar} patentes sin estado válido quedan fuera de la torta.` : ''}`;
    $('leyenda-estados').append(nota);
    if (!total) { $('grafico-estados').textContent = 'Sin estados disponibles para este mes.'; return; }
    const svg = lienzo('grafico-estados', 360, 280, `Distribución de estados de ${datos.mes}`);
    let angulo = -Math.PI / 2;
    estados.forEach(([nombre, cantidad], i) => {
      if (!cantidad) return;
      const fin = angulo + cantidad / total * Math.PI * 2;
      const sector = cantidad === total ? svgNodo('circle', {cx: 180, cy: 140, r: 118, fill: colores[i]}) : svgNodo('path', {
        d: `M180 140 L${180 + 118 * Math.cos(angulo)} ${140 + 118 * Math.sin(angulo)} A118 118 0 ${fin - angulo > Math.PI ? 1 : 0} 1 ${180 + 118 * Math.cos(fin)} ${140 + 118 * Math.sin(fin)} Z`,
        fill: colores[i], stroke: '#fff', 'stroke-width': 2
      });
      sector.append(svgNodo('title', {}, `${nombre}: ${cantidad} (${numero.format(cantidad / total * 100)}%)`));
      svg.append(sector);
      if (cantidad / total >= 0.06) svg.append(svgNodo('text', {x: 180 + 78 * Math.cos((angulo + fin) / 2), y: 145 + 78 * Math.sin((angulo + fin) / 2), 'text-anchor': 'middle', fill: '#fff', 'font-weight': 'bold'}, `${numero.format(cantidad / total * 100)}%`));
      angulo = fin;
    });
  }
  $('mes').value = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`;
  function semaforo(p) {
    const span = document.createElement('span');
    span.className = `semaforo ${p === null ? 'neutro' : p >= 90 ? 'verde' : p >= 70 ? 'amarillo' : 'rojo'}`;
    span.textContent = p === null ? '—' : `${numero.format(p)}%`;
    span.title = p === null ? 'Sin patentes aplicables' : p >= 90 ? 'Verde' : p >= 70 ? 'Amarillo' : 'Rojo';
    return span;
  }
  function fila(nombre, datos, clase) {
    const tr = document.createElement('tr');
    tr.className = clase;
    for (const valor of [nombre, ...campos.map(c => numero.format(datos[c]))]) {
      const td = document.createElement('td');
      td.textContent = valor;
      tr.append(td);
    }
    const td = document.createElement('td');
    td.append(semaforo(datos.porcentaje));
    tr.append(td);
    return tr;
  }
  function renderizar(fuente) {
    fuente = aplicarConfiguracion(fuente);
    const visibles = nombresRegiones(fuente).length;
    $('programa-alcance').textContent = visibles ? `${visibles} regiones incluidas. Los gráficos y totales consideran solo las regiones configuradas.` : 'No hay regiones incluidas. Abre Configuraciones para seleccionar las regiones que quieres mostrar.';
    const datos = datosRegion(fuente);
      $('detalle').replaceChildren();
      $('totales').replaceChildren(fila(seleccion.region ? 'TOTAL REGIÓN' : 'TOTAL GENERAL', datos, 'total'));
      for (const region of datos.regiones) {
        $('detalle').append(fila(region.region, region, 'region'));
        for (const ceco of region.cecos) $('detalle').append(fila(ceco.ceco, ceco, 'ceco'));
      }
      $('kpis').replaceChildren();
      for (const [titulo, valor] of [['Programadas', datos.total], ['Realizadas', datos.realizadas], ['Regularizadas', datos.regularizadas], ['No realizadas', datos.no_realizadas], ['N/A', datos.na]]) {
        const tarjeta = document.createElement('div');
        tarjeta.className = 'kpi';
        const etiqueta = document.createElement('span');
        etiqueta.textContent = titulo;
        const cantidad = document.createElement('b');
        cantidad.textContent = numero.format(valor);
        tarjeta.append(etiqueta, cantidad);
        $('kpis').append(tarjeta);
      }
      graficos(fuente);
      $('periodo').textContent = `${nombreMes(datos.mes)} ${datos.mes.slice(0,4)} · ${seleccion.region || 'Todas las regiones'}`;
  }
  async function consultar(event) {
    event?.preventDefault();
    if (!$('programa-form').reportValidity()) return;
    $('consultar').disabled = true;
    $('mes').disabled = true;
    $('region-programa').disabled = true;
    $('resultados').hidden = true;
    $('avisos').hidden = true;
    $('estado').className = '';
    $('estado').textContent = 'Leyendo hoja PROGRAMA…';
    try {
      const respuesta = await fetch(`/api/programa-mantencion?mes=${encodeURIComponent($('mes').value)}`);
      const datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.error || 'No se pudo consultar el programa.');
      datosActuales = datos;
      prepararRegiones(aplicarConfiguracion(datos));
      configurar();
      renderizar(datos);
      $('avisos').textContent = datos.advertencias.join(' ');
      $('avisos').hidden = !datos.advertencias.length;
      $('fuente').textContent = `Fuente: ${datos.fuente} · ${datos.hoja}`;
      $('estado').textContent = datos.total ? 'Programa actualizado.' : 'No hay patentes programadas para el mes seleccionado.';
      $('resultados').hidden = false;
    } catch (error) {
      $('estado').className = 'error';
      $('estado').textContent = error.message;
    } finally {
      $('consultar').disabled = false;
      $('mes').disabled = false;
      $('region-programa').disabled = false;
    }
  }
  $('programa-form').addEventListener('submit', consultar);
  $('mes').addEventListener('change', consultar);
  $('region-programa').addEventListener('change', () => cambiarSeleccion($('region-programa').value ? {nivel: 'cecos', region: $('region-programa').value} : {nivel: 'total'}));
  consultar();
})();
