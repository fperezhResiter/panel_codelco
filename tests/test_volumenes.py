"""Descargas PDF y compilado de la selección filtrada de volumen."""
import tempfile
import threading
import unittest
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError
from zipfile import ZipFile
from pypdf import PdfReader
from app.base_datos import actualizar_base_datos
from app.servidor import ServidorPanel, crear_handler
from soporte_usuarios import crear_handler_administrador as crear_handler
from app.volumenes import clasificar, leer_volumenes, resumen
from test_densidades import maestra, edp, edp_andina


def texto_pdf(contenido):
    return '\n'.join(p.extract_text() for p in PdfReader(BytesIO(contenido)).pages)


class VolumenesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        fuentes = self.raiz / 'Fuentes'
        fuentes.mkdir()
        maestra(fuentes, [('Madera', 100, 300), ('Asimilable a RINP', 350, 600)])
        edp(fuentes)
        edp_andina(fuentes)
        original = fuentes / 'Codelco El Salvador' / '2026 -05 EDP 47' / 'EDP.xlsx'
        for periodo in ('2025 -05 EDP 47', '2026 -06 EDP 48'):
            carpeta = original.parent.parent / periodo
            carpeta.mkdir()
            (carpeta / 'EDP.xlsx').write_bytes(original.read_bytes())
        self.bd = self.raiz / 'panel.sqlite3'
        actualizar_base_datos(fuentes, self.bd)
        self.servidor = ServidorPanel(('127.0.0.1', 0), crear_handler(fuentes, self.raiz / 'Auditoria', self.bd))
        self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.hilo.start()
        self.addCleanup(self.cerrar)
        self.base = f'http://127.0.0.1:{self.servidor.server_port}'

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.hilo.join()

    def descargar(self, ruta):
        with urlopen(self.base + ruta) as respuesta:
            return respuesta.headers, respuesta.read()

    def test_limites_y_porcentajes_incluyen_sin_volumen(self):
        for valor, esperado in [(9.9999, 'menor_10'), (10, '10_20'), (19.9999, '10_20'),
                                (20, '20_30'), (30, '20_30'), (30.0001, 'mayor_30'), (None, 'sin_volumen')]:
            self.assertEqual(clasificar(valor), esperado)
        grupos = resumen([{'volumen_m3': 10}, {'volumen_m3': 20}, {'volumen_m3': None}])
        self.assertAlmostEqual(sum(g['porcentaje'] for g in grupos), 100)
        self.assertEqual(sum(g['volumen_m3'] or 0 for g in grupos), 30)

    def test_pdf_respeta_filtros_combinados_y_tickets_cero(self):
        p = {'unidad':'El Salvador', 'anio':'2026', 'trimestre':'2', 'mes':'5', 'edp':'47',
             'residuo':'Madera', 'estado':'coincide', 'volumen_tipo':'20', 'buscar':'0', 'tramo_volumen':'20_30'}
        datos = leer_volumenes(self.bd, p)
        self.assertEqual([t['volumen_m3'] for t in datos['tickets']], [20])
        from urllib.parse import urlencode
        headers, contenido = self.descargar('/api/volumenes/reporte.pdf?' + urlencode(p))
        self.assertEqual(headers.get_content_type(), 'application/pdf')
        self.assertIn('salvador-2026-05-edp-47-volumen.pdf', headers['Content-Disposition'])
        texto = texto_pdf(contenido)
        for esperado in ('Distribución de volumen', 'Tickets: 1', '20,00 m³', '100,0%', 'tramo_volumen', '0 /'):
            self.assertIn(esperado, texto)
        self.assertNotIn('(sin ID)', texto)
        self.assertNotIn('Chequeo de densidades', texto)
        self.assertNotIn('Andina', texto)

    def test_compilado_separa_periodos_y_respeta_tramo(self):
        headers, contenido = self.descargar('/api/volumenes/compilado.zip?unidad=El%20Salvador&tramo_volumen=20_30')
        self.assertEqual(headers.get_content_type(), 'application/zip')
        self.assertLess(len(headers['Content-Disposition'].split("UTF-8''")[1]), 80)
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertTrue(all(len(n) <= 40 and '/' not in n for n in archivo.namelist()))
            self.assertIsNone(archivo.testzip())
            archivo.extractall(self.raiz / 'extraidos')
            self.assertEqual(set(archivo.namelist()), {
                'salvador-2025-05-edp-47-volumen.pdf',
                'salvador-2026-05-edp-47-volumen.pdf',
                'salvador-2026-06-edp-48-volumen.pdf'})
            for nombre in archivo.namelist():
                texto = texto_pdf(archivo.read(nombre))
                self.assertIn('Tickets: 1', texto)
                self.assertIn('tramo_volumen: 20 a 30 m³', texto)
        _, contenido = self.descargar('/api/volumenes/compilado.zip?unidad=Andina&anio=2026&mes=5&edp=47')
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertEqual(archivo.namelist(), ['andina-2026-05-edp-47-volumen.pdf'])

    def test_sin_datos_o_tramo_invalido_devuelve_error(self):
        for consulta in ('tramo_volumen=20', 'edp=999'):
            with self.assertRaises(HTTPError) as error:
                self.descargar('/api/volumenes/reporte.pdf?' + consulta)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()

    def test_botones_publicados_y_csv_disponible(self):
        _, contenido = self.descargar('/web/pages/Panel_Volumenes.html')
        html = contenido.decode()
        self.assertIn('id="generar-pdf" type="button"', html)
        self.assertIn('id="descargar-compilado" type="button"', html)
        self.assertIn('id="exportar"', html)


if __name__ == '__main__':
    unittest.main()
