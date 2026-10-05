"""Descargas reales: separación por unidad/período/EDP y alcance de los filtros."""
import copy
import json
import tempfile
import threading
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile
from unittest.mock import patch
from pypdf import PdfReader
from app.auditoria import Auditoria
from app.base_datos import actualizar_base_datos
from app.servidor import ServidorPanel, crear_handler
from test_auditoria import excel, excel_andina
from test_densidades import maestra, edp, edp_andina
from test_pdf import instantanea


def texto_pdf(contenido):
    return '\n'.join(p.extract_text() for p in PdfReader(BytesIO(contenido)).pages)


class CompiladosTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        fuentes = self.raiz / 'Fuentes'
        for unidad, periodo, numero in [('El Salvador', '2026 -05', 47), ('El Salvador', '2026 -05', 48),
                                       ('El Salvador', '2025 -05', 47), ('Andina', '2026 -05', 55)]:
            carpeta = fuentes / ('Codelco ' + unidad) / f'{periodo} EDP {numero}'
            carpeta.mkdir(parents=True)
            (carpeta / 'EDP.xlsx').write_bytes(excel_andina() if unidad == 'Andina' else excel())
        self.auditoria = Auditoria(fuentes, self.raiz / 'Auditoria')
        fuente = next(f for f in self.auditoria.catalogo()['fuentes']
                      if f['unidad'] == 'El Salvador' and f['anio'] == 2026 and f['edp'] == 47)
        self.revisiones = [self.auditoria.sortear({'fuente': fuente['id'], 'cantidad': 3}) for _ in range(2)]
        densidades = self.raiz / 'Densidades'
        densidades.mkdir()
        maestra(densidades, [('Madera', 100, 300), ('Asimilable a RINP', 350, 600)])
        edp(densidades)
        edp_andina(densidades)
        original = densidades / 'Codelco El Salvador' / '2026 -05 EDP 47' / 'EDP.xlsx'
        for periodo in ('2025 -05 EDP 47', '2026 -06 EDP 48'):
            carpeta = original.parent.parent / periodo
            carpeta.mkdir()
            (carpeta / 'EDP.xlsx').write_bytes(original.read_bytes())
        ruta_bd = self.raiz / 'densidades.sqlite3'
        actualizar_base_datos(densidades, ruta_bd)
        self.servidor = ServidorPanel(('127.0.0.1', 0), crear_handler(fuentes, self.raiz / 'Auditoria', ruta_bd))
        self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.hilo.start()
        self.addCleanup(self.cerrar_servidor)
        self.base = f'http://127.0.0.1:{self.servidor.server_port}'

    def cerrar_servidor(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.hilo.join()

    def descargar(self, ruta, datos=None):
        solicitud = Request(self.base + ruta, data=json.dumps(datos).encode() if datos is not None else None,
                            headers={'Content-Type': 'application/json'} if datos is not None else {})
        with urlopen(solicitud) as respuesta:
            return respuesta.headers, respuesta.read()

    def test_conciliacion_separa_unidad_mes_anio_edp_y_agrupa_duplicados(self):
        datos = instantanea()
        base = datos['registros'][0]
        datos['registros'] = [base, copy.deepcopy(base), {**base, 'unidad': 'Andina'},
                              {**base, 'anio': 2025, 'periodo': '2025-05'},
                              {**base, 'periodo': '2026-06', 'mes_nombre': 'Junio'}, {**base, 'edp': 48}]
        with patch('app.reportes.crear_reporte', side_effect=AssertionError('No debe releer Excel')):
            headers, contenido = self.descargar('/api/conciliacion/compilado.zip', datos)
        self.assertEqual(headers.get_content_type(), 'application/zip')
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertEqual(set(archivo.namelist()), {
                'el-salvador-mayo-2026-edp-47-panel-conciliacion.pdf',
                'andina-mayo-2026-edp-47-panel-conciliacion.pdf',
                'el-salvador-mayo-2025-edp-47-panel-conciliacion.pdf',
                'el-salvador-junio-2026-edp-47-panel-conciliacion.pdf',
                'el-salvador-mayo-2026-edp-48-panel-conciliacion.pdf'})
            texto = texto_pdf(archivo.read('el-salvador-mayo-2026-edp-47-panel-conciliacion.pdf'))
            self.assertIn('2 cuadran', texto)
            for nombre in archivo.namelist():
                texto = texto_pdf(archivo.read(nombre))
                self.assertNotIn('Última lectura', texto)
                self.assertNotIn(datos['actualizado'], texto)

    def test_densidades_separa_periodos_y_conserva_filtros_de_tickets(self):
        with patch('app.densidades.FuenteExcel', side_effect=AssertionError('No debe leer Excel')):
            headers, contenido = self.descargar('/api/densidades/compilado.zip?unidad=El%20Salvador&estado=coincide')
        self.assertEqual(headers.get_content_type(), 'application/zip')
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertEqual(len(archivo.namelist()), 3)
            self.assertIn('el-salvador-mayo-2025-edp-47-panel-densidades.pdf', archivo.namelist())
            for nombre in archivo.namelist():
                texto = texto_pdf(archivo.read(nombre))
                self.assertIn('Tickets: 2', texto)
                self.assertNotIn('Datos de BD actualizados', texto)
                self.assertNotIn('Andina', texto)
        _, contenido = self.descargar('/api/densidades/compilado.zip?unidad=Andina&anio=2026&mes=5&edp=47')
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertEqual(archivo.namelist(), ['andina-mayo-2026-edp-47-panel-densidades.pdf'])

    def test_auditoria_un_pdf_por_edp_con_historial_y_sin_revision(self):
        headers, contenido = self.descargar('/api/auditoria/compilado.zip?unidad=El%20Salvador&anio=2026&mes=5')
        self.assertEqual(headers.get_content_type(), 'application/zip')
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertEqual(set(archivo.namelist()), {'el-salvador-mayo-2026-edp-47-panel-auditoria-edp.pdf',
                                                     'el-salvador-mayo-2026-edp-48-panel-auditoria-edp.pdf'})
            texto = texto_pdf(archivo.read('el-salvador-mayo-2026-edp-47-panel-auditoria-edp.pdf'))
            for muestra in self.revisiones:
                self.assertIn(muestra['id'], texto)
            self.assertIn('Mayo 2026 | EDP 47', texto)
            texto = texto_pdf(archivo.read('el-salvador-mayo-2026-edp-48-panel-auditoria-edp.pdf'))
            self.assertIn('Sin revisiones guardadas', texto)
            for muestra in self.revisiones:
                self.assertNotIn(muestra['id'], texto)

    def test_selecciones_vacias_no_descargan_zip_vacio(self):
        for ruta, datos in [('/api/conciliacion/compilado.zip', {'registros': []}),
                            ('/api/densidades/compilado.zip?edp=999', None),
                            ('/api/auditoria/compilado.zip?unidad=Andina&anio=2025', None)]:
            with self.subTest(ruta=ruta), self.assertRaises(HTTPError) as error:
                self.descargar(ruta, datos)
            self.assertEqual(error.exception.code, 400)

    def test_pdf_individual_y_botones_publicados(self):
        _, contenido = self.descargar('/api/reporte.pdf', instantanea())
        self.assertNotIn('Última lectura', texto_pdf(contenido))
        _, contenido = self.descargar('/api/densidades/reporte.pdf?unidad=Andina')
        self.assertNotIn('Datos de BD actualizados', texto_pdf(contenido))
        for pagina in ('Panel_Conciliacion.html', 'Panel_Densidades.html', 'Panel_Auditoria_EDP.html'):
            _, contenido = self.descargar('/web/pages/' + pagina)
            self.assertIn(b'id="descargar-compilado"', contenido)


if __name__ == '__main__':
    unittest.main()
