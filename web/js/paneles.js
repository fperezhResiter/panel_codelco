(() => {
  'use strict';
  const portal = document.querySelector('.paneles');
  const numerar = origen => {
    const cantidad = origen.querySelectorAll('.panel-enlace:not([data-panel-configuraciones])').length;
    const numero = String(cantidad + 1).padStart(2, '0');
    document.querySelectorAll('[data-numero-configuraciones]').forEach(n => {
      if (n.textContent !== numero) n.textContent = numero;
    });
  };
  if (portal) {
    const configuraciones = portal.querySelector('[data-panel-configuraciones]');
    const actualizar = () => {
      if (configuraciones && portal.lastElementChild !== configuraciones) portal.appendChild(configuraciones);
      numerar(portal);
    };
    actualizar();
    new MutationObserver(actualizar).observe(portal, {childList: true});
  } else if (document.querySelector('[data-numero-configuraciones]')) {
    // El portal es la fuente del orden y número de todos los paneles.
    window.PanelSesion.listo.then(async () => {
      if (!window.PanelSesion.permite('configurar')) return;
      try {
        const respuesta = await fetch('/Panel.html', {cache: 'no-store'});
        if (!respuesta.ok) return;
        const origen = new DOMParser().parseFromString(await respuesta.text(), 'text/html');
        const paneles = origen.querySelector('.paneles');
        if (!paneles) return;
        numerar(paneles);
        const navegacion = document.querySelector('[data-navegacion-configuraciones]');
        if (navegacion) {
          navegacion.replaceChildren(...Array.from(paneles.querySelectorAll('.panel-enlace')).map(panel => {
            const enlace = document.createElement('a');
            const ruta = panel.getAttribute('href');
            enlace.href = new URL(ruta, new URL('/Panel.html', location.origin)).href;
            enlace.textContent = panel.querySelector('h3').textContent;
            if (panel.hasAttribute('data-panel-configuraciones')) enlace.setAttribute('aria-current', 'page');
            return enlace;
          }));
        }
      } catch (error) { console.error('No se pudo cargar la navegación de paneles.', error); }
    });
  }
})();
