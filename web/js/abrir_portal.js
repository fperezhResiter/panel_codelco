// El acceso desde el archivo local se dirige al servidor del panel.
(() => {
  if (location.protocol !== 'file:') return;
  const paginas = ['Panel_Conciliacion.html', 'Panel_Densidades.html', 'Panel_Auditoria_EDP.html'];
  const pagina = location.pathname.split('/').pop();
  const ruta = paginas.includes(pagina) ? '/web/pages/' + pagina : '/Panel.html';
  const destino = new URL(ruta, 'http://127.0.0.1:8765');
  destino.search = location.search;
  destino.hash = location.hash;
  location.replace(destino.href);
})();
