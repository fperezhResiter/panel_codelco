"""Comentarios: permisos, selección por fila y persistencia al reimportar Excel."""
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from app.base_datos import actualizar_base_datos
from app.densidades import guardar_comentario, leer_densidades, ruta_comentarios
from app.servidor import crear_handler
from app.usuarios import Usuarios
from test_densidades import maestra, edp, edp_andina


class ComentariosTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        maestra(self.raiz, [('Madera', 100, 300), ('Asimilable a RINP', 350, 600)])
        edp(self.raiz)
        edp_andina(self.raiz)
        self.bd = self.raiz / 'bd.sqlite3'
        actualizar_base_datos(self.raiz, self.bd)
        self.tickets = leer_densidades(self.bd, {'unidad': 'Andina'})['tickets']
        self.rojo = next(t for t in self.tickets if t['estado'] == 'no_coincide_mayor')
        self.datos = {'unidad': 'Andina', 'id': self.rojo['id'], 'comentario': 'Revisar peso: excede las tolvas disponibles.'}

    def usuario(self, rol):
        return Usuarios.publico({'nombre': rol + '@prueba.cl', 'rol': rol})

    def test_persistencia_edicion_y_actualizacion_de_base(self):
        resultado = guardar_comentario(self.bd, self.datos, self.usuario('auditor'))
        self.assertEqual(resultado['comentario_autor'], 'auditor@prueba.cl')
        actualizar_base_datos(self.raiz, self.bd)
        tickets = leer_densidades(self.bd, {'unidad': 'Andina'})['tickets']
        self.assertEqual([t['comentario'] for t in tickets if t['id'] == self.rojo['id']], [self.datos['comentario']])
        self.assertTrue(all(not t['comentario'] for t in tickets if t['id'] != self.rojo['id']))
        guardar_comentario(self.bd, {**self.datos, 'comentario': 'Corrección validada'}, self.usuario('administrador'))
        guardar_comentario(self.bd, {**self.datos, 'comentario': ''}, self.usuario('auditor'))
        self.assertEqual(next(t for t in leer_densidades(self.bd, {'unidad': 'Andina'})['tickets'] if t['id'] == self.rojo['id'])['comentario'], '')
        # Dos tickets con número 0 se mantienen separados por fila.
        salvador = leer_densidades(self.bd)['tickets']
        self.assertNotEqual(salvador[0]['id'], salvador[1]['id'])

    def test_rechazo_de_roles_otros_estados_y_entradas_invalidas(self):
        with self.assertRaises(PermissionError):
            guardar_comentario(self.bd, self.datos, self.usuario('general'))
        for t in self.tickets:
            if t['estado'] != 'no_coincide_mayor':
                with self.subTest(estado=t['estado']), self.assertRaisesRegex(ValueError, 'rojo'):
                    guardar_comentario(self.bd, {**self.datos, 'id': t['id']}, self.usuario('auditor'))
        for cambios in ({'comentario': 'a' * 2001}, {'comentario': None}, {'id': 'inexistente'}, {'unidad': 'El Salvador'}):
            with self.subTest(cambios=cambios), self.assertRaises(ValueError):
                guardar_comentario(self.bd, {**self.datos, **cambios}, self.usuario('administrador'))
        self.assertFalse(ruta_comentarios(self.bd).exists())

    def test_endpoint_autoriza_sesion_y_valida_rojo(self):
        handler = crear_handler(self.raiz, self.raiz / 'Auditoria', self.bd)

        def solicitud(usuario, datos, origen=None):
            instancia = handler.__new__(handler)
            cuerpo = json.dumps(datos).encode()
            instancia.path = '/api/densidades/comentario'
            instancia.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(cuerpo)), 'Host': '127.0.0.1:8765'}
            if origen:
                instancia.headers['Origin'] = origen
            instancia.rfile = BytesIO(cuerpo)
            instancia.sesion_actual = lambda: {'usuario': usuario} if usuario else None
            resultados = []
            instancia.json_respuesta = lambda datos, status=200: resultados.append((status, datos))
            instancia.do_POST()
            return resultados[0]

        self.assertEqual(solicitud(None, self.datos)[0], 401)
        self.assertEqual(solicitud(self.usuario('general'), {**self.datos, 'rol': 'administrador'})[0], 403)
        admin_general = {**self.usuario('general'), 'rol_real': 'administrador', 'vista_general': True}
        self.assertEqual(solicitud(admin_general, self.datos)[0], 403)
        for rol in ('auditor', 'administrador'):
            self.assertEqual(solicitud(self.usuario(rol), self.datos)[0], 200)
        verde = next(t for t in self.tickets if t['estado'] == 'coincide')
        self.assertEqual(solicitud(self.usuario('auditor'), {**self.datos, 'id': verde['id']})[0], 400)
        self.assertEqual(solicitud(self.usuario('auditor'), self.datos, 'https://otro.example')[0], 400)
