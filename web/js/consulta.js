/* Adaptador de consultas locales. Nunca consulta HTTP ni escribe bases de datos. */
(() => {
  'use strict';
  const publicado = window.PanelPublicado;
  const clonar = v => JSON.parse(JSON.stringify(v));
  const normalizar = v => String(v ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim().toUpperCase();
  const tramo = v => v == null || !Number.isFinite(v) || v < 0 ? 'sin_volumen' : v < 10 ? 'menor_10' : v < 20 ? '10_20' : v <= 30 ? '20_30' : 'mayor_30';
  const respuesta = (datos, tipo = 'application/json', nombre = null, status = 200) => new Response(tipo === 'application/json' ? JSON.stringify(datos) : datos, {
    status, headers: {'Content-Type': tipo, ...(nombre ? {'Content-Disposition': "attachment; filename*=UTF-8''" + encodeURIComponent(nombre)} : {})}
  });
  const base = new URL('../publicado/', document.currentScript.src);
  const descargarArchivo = id => {
    const a = publicado.archivos[id]; if (!a) throw new Error('La descarga no está incluida en esta publicación.');
    const enlace = document.createElement('a'); enlace.href = new URL(a.ruta, base).href; enlace.download = a.nombre;
    document.body.appendChild(enlace); enlace.click(); enlace.remove();
  };
  function descargarAuditoria(extension, seleccion) {
    if (extension === 'csv') { descargarArchivo(seleccion.csv_publicado); return; }
    const p = new URLSearchParams(Object.entries(seleccion).filter(([k]) => ['unidad','anio','mes','edp'].includes(k)));
    const r = publicado.reportes_auditoria.filter(r => coincide(r.registro,p));
    if (r.length !== 1) throw new Error('Selecciona un EDP con tickets completados publicados.');
    descargarArchivo(extension === 'pdf' ? r[0].pdf : r[0].zip);
  }
  const coincide = (r, p) => [...p].every(([k, v]) => !v || (k === 'estado' ? String(r.estado_codigo ?? r.estado) === v : k === 'trimestre' ? String(Math.ceil(Number(r.mes) / 3)) === v : String(r[k]) === v));

  function densidades(p) {
    const datos = clonar(publicado.densidades[p.get('unidad') || 'El Salvador']);
    if (!datos) throw new Error('Unidad no disponible.');
    datos.tickets = datos.tickets.filter(t => [...p].every(([k, v]) => !v ||
      (k === 'buscar' ? normalizar([t.ticket,t.retiro,t.residuo,t.residuo_original,t.archivo,t.fila].join(' ')).includes(normalizar(v)) :
       k === 'residuo' ? normalizar(t.residuo) === normalizar(v) : k === 'tramo_volumen' ? tramo(t.volumen_m3) === v :
       String(k === 'trimestre' ? Math.ceil(Number(t.mes) / 3) : t[k]) === v)));
    datos.filtros = Object.fromEntries(p);
    datos.avisos = [...datos.maestra.avisos, ...datos.avisos_edp.filter(a => ['anio','trimestre','mes','edp'].every(k => !p.get(k) || String(k === 'trimestre' ? Math.ceil(Number(a.mes)/3) : a[k]) === p.get(k))).map(a => a.mensaje)];
    const faltantes = new Map();
    datos.tickets.filter(t => !t.referencia_maestra).forEach(t => { const n = t.residuo || '(sin tipo declarado)'; faltantes.set(n, (faltantes.get(n) || 0) + 1); });
    for (const [n, cantidad] of faltantes) datos.avisos.push(`${datos.unidad}: ${n}, ${cantidad} tickets sin correspondencia en AUX; revisar caso a caso.`);
    const estimados = datos.tickets.filter(t => t.residuo_es_estimado).length;
    if (estimados) datos.avisos.push(`${datos.unidad}: ${estimados} tickets con tipo de residuo estimado. La densidad de AUX corresponde al material estimado; el original y el criterio se conservan en el detalle y reportes.`);
    return datos;
  }

  // ZIP sin compresión, compatible con Windows. Solo incluye archivos de la publicación.
  function zip(archivos) {
    const codificar = new TextEncoder(), partes = [], central = [];
    let posicion = 0;
    const cabecera = (tam, campos) => { const b = new Uint8Array(tam), v = new DataView(b.buffer); for (const [p, n, ancho] of campos) ancho === 2 ? v.setUint16(p,n,true) : v.setUint32(p,n,true); return b; };
    const crc = b => { let c = 0xffffffff; for (const n of b) { c ^= n; for(let i=0;i<8;i++) c = (c >>> 1) ^ (c & 1 ? 0xedb88320 : 0); } return (c ^ 0xffffffff) >>> 0; };
    const nombres = new Set();
    for (const [nombre, contenido] of archivos) {
      if (nombres.has(nombre)) throw new Error('Hay nombres de descargas repetidos.');
      nombres.add(nombre);
      const n = codificar.encode(nombre), b = contenido instanceof Uint8Array ? contenido : codificar.encode(contenido), checksum = crc(b);
      const local = cabecera(30, [[0,0x04034b50],[4,20,2],[6,0x800,2],[14,checksum],[18,b.length],[22,b.length],[26,n.length,2]]);
      const entrada = cabecera(46, [[0,0x02014b50],[4,20,2],[6,20,2],[8,0x800,2],[16,checksum],[20,b.length],[24,b.length],[28,n.length,2],[42,posicion]]);
      partes.push(local,n,b); central.push(entrada,n); posicion += local.length+n.length+b.length;
    }
    const largo = central.reduce((s,b) => s+b.length,0);
    return new Blob([...partes,...central,cabecera(22,[[0,0x06054b50],[8,archivos.length,2],[10,archivos.length,2],[12,largo],[16,posicion]])],{type:'application/zip'});
  }

  async function auditoria(ruta, p) {
    const id = p.get('id'), muestra = publicado.muestras[id];
    if (ruta === '/api/auditoria') return respuesta(clonar(publicado.auditoria));
    if (ruta.endsWith('/muestra')) { if (!muestra) throw new Error('Revisión no publicada.'); return respuesta(clonar(muestra)); }
    throw new Error('Esta función requiere Iniciar_Panel.bat.');
  }

  window.fetch = async (entrada, opciones = {}) => {
    try {
      if (!publicado) throw new Error('No hay una publicación disponible. Ejecuta Actualizar_BD.bat.');
      const url = new URL(String(entrada), 'http://consulta.local'), ruta = url.pathname, p = url.searchParams;
      if ((opciones.method || 'GET').toUpperCase() !== 'GET' && ruta !== '/api/reporte.pdf') throw new Error('La consulta publicada no permite guardar cambios.');
      if (ruta === '/api/conciliacion') return respuesta(clonar(publicado.conciliacion));
      if (ruta === '/api/densidades') return respuesta(densidades(p));
      if (ruta.startsWith('/api/auditoria')) return await auditoria(ruta, p);
      if (ruta === '/api/reporte.pdf') return respuesta(await window.PanelPDF.conciliacion(JSON.parse(opciones.body)), 'application/pdf', 'conciliacion-edp.pdf');
      if (ruta === '/api/densidades/reporte.pdf' || ruta === '/api/volumenes/reporte.pdf') {
        const distribucion = ruta.includes('/volumenes/');
        const datos = densidades(p);
        return respuesta(await window.PanelPDF.densidades(datos, distribucion), 'application/pdf', `${distribucion ? 'distribucion-volumen' : 'densidades'}-${datos.unidad.toLowerCase().replace(/ /g,'-')}.pdf`);
      }
      throw new Error('Esta función requiere Iniciar_Panel.bat.');
    } catch (error) { return respuesta({error: error.message}, 'application/json', null, 400); }
  };
  // Los enlaces de respaldo también funcionan por file://, sin llamadas a /api.
  document.addEventListener('click', event => {
    const a = event.target.closest('a[href^="/api/auditoria/respaldo-ticket"]');
    if (!a) return;
    event.preventDefault();
    const p = new URL(a.getAttribute('href'), 'http://consulta.local').searchParams;
    const t = publicado.muestras[p.get('id')]?.tickets.find(t => String(t.fila) === p.get('fila'));
    if (!t?.respaldo_publicado) return;
    descargarArchivo(t.respaldo_publicado);
  });
  window.PanelConsultaDatos = {densidades, zip, descargarAuditoria};
})();
