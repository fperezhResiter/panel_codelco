import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from app.auditoria import Auditoria
from app.servidor import ServidorPanel, crear_handler
from app.usuarios import Usuarios, ROLES
from test_auditoria import excel, adjunto


class UsuariosTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        self.usuarios = Usuarios(self.raiz / 'usuarios.sqlite3')
        carpeta = self.raiz / 'Fuentes' / 'Codelco El Salvador' / '2026 -05 EDP 47'
        carpeta.mkdir(parents=True)
        (carpeta / 'EDP.xlsx').write_bytes(excel())
        (carpeta / '2.5a TICKET INTERNO.pdf').write_bytes(b'%PDF-1.4\nrespaldo')
        self.a = Auditoria(self.raiz / 'Fuentes', self.raiz / 'Auditoria')
        self.fuente = self.a.catalogo()['fuentes'][0]['id']
        for t in self.a.listar_tickets(self.fuente)['tickets']:
            (carpeta / f'{t["ticket"]}_EDP47.pdf').write_bytes(b'%PDF-1.4\nRespaldo de prueba')
        self.servidor = ServidorPanel(('127.0.0.1', 0), crear_handler(
            self.raiz / 'Fuentes', self.raiz / 'Auditoria', usuarios=self.usuarios))
        self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.hilo.start()
        self.addCleanup(self.cerrar)
        self.base = f'http://127.0.0.1:{self.servidor.server_port}'

    def cerrar(self):
        self.servidor.shutdown(); self.servidor.server_close(); self.hilo.join()

    def solicitud(self, ruta, datos=None, cookie='', origen=None):
        headers = {'Cookie': cookie, 'Content-Type': 'application/json'}
        if origen:
            headers['Origin'] = origen
        request = Request(self.base + ruta, json.dumps(datos).encode() if datos is not None else None, headers)
        try:
            with urlopen(request) as r:
                return r.status, r.read(), r.headers
        except HTTPError as error:
            with error:
                return error.code, error.read(), error.headers

    def configurar(self):
        self.assertEqual(self.solicitud('/api/sesion/configurar', {'correo': 'administrador@prueba.cl', 'password': 'administrador-clave-2026'})[0], 200)
        cookie = self.ingresar('administrador')
        for rol in ('auditor', 'general'):
            self.assertEqual(self.solicitud('/api/configuraciones/usuarios', {'correo': rol + '@prueba.cl', 'rol': rol, 'password': rol + '-clave-2026'}, cookie)[0], 201)

    def ingresar(self, rol):
        status, cuerpo, headers = self.solicitud('/api/sesion/ingresar', {'usuario': rol + '@prueba.cl', 'password': rol + '-clave-2026'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(cuerpo)['usuario']['rol'], rol)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        return headers['Set-Cookie'].split(';')[0]

    def test_eliminar_muestra_solo_admin_auditor_y_conserva_otras_revisiones_y_fuentes(self):
        self.configurar()
        cookies = {r: self.ingresar(r) for r in ROLES}
        anterior = self.a.sortear({'fuente': self.fuente, 'cantidad': 3})
        for rol in ('auditor', 'administrador'):
            muestra = self.a.sortear({'fuente': self.fuente, 'cantidad': 3})
            fila = muestra['tickets'][0]['fila']
            m = self.a.modificar({'muestra': muestra['id'], 'fila': fila, 'comprobado': True}, 'comprobar')
            documento = m['tickets'][0]['documentos'][0]['id']
            datos = {'muestra': muestra['id']}
            self.assertEqual(self.solicitud('/api/auditoria/eliminar', datos)[0], 401)
            self.assertEqual(self.solicitud('/api/auditoria/eliminar', datos, cookies['general'])[0], 403)
            self.assertEqual(self.solicitud('/api/auditoria/eliminar', {}, cookies[rol])[0], 400)
            self.assertEqual(self.solicitud('/api/auditoria/eliminar', datos, cookies[rol])[0], 200)
            self.assertEqual(self.solicitud('/api/auditoria/eliminar', datos, cookies[rol])[0], 400)
            self.assertEqual(self.solicitud('/api/auditoria/muestra?id=' + muestra['id'], cookie=cookies[rol])[0], 400)
            with self.assertRaises(ValueError):
                self.a.documento(documento)
            self.assertTrue((self.a.fuentes / muestra['archivo']).is_file())
            self.assertTrue((self.a.fuentes / muestra['archivo']).parent.joinpath(f'{m["tickets"][0]["ticket"]}_EDP47.pdf').is_file())
        self.assertEqual([m['id'] for m in self.a.catalogo()['muestras']], [anterior['id']])
        self.assertEqual(self.a.catalogo()['estados_pago'][0]['muestra_vigente'], anterior['id'])

    def test_acceso_roles_y_consulta_general_sin_escrituras(self):
        self.assertEqual(self.solicitud('/api/auditoria')[0], 401)
        self.assertEqual(self.solicitud('/api/auditoria/comprobar', {})[0], 401)
        self.configurar()
        cookies = {r: self.ingresar(r) for r in ROLES}
        muestra = self.a.sortear({'fuente': self.fuente, 'cantidad': 3})
        cambio = {'muestra': muestra['id'], 'fila': muestra['tickets'][0]['fila'], 'comprobado': True, 'rol': 'administrador'}
        # Intentar elevar el rol mediante JSON o una cookie falsa no concede permisos.
        self.assertEqual(self.solicitud('/api/auditoria/comprobar', cambio, cookies['general'])[0], 403)
        self.assertEqual(self.solicitud('/api/auditoria/comprobar', cambio, 'panel_sesion=falso; rol=administrador')[0], 401)
        self.assertFalse(self.a.obtener(muestra['id'])['tickets'][0]['comprobado'])
        for rol in ('auditor', 'administrador'):
            status, cuerpo, _ = self.solicitud('/api/auditoria/comprobar', cambio, cookies[rol])
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(cuerpo)['tickets'][0]['comprobado'])
        for cookie in cookies.values():
            for extension in ('pdf', 'csv', 'zip'):
                self.assertEqual(self.solicitud('/api/auditoria/reporte.' + extension + '?id=' + muestra['id'], cookie=cookie)[0], 200)
        cambio_sin_check = {**cambio, 'comprobado': False}
        self.solicitud('/api/auditoria/comprobar', cambio_sin_check, cookies['administrador'])
        nombre = f'{muestra["tickets"][0]["ticket"]}_EDP47.pdf'
        self.assertEqual(self.solicitud('/api/auditoria/adjuntar', {**cambio, **adjunto(nombre)}, cookies['general'])[0], 403)
        status, cuerpo, _ = self.solicitud('/api/auditoria/adjuntar', {**cambio, **adjunto(nombre)}, cookies['auditor'])
        self.assertEqual(status, 200)
        status, cuerpo, _ = self.solicitud('/api/auditoria/adjuntar', {**cambio, **adjunto(nombre)}, cookies['administrador'])
        self.assertEqual(status, 200)
        documento = json.loads(cuerpo)['tickets'][0]['documentos'][0]['id']
        self.assertEqual(self.solicitud('/api/auditoria/quitar', {**cambio, 'documento': documento}, cookies['administrador'])[0], 200)
        antes_auditor = len(self.a.catalogo()['muestras'])
        self.assertEqual(self.solicitud('/api/auditoria/sortear', {'fuente': self.fuente, 'cantidad': 3}, cookies['auditor'])[0], 200)
        self.assertEqual(len(self.a.catalogo()['muestras']), antes_auditor + 1)
        for rol in ('general', 'auditor'):
            self.assertEqual(self.solicitud('/api/configuraciones', cookie=cookies[rol])[0], 403)
            for ruta in ('quitar', 'futura-escritura'):
                self.assertEqual(self.solicitud('/api/auditoria/' + ruta, {}, cookies[rol])[0], 403)
            self.assertEqual(self.solicitud('/api/futura-escritura', {}, cookies[rol])[0], 403)
        # Descargar reportes usa POST pero no modifica datos.
        with patch('app.pdf.crear_pdf', return_value=b'%PDF-prueba'):
            for cookie in cookies.values():
                self.assertEqual(self.solicitud('/api/reporte.pdf', {'registros': []}, cookie)[0], 200)
        antes = len(self.a.catalogo()['muestras'])
        for ruta, datos in [('sortear', {'fuente': self.fuente, 'cantidad': 3}),
                            ('seleccionar', {'fuente': self.fuente, 'filas': [2, 3, 4], 'sha256': self.a.listar_tickets(self.fuente)['sha256']})]:
            status, cuerpo, _ = self.solicitud('/api/auditoria/' + ruta, datos, cookies['general'])
            self.assertEqual(status, 403)
            self.assertEqual(len(self.a.catalogo()['muestras']), antes)
            for rol in ('auditor', 'administrador'):
                status, cuerpo, _ = self.solicitud('/api/auditoria/' + ruta, datos, cookies[rol])
                self.assertEqual(status, 200)
                self.assertFalse(json.loads(cuerpo).get('preview', False))
            antes = len(self.a.catalogo()['muestras'])
        self.assertEqual(self.solicitud('/api/auditoria/tickets?id=' + self.fuente, cookie=cookies['general'])[0], 403)
        for rol in ('auditor', 'administrador'):
            self.assertEqual(self.solicitud('/api/auditoria/tickets?id=' + self.fuente, cookie=cookies[rol])[0], 200)
        status, cuerpo, _ = self.solicitud('/api/auditoria/muestra?id=' + muestra['id'], cookie=cookies['general'])
        self.assertEqual(status, 200)
        self.assertIn('comprobado', json.loads(cuerpo)['tickets'][0])
        self.assertEqual(self.solicitud('/api/sesion/salir', {}, cookies['general'])[0], 200)
        self.assertEqual(self.solicitud('/api/auditoria', cookie=cookies['general'])[0], 401)
        token = cookies['auditor'].split('=')[1]
        self.usuarios.sesiones[token]['vence'] = 0
        self.assertEqual(self.solicitud('/api/auditoria', cookie=cookies['auditor'])[0], 401)

    def test_alta_unica_contrasenas_y_origen(self):
        self.assertFalse(json.loads(self.solicitud('/api/sesion')[1])['configurado'])
        self.assertEqual(self.solicitud('/api/sesion/configurar', {r: 'corta' for r in ROLES})[0], 400)
        self.assertFalse(self.usuarios.configurado())
        self.assertEqual(self.solicitud('/api/sesion/configurar', {}, origen='https://otro.example')[0], 400)
        self.configurar()
        self.assertEqual(self.solicitud('/api/sesion/configurar', {r: 'otra-clave-2026' for r in ROLES})[0], 400)
        self.assertNotIn(b'administrador-clave-2026', self.usuarios.ruta.read_bytes())
        cookie = self.ingresar('administrador')
        sesion = json.loads(self.solicitud('/api/sesion', cookie=cookie)[1])
        self.assertIn('configurar', sesion['usuario']['permisos'])
        for _ in range(6):
            self.assertEqual(self.solicitud('/api/sesion/ingresar', {'usuario': 'general@prueba.cl', 'password': 'incorrecta'})[0], 400)
        self.assertEqual(self.solicitud('/api/sesion/ingresar', {'usuario': 'general@prueba.cl', 'password': 'general-clave-2026'})[0], 400)

    def test_configuraciones_y_vista_general_de_admin(self):
        self.configurar()
        admin = self.ingresar('administrador')
        auditor = self.ingresar('auditor')
        general = self.ingresar('general')
        cuenta = {'correo': ' Nueva.Persona@Resiter.cl ', 'rol': 'auditor', 'password': 'Nueva.Clave2026'}
        for cookie in ('', auditor, general):
            esperado = 401 if not cookie else 403
            self.assertEqual(self.solicitud('/api/configuraciones/usuarios', cuenta, cookie)[0], esperado)
            self.assertEqual(self.solicitud('/configuraciones', cookie=cookie)[0], esperado)
        self.assertEqual(self.solicitud('/api/configuraciones/usuarios', cuenta, admin, 'https://otro.example')[0], 400)
        self.assertEqual(self.solicitud('/configuraciones', cookie=admin)[0], 200)
        status, cuerpo, _ = self.solicitud('/api/configuraciones/usuarios', cuenta, admin)
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(cuerpo)['usuario']['correo'], 'nueva.persona@resiter.cl')
        self.assertEqual(self.solicitud('/api/configuraciones/usuarios', cuenta, admin)[0], 400)
        for datos in ({**cuenta, 'correo': 'incorrecto'}, {**cuenta, 'rol': 'superadmin'},
                      {**cuenta, 'password': 'corta'}, {**cuenta, 'rol': []}):
            self.assertEqual(self.solicitud('/api/configuraciones/usuarios', datos, admin)[0], 400)
        lista = json.loads(self.solicitud('/api/configuraciones/usuarios', cookie=admin)[1])['usuarios']
        self.assertEqual(len(lista), 4)
        self.assertFalse(any(k in u for u in lista for k in ('clave', 'sal', 'password')))
        self.assertEqual(self.solicitud('/api/sesion/ingresar', {'usuario': 'NUEVA.PERSONA@RESITER.CL', 'password': cuenta['password']})[0], 200)
        for cookie in (auditor, general):
            self.assertEqual(self.solicitud('/api/sesion/vista', {'general': False}, cookie)[0], 403)
        self.assertEqual(self.solicitud('/api/sesion/vista', {'general': 'true'}, admin)[0], 400)
        status, cuerpo, _ = self.solicitud('/api/sesion/vista', {'general': True}, admin)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(cuerpo)['usuario']['rol'], 'general')
        self.assertEqual(json.loads(cuerpo)['usuario']['rol_real'], 'administrador')
        self.assertEqual(self.solicitud('/api/configuraciones/usuarios', cuenta, admin)[0], 403)
        self.assertEqual(self.solicitud('/configuraciones', cookie=admin)[0], 403)
        self.assertEqual(self.solicitud('/api/auditoria/comprobar', {}, admin)[0], 403)
        antes = len(self.a.catalogo()['muestras'])
        self.assertEqual(self.solicitud('/api/auditoria/sortear', {'fuente': self.fuente, 'cantidad': 3}, admin)[0], 403)
        self.assertEqual(self.solicitud('/api/auditoria/seleccionar', {}, admin)[0], 403)
        self.assertEqual(self.solicitud('/api/auditoria/tickets?id=' + self.fuente, cookie=admin)[0], 403)
        self.assertEqual(len(self.a.catalogo()['muestras']), antes)
        self.assertEqual(self.solicitud('/api/sesion/vista', {'general': False}, admin)[0], 200)
        self.assertEqual(self.solicitud('/configuraciones', cookie=admin)[0], 200)
        self.assertIn('configurar', json.loads(self.solicitud('/api/sesion', cookie=admin)[1])['usuario']['permisos'])

    def test_editar_roles_contrasenas_y_sesiones(self):
        self.configurar()
        admin = self.ingresar('administrador')
        auditor = self.ingresar('auditor')
        general = self.ingresar('general')
        ruta = '/api/configuraciones/usuarios/editar'
        datos = {'correo': 'general@prueba.cl', 'rol': 'auditor', 'password': ''}
        for cookie, status in [('', 401), (auditor, 403), (general, 403)]:
            self.assertEqual(self.solicitud(ruta, datos, cookie)[0], status)
        self.assertEqual(self.solicitud(ruta, datos, admin, 'https://otro.example')[0], 400)
        for invalido in ({**datos, 'rol': 'otro'}, {**datos, 'password': 'corta'},
                         {**datos, 'correo': 'no-existe@prueba.cl'}, {**datos, 'password': None}):
            self.assertEqual(self.solicitud(ruta, invalido, admin)[0], 400)
        self.assertEqual(self.solicitud('/api/sesion/vista', {'general': True}, admin)[0], 200)
        self.assertEqual(self.solicitud(ruta, datos, admin)[0], 403)
        self.assertEqual(self.solicitud('/api/sesion/vista', {'general': False}, admin)[0], 200)
        status, cuerpo, _ = self.solicitud(ruta, datos, admin)
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(cuerpo)['sesion_cerrada'])
        self.assertEqual(self.solicitud('/api/auditoria', cookie=general)[0], 401)
        status, cuerpo, headers = self.solicitud('/api/sesion/ingresar', {'usuario': datos['correo'], 'password': 'general-clave-2026'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(cuerpo)['usuario']['rol'], 'auditor')
        general_nueva = headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.solicitud(ruta, datos, admin)[0], 200)
        self.assertEqual(self.solicitud('/api/auditoria', cookie=general_nueva)[0], 200, 'Guardar sin cambios no cierra sesiones')
        datos['password'] = 'Contraseña.Nueva2026'
        self.assertEqual(self.solicitud(ruta, datos, admin)[0], 200)
        self.assertEqual(self.solicitud('/api/auditoria', cookie=general_nueva)[0], 401)
        self.assertEqual(self.solicitud('/api/sesion/ingresar', {'usuario': datos['correo'], 'password': 'general-clave-2026'})[0], 400)
        self.assertEqual(self.solicitud('/api/sesion/ingresar', {'usuario': datos['correo'], 'password': datos['password']})[0], 200)
        ultimo = {'correo': 'administrador@prueba.cl', 'rol': 'general'}
        self.assertEqual(self.solicitud(ruta, ultimo, admin)[0], 400, 'No puede quitarse el último Admin')
        self.assertEqual(self.solicitud('/configuraciones', cookie=admin)[0], 200)
        self.assertEqual(self.solicitud('/api/configuraciones/usuarios', {'correo': 'otro-admin@prueba.cl', 'rol': 'administrador', 'password': 'Otra.Clave2026'}, admin)[0], 201)
        status, cuerpo, _ = self.solicitud(ruta, ultimo, admin)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(cuerpo)['sesion_cerrada'])
        self.assertEqual(self.solicitud('/api/auditoria', cookie=admin)[0], 401)
        nuevo = json.loads(self.solicitud('/api/sesion/ingresar', {'usuario': ultimo['correo'], 'password': 'administrador-clave-2026'})[1])['usuario']
        self.assertEqual(nuevo['rol'], 'general')
        self.assertNotIn('configurar', nuevo['permisos'])

    def test_perfil_cambio_password_propio_para_todos_los_roles(self):
        ruta = '/api/sesion/password'
        self.assertEqual(self.solicitud(ruta, {'actual': 'actual', 'nueva': 'Nueva.Clave2026'})[0], 401)
        self.configurar()
        for rol in ('general', 'auditor', 'administrador'):
            cookie = self.ingresar(rol)
            otra_sesion = self.ingresar(rol)
            self.assertEqual(self.solicitud('/perfil', cookie=cookie)[0], 200)
            if rol == 'administrador':
                self.assertEqual(self.solicitud('/api/sesion/vista', {'general': True}, cookie)[0], 200)
            datos = {'actual': rol + '-clave-2026', 'nueva': 'Nueva.Clave2026.' + rol,
                     'correo': 'otra-cuenta@prueba.cl', 'rol': 'administrador'}
            self.assertEqual(self.solicitud(ruta, datos, cookie, 'https://otro.example')[0], 400)
            for invalido in ({**datos, 'actual': 'incorrecta'}, {**datos, 'nueva': 'corta'},
                             {**datos, 'actual': None}, {**datos, 'nueva': None}):
                self.assertEqual(self.solicitud(ruta, invalido, cookie)[0], 400)
            status, _, headers = self.solicitud(ruta, datos, cookie)
            self.assertEqual(status, 200)
            self.assertIn('Max-Age=0', headers['Set-Cookie'])
            for sesion in (cookie, otra_sesion):
                self.assertEqual(self.solicitud('/api/auditoria', cookie=sesion)[0], 401)
            correo = rol + '@prueba.cl'
            self.assertEqual(self.solicitud('/api/sesion/ingresar', {'usuario': correo, 'password': datos['actual']})[0], 400)
            status, cuerpo, _ = self.solicitud('/api/sesion/ingresar', {'usuario': correo, 'password': datos['nueva']})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(cuerpo)['usuario']['rol'], rol, 'Cambiar contraseña no cambia el rol')
            self.assertNotIn(datos['nueva'].encode(), self.usuarios.ruta.read_bytes())

    def test_perfil_limita_intentos_de_contrasena_actual(self):
        self.configurar()
        cookie = self.ingresar('general')
        for _ in range(5):
            self.assertEqual(self.solicitud('/api/sesion/password', {'actual': 'incorrecta', 'nueva': 'Nueva.Clave2026'}, cookie)[0], 400)
        self.assertEqual(self.solicitud('/api/sesion/password', {'actual': 'general-clave-2026', 'nueva': 'Nueva.Clave2026'}, cookie)[0], 400)
        self.assertEqual(self.solicitud('/api/auditoria', cookie=cookie)[0], 200)

    def test_cuentas_antiguas_sin_correo_no_dan_acceso(self):
        with self.usuarios.conexion() as db:
            db.execute('INSERT INTO usuarios VALUES (?,?,?,?)', ('administrador', 'administrador', '00' * 16, 'antigua'))
        self.assertFalse(self.usuarios.configurado())
        self.assertEqual(self.usuarios.listar(), [])
        with self.assertRaises(ValueError):
            self.usuarios.ingresar('administrador', 'antigua')
        self.configurar()
        self.assertEqual(len(self.usuarios.listar()), 3)


if __name__ == '__main__':
    unittest.main()
