/* La BD y el servidor calculan el volumen y la clasificación de cada ticket. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const num = (v, d = 2) => v == null ? '—' : new Intl.NumberFormat('es-CL', {minimumFractionDigits:d, maximumFractionDigits:d}).format(v);
  const normalizar = v => String(v).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim().toUpperCase();
  const estados = {coincide:['Coincide con volumen','verde','#2E9E6B'], no_coincide_menor:['No coincide con volumen menor','amarillo','#997000'], no_coincide_mayor:['No coincide con volumen mayor','rojo','#a12424'], sin_evaluar:['Sin evaluar','gris','#5B6B7C']};
  const filtros = ['unidad','anio','mes','edp','residuo','filtro-estado','volumen_tipo','buscar'];
  const meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  let datos = null, visibles = [], cargando = false, exportando = false, pagina = 0;
  const porPagina = 100;
  function parametros() {
    const p = new URLSearchParams();
    filtros.forEach(k => {if ($(k).value.trim()) p.set(k === 'filtro-estado' ? 'estado' : k, $(k).value.trim());});
    return p;
  }
  function botones() {
    $('unidad').disabled = cargando || exportando;
    $('actualizar').disabled = cargando;
    $('generar-pdf').disabled = $('descargar-compilado').disabled = cargando || exportando || !visibles.length;
    $('exportar').disabled = cargando || !visibles.length;
  }
  function opciones() {
    ['anio','mes','edp','residuo'].forEach(k => {
      const valor = $(k).value, titulo = $(k).options[0].textContent;
      const valores = [...new Set(datos.tickets.map(t => t[k]).filter(v => v != null))].sort((a,b) => k === 'residuo' ? a.localeCompare(b) : a-b);
      $(k).replaceChildren(new Option(titulo, ''));
      valores.forEach(v => $(k).add(new Option(k === 'mes' ? meses[v-1] : k === 'edp' ? 'EDP ' + v : String(v), v)));
      if (valores.some(v => String(v) === valor)) $(k).value = valor;
    });
    const capacidad = $('volumen_tipo').value;
    $('volumen_tipo').replaceChildren(new Option('Todas las capacidades', ''));
    datos.volumenes.forEach(v => $('volumen_tipo').add(new Option(v + ' m³', v)));
    if (datos.volumenes.some(v => String(v) === capacidad)) $('volumen_tipo').value = capacidad;
    $('unidad-titulo').textContent = 'CONTROL DE VOLUMEN · ' + datos.unidad.toUpperCase();
    $('unidad-descripcion').textContent = 'Compara el volumen de cada ticket con capacidades de ' + datos.volumenes.join(', ') + ' m³. ' +
      (datos.unidad === 'Andina' ? 'Cantidad (t) × 1.000 = peso (kg).' : 'Se usa Peso Total (kg) del ticket.');
    $('regla-capacidades').textContent = datos.volumenes.join(', ') + ' m³ · tolerancia ±' + datos.tolerancia_m3 + ' m³';
    $('kpi-total-nota').textContent = 'Filas de ' + datos.unidad + ' en la selección';
    $('kpi-verdes-nota').textContent = 'Dentro de ±3 m³ de ' + datos.volumenes.join(', ');
    $('kpi-amarillos-nota').textContent = 'Fuera de rangos y menor a ' + datos.umbral_m3 + ' m³ · amarillo';
    $('kpi-rojos-nota').textContent = 'Fuera de rangos y mayor a ' + datos.umbral_m3 + ' m³ · rojo';
    const ventanas = datos.volumenes.map(v => (v - datos.tolerancia_m3) + '–' + (v + datos.tolerancia_m3)).join(', ');
    $('nota-volumenes').textContent = 'Bandas de ' + datos.unidad + ': ' + ventanas + ' m³. Cada punto representa un ticket; pasa el cursor o enfócalo para ver su valor. Verde: coincide. Amarillo: fuera de rangos y menor a ' + datos.umbral_m3 + ' m³. Rojo: fuera de rangos y mayor a ' + datos.umbral_m3 + ' m³. Gris: sin evaluar; sin punto de volumen.';
    $('unidad-footer').textContent = 'Reporte Codelco · ' + datos.unidad;
  }
  function barras(id, grupos) {
    const maximo = Math.max(1, ...grupos.map(g => g[1]));
    $(id).innerHTML = grupos.map(([nombre, cantidad, color]) => `<div class="barra-fila"><strong class="barra-etiqueta">${esc(nombre)}</strong><div class="barra"><div class="barra-pista"><span class="barra-relleno" style="background:${color};width:${cantidad/maximo*100}%"></span></div><span>${num(cantidad,0)} tickets</span></div></div>`).join('');
  }
  function dispersion() {
    const tickets = visibles.filter(t => t.volumen_m3 != null);
    if (!tickets.length) { $('grafico-volumenes').innerHTML = '<p class="vacio">Sin volúmenes calculables en esta selección.</p>'; return; }
    const ancho = 1100, alto = 300, izq = 65, arriba = 16, base = 248, largo = ancho-izq-25;
    const max = Math.max(Math.max(...datos.volumenes) + 6, ...tickets.map(t => t.volumen_m3 * 1.03));
    const y = v => base-(base-arriba)*v/max;
    let svg = `<svg viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="Volumen de ${tickets.length} tickets de ${esc(datos.unidad)} frente a capacidades de ${datos.volumenes.join(', ')} metros cúbicos"><title>Volumen por ticket y tolerancia de ±3 m³</title>`;
    datos.volumenes.forEach(v => { svg += `<rect x="${izq}" y="${y(v+3)}" width="${largo}" height="${y(v-3)-y(v+3)}" fill="#E4F4EC"/><line x1="${izq}" x2="${ancho-25}" y1="${y(v)}" y2="${y(v)}" stroke="#2E9E6B" stroke-dasharray="5 4"/><text x="${izq-9}" y="${y(v)+4}" text-anchor="end" font-size="12" fill="#176344">${v} m³</text>`; });
    svg += `<line x1="${izq}" x2="${ancho-25}" y1="${base}" y2="${base}" stroke="#bdcbd8"/><text x="${izq-9}" y="${base+4}" text-anchor="end" font-size="12">0</text><text x="${izq}" y="${arriba+10}" font-size="12" fill="#5B6B7C">Máximo de escala: ${num(max,1)} m³</text>`;
    tickets.forEach((t,i) => { const texto = `Ticket ${t.ticket || '(sin ID)'} · ${t.periodo} · EDP ${t.edp} · fila ${t.fila}: ${num(t.volumen_m3,3)} m³ · ${t.motivo}${t.residuo_es_estimado ? ' · Tipo de residuo estimado: ' + t.residuo : ''}`;
      svg += `<circle tabindex="0" aria-label="${esc(texto)}" cx="${izq+largo*(i+.5)/tickets.length}" cy="${y(t.volumen_m3)}" r="3.2" fill="${estados[t.estado][2]}" opacity=".8"><title>${esc(texto)}</title></circle>`; });
    svg += `<text x="${izq}" y="283" font-size="12" fill="#5B6B7C">${num(tickets.length,0)} tickets en orden de período y fila. Todos los puntos están incluidos.</text></svg>`;
    $('grafico-volumenes').innerHTML = svg;
  }
  function tabla() {
    const inicio = pagina * porPagina;
    $('filas').innerHTML = visibles.slice(inicio,inicio+porPagina).map(t => {
      const ref = t.referencia_maestra;
      const original = t.residuo_original !== t.residuo ? '<small>Original: '+esc(t.residuo_original || '(sin tipo declarado)')+'</small>' : '';
      const estimacion = t.residuo_es_estimado ? '<small><strong>Tipo y densidad estimados</strong></small><details><summary>Ver estimación</summary><small>'+esc(t.criterio_estimacion_residuo)+'</small></details>' : '';
      return `<tr><td><strong>${esc(t.periodo)}</strong><small>EDP ${esc(t.edp)} · fila ${t.fila}</small></td><td>${esc(t.ticket || '(sin ID)')}<small>${esc(t.fecha || 'Sin fecha')}</small></td><td class="densidad-texto">${esc(t.residuo || 'Sin residuo')}${original}${estimacion}<small>${esc(t.retiro)}</small></td><td>${num(t.peso_kg)}</td><td title="Inferior: ${num(t.inferior_kg_m3)} / superior: ${num(t.superior_kg_m3)}">${num(t.densidad_kg_m3)}${t.residuo_es_estimado ? '<small>Según material estimado</small>' : ''}</td><td>${num(t.volumen_m3,3)}</td><td>${t.volumen_tipo == null ? '—' : t.volumen_tipo + ' m³'}</td><td>${num(t.diferencia_m3,3)}</td><td class="densidad-texto"><span class="semaforo ${estados[t.estado][1]}">${estados[t.estado][0]}</span><small>${esc(t.motivo)}${t.capacidades_compatibles.length > 1 ? ' Compatible también con: ' + t.capacidades_compatibles.filter(v => v !== t.volumen_tipo).join(', ') + ' m³.' : ''}</small></td><td class="densidad-texto"><small>${esc(t.archivo)}<br>${esc(t.hoja_ticket)}!${esc(t.celda)}${ref ? '<br>Maestra: '+esc(ref.hoja)+'!'+esc(ref.celda_inferior)+' / '+esc(ref.celda_superior) : ''}</small></td></tr>`;
    }).join('') || '<tr><td colspan="10" class="vacio">No hay tickets que coincidan con los filtros.</td></tr>';
    $('cantidad-tickets').textContent = `${num(visibles.length,0)} tickets · mostrando ${visibles.length ? inicio+1 : 0}–${Math.min(inicio+porPagina,visibles.length)}. PDF y CSV incluyen toda la selección.`;
    let controles = $('paginacion');
    if (!controles) { controles = document.createElement('div'); controles.id = 'paginacion'; controles.className = 'densidad-paginacion'; $('filas').closest('.scroll').after(controles); }
    controles.replaceChildren();
    if (visibles.length > porPagina) {
      const previo = document.createElement('button'), siguiente = document.createElement('button');
      previo.textContent = 'Anterior'; previo.disabled = pagina === 0; previo.onclick = () => {pagina--; tabla();};
      siguiente.textContent = 'Siguiente'; siguiente.disabled = inicio+porPagina >= visibles.length; siguiente.onclick = () => {pagina++; tabla();};
      controles.append(previo, document.createTextNode(` Página ${pagina+1} de ${Math.ceil(visibles.length/porPagina)} `), siguiente);
    }
  }
  function renderizar() {
    if (!datos) return;
    const p = parametros();
    visibles = datos.tickets.filter(t => [...p].every(([k,v]) => k === 'buscar' ? normalizar([t.ticket,t.retiro,t.residuo,t.residuo_original,t.archivo,t.fila].join(' ')).includes(normalizar(v)) : k === 'residuo' ? normalizar(t[k]) === normalizar(v) : String(t[k]) === v));
    const sinMaestra = new Map();
    visibles.filter(t => !t.referencia_maestra).forEach(t => {const nombre = t.residuo || '(sin tipo declarado)'; sinMaestra.set(nombre, (sinMaestra.get(nombre) || 0) + 1);});
    const avisos = [...datos.maestra.avisos, ...datos.avisos_edp.filter(a => ['anio','mes','edp'].every(k => !p.get(k) || String(a[k]) === p.get(k))).map(a => a.mensaje),
      ...[...sinMaestra].map(([nombre, cantidad]) => `${datos.unidad}: ${nombre}, ${num(cantidad,0)} tickets sin correspondencia en AUX; revisar caso a caso.`)];
    const estimados = visibles.filter(t => t.residuo_es_estimado).length;
    if (estimados) avisos.push(`${num(estimados,0)} tickets usan un tipo de residuo estimado y la densidad de ese material en AUX. El detalle y los reportes conservan el original y el criterio de estimación.`);
    $('avisos').hidden = !avisos.length; $('avisos').innerHTML = avisos.map(a => '<p>'+esc(a)+'</p>').join('');
    const contar = e => visibles.filter(t => t.estado === e).length;
    $('kpi-total').textContent = num(visibles.length,0); $('kpi-verdes').textContent = num(contar('coincide'),0);
    $('kpi-amarillos').textContent = num(contar('no_coincide_menor'),0);
    $('kpi-rojos').textContent = num(contar('no_coincide_mayor'),0); $('kpi-pendientes').textContent = num(contar('sin_evaluar'),0);
    $('cobertura').textContent = `${num(visibles.filter(t => t.volumen_m3 != null).length,0)} tickets con volumen calculado de ${num(visibles.length,0)} seleccionados. Densidad utilizada: promedio de ambas densidades.`;
    barras('grafico-estados', Object.entries(estados).map(([k,v]) => [v[0],contar(k),v[2]]));
    barras('grafico-capacidades', datos.volumenes.map(v => [v+' m³',visibles.filter(t => t.volumen_tipo === v).length,'#0E81C5']));
    dispersion(); tabla(); botones();
  }
  async function cargar() {
    cargando = true; botones(); $('estado').className = ''; $('estado').textContent = 'Cargando datos guardados…';
    try {
      const res = await fetch('/api/densidades?unidad=' + encodeURIComponent($('unidad').value), {cache:'no-store'}); const body = await res.json();
      if (!res.ok) throw new Error(body.error || 'No se pudieron cargar los datos.');
      datos = body; opciones(); pagina = 0;
      $('estado').textContent = 'Última actualización de la BD: '+new Date(datos.actualizado).toLocaleString('es-CL');
      $('maestra-origen').textContent = 'Fuente: '+(datos.maestra.archivo || 'No disponible')+' · '+datos.maestra.materiales.length+' materiales guardados en BD.';
      $('filas-maestra').innerHTML = datos.maestra.materiales.map(m => `<tr><td>${esc(m.material)}</td><td>${num(m.inferior_kg_m3)}</td><td>${num(m.superior_kg_m3)}</td><td>${num(m.densidad_kg_m3)}</td><td class="densidad-texto">${esc(m.hoja)}!${esc(m.celda_inferior)} / ${esc(m.celda_superior)}<small>${esc(m.error || '')}</small></td></tr>`).join('');
      renderizar();
    } catch (e) {datos = null; visibles = []; $('estado').className = 'error'; $('estado').textContent = e.message;
      $('filas').innerHTML = '<tr><td colspan="10" class="vacio">Datos no disponibles. Revisa el mensaje anterior.</td></tr>';
      ['kpi-total','kpi-verdes','kpi-amarillos','kpi-rojos','kpi-pendientes'].forEach(k => $(k).textContent = '—');
      ['grafico-estados','grafico-capacidades','grafico-volumenes','filas-maestra','cantidad-tickets','cobertura'].forEach(k => $(k).replaceChildren());
      $('avisos').hidden = true;
      if ($('paginacion')) $('paginacion').replaceChildren();
      $('maestra-origen').textContent = 'Maestra no disponible.';
    } finally {cargando = false; botones();}
  }
  function descargar(blob, nombre) {
    const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = nombre; a.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
  }
  async function generarPdf(compilado = false) {
    if (cargando || exportando || !visibles.length) return;
    exportando = true; botones(); const estado = $('pdf-estado'); estado.hidden = false; estado.textContent = compilado ? 'Generando un PDF por unidad, mes, año y EDP de la selección…' : 'Generando reporte PDF de toda la selección…';
    try { const r = await fetch('/api/densidades/' + (compilado ? 'compilado.zip?' : 'reporte.pdf?') + parametros()); if (!r.ok) {const body = await r.json(); throw new Error(body.error || 'No se pudo generar la descarga.');}
      descargar(await r.blob(), decodeURIComponent(r.headers.get('Content-Disposition').split("filename*=UTF-8''")[1])); estado.textContent = compilado ? 'Compilado ZIP generado con los PDF separados. Revisa las descargas del navegador.' : 'Reporte PDF generado.';
    } catch(e) {estado.textContent = e.message;} finally {exportando = false; botones();}
  }
  $('generar-pdf').addEventListener('click', () => generarPdf());
  $('descargar-compilado').addEventListener('click', () => generarPdf(true));
  $('exportar').addEventListener('click', () => {
    const campos = ['unidad','periodo','edp','fila','ticket','fecha','residuo','residuo_original','residuo_es_estimado','criterio_estimacion_residuo','retiro','peso_ton','peso_kg','inferior_kg_m3','superior_kg_m3','densidad_kg_m3','volumen_m3','volumen_tipo','volumen_cercano','diferencia_m3','estado','motivo','archivo','hoja_ticket','celda'];
    const celda = v => '"'+String(v ?? '').replace(/^[=+@-]/,'\'$&').replace(/"/g,'""')+'"';
    const csv = [campos.map(celda).join(';'), ...visibles.map(t => campos.map(k => celda(t[k])).join(';'))].join('\r\n');
    descargar(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}),'chequeo-densidades-' + ($('unidad').value === 'Andina' ? 'andina' : 'salvador') + '.csv');
  });
  filtros.filter(k => k !== 'unidad').forEach(k => $(k).addEventListener(k === 'buscar' ? 'input' : 'change', () => {pagina = 0; renderizar();}));
  $('unidad').addEventListener('change', () => {filtros.filter(k => k !== 'unidad').forEach(k => $(k).value = ''); $('pdf-estado').hidden = true; cargar();});
  $('limpiar').onclick = () => {filtros.filter(k => k !== 'unidad').forEach(k => $(k).value = ''); pagina = 0; renderizar();};
  $('actualizar').onclick = cargar;
  cargar();
})();
