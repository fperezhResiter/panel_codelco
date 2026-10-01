// Los archivos locales abren su equivalente HTTP para poder consultar el Excel.
(() => {
  if (location.protocol !== 'file:') return;

  const pagina = location.pathname.split('/').pop();
  const destino = new URL('/' + pagina, 'http://127.0.0.1:8765');
  destino.search = location.search;
  destino.hash = location.hash;
  location.replace(destino.href);
})();
