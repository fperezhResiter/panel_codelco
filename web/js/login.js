(() => {
  'use strict';
  const estado = document.getElementById('estado-acceso');
  async function cargar() {
    try {
      const respuesta = await fetch('/api/sesion', {cache: 'no-store'});
      if (!respuesta.ok) throw new Error('No se pudo consultar el acceso.');
      const datos = await respuesta.json();
      if (datos.usuario) { location.replace('/Panel.html'); return; }
      document.getElementById('ingreso').hidden = !datos.configurado;
      document.getElementById('configurar').hidden = datos.configurado;
      document.getElementById('titulo-acceso').textContent = datos.configurado ? 'Iniciar sesión' : 'Crear cuenta Admin';
      estado.textContent = datos.configurado ? (new URLSearchParams(location.search).get('password_actualizada') === '1' ? 'Contraseña actualizada. Ingresa con tu correo y nueva contraseña.' : 'Ingresa tu correo y contraseña.') : 'Primer inicio: crea la cuenta Admin del panel.';
    } catch (error) { estado.textContent = error.message; }
  }
  for (const id of ['ingreso', 'configurar']) {
    document.getElementById(id).addEventListener('submit', async event => {
      event.preventDefault();
      const form = event.target;
      const boton = form.querySelector('button');
      boton.disabled = true;
      try {
        const datos = Object.fromEntries(new FormData(form));
        const respuesta = await fetch('/api/sesion/' + (id === 'ingreso' ? 'ingresar' : 'configurar'), {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(datos),
        });
        const resultado = await respuesta.json();
        if (!respuesta.ok) throw new Error(resultado.error);
        form.reset();
        if (id === 'ingreso') location.replace('/Panel.html');
        else await cargar();
      } catch (error) { estado.textContent = error.message; }
      finally { boton.disabled = false; }
    });
  }
  cargar();
})();
