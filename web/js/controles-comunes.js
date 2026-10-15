/* Navegación y tema compartidos por todos los paneles Resiter. */
(() => {
  'use strict';
  const script = document.currentScript;
  const raiz = document.documentElement;
  const clave = 'resiterTema';
  const parametro = new URLSearchParams(location.search).get('tema');
  let tema = parametro;
  try { tema = tema || localStorage.getItem(clave) || localStorage.getItem('panelAdmTema'); } catch (_) {}
  tema = tema === 'oscuro' ? 'oscuro' : 'claro';
  // Conservar el matiz de cada serie y aclararlo solo en modo oscuro.
  // light-dark se resuelve por CSS: cambiar el tema no reconstruye los gráficos
  // ni borra su selección, foco o eventos.
  const coloresGraficos = new Map();
  function colorGrafico(color) {
    if (coloresGraficos.has(color)) return coloresGraficos.get(color);
    const contexto = document.createElement('canvas').getContext('2d');
    contexto.fillStyle = color;
    const normal = contexto.fillStyle;
    if (!/^#[\da-f]{6}$/i.test(normal)) return color;
    const rgb = normal.slice(1).match(/../g).map(v => parseInt(v, 16));
    const luminancia = valores => valores.map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
      .reduce((s, v, i) => s + v * [.2126, .7152, .0722][i], 0);
    const fondo = luminancia([21, 43, 68]);
    let claro = rgb;
    for (let mezcla = 0; (luminancia(claro) + .05) / (fondo + .05) < 4.8 && mezcla <= 1; mezcla += .025) {
      claro = rgb.map(v => Math.round(v + (255 - v) * mezcla));
    }
    const valor = `light-dark(${color}, rgb(${claro.join(' ')}))`;
    coloresGraficos.set(color, valor);
    return valor;
  }
  window.PanelTema = Object.freeze({colorGrafico});
  function aplicar(valor) {
    tema = valor;
    raiz.setAttribute('data-tema', valor);
    try { localStorage.setItem(clave, valor); localStorage.setItem('panelAdmTema', valor); } catch (_) {}
    try {
      const url = new URL(location.href);
      if (url.searchParams.has('tema')) {
        url.searchParams.set('tema', valor);
        history.replaceState(history.state, '', url.href);
      }
    } catch (_) {}
    document.querySelectorAll('[data-control-tema]').forEach(b => {
      const etiqueta = valor === 'oscuro' ? 'Activar modo claro' : 'Activar modo oscuro';
      b.title = etiqueta;
      b.setAttribute('aria-label', etiqueta);
      b.setAttribute('aria-pressed', String(valor === 'oscuro'));
    });
  }
  aplicar(tema);
  const menu = new URL(location.protocol === 'file:' ? script.dataset.menu : '/principal/Panel%20Universal.html', location.href);
  function iniciar() {
    const cabecera = document.querySelector('.top-in') || document.querySelector('body > header');
    if (!cabecera) return;
    const controles = document.createElement('div');
    controles.className = 'controles-universales';
    const principal = location.pathname.endsWith('/Panel%20Universal.html') || decodeURI(location.pathname).endsWith('/Panel Universal.html');
    if (!principal) {
      const enlace = document.createElement('a');
      enlace.className = 'menu-principal'; enlace.href = menu.href;
      enlace.textContent = 'Menu principal'; controles.append(enlace);
    }
    // Reutilizar el control original de Administradores evita duplicarlo.
    const boton = document.getElementById('btnTema') || document.createElement('button');
    boton.type = 'button'; boton.classList.add('control-tema');
    boton.dataset.controlTema = '';
    const icono = document.createElement('span');
    icono.className = 'icono-tema'; icono.textContent = '◐';
    icono.setAttribute('aria-hidden', 'true'); boton.replaceChildren(icono);
    boton.onclick = () => {
      aplicar(tema === 'oscuro' ? 'claro' : 'oscuro');
    };
    const inicio = cabecera.querySelector(':scope > .volver-inicio, :scope > small');
    if (inicio) controles.prepend(inicio);
    controles.append(boton);
    const publicacion = cabecera.querySelector(':scope > .publicacion-header, :scope > .ultima-actualizacion');
    cabecera.insertBefore(controles, publicacion);
    // El acceso y el tema también están disponibles antes de ingresar a Costos.
    const acceso = document.getElementById('gate');
    if (acceso) {
      const copia = controles.cloneNode(true);
      copia.querySelector('button').removeAttribute('id');
      copia.querySelector('button').onclick = boton.onclick;
      acceso.prepend(copia);
    }
    aplicar(tema);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
  // Transportar el tema entre HTML locales aunque el navegador aísle su almacenamiento.
  document.addEventListener('click', evento => {
    const enlace = evento.target.closest('a[href]');
    if (!enlace || enlace.hasAttribute('download')) return;
    const destino = new URL(enlace.href, location.href);
    if (!/\.html?$/i.test(destino.pathname) || !['file:', 'http:', 'https:'].includes(destino.protocol)) return;
    if (destino.protocol !== 'file:' && destino.origin !== location.origin) return;
    destino.searchParams.set('tema', tema); enlace.href = destino.href;
  }, true);
  window.addEventListener('storage', evento => {
    if (evento.key === clave && ['claro', 'oscuro'].includes(evento.newValue)) aplicar(evento.newValue);
  });
})();
