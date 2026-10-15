(() => {
  'use strict';
  const sesion = window.PanelSesion = {usuario: null, permite: permiso => Boolean(sesion.usuario?.permisos.includes(permiso))};
  if (window.PanelConsulta) {
    sesion.permite = permiso => permiso === 'consultar';
    sesion.listo = Promise.resolve();
    document.addEventListener('DOMContentLoaded', () => {
      document.querySelectorAll('[data-permiso]').forEach(n => { n.hidden = !sesion.permite(n.dataset.permiso); });
      const fecha = document.createElement('p');
      fecha.className = 'ultima-actualizacion';
      fecha.textContent = window.PanelPublicado ? 'Última actualización: ' + new Date(window.PanelPublicado.actualizado).toLocaleString('es-CL', {timeZone:'America/Santiago'}) : 'Publicación no disponible. Ejecuta Actualizar_BD.bat.';
      document.querySelector('header').append(fecha);
    });
    return;
  }
  // Redirigir también cuando una sesión vence con el panel ya abierto.
  const consultar = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const respuesta = await consultar(...args);
    if (respuesta.status === 401) location.replace('/login');
    return respuesta;
  };
  sesion.listo = (async () => {
    try {
      const respuesta = await fetch('/api/sesion', {cache: 'no-store'});
      if (!respuesta.ok) throw new Error('No se pudo consultar la sesión. Recarga el panel.');
      const datos = await respuesta.json();
      if (!datos.usuario) { location.replace('/login'); return; }
      sesion.usuario = datos.usuario;
      const barra = document.createElement('div');
      barra.className = 'sesion-usuario';
      const etiqueta = document.createElement('span');
      etiqueta.textContent = `${datos.usuario.rol_nombre} · ${datos.usuario.nombre}`;
      const salir = document.createElement('button');
      salir.type = 'button'; salir.textContent = 'Cerrar sesión';
      salir.addEventListener('click', async () => {
        salir.disabled = true;
        try {
          const respuesta = await fetch('/api/sesion/salir', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
          if (!respuesta.ok) throw new Error('No se pudo cerrar la sesión.');
          location.replace('/login');
        } catch (error) { salir.disabled = false; etiqueta.textContent = error.message; }
      });
      barra.append(etiqueta, salir);
      const perfil = document.createElement('a');
      perfil.href = '/perfil'; perfil.textContent = 'Mi perfil';
      perfil.className = 'boton-perfil';
      const encabezado = document.querySelector('header');
      const acciones = document.createElement('div');
      acciones.className = 'acciones-encabezado';
      const inicio = encabezado.querySelector('.volver-inicio') || encabezado.querySelector('small');
      if (inicio) acciones.append(inicio);
      acciones.append(perfil);
      encabezado.append(acciones);
      if (datos.usuario.rol_real === 'administrador') {
        const vista = document.createElement('button');
        vista.type = 'button';
        vista.textContent = datos.usuario.vista_general ? 'Volver a vista Admin' : 'Ver como General';
        vista.addEventListener('click', async () => {
          vista.disabled = true;
          try {
            const respuesta = await fetch('/api/sesion/vista', {method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({general: !datos.usuario.vista_general})});
            const resultado = await respuesta.json();
            if (!respuesta.ok) throw new Error(resultado.error);
            location.replace('/Panel.html');
          } catch (error) { vista.disabled = false; etiqueta.textContent = error.message; }
        });
        barra.insertBefore(vista, salir);
      }
      document.querySelector('header').after(barra);
      document.querySelectorAll('[data-permiso]').forEach(n => { n.hidden = !sesion.permite(n.dataset.permiso); });
    } catch (error) {
      const aviso = document.createElement('p'); aviso.className = 'error'; aviso.textContent = error.message;
      document.querySelector('header').after(aviso);
    }
  })();
})();
