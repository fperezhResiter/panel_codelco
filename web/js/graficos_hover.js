/* Destaque por entidad y proximidad a puntos, sin modificar filtros ni datos. */
(() => {
  'use strict';
  const selector = '[data-grafico-clave]';
  let apuntado = null, enfocado = null, rangoHover = null, rangoFijo = null, mostrado = null;
  let cursor = null;
  const tooltip = document.createElement('div');
  tooltip.id = 'grafico-tooltip'; tooltip.className = 'grafico-tooltip';
  tooltip.setAttribute('role', 'tooltip'); tooltip.hidden = true;
  document.body.append(tooltip);
  const elemento = nodo => nodo instanceof Element ? nodo.closest(selector) : null;
  const esRango = item => item && /^(tramo|capacidad):/.test(item.dataset.graficoClave) && item.tagName.toLowerCase() !== 'circle';
  const pertenece = (item, clave) => item.dataset.graficoClave === clave || JSON.parse(item.dataset.graficoRangos || '[]').includes(clave);
  function ubicarTooltip() {
    if (tooltip.hidden || !mostrado) return;
    const rect = mostrado.getBoundingClientRect();
    const x = cursor ? cursor.x : rect.right, y = cursor ? cursor.y : rect.top;
    const ancho = tooltip.offsetWidth, alto = tooltip.offsetHeight;
    tooltip.style.left = Math.max(12, Math.min(x + 14, innerWidth - ancho - 12)) + 'px';
    tooltip.style.top = Math.max(12, y + alto + 26 > innerHeight ? y - alto - 14 : y + 14) + 'px';
  }
  function destacar() {
    const actual = apuntado?.isConnected ? apuntado : enfocado?.isConnected ? enfocado : null;
    if (!rangoFijo?.isConnected) rangoFijo = null;
    const rango = rangoFijo || (rangoHover?.isConnected ? rangoHover : esRango(actual) ? actual : null);
    const referencia = rango || actual;
    const clave = referencia?.dataset.graficoClave;
    const punto = actual?.tagName.toLowerCase() === 'circle';
    document.querySelectorAll('.grafico, #grafico-volumenes').forEach(grafico => {
      const items = [...grafico.querySelectorAll(selector)];
      const vinculado = referencia && items.some(item => pertenece(item, clave));
      items.forEach(item => {
        const circulo = item.tagName.toLowerCase() === 'circle';
        const coincide = vinculado && (punto && !rango && circulo ? item === actual : pertenece(item, clave));
        const senalado = item === actual;
        item.classList.toggle('grafico-destacado', Boolean(coincide || senalado));
        item.classList.toggle('grafico-atenuado', Boolean(vinculado && !coincide && !senalado));
        item.classList.toggle('grafico-senalado', senalado);
        item.classList.toggle('grafico-en-rango', Boolean(circulo && rango && coincide));
      });
    });
    if (mostrado) mostrado.removeAttribute('aria-describedby');
    mostrado = punto ? actual : null;
    tooltip.hidden = !mostrado;
    if (mostrado) {
      tooltip.textContent = mostrado.getAttribute('aria-label');
      mostrado.setAttribute('aria-describedby', tooltip.id);
      ubicarTooltip();
    }
  }
  function apuntar(item, rango) {
    if (apuntado === item && rangoHover === rango) return;
    apuntado = item; rangoHover = rango; destacar();
  }
  function cercano(svg, x, y) {
    const matriz = svg.getScreenCTM();
    if (!matriz) return null;
    let elegido = null, distancia = 100; // Diez píxeles en pantalla, incluso al redimensionar.
    svg.querySelectorAll('circle[data-volumen]').forEach(item => {
      const px = item.cx.baseVal.value * matriz.a + matriz.e;
      const py = item.cy.baseVal.value * matriz.d + matriz.f;
      const d = (x-px)**2 + (y-py)**2;
      if (d < distancia) { distancia = d; elegido = item; }
    });
    return elegido;
  }
  document.addEventListener('pointermove', evento => {
    cursor = {x:evento.clientX, y:evento.clientY};
    const item = elemento(evento.target);
    const svg = evento.target instanceof Element ? evento.target.closest('#grafico-volumenes svg') : null;
    const proximo = svg ? cercano(svg, cursor.x, cursor.y) : null;
    const rango = esRango(item) ? item : proximo && rangoHover && pertenece(proximo, rangoHover.dataset.graficoClave) ? rangoHover : null;
    apuntar(proximo || item, rango);
    ubicarTooltip();
  });
  document.addEventListener('pointerover', evento => {
    const item = elemento(evento.target);
    apuntar(item, esRango(item) ? item : null);
  });
  document.addEventListener('pointerout', evento => {
    const item = elemento(evento.relatedTarget);
    apuntar(item, esRango(item) ? item : null);
  });
  document.addEventListener('focusin', evento => {
    enfocado = elemento(evento.target); cursor = null; destacar();
  });
  document.addEventListener('focusout', evento => {
    enfocado = elemento(evento.relatedTarget); destacar();
  });
  function fijar(item) {
    rangoFijo = rangoFijo === item ? null : item;
    destacar();
  }
  document.addEventListener('click', evento => {
    const item = elemento(evento.target);
    if (esRango(item)) fijar(item);
  });
  document.addEventListener('keydown', evento => {
    if (evento.key === 'Escape') { rangoFijo = null; apuntado = enfocado = rangoHover = null; destacar(); }
    const item = elemento(evento.target);
    if (esRango(item) && (evento.key === 'Enter' || evento.key === ' ')) { evento.preventDefault(); fijar(item); }
  });
  window.addEventListener('blur', () => { apuntado = enfocado = rangoHover = null; destacar(); });
  window.addEventListener('scroll', () => {
    cursor = null;
    if (apuntado?.tagName.toLowerCase() === 'circle') { apuntado = rangoHover = null; destacar(); }
    else ubicarTooltip();
  }, true);
})();
