/* Integración en Chromium: abre archivos file://, bloquea red y verifica descargas. */
const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
const assert = require('assert/strict');
const {chromium} = require(process.env.CODELCO_NODE_MODULES + '/playwright');

(async () => {
  const root = path.resolve(__dirname,'..');
  const salida = path.join(root,'tmp','consulta-qa'); fs.mkdirSync(salida,{recursive:true});
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const context = await browser.newContext({acceptDownloads:true});
  const page = await context.newPage(), errores = [], red = [];
  page.on('pageerror', e => errores.push(e.message));
  await page.route(/^https?:\/\//, route => {red.push(route.request().url());return route.abort();});
  const abrir = async nombre => { await page.goto(pathToFileURL(path.join(root,nombre)).href); await page.waitForFunction(() => window.PanelPublicado && window.PanelSesion); };
  const descarga = async (selector,nombre) => {
    const promesa = page.waitForEvent('download');await page.click(selector);const d = await promesa;await d.saveAs(path.join(salida,nombre));assert.equal(await d.failure(),null);
  };
  await abrir('Panel.html');
  assert.match(await page.locator('.ultima-actualizacion').innerText(),/Última actualización:/);
  assert.equal(await page.locator('.sesion-usuario').count(),0);
  assert.equal(await page.locator('[data-panel-configuraciones]').isVisible(),false);
  await page.locator('a[href="web/pages/Panel_Conciliacion.html"]').click();
  await page.waitForURL('**/web/pages/Panel_Conciliacion.html');
  await page.waitForFunction(() => document.getElementById('exportar') && !document.getElementById('exportar').disabled);
  await page.selectOption('#unidad','Andina');await page.selectOption('#anio','2025');
  const total = await page.locator('#cantidad-registros').innerText(); assert.match(total,/estados de pago/);
  assert.ok(await page.locator('#grafico-ton .barra-fila').count());
  await descarga('#exportar','conciliacion.csv');await descarga('#generar-pdf','conciliacion.pdf');
  await page.screenshot({path:path.join(salida,'conciliacion.png'),fullPage:true});
  for(const [vista,nombre]of[['Panel_Densidades.html','densidades'],['Panel_Volumenes.html','volumenes']]){
    await abrir('web/pages/'+vista);await page.waitForFunction(() => !document.getElementById('exportar').disabled);
    await page.selectOption('#unidad','Andina');await page.waitForFunction(() => !document.getElementById('exportar').disabled);
    await page.selectOption('#anio','2025');await page.selectOption('#mes','7');
    assert.ok(await page.locator('#grafico-volumenes circle').count());
    assert.equal(await page.locator('textarea').count(),0);
    await descarga('#exportar',nombre+'.csv');await descarga('#generar-pdf',nombre+'.pdf');
    await page.screenshot({path:path.join(salida,nombre+'.png'),fullPage:true});
  }
  await abrir('web/pages/Panel_Auditoria_EDP.html');await page.waitForFunction(() => document.querySelector('#estados-pago').rows.length > 0);
  assert.equal(await page.locator('#conexion-bd').isVisible(),false);
  const resumen = await page.evaluate(() => ({muestras:Object.keys(PanelPublicado.muestras).length,pdfs:PanelPublicado.reportes_auditoria.length}));
  if(resumen.muestras){
    const m = await page.evaluate(() => Object.values(PanelPublicado.muestras).find(m => m.tickets.some(t => t.comprobado)) || Object.values(PanelPublicado.muestras)[0]);
    for(const [id,valor]of[['unidad',m.unidad],['anio',m.anio],['trimestre',''],['mes',m.mes],['fuente',m.fuente],['historial',m.id]]){
      await page.selectOption('#'+id,String(valor));
      await page.waitForFunction(() => !document.getElementById('unidad').disabled);
    }
    await page.waitForFunction(() => !document.getElementById('exportar').disabled);
    await descarga('#exportar','auditoria.csv');
    if(await page.locator('#generar-pdf').isEnabled())await descarga('#generar-pdf','auditoria.zip');
    assert.equal(await page.locator('[data-comprobar]:enabled').count(),0);
  }
  const resultado=await page.evaluate(async()=>{const r=await fetch('/api/densidades/comentario',{method:'POST',body:'{}'});return {status:r.status,body:await r.json()};});
  assert.equal(resultado.status,400);assert.match(resultado.body.error,/no permite guardar/);
  assert.deepEqual(errores,[]);assert.deepEqual(red,[]);
  console.log(JSON.stringify({ok:true,total,resumen,errores,red}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
