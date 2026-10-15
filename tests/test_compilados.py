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
from soporte_usuarios import crear_handler_administrador as crear_handler
from test_auditoria import excel, excel_andina, adjunto
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
            self.assertEqual(set(n for n in archivo.namelist() if '/respaldos/' not in n), {
                'el-salvador-mayo-2026-edp-47-panel-conciliacion.pdf',
                'andina-mayo-2026-edp-47-panel-conciliacion.pdf',
                'el-salvador-mayo-2025-edp-47-panel-conciliacion.pdf',
                'el-salvador-junio-2026-edp-47-panel-conciliacion.pdf',
                'el-salvador-mayo-2026-edp-48-panel-conciliacion.pdf'})
            texto = texto_pdf(archivo.read('el-salvador-mayo-2026-edp-47-panel-conciliacion.pdf'))
            self.assertIn('2 cuadran', texto)
            for nombre in [n for n in archivo.namelist() if '/respaldos/' not in n]:
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
            for nombre in [n for n in archivo.namelist() if '/respaldos/' not in n]:
                texto = texto_pdf(archivo.read(nombre))
                self.assertIn('Tickets: 2', texto)
                self.assertNotIn('Datos de BD actualizados', texto)
                self.assertNotIn('Andina', texto)
        _, contenido = self.descargar('/api/densidades/compilado.zip?unidad=Andina&anio=2026&mes=5&edp=47')
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertEqual(archivo.namelist(), ['andina-mayo-2026-edp-47-panel-densidades.pdf'])

    def test_auditoria_edp_reune_completados_sin_duplicar_filas_y_sin_fechas(self):
        fuente = self.revisiones[0]['fuente']
        lista = self.auditoria.listar_tickets(fuente)
        # Las primeras dos filas tienen el mismo número de ticket 0.
        confirmadas = []
        for fila, nombre in [(2, '0_EDP47.pdf'), (3, '0_EDP47.pdf'), (2, '0_EDP47.pdf')]:
            m = self.auditoria.seleccionar({'fuente': fuente, 'fila': fila, 'sha256': lista['sha256']})
            cambio = {'muestra': m['id'], 'fila': fila}
            self.auditoria.modificar({**cambio, **adjunto(nombre)}, 'adjuntar')
            confirmadas.append(self.auditoria.modificar({**cambio, 'comprobado': True}, 'comprobar'))
        headers, contenido = self.descargar('/api/auditoria/compilado.zip?unidad=El%20Salvador&anio=2026&mes=5')
        self.assertEqual(headers.get_content_type(), 'application/zip')
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertEqual([n for n in archivo.namelist() if '/respaldos/' not in n], ['2026/05-mayo/el-salvador-mayo-2026-edp-47-panel-auditoria-edp.pdf'])
            self.assertTrue(any(n.endswith('/0_EDP47.pdf') for n in archivo.namelist()))
            pdf = archivo.read(archivo.namelist()[0])
        texto = texto_pdf(pdf)
        for esperado in ('Mayo 2026 | EDP 47', 'Tickets revisados: 2', 'Campo adicional',
                         'Fila Excel 2', 'Fila Excel 3', '0_EDP47.pdf'):
            self.assertIn(esperado, texto)
        self.assertEqual(texto.count('COMPROBADO MANUALMENTE'), 2)
        for excluido in ('Generado:', 'Creada', 'Último cambio', 'Confirmado el:', 'Cargado:',
                         'PENDIENTE DE COMPROBACIÓN', 'EDP 48', 'Andina', '2025-05'):
            self.assertNotIn(excluido, texto)
        for m in confirmadas:
            self.assertNotIn(m['creado'], texto)
            self.assertNotIn(m['actualizado'], texto)
        # Ambas rutas PDF agrupan todas las revisiones del EDP, incluso partiendo de una antigua.
        for ruta in ['/api/auditoria/reporte.pdf?id=' + confirmadas[0]['id'],
                     '/api/auditoria/unidad.pdf?unidad=El%20Salvador&anio=2026&mes=5&edp=47']:
            headers, contenido = self.descargar(ruta)
            self.assertIn('el-salvador-mayo-2026-edp-47-panel-auditoria-edp.pdf', headers['Content-Disposition'])
            self.assertIn('Tickets revisados: 2', texto_pdf(contenido))
        for ruta in ['/api/auditoria/reporte.zip?id=' + confirmadas[0]['id'],
                     '/api/auditoria/unidad.zip?unidad=El%20Salvador&anio=2026&mes=5&edp=47']:
            headers, contenido = self.descargar(ruta)
            self.assertEqual(headers.get_content_type(), 'application/zip')
            with ZipFile(BytesIO(contenido)) as paquete:
                self.assertEqual(len(paquete.namelist()), 2)
                pdf = next(n for n in paquete.namelist() if '/respaldos/' not in n)
                respaldo = next(n for n in paquete.namelist() if n.endswith('/0_EDP47.pdf'))
                self.assertIn('Tickets revisados: 2', texto_pdf(paquete.read(pdf)))
                self.assertEqual(paquete.read(respaldo), b'%PDF-1.4\nRespaldo de prueba')
        with self.assertRaises(HTTPError) as error:
            self.descargar('/api/auditoria/unidad.pdf?unidad=El%20Salvador&anio=2026&mes=5&edp=48')
        self.assertEqual(error.exception.code, 400)

    def test_selecciones_vacias_no_descargan_zip_vacio(self):
        for ruta, datos in [('/api/conciliacion/compilado.zip', {'registros': []}),
                            ('/api/densidades/compilado.zip?edp=999', None),
                            ('/api/auditoria/compilado.zip?unidad=Andina&anio=2025', None)]:
            with self.subTest(ruta=ruta), self.assertRaises(HTTPError) as error:
                self.descargar(ruta, datos)
            self.assertEqual(error.exception.code, 400)

    def test_pdf_edp_andina_solo_confirmados_con_cantidad_en_toneladas(self):
        fuente = next(f for f in self.auditoria.catalogo()['fuentes'] if f['unidad'] == 'Andina')
        ruta = self.auditoria.fuentes / fuente['archivo']
        (ruta.parent / '0_EDP55.pdf').write_bytes(b'%PDF-1.4\nRespaldo Andina')
        lista = self.auditoria.listar_tickets(fuente['id'])
        m = self.auditoria.seleccionar({'fuente': fuente['id'], 'fila': 3, 'sha256': lista['sha256']})
        self.auditoria.modificar({'muestra': m['id'], 'fila': 3, 'comprobado': True}, 'comprobar')
        headers, contenido = self.descargar('/api/auditoria/unidad.pdf?unidad=Andina&anio=2026&mes=5&edp=55')
        self.assertIn('andina-mayo-2026-edp-55-panel-auditoria-edp.pdf', headers['Content-Disposition'])
        texto = texto_pdf(contenido)
        for esperado in ('Andina | Mayo 2026 | EDP 55', 'Tickets revisados: 1',
                         '0.2 t', '0_EDP55.pdf'):
            self.assertIn(esperado, texto)
        self.assertNotIn('El Salvador', texto)
        self.assertNotIn('Confirmado el:', texto)

    def test_compilado_por_filtro_organiza_anios_meses(self):
        fuentes = self.auditoria.catalogo()['fuentes']
        for fuente in fuentes:
            if fuente['unidad'] == 'El Salvador' and fuente['edp'] == 48:
                continue
            lista = self.auditoria.listar_tickets(fuente['id'])
            m = self.auditoria.seleccionar({'fuente': fuente['id'], 'fila': 3, 'sha256': lista['sha256']})
            cambio = {'muestra': m['id'], 'fila': 3}
            self.auditoria.modificar({**cambio, **adjunto(f'{m["tickets"][0]["ticket"]}_EDP{m["edp"]}.pdf')}, 'adjuntar')
            self.auditoria.modificar({**cambio, 'comprobado': True}, 'comprobar')
        ruta = '/api/auditoria/compilado.zip?unidad=El%20Salvador'
        headers, contenido = self.descargar(ruta)
        self.assertEqual(headers.get_content_type(), 'application/zip')
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertEqual(set(n for n in archivo.namelist() if '/respaldos/' not in n), {
                '2025/05-mayo/el-salvador-mayo-2025-edp-47-panel-auditoria-edp.pdf',
                '2026/05-mayo/el-salvador-mayo-2026-edp-47-panel-auditoria-edp.pdf'})
            for nombre in [n for n in archivo.namelist() if '/respaldos/' not in n]:
                texto = texto_pdf(archivo.read(nombre))
                self.assertIn('Tickets revisados: 1', texto)
                self.assertNotIn('Andina', texto)
                self.assertNotIn('EDP 48', texto)
        _, contenido = self.descargar(ruta + '&anio=2026&mes=5&edp=47&estado=completo')
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertEqual([n for n in archivo.namelist() if '/respaldos/' not in n],
                             ['2026/05-mayo/el-salvador-mayo-2026-edp-47-panel-auditoria-edp.pdf'])
        with self.assertRaises(HTTPError) as error:
            self.descargar(ruta + '&alcance=unidad&anio=2026&edp=48&estado=sin_revision')
        self.assertEqual(error.exception.code, 400)
        _, contenido = self.descargar('/api/auditoria/compilado.zip?unidad=Andina&alcance=unidad')
        with ZipFile(BytesIO(contenido)) as archivo:
            self.assertEqual([n for n in archivo.namelist() if '/respaldos/' not in n], ['2026/05-mayo/andina-mayo-2026-edp-55-panel-auditoria-edp.pdf'])

    def test_trimestre_sin_anio_compila_meses_de_todos_los_anios(self):
        esperados = set()
        for anio, mes in [(2025, 1), (2025, 2), (2025, 3), (2026, 1), (2026, 2), (2026, 3), (2026, 4)]:
            numero = mes + 60
            carpeta = self.auditoria.fuentes / 'Codelco Andina' / str(anio) / f'{anio} -{mes:02d} EDP {numero}'
            carpeta.mkdir(parents=True)
            (carpeta / 'EDP.xlsx').write_bytes(excel_andina())
            (carpeta / f'0_EDP{numero}.pdf').write_bytes(b'%PDF-1.4\nRespaldo Andina')
            fuente = next(f for f in self.auditoria.catalogo()['fuentes']
                          if f['unidad'] == 'Andina' and f['anio'] == anio and f['mes'] == mes)
            lista = self.auditoria.listar_tickets(fuente['id'])
            muestra = self.auditoria.seleccionar({'fuente': fuente['id'], 'fila': 3, 'sha256': lista['sha256']})
            self.auditoria.modificar({'muestra': muestra['id'], 'fila': 3, 'comprobado': True}, 'comprobar')
            if mes <= 3:
                esperados.add(f'{anio}/{mes:02d}-' + ('enero', 'febrero', 'marzo')[mes - 1])
        ruta = '/api/auditoria/compilado.zip?unidad=Andina&trimestre=1'
        _, contenido = self.descargar(ruta)
        with ZipFile(BytesIO(contenido)) as archivo:
            reportes = [n for n in archivo.namelist() if '/respaldos/' not in n]
            self.assertEqual(len(reportes), 6)
            self.assertEqual({'/'.join(n.split('/')[:2]) for n in reportes}, esperados)
            self.assertEqual(len([n for n in archivo.namelist() if '/respaldos/' in n]), 6)
        _, contenido = self.descargar(ruta + '&anio=2026')
        with ZipFile(BytesIO(contenido)) as archivo:
            reportes = [n for n in archivo.namelist() if '/respaldos/' not in n]
            self.assertEqual(len(reportes), 3)
            self.assertTrue(all(n.startswith('2026/') for n in reportes))
        with self.assertRaises(HTTPError) as error:
            self.descargar('/api/auditoria/compilado.zip?unidad=Andina&trimestre=5')
        self.assertEqual(error.exception.code, 400)

    def test_pdf_individual_y_botones_publicados(self):
        _, contenido = self.descargar('/api/reporte.pdf', instantanea())
        self.assertNotIn('Última lectura', texto_pdf(contenido))
        _, contenido = self.descargar('/api/densidades/reporte.pdf?unidad=Andina')
        self.assertNotIn('Datos de BD actualizados', texto_pdf(contenido))
        for pagina in ('Panel_Conciliacion.html', 'Panel_Densidades.html', 'Panel_Auditoria_EDP.html', 'Panel_Volumenes.html'):
            _, contenido = self.descargar('/web/pages/' + pagina)
            self.assertIn(b'id="descargar-compilado"', contenido)
            self.assertIn(b'Descargar compilado por filtro', contenido)


if __name__ == '__main__':
    unittest.main()
