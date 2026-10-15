"""Formato individual, conservación histórica y paquetes de reporte con respaldos."""
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from app.auditoria import Auditoria
from app.compilados import compilar_auditoria
from test_auditoria import excel, excel_andina, adjunto


class RespaldosTicketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        self.fuentes = self.raiz / 'Fuentes'
        self.carpeta = self.fuentes / 'Codelco El Salvador' / '2026 -05 EDP 49'
        self.carpeta.mkdir(parents=True)
        (self.carpeta / 'EDP.xlsx').write_bytes(excel())
        self.a = Auditoria(self.fuentes, self.raiz / 'Auditoria')
        fuente = self.a.catalogo()['fuentes'][0]['id']
        lista = self.a.listar_tickets(fuente)
        self.m = self.a.seleccionar({'fuente': fuente, 'filas': [2, 3, 4], 'sha256': lista['sha256']})
        self.cambio = {'muestra': self.m['id'], 'fila': 4}
        self.nombre = '000002_EDP49.pdf'
        self.contenido = b'%PDF-1.4\nRespaldo individual original'

    def comprobar(self, valor=True):
        return self.a.modificar({**self.cambio, 'comprobado': valor}, 'comprobar')

    def test_solo_nombre_individual_en_el_edp_correcto_permite_comprobar(self):
        for nombre in ('cualquiera.pdf', '2.5a TICKET INTERNO (EDP 49).pdf',
                       '000002_EDP48.pdf', '2_EDP49.pdf'):
            (self.carpeta / nombre).write_bytes(self.contenido)
        otro = self.fuentes / 'Codelco El Salvador' / '2026 -06 EDP 50'
        otro.mkdir()
        (otro / self.nombre).write_bytes(self.contenido)
        with self.assertRaisesRegex(ValueError, self.nombre):
            self.comprobar()
        ruta = self.carpeta / self.nombre
        ruta.write_bytes(b'No es un PDF')
        with self.assertRaises(ValueError): self.comprobar()
        ruta.write_bytes(self.contenido)
        m = self.comprobar()
        self.assertTrue(m['tickets'][2]['comprobado'])
        self.assertEqual(m['tickets'][2]['respaldo_ticket']['nombre'], self.nombre)
        self.assertIsNone(m['tickets'][0]['respaldo_ticket'])
        ruta.unlink()
        self.assertEqual(self.a.documento_ticket(m['id'], 4), (self.nombre, self.contenido))
        self.comprobar(False)
        # La copia guardada nunca sustituye el requisito de Fuentes para una nueva autorización.
        with self.assertRaises(ValueError): self.comprobar()

    def test_subir_guarda_en_fuentes_y_no_admite_nombre_generico_ni_pdf_invalido(self):
        for nombre, contenido in [('respaldo.pdf', self.contenido), ('000002_EDP48.pdf', self.contenido),
                                  ('000002_EDP49', b'texto'), ('000002_EDP49.jpg:oculto', b'texto'), (self.nombre, b'no pdf')]:
            with self.assertRaises(ValueError):
                self.a.modificar({**self.cambio, **adjunto(nombre, contenido)}, 'adjuntar')
        m = self.a.modificar({**self.cambio, **adjunto(self.nombre, self.contenido)}, 'adjuntar')
        self.assertEqual((self.carpeta / self.nombre).read_bytes(), self.contenido)
        self.assertFalse(m['tickets'][2]['comprobado'])
        self.comprobar()
        with self.assertRaises(ValueError):
            self.a.modificar({**self.cambio, **adjunto(self.nombre, self.contenido)}, 'adjuntar')

    def test_cualquier_extension_conserva_nombre_contenido_y_copia_confirmada(self):
        for extension in ('.jpg', '.PNG', '.docx', '.xlsx', '.txt', '.heic', '.formato_personal'):
            with self.subTest(extension=extension):
                nombre = '000002_EDP49' + extension
                contenido = b'Contenido original del documento'
                self.a.modificar({**self.cambio, **adjunto(nombre, contenido)}, 'adjuntar')
                self.assertEqual((self.carpeta / nombre).read_bytes(), contenido)
                m = self.comprobar()
                self.assertEqual(self.a.documento_ticket(m['id'], 4), (nombre, contenido))
                (self.carpeta / nombre).unlink()
                self.assertEqual(self.a.documento_ticket(m['id'], 4), (nombre, contenido))
                paquete = compilar_auditoria(self.a.reporte_unidad('El Salvador'), {'anio': 2026, 'mes': 5, 'edp': 49}, auditoria=self.a)
                with ZipFile(BytesIO(paquete)) as z:
                    respaldo = next(n for n in z.namelist() if n.endswith('/' + nombre))
                    self.assertEqual(z.read(respaldo), contenido)
                self.comprobar(False)

    def test_zip_incluye_todos_los_formatos_del_ticket_y_excluye_otros_tickets(self):
        for nombre, contenido in [(self.nombre, self.contenido), ('000002_EDP49.jpg', b'imagen'),
                                  ('000002_EDP49.docx', b'documento'), ('000002 - EDP 49.png', b'otra imagen'), ('000003_EDP49.jpg', b'otro ticket'),
                                  ('2_EDP49.jpg', b'numero sin ceros'), ('000002_EDP48.jpg', b'otro EDP')]:
            (self.carpeta / nombre).write_bytes(contenido)
        m = self.comprobar()
        self.assertEqual(m['tickets'][2]['respaldo_ticket']['nombre'], self.nombre)
        paquete = compilar_auditoria(self.a.reporte_unidad('El Salvador'), {'anio': 2026, 'mes': 5, 'edp': 49}, auditoria=self.a)
        with ZipFile(BytesIO(paquete)) as z:
            nombres = {Path(n).name for n in z.namelist() if '/respaldos/' in n}
            self.assertEqual(nombres, {self.nombre, '000002_EDP49.jpg', '000002_EDP49.docx', '000002 - EDP 49.png'})
            self.assertEqual(z.read(next(n for n in z.namelist() if n.endswith('.jpg'))), b'imagen')

    def test_variantes_de_nombre_se_suben_se_detectan_y_se_descargan_sin_renombrar(self):
        for base in ('000002 EDP 49', '000002-EDP-49', '000002 - EDP 49',
                     '000002_EDP_49', '000002EDP49', '000002 edp 49'):
            with self.subTest(base=base):
                nombre = base + '.jpg'
                contenido = b'imagen del ticket'
                self.a.modificar({**self.cambio, **adjunto(nombre, contenido)}, 'adjuntar')
                self.assertEqual(self.a.obtener(self.m['id'])['tickets'][2]['respaldo_ticket']['nombre'], nombre)
                self.comprobar()
                paquete = compilar_auditoria(self.a.reporte_unidad('El Salvador'), {'anio': 2026, 'mes': 5, 'edp': 49}, auditoria=self.a)
                with ZipFile(BytesIO(paquete)) as z:
                    self.assertEqual(z.read(next(n for n in z.namelist() if n.endswith('/' + nombre))), contenido)
                self.comprobar(False)
                (self.carpeta / nombre).unlink()
        # Archivos copiados directamente en Fuentes usan la misma regla.
        nombre = '000002 - EDP - 49.png'
        (self.carpeta / nombre).write_bytes(b'imagen externa')
        self.assertEqual(self.comprobar()['tickets'][2]['respaldo_ticket']['nombre'], nombre)

    def test_variantes_no_permiten_otro_ticket_edp_ni_texto_adicional(self):
        for nombre in ('000003 EDP 49.jpg', '000002 - EDP 48.jpg', '2 EDP 49.jpg',
                       '000002 EDP 49 copia.jpg', 'ticket 000002 EDP 49.jpg', '000002 EDP.jpg'):
            with self.subTest(nombre=nombre):
                with self.assertRaises(ValueError):
                    self.a.modificar({**self.cambio, **adjunto(nombre, b'imagen')}, 'adjuntar')
                (self.carpeta / nombre).write_bytes(b'imagen')
        with self.assertRaises(ValueError):
            self.comprobar()

    def test_conserva_autorizacion_anterior_y_el_respaldo_comun_guardado(self):
        nombre = '2.5a TICKET INTERNO (EDP 49).pdf'
        with self.a.conexion() as db:
            m = json.loads(db.execute('SELECT datos FROM muestras WHERE id=?', (self.m['id'],)).fetchone()[0])
            m['tickets'][2].update(comprobado=True, comprobado_en=m['creado'])
            db.execute('UPDATE muestras SET datos=? WHERE id=?', (json.dumps(m), m['id']))
            db.execute('INSERT INTO documentos VALUES (?,?,?,?,?,?)', ('legado', m['id'], 0, nombre, m['creado'], self.contenido))
        m = self.a.obtener(self.m['id'])
        self.assertTrue(m['tickets'][2]['comprobado'])
        self.assertTrue(m['tickets'][2]['respaldo_ticket']['historico'])
        self.assertEqual(self.a.documento_ticket(m['id'], 4), (nombre, self.contenido))
        self.assertTrue(self.comprobar()['tickets'][2]['comprobado'])
        paquete = compilar_auditoria(self.a.reporte_unidad('El Salvador'), {'anio': 2026, 'mes': 5, 'edp': 49}, auditoria=self.a)
        with ZipFile(BytesIO(paquete)) as z:
            respaldo = next(n for n in z.namelist() if n.endswith('/' + nombre))
            self.assertEqual(z.read(respaldo), self.contenido)
        self.comprobar(False)
        with self.assertRaises(ValueError): self.comprobar()

    def test_paquete_incluye_pdf_y_respaldo_individual_actual_sin_repetirlo(self):
        self.a.modificar({**self.cambio, **adjunto(self.nombre, self.contenido)}, 'adjuntar')
        self.comprobar()
        (self.carpeta / self.nombre).write_bytes(b'%PDF-1.4\nModificado despues')
        paquete = compilar_auditoria(self.a.reporte_unidad('El Salvador'), {'anio': 2026, 'mes': 5, 'edp': 49}, auditoria=self.a)
        with ZipFile(BytesIO(paquete)) as z:
            self.assertEqual(len(z.namelist()), 2)
            pdf = next(n for n in z.namelist() if '/respaldos/' not in n)
            self.assertTrue(z.read(pdf).startswith(b'%PDF-'))
            respaldo = next(n for n in z.namelist() if n.endswith('/' + self.nombre))
            self.assertEqual(z.read(respaldo), b'%PDF-1.4\nModificado despues')

    def test_pdf_individual_tiene_prioridad_sobre_el_respaldo_historico(self):
        nombre_historico = '2.5a TICKET INTERNO (EDP 49).pdf'
        with self.a.conexion() as db:
            m = json.loads(db.execute('SELECT datos FROM muestras WHERE id=?', (self.m['id'],)).fetchone()[0])
            m['tickets'][2].update(comprobado=True, comprobado_en=m['creado'])
            db.execute('UPDATE muestras SET datos=? WHERE id=?', (json.dumps(m), m['id']))
            db.execute('INSERT INTO documentos VALUES (?,?,?,?,?,?)', ('legado', m['id'], 0, nombre_historico, m['creado'], b'%PDF-1.4\nHistorico'))
        ruta = self.carpeta / self.nombre
        ruta.write_bytes(self.contenido)
        ticket = self.a.obtener(self.m['id'])['tickets'][2]
        self.assertTrue(ticket['comprobado'])
        self.assertFalse(ticket['respaldo_ticket']['historico'])
        self.assertEqual(self.a.documento_ticket(self.m['id'], 4), (self.nombre, self.contenido))
        paquete = compilar_auditoria(self.a.reporte_unidad('El Salvador'), {'anio': 2026, 'mes': 5, 'edp': 49}, auditoria=self.a)
        with ZipFile(BytesIO(paquete)) as z:
            self.assertTrue(any(n.endswith('/' + self.nombre) for n in z.namelist()))
            self.assertFalse(any(n.endswith('/' + nombre_historico) for n in z.namelist()))
            from pypdf import PdfReader
            pdf = z.read(next(n for n in z.namelist() if '/respaldos/' not in n))
            texto = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
            self.assertIn(self.nombre, texto)
            self.assertNotIn(nombre_historico, texto)
        ruta.unlink()
        self.assertEqual(self.a.documento_ticket(self.m['id'], 4)[0], nombre_historico)

    def test_andina_exige_el_mismo_formato_individual(self):
        carpeta = self.fuentes / 'Codelco Andina' / '2026 -05 EDP 55'
        carpeta.mkdir(parents=True)
        (carpeta / 'EDP.xlsx').write_bytes(excel_andina())
        fuente = next(f['id'] for f in self.a.catalogo()['fuentes'] if f['unidad'] == 'Andina')
        lista = self.a.listar_tickets(fuente)
        m = self.a.seleccionar({'fuente': fuente, 'filas': [2, 3, 4], 'sha256': lista['sha256']})
        cambio = {'muestra': m['id'], 'fila': 4, 'comprobado': True}
        (carpeta / '1.1 Retiro RINSP.pdf').write_bytes(self.contenido)
        with self.assertRaises(ValueError): self.a.modificar(cambio, 'comprobar')
        (carpeta / '000002_EDP55.pdf').write_bytes(self.contenido)
        self.assertTrue(self.a.modificar(cambio, 'comprobar')['tickets'][2]['comprobado'])
