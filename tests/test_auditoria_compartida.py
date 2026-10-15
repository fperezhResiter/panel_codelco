"""Dos equipos con cachés distintas y sincronización fuera de orden de OneDrive."""
import json
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from io import BytesIO
from urllib.parse import urlsplit
from unittest.mock import patch

from app.auditoria import Auditoria
from app.auditoria_compartida import AuditoriaCompartida
from app.servidor import crear_handler
from soporte_usuarios import crear_handler_administrador as crear_handler
from test_auditoria import excel, adjunto


class AuditoriaCompartidaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temp.name)
        self.fuentes = self.raiz / 'Fuentes'
        carpeta = self.fuentes / 'Codelco El Salvador' / '2026 -05 EDP 47'
        carpeta.mkdir(parents=True)
        (carpeta / 'EDP.xlsx').write_bytes(excel())
        (carpeta / '2.5a TICKET INTERNO (EDP 47).pdf').write_bytes(b'%PDF-1.4\nRespaldo compartido')
        self.comun = self.raiz / 'Equipo A' / 'Auditoria'
        self.replica = self.raiz / 'Equipo B' / 'Auditoria'
        self.a = AuditoriaCompartida(self.fuentes, self.comun, self.raiz / 'cache-A')
        self.b = AuditoriaCompartida(self.fuentes, self.replica, self.raiz / 'cache-B')
        fuente = self.a.catalogo()['fuentes'][0]['id']
        self.m = self.a.sortear({'fuente': fuente, 'cantidad': 3})
        for t in self.a.listar_tickets(fuente)['tickets']:
            (carpeta / f'{t["ticket"]}_EDP47.pdf').write_bytes(b'%PDF-1.4\nRespaldo compartido')

    def tearDown(self):
        self.temp.cleanup()

    def sincronizar_carpetas(self):
        # Simular lo que hace OneDrive entre carpetas locales de dos equipos.
        for origen, destino in ((self.comun, self.replica), (self.replica, self.comun)):
            compartido = origen / 'Compartido'
            if compartido.is_dir():
                shutil.copytree(compartido, destino / 'Compartido', dirs_exist_ok=True)

    def cambiar(self, equipo, indice, comprobado):
        return equipo.modificar({'muestra': self.m['id'], 'fila': self.m['tickets'][indice]['fila'],
                                 'comprobado': comprobado}, 'comprobar')

    def test_otro_equipo_recibe_check_y_documento_sin_compartir_sqlite(self):
        self.cambiar(self.a, 0, True)
        self.sincronizar_carpetas()
        m = self.b.obtener(self.m['id'])
        self.assertTrue(m['tickets'][0]['comprobado'])
        self.assertEqual(self.b.documento_edp(m['id'])[1], b'%PDF-1.4\nRespaldo compartido')
        t = m['tickets'][0]
        (self.fuentes / m['archivo']).parent.joinpath(f'{t["ticket"]}_EDP47.pdf').unlink()
        self.assertEqual(self.b.documento_ticket(m['id'], t['fila'])[1], b'%PDF-1.4\nRespaldo compartido')
        self.assertEqual(self.b.catalogo()['estados_pago'][0]['color'], 'amarillo')
        self.assertEqual(self.b.estado_conexion()['modo'], 'carpeta_compartida')
        self.assertFalse((self.replica / 'auditoria.sqlite3').exists())
        # Iniciar de cero en un tercer equipo reconstruye su BD desde la carpeta.
        c = AuditoriaCompartida(self.fuentes, self.replica, self.raiz / 'cache-C')
        self.assertTrue(c.obtener(self.m['id'])['tickets'][0]['comprobado'])

    def test_dos_equipos_cambian_filas_distintas_sin_perder_checks(self):
        self.sincronizar_carpetas()
        self.b.obtener(self.m['id'])
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda x: self.cambiar(*x), [(self.a, 0, True), (self.b, 1, True)]))
        self.assertEqual(len(resultados), 2)
        self.sincronizar_carpetas()
        for equipo in (self.a, self.b):
            m = equipo.obtener(self.m['id'])
            self.assertTrue(all(t['comprobado'] for t in m['tickets'][:2]))
            self.assertFalse(m['tickets'][2]['comprobado'])
        self.cambiar(self.b, 2, True)
        self.sincronizar_carpetas()
        self.assertEqual(self.a.catalogo()['estados_pago'][0]['estado'], 'Chequeo completo')
        self.cambiar(self.a, 0, False)
        self.sincronizar_carpetas()
        self.assertFalse(self.b.obtener(self.m['id'])['tickets'][0]['comprobado'])

    def test_evento_sin_archivo_espera_y_reintenta_sin_aplicacion_parcial(self):
        self.cambiar(self.a, 0, True)
        shutil.copytree(self.comun / 'Compartido' / 'eventos', self.replica / 'Compartido' / 'eventos')
        catalogo = self.b.catalogo()
        self.assertGreater(catalogo['conexion_bd']['pendientes'], 0)
        self.assertFalse(self.b.obtener(self.m['id'])['tickets'][0]['comprobado'])
        self.sincronizar_carpetas()
        self.assertTrue(self.b.obtener(self.m['id'])['tickets'][0]['comprobado'])
        self.assertEqual(self.b.estado_conexion()['pendientes'], 0)

    def test_eventos_duplicados_y_reordenados_no_revierten_uncheck(self):
        self.cambiar(self.a, 0, True)
        self.cambiar(self.a, 0, False)
        self.sincronizar_carpetas()
        self.assertFalse(self.b.obtener(self.m['id'])['tickets'][0]['comprobado'])
        antes = len(self.b.catalogo()['muestras'])
        self.sincronizar_carpetas()
        self.assertEqual(len(self.b.catalogo()['muestras']), antes)
        self.assertFalse(self.b.obtener(self.m['id'])['tickets'][0]['comprobado'])

    def test_adjuntar_y_quitar_se_comparten_con_restablecimiento_del_check(self):
        fila = self.m['tickets'][0]['fila']
        nombre = f'{self.m["tickets"][0]["ticket"]}_EDP47.pdf'
        contenido = b'%PDF-1.4\nRespaldo compartido'
        m = self.a.modificar({'muestra': self.m['id'], 'fila': fila, **adjunto(nombre, contenido)}, 'adjuntar')
        documento = m['tickets'][0]['documentos'][0]['id']
        self.cambiar(self.a, 0, True)
        self.sincronizar_carpetas()
        self.assertEqual(self.b.documento(documento)[1], contenido)
        m = self.b.modificar({'muestra': m['id'], 'fila': fila, 'documento': documento}, 'quitar')
        self.sincronizar_carpetas()
        m = self.a.obtener(m['id'])
        self.assertFalse(m['tickets'][0]['comprobado'])
        self.assertEqual(m['tickets'][0]['documentos'], [])

    def test_migra_copias_en_conflicto_preservando_checks_y_originales(self):
        legado = self.raiz / 'Legado'
        original = Auditoria(self.fuentes, legado)
        fuente = original.catalogo()['fuentes'][0]['id']
        m = original.sortear({'fuente': fuente, 'cantidad': 3})
        original.modificar({'muestra': m['id'], 'fila': m['tickets'][0]['fila'], 'comprobado': True}, 'comprobar')
        copia = legado / 'auditoria-EQUIPO.sqlite3'
        shutil.copyfile(legado / 'auditoria.sqlite3', copia)
        # Simular una copia concurrente que confirmó otro ticket.
        import sqlite3
        with sqlite3.connect(copia) as db:
            dato = json.loads(db.execute('SELECT datos FROM muestras WHERE id=?', (m['id'],)).fetchone()[0])
            dato['tickets'][0].update(comprobado=False, comprobado_en=None)
            dato['tickets'][1].update(comprobado=True, comprobado_en=dato['actualizado'])
            db.execute('UPDATE muestras SET datos=? WHERE id=?', (json.dumps(dato), m['id']))
        db.close()
        originales = {p.name: p.read_bytes() for p in legado.glob('*.sqlite3')}
        nuevo = AuditoriaCompartida(self.fuentes, legado, self.raiz / 'cache-migracion')
        self.assertTrue(all(t['comprobado'] for t in nuevo.obtener(m['id'])['tickets'][:2]))
        for p in legado.glob('*.sqlite3'):
            self.assertEqual(p.read_bytes(), originales[p.name])
        nuevo.modificar({'muestra': m['id'], 'fila': m['tickets'][0]['fila'], 'comprobado': False}, 'comprobar')
        reinicio = AuditoriaCompartida(self.fuentes, legado, self.raiz / 'cache-reinicio')
        self.assertFalse(reinicio.obtener(m['id'])['tickets'][0]['comprobado'])
        self.assertTrue(reinicio.obtener(m['id'])['tickets'][1]['comprobado'])

    def test_ruta_del_panel_publica_estado_de_bd_compartida(self):
        clase = crear_handler(self.fuentes, self.comun, compartir_auditoria=True)
        handler = clase.__new__(clase)
        resultado = {}
        handler.responder = lambda status, contenido, tipo, descarga=None: resultado.update(status=status, contenido=contenido)
        handler.log_error = lambda *args: None
        handler.auditoria_get(urlsplit('/api/auditoria'))
        self.assertEqual(resultado['status'], 200)
        self.assertEqual(json.loads(resultado['contenido'])['conexion_bd']['modo'], 'carpeta_compartida')

    def test_error_al_publicar_no_confirma_solo_en_la_bd_local(self):
        with patch('app.auditoria_compartida.escribir_atomico', side_effect=OSError('Carpeta no disponible')):
            with self.assertRaises(OSError):
                self.cambiar(self.a, 0, True)
        self.assertFalse(self.a.obtener(self.m['id'])['tickets'][0]['comprobado'])
        self.sincronizar_carpetas()
        self.assertFalse(self.b.obtener(self.m['id'])['tickets'][0]['comprobado'])

    def test_archivo_incompleto_no_bloquea_los_otros_chequeos(self):
        self.cambiar(self.a, 0, True)
        self.sincronizar_carpetas()
        (self.b.eventos / 'incompleto.json').write_text('{', encoding='utf-8')
        c = self.b.catalogo()
        self.assertEqual(c['conexion_bd']['pendientes'], 1)
        self.assertTrue(self.b.obtener(self.m['id'])['tickets'][0]['comprobado'])

    def test_eliminar_se_sincroniza_y_no_revive_con_checks_tardios_o_cache_nueva(self):
        self.cambiar(self.a, 0, True)
        self.sincronizar_carpetas()
        self.b.obtener(self.m['id'])
        self.a.eliminar({'muestra': self.m['id']})
        # Un equipo sin recibir todavía la eliminación publica otro check.
        self.cambiar(self.b, 1, True)
        self.sincronizar_carpetas()
        c = AuditoriaCompartida(self.fuentes, self.replica, self.raiz / 'cache-C')
        for equipo in (self.a, self.b, c):
            self.assertEqual(equipo.catalogo()['muestras'], [])
            self.assertEqual(equipo.catalogo()['estados_pago'][0]['estado_codigo'], 'sin_revision')
            self.assertEqual(equipo.estado_conexion()['pendientes'], 0)
            with equipo.conexion() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM documentos').fetchone()[0], 0)
            with self.assertRaises(ValueError):
                equipo.obtener(self.m['id'])
        self.assertTrue((self.fuentes / self.m['archivo']).is_file())

    def test_fallo_publicando_eliminacion_conserva_muestra_y_documentos(self):
        self.cambiar(self.a, 0, True)
        with patch('app.auditoria_compartida.escribir_atomico', side_effect=OSError('Sin conexión')):
            with self.assertRaises(OSError):
                self.a.eliminar({'muestra': self.m['id']})
        m = self.a.obtener(self.m['id'])
        self.assertTrue(m['tickets'][0]['comprobado'])
        self.assertTrue(m['tickets'][0]['documentos'])
