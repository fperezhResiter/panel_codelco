(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const form = $('password-perfil');
  const boton = form.querySelector('button');
  const mensaje = (texto, error = false) => { $('estado-perfil').textContent = texto; $('estado-perfil').className = error ? 'error' : ''; };
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (boton.disabled) return;
    boton.disabled = true;
    try {
      const datos = Object.fromEntries(new FormData(form));
      if (datos.nueva !== datos.confirmacion) throw new Error('Las contraseñas nuevas no coinciden.');
      const respuesta = await fetch('/api/sesion/password', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({actual: datos.actual, nueva: datos.nueva})});
      const resultado = await respuesta.json();
      if (!respuesta.ok) throw new Error(resultado.error);
      form.reset();
      location.replace('/login?password_actualizada=1');
    } catch (error) { mensaje(error.message, true); boton.disabled = false; }
  });
  window.PanelSesion.listo.then(() => {
    const usuario = window.PanelSesion.usuario;
    if (!usuario) return;
    $('perfil-correo').textContent = usuario.correo;
    $('perfil-rol').textContent = {administrador: 'Admin', auditor: 'Auditor', general: 'General'}[usuario.rol_real];
    $('perfil-vista').hidden = !usuario.vista_general;
    mensaje('Puedes actualizar la contraseña de tu cuenta.');
    boton.disabled = false;
  });
})();
