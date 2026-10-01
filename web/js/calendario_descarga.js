// Informe autónomo: calendario mensual y tabla completa de una sola región.
function escaparCalendario(valor)
{
    return String(valor??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function informeCalendarioMt(equipos,mes,region,inicio,referencia)
{
    if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(mes)||Number(mes.slice(0,4))<1000||!region)throw new Error('Selecciona un mes y una región válidos.');
    const eventos=equipos.filter(e=>e.region===region&&e.calculo.fecha_proyectada?.slice(0,7)===mes).sort((a,b)=>a.calculo.fecha_proyectada.localeCompare(b.calculo.fecha_proyectada)||a.patente.localeCompare(b.patente));
    const [ano,m]=mes.split('-').map(Number),offset=(new Date(Date.UTC(ano,m-1,1)).getUTCDay()+6)%7,dias=new Date(Date.UTC(ano,m,0)).getUTCDate(),celdas=Array(offset).fill(null);
    for(let d=1;d<=dias;d++)celdas.push(`${mes}-${String(d).padStart(2,'0')}`);
    while(celdas.length%7)celdas.push(null);
    const esc=escaparCalendario,fecha=s=>s?s.split('-').reverse().join('-'):'—',numero=n=>Number.isFinite(n)?n.toLocaleString('es-CL',{maximumFractionDigits:1}):'—';
    let calendario='';
    for(let i=0;i<celdas.length;i+=7){
        calendario+='<tr>';
        for(const dia of celdas.slice(i,i+7)){
            if(!dia){
                calendario+='<td class="vacio"></td>';
                continue;
            }
            const lista=eventos.filter(e=>e.calculo.fecha_proyectada===dia);
            calendario+=`<td class="${lista.length?'programado':''}"><b>${Number(dia.slice(-2))}</b>${lista.length?`<strong>${lista.length} ${lista.length===1?'mantención preventiva':'mantenciones preventivas'}</strong><span>${lista.slice(0,3).map(e=>esc(e.patente)).join('<br>')}${lista.length>3?'<br>… Ver tabla completa':''}</span>`:''}</td>`;
        }
        calendario+='</tr>';
    }
    const tabla=eventos.map(e=>{const estado=['REVISAR','REVISADO'].includes(e.calculo.estado?.toUpperCase())?'STAND BY':e.calculo.estado;return '<tr>'+[fecha(e.calculo.fecha_proyectada),e.patente,e.region,e.ceco,e.unidad||'—',numero(e.calculo.proxima),estado].map(v=>`<td>${esc(v)}</td>`).join('')+'</tr>';}).join('')||'<tr><td colspan="7">Sin mantenciones proyectadas para esta región y mes.</td></tr>';
    return `<!doctype html>
    <html lang="es"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Calendario ${esc(region)} · ${esc(mes)}</title>
    <style>
    *{box-sizing:border-box}body{font:14px/1.45 Arial,sans-serif;color:#1b2a3a;
    margin:30px auto;max-width:1150px;
    padding:0 20px}h1,h2{color:#073762}header{border-bottom:3px solid #0e81c5;
    margin-bottom:22px}p{color:#526373}.etiqueta{color:#0e81c5;
    font-weight:bold;
    letter-spacing:1px}table{width:100%;
    border-collapse:collapse;
    margin:16px 0 28px}th,td{border:1px solid #ccd9e4;
    padding:8px;
    vertical-align:top;
    text-align:left}th{background:#e3edf7;
    color:#073762}.calendario{table-layout:fixed}.calendario th{text-align:center}.calendario td{height:105px}.calendario b{font-size:19px}.calendario strong,.calendario span{display:block;font-size:11px;margin-top:6px;overflow-wrap:anywhere}.programado{background:#e4f2fc;
    border:2px solid #0e81c5}.vacio{background:#f6f7f9}.detalle{font-size:12px}.detalle td{overflow-wrap:anywhere}footer{border-top:1px solid #ccd9e4;padding-top:12px;
    color:#526373;font-size:12px}@media print{@page{size:A4 landscape;margin:12mm}body{margin:0;padding:0;max-width:none}.instruccion{display:none}.tabla-patentes{break-before:page}.detalle thead{display:table-header-group}.detalle tr{break-inside:avoid}.programado{print-color-adjust:exact;-webkit-print-color-adjust:exact}.calendario td{height:90px}}@media(max-width:650px){body{padding:0 8px}.calendario td{padding:4px}.calendario span{font-size:10px}.detalle{font-size:10px}}
    </style>
    </head>
    <body><header>
    <p class="etiqueta">RESITER / MINERÍA</p>
    <h1>Calendario de mantención</h1>
    <h2>${esc(region)} · ${esc(mes)}</h2>
    <p>${eventos.length} patentes con fecha proyectada en el mes.</p>
    <p>Lecturas: semana 1 ${esc(fecha(inicio))} · hasta referencia ${esc(fecha(referencia))}, según las columnas con fecha del Excel.</p>
    </header>
    <p class="instruccion">Este archivo se puede consultar sin conexión. Para imprimirlo o guardarlo como PDF usa la opción Imprimir de tu navegador.</p>
    <table class="calendario">
        <caption>Los días destacados tienen mantenciones proyectadas.</caption>
        <thead>
            <tr>${['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'].map(d=>`<th>${d}</th>`).join('')}</tr>
        </thead>
        <tbody>${calendario}</tbody>
    </table>
    <section class="tabla-patentes">
        <h2>Tabla de patentes · ${esc(region)}</h2>
        <table class="detalle">
            <thead>
                <tr>${['Fecha proyectada','Patente','Región','CeCo','Unidad','Próxima mantención','Estado'].map(c=>`<th>${c}</th>`).join('')}</tr>
            </thead>
            <tbody>${tabla}</tbody>
        </table>
    </section>
    <footer>Fuente: Control de Equipos Móviles – Minería.xlsx · Seguimiento KM-HR. Las fechas son estimaciones según uso, no órdenes de trabajo confirmadas. Se incluyen solo las patentes de esta región con fecha en el mes elegido. Los equipos sin proyección quedan fuera. Si un equipo está en STAND BY, valida la fecha si su ritmo de uso cambió.</footer>
    </body>
    </html>`;
}
if(typeof module!=='undefined')module.exports={informeCalendarioMt,escaparCalendario};
