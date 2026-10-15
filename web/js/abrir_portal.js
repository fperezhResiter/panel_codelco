// Los archivos locales consultan la publicación; HTTP conserva el panel con sesión.
(() => {
  if (location.protocol !== 'file:' && !location.pathname.startsWith('/principal/')) return;
  window.PanelConsulta = true;
  const base = new URL('../', document.currentScript.src);
  for (const ruta of ['publicado/datos.js', 'vendor/pdf-lib.min.js', 'js/pdf_consulta.js', 'js/consulta.js']) {
    const url = new URL(ruta, base).href.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    document.write('<script src="' + url + '"><' + '/script>');
  }
})();
