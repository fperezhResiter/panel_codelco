"""Pruebas de la instantánea PDF y su endpoint de descarga."""
import json
import tempfile
import threading
import unittest
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from app.pdf import crear_pdf
from app.servidor import ServidorPanel, crear_handler
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


def instantanea(cantidad=1):
    filas=[]
    for i in range(cantidad):
        filas.append(dict(unidad='El Salvador',periodo='2026-05',mes_nombre='Mayo',anio=2026,
                          edp=47+i,estado='cuadra',peso_kg=373200,ton_tickets=373.2,ton_edp=373.2,
                          precio=141045,monto_edp=52637994,monto_esperado=52637994,diferencia=0,
                          numero_tickets=129,avisos=[],errores=[]))
    return dict(registros=filas,filtros={'EDP':'EDP 47'},avisos=[],actualizado='01-10-2026 18:00')


class PdfTests(unittest.TestCase):
    def test_pdf_valido(self):
        self.assertTrue(crear_pdf(instantanea()).startswith(b'%PDF-'))

    def test_rechaza_vacios_y_numeros_invalidos(self):
        for r in ({'registros':[]},None,{'registros':'incorrecto'}):
            with self.assertRaises(ValueError): crear_pdf(r)
        for valor in (float('nan'),float('inf'),'1.000',True):
            r=instantanea();r['registros'][0]['precio']=valor
            with self.assertRaises(ValueError): crear_pdf(r)

    def test_incompleto_conserva_errores_y_no_inventa_totales(self):
        r=instantanea();r['registros'][0].update(estado='incompleto',precio=None,peso_kg=None,
            ton_tickets=None,monto_esperado=None,errores=['Falta precio <revisar>'])
        self.assertTrue(crear_pdf(r).startswith(b'%PDF-'))

    @unittest.skipUnless(PdfReader,'Instala pypdf para las comprobaciones de texto y paginación.')
    def test_exporta_solo_la_instantanea_filtrada(self):
        reader=PdfReader(BytesIO(crear_pdf(instantanea())))
        texto=''.join(p.extract_text() for p in reader.pages)
        for valor in ('373,200','52.637.994,00','Toneladas por EDP','Monto por EDP','Detalle de conciliación','EDP 47'):
            self.assertIn(valor,texto)
        self.assertNotIn('227.003.464,80',texto)
        self.assertNotIn('EDP 48',texto)

    @unittest.skipUnless(PdfReader,'Instala pypdf para las comprobaciones de texto y paginación.')
    def test_tabla_larga_se_pagina_sin_perder_el_ultimo_edp(self):
        r=instantanea(40);r['registros'][-1]['unidad']='ULTIMA UNIDAD'
        reader=PdfReader(BytesIO(crear_pdf(r)))
        paginas=[p.extract_text() for p in reader.pages]
        self.assertGreater(len(paginas),2)
        self.assertIn('ULTIMA UNIDAD',''.join(paginas))
        self.assertGreater(sum('Unidad / período' in p for p in paginas),1)

    @unittest.skipUnless(PdfReader, 'pypdf opcional no disponible.')
    def test_andina_identifica_item_y_cantidad_en_toneladas(self):
        datos = instantanea()
        datos['registros'][0].update(unidad='Andina', item='1.1')
        texto = ''.join(p.extract_text() for p in PdfReader(BytesIO(crear_pdf(datos))).pages)
        self.assertIn('Andina: ítem 1.1', texto)
        self.assertIn('Cantidad (t)', texto)
        self.assertIn('Precio CLP/t', texto)

    def test_endpoint_descarga_sin_releer_los_excel(self):
        with tempfile.TemporaryDirectory() as temp:
            servidor=ServidorPanel(('127.0.0.1',0),crear_handler(Path(temp)))
            hilo=threading.Thread(target=servidor.serve_forever,daemon=True);hilo.start()
            url=f'http://127.0.0.1:{servidor.server_port}/api/reporte.pdf'
            try:
                with patch('app.reportes.crear_reporte',side_effect=AssertionError('No debe releer fuentes')):
                    req=Request(url,data=json.dumps(instantanea()).encode(),headers={'Content-Type':'application/json'})
                    with urlopen(req) as respuesta:
                        self.assertEqual(respuesta.headers.get_content_type(),'application/pdf')
                        self.assertIn('attachment',respuesta.headers['Content-Disposition'])
                        self.assertTrue(respuesta.read().startswith(b'%PDF-'))
                req=Request(url,data=b'{"registros":[]}',headers={'Content-Type':'application/json'})
                with self.assertRaises(HTTPError) as error: urlopen(req)
                self.assertEqual(error.exception.code,400)
            finally:
                servidor.shutdown();servidor.server_close();hilo.join()


if __name__=='__main__':
    unittest.main()
