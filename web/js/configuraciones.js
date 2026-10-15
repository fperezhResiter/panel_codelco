(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const form = $('crear-usuario');
  const edicion = $('editar-usuario');
  let ocupado = false;
  function controles() {
    document.querySelectorAll('.configuraciones button').forEach(n => { n.disabled = ocupado || !window.PanelSesion.permite('configurar'); });
  }
  function cerrarEdicion() { edicion.reset(); $('edicion-usuario').hidden = true; }
  const mensaje = (texto, error = false) => { $('estado-configuracion').textContent = texto; $('estado-configuracion').className = error ? 'error' : ''; };
  const descripciones = {
    general: 'Puede consultar datos, filtrar y descargar reportes. Los sorteos son vistas previas sin guardar cambios.',
    auditor: 'Puede guardar revisiones y marcar o desmarcar comprobaciones de tickets, además de consultar, filtrar y descargar.',
    administrador: 'Acceso completo, incluidos respaldos y configuración de usuarios.',
  };
  form.elements.rol.addEventListener('change', () => { $('descripcion-rol').textContent = descripciones[form.elements.rol.value]; });
  async function cargar() {
    const respuesta = await fetch('/api/configuraciones/usuarios', {cache: 'no-store'});
    const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos.error);
    $('usuarios-configuracion').replaceChildren(...datos.usuarios.map(usuario => {
      const fila = document.createElement('tr');
      for (const valor of [usuario.correo, usuario.rol === 'administrador' ? 'Admin' : usuario.rol_nombre]) {
        const celda = document.createElement('td'); celda.textContent = valor; fila.appendChild(celda);
      }
      const acciones = document.createElement('td');
      const editar = document.createElement('button'); editar.type = 'button'; editar.textContent = 'Editar';
      editar.setAttribute('aria-label', `Editar ${usuario.correo}`);
      editar.addEventListener('click', () => {
        edicion.reset();
        edicion.elements.correo.value = usuario.correo;
        edicion.elements.rol.value = usuario.rol;
        $('edicion-usuario').hidden = false;
        edicion.elements.rol.focus();
      });
      acciones.appendChild(editar); fila.appendChild(acciones);
      return fila;
    }));
    $('total-usuarios').textContent = `${datos.usuarios.length} usuario(s) registrados`;
    controles();
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (ocupado) return;
    ocupado = true; controles();
    try {
      const datos = Object.fromEntries(new FormData(form));
      if (datos.password !== datos.confirmacion) throw new Error('Las contraseñas no coinciden.');
      delete datos.confirmacion;
      const respuesta = await fetch('/api/configuraciones/usuarios', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(datos)});
      const resultado = await respuesta.json();
      if (!respuesta.ok) throw new Error(resultado.error);
      form.reset(); $('descripcion-rol').textContent = descripciones.general;
      mensaje(`Usuario ${resultado.usuario.correo} creado correctamente.`);
      await cargar();
    } catch (error) { mensaje(error.message, true); }
    finally { ocupado = false; controles(); }
  });
  $('cancelar-edicion').addEventListener('click', cerrarEdicion);
  edicion.addEventListener('submit', async event => {
    event.preventDefault();
    if (ocupado) return;
    ocupado = true; controles();
    try {
      const datos = Object.fromEntries(new FormData(edicion));
      if (datos.password !== datos.confirmacion) throw new Error('Las contraseñas no coinciden.');
      delete datos.confirmacion;
      const respuesta = await fetch('/api/configuraciones/usuarios/editar', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(datos)});
      const resultado = await respuesta.json();
      if (!respuesta.ok) throw new Error(resultado.error);
      cerrarEdicion();
      if (resultado.sesion_cerrada) { location.replace('/login'); return; }
      mensaje(`Usuario ${resultado.usuario.correo} actualizado correctamente.`);
      await cargar();
    } catch (error) { mensaje(error.message, true); }
    finally { ocupado = false; controles(); }
  });
  window.PanelSesion.listo.then(async () => {
    if (!window.PanelSesion.permite('configurar')) { location.replace('/Panel.html'); return; }
    try { await cargar(); mensaje('Solo Admin puede agregar usuarios y editar sus roles y contraseñas.'); controles(); }
    catch (error) { mensaje(error.message, true); }
  });
})();
