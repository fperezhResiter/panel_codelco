"""Publicación coherente, sin cuentas y con comentarios persistentes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.publicacion import publicar
from app.base_datos import actualizar_base_datos
from app.densidades import leer_densidades, guardar_comentario
from app.auditoria_compartida import AuditoriaCompartida
from test_densidades import maestra, edp, edp_andina


class PublicacionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        self.fuentes = self.raiz / 'Fuentes'
        self.fuentes.mkdir()
        maestra(self.fuentes, [('Madera', 100, 300), ('Asimilable a RINP', 350, 600)])
        edp(self.fuentes)
        edp_andina(self.fuentes)
        self.bd = self.raiz / 'Datos' / 'conciliacion.sqlite3'
        self.auditorias = self.bd.parent / 'Auditoria'
        actualizar_base_datos(self.fuentes, self.bd)
        self.destino = self.raiz / 'web' / 'publicado' / 'datos.js'

    def publicar(self):
        return publicar(self.fuentes, self.bd, self.destino, self.auditorias)

    def test_publica_comentarios_y_los_conserva_al_actualizar(self):
        t = next(t for t in leer_densidades(self.bd, {'unidad': 'Andina'})['tickets'] if t['estado'] == 'no_coincide_mayor')
        guardar_comentario(self.bd, {'unidad': 'Andina', 'id': t['id'], 'comentario': 'Revisar tolva'}, {'correo': 'auditor@prueba.cl', 'rol': 'auditor', 'permisos': ['revisar']})
        primera = self.publicar()
        actualizar_base_datos(self.fuentes, self.bd)
        segunda = self.publicar()
        for p in [primera, segunda]:
            self.assertEqual(next(fila for fila in p['densidades']['Andina']['tickets'] if fila['id'] == t['id'])['comentario'], 'Revisar tolva')
            self.assertNotIn('usuarios', p)
        self.assertGreaterEqual(segunda['actualizado'], primera['actualizado'])
        contenido = self.destino.read_text(encoding='utf-8')
        self.assertTrue(contenido.startswith('window.PanelPublicado = '))
        self.assertEqual(json.loads(contenido.removeprefix('window.PanelPublicado = ').strip().removesuffix(';'))['version'], 1)

    def test_fallo_conserva_publicacion_anterior(self):
        self.publicar()
        anterior = self.destino.read_bytes()
        with patch('app.publicacion.leer_densidades', side_effect=ValueError('Fallo de lectura')):
            with self.assertRaisesRegex(ValueError, 'Fallo de lectura'):
                self.publicar()
        self.assertEqual(self.destino.read_bytes(), anterior)

    def test_bd_de_auditoria_permanece_en_proyecto(self):
        a = AuditoriaCompartida(self.fuentes, self.auditorias)
        a.catalogo()
        self.assertEqual(a.carpeta, self.auditorias / 'BD')
        self.assertTrue((a.carpeta / 'auditoria.sqlite3').is_file())

    def test_revisiones_y_descargas_persisten_al_reimportar(self):
        from test_auditoria import adjunto
        from zipfile import ZipFile
        a = AuditoriaCompartida(self.fuentes, self.auditorias)
        f = next(f for f in a.catalogo()['fuentes'] if f['unidad'] == 'Andina')
        m = a.sortear({'fuente': f['id'], 'cantidad': 3})
        ticket = m['tickets'][0]
        a.modificar({'muestra': m['id'], 'fila': ticket['fila'], **adjunto(f"{ticket['ticket']}_EDP47.pdf")}, 'adjuntar')
        a.modificar({'muestra': m['id'], 'fila': ticket['fila'], 'comprobado': True}, 'comprobar')
        actualizar_base_datos(self.fuentes, self.bd)
        p = self.publicar()
        self.assertTrue(next(t for t in p['muestras'][m['id']]['tickets'] if t['fila'] == ticket['fila'])['comprobado'])
        reporte = next(r for r in p['reportes_auditoria'] if r['registro']['unidad'] == 'Andina')
        archivo = p['archivos'][reporte['zip']]
        with ZipFile(self.destino.parent / archivo['ruta']) as zip:
            self.assertTrue(any(n.endswith('.pdf') for n in zip.namelist()))
            self.assertTrue(any('respaldos/' in n for n in zip.namelist()))
        otra = self.publicar()
        self.assertEqual(p['archivos'], otra['archivos'])

    def test_publica_imagen_con_tipo_correcto_y_zip_con_ambos_formatos(self):
        from test_auditoria import adjunto
        from zipfile import ZipFile
        a = AuditoriaCompartida(self.fuentes, self.auditorias)
        f = next(f for f in a.catalogo()['fuentes'] if f['unidad'] == 'Andina')
        m = a.sortear({'fuente': f['id'], 'cantidad': 3})
        ticket = m['tickets'][0]
        base = f"{ticket['ticket']}_EDP47"
        cambio = {'muestra': m['id'], 'fila': ticket['fila']}
        a.modificar({**cambio, **adjunto(base + '.jpg', b'imagen original')}, 'adjuntar')
        a.modificar({**cambio, 'comprobado': True}, 'comprobar')
        p = self.publicar()
        t = next(t for t in p['muestras'][m['id']]['tickets'] if t['fila'] == ticket['fila'])
        self.assertEqual(p['archivos'][t['respaldo_publicado']]['tipo'], 'image/jpeg')
        a.modificar({**cambio, 'comprobado': False}, 'comprobar')
        a.modificar({**cambio, **adjunto(base + '.pdf')}, 'adjuntar')
        a.modificar({**cambio, 'comprobado': True}, 'comprobar')
        p = self.publicar()
        reporte = next(r for r in p['reportes_auditoria'] if r['registro']['unidad'] == 'Andina')
        self.assertEqual({p['archivos'][r]['tipo'] for r in reporte['respaldos']}, {'application/pdf', 'image/jpeg'})
        with ZipFile(self.destino.parent / p['archivos'][reporte['zip']]['ruta']) as z:
            self.assertEqual(z.read(next(n for n in z.namelist() if n.endswith('.jpg'))), b'imagen original')
            self.assertTrue(any(n.endswith('/' + base + '.pdf') for n in z.namelist()))

    def test_pendientes_no_reemplazan_publicacion(self):
        self.publicar()
        anterior = self.destino.read_bytes()
        with patch('app.publicacion.AuditoriaCompartida.catalogo', return_value={'conexion_bd': {'pendientes': 1}}):
            with self.assertRaisesRegex(ValueError, 'pendientes'):
                self.publicar()
        self.assertEqual(self.destino.read_bytes(), anterior)
