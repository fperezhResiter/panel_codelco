"""Lectura anual y continuidad de comentarios, revisiones y respaldos al mover EDP."""
import tempfile
import unittest
from pathlib import Path

from app.auditoria import Auditoria
from app.auditoria_pdf import tickets_completados
from app.base_datos import actualizar_base_datos
from app.densidades import guardar_comentario, leer_densidades
from app.reportes import metadatos, ruta_fuente_canonica
from app.volumenes import leer_volumenes
from test_densidades import maestra, edp, edp_andina


class FuentesPorAnioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        self.fuentes = self.raiz / 'Fuentes'
        self.fuentes.mkdir()

    def mover_a_anio(self, carpeta):
        destino = carpeta.parent / '2026' / carpeta.name
        self.assertTrue(carpeta.resolve().is_relative_to(self.raiz.resolve()))
        self.assertTrue(destino.resolve().is_relative_to(self.raiz.resolve()))
        destino.parent.mkdir(exist_ok=True)
        carpeta.rename(destino)
        return destino

    def test_metadatos_con_mes_numerico_nombre_y_formato_anterior(self):
        for unidad in ('Andina', 'El Salvador'):
            for carpeta in ('2026/2026 -05 EDP 47', '2026/05 EDP 47', '2026/Mayo EDP 47', '2026 -05 EDP 47'):
                ruta = self.fuentes / ('Codelco ' + unidad) / carpeta / 'EDP.xlsx'
                datos = metadatos(ruta, self.fuentes)
                self.assertEqual((datos['unidad'], datos['anio'], datos['mes'], datos['edp']), (unidad, 2026, 5, 47))
        for carpeta in ('2026/2025 -05 EDP 47', '2026/13 EDP 47', '2026/EDP 47', '2026/Mayo EDP 47 EDP 48'):
            with self.assertRaises(ValueError):
                metadatos(self.fuentes / 'Codelco Andina' / carpeta / 'EDP.xlsx', self.fuentes)
        self.assertNotEqual(ruta_fuente_canonica('Codelco Andina/2025/05 EDP 47/EDP.xlsx'),
                            ruta_fuente_canonica('Codelco Andina/2026/05 EDP 47/EDP.xlsx'))

    def test_bd_densidades_volumen_y_comentarios_se_conservan(self):
        maestra(self.fuentes, [('Madera', 100, 300), ('Asimilable a RINP', 350, 600)])
        edp(self.fuentes)
        edp_andina(self.fuentes)
        bd = self.raiz / 'panel.sqlite3'
        antes = actualizar_base_datos(self.fuentes, bd)
        tickets = leer_densidades(bd, {'unidad': 'Andina'})['tickets']
        rojo = next(t for t in tickets if t['estado'] == 'no_coincide_mayor')
        guardar_comentario(bd, {'unidad': 'Andina', 'id': rojo['id'], 'comentario': 'Comentario antes del traslado'},
                           {'rol': 'auditor', 'correo': 'auditor@prueba.cl', 'permisos': ['revisar']})
        ids = [t['id'] for t in tickets]
        for unidad in ('Andina', 'El Salvador'):
            self.mover_a_anio(self.fuentes / ('Codelco ' + unidad) / '2026 -05 EDP 47')
        despues = actualizar_base_datos(self.fuentes, bd)
        self.assertEqual(len(antes['registros']), len(despues['registros']))
        self.assertEqual(sum(len(r['tickets']) for r in antes['registros']), sum(len(r['tickets']) for r in despues['registros']))
        self.assertTrue(all('/2026/' in r['archivo'] for r in despues['registros']))
        nuevos = leer_densidades(bd, {'unidad': 'Andina'})['tickets']
        self.assertEqual([t['id'] for t in nuevos], ids)
        self.assertEqual(next(t for t in nuevos if t['id'] == rojo['id'])['comentario'], 'Comentario antes del traslado')
        for unidad in ('Andina', 'El Salvador'):
            self.assertTrue(leer_volumenes(bd, {'unidad': unidad})['tickets'])

    def test_historial_respaldo_subida_y_deduplicacion_tras_el_traslado(self):
        edp(self.fuentes)
        carpeta = self.fuentes / 'Codelco El Salvador' / '2026 -05 EDP 47'
        (carpeta / '2.5a TICKET INTERNO (EDP 47).pdf').write_bytes(b'%PDF-1.4\nHistorico')
        a = Auditoria(self.fuentes, self.raiz / 'Auditoria')
        fuente = a.catalogo()['fuentes'][0]['id']
        lista = a.listar_tickets(fuente)
        m = a.seleccionar({'fuente': fuente, 'filas': [2, 3, 4], 'sha256': lista['sha256']})
        destino = self.mover_a_anio(carpeta)
        self.assertEqual(a.catalogo()['fuentes'][0]['id'], fuente)
        self.assertEqual(a.catalogo()['muestras'][0]['fuente'], fuente)
        self.assertEqual(a.documento_edp(m['id'])[1], b'%PDF-1.4\nHistorico')
        from test_auditoria import adjunto
        a.modificar({'muestra': m['id'], 'fila': 4, **adjunto('3_EDP47.pdf')}, 'adjuntar')
        self.assertTrue((destino / '3_EDP47.pdf').is_file())
        antigua = a.modificar({'muestra': m['id'], 'fila': 4, 'comprobado': True}, 'comprobar')
        nueva = a.seleccionar({'fuente': fuente, 'filas': [2, 3, 4], 'sha256': lista['sha256']})
        self.assertIn('/2026/', nueva['archivo'])
        nueva = a.modificar({'muestra': nueva['id'], 'fila': 4, 'comprobado': True}, 'comprobar')
        self.assertEqual(len(tickets_completados([antigua, nueva])), 1)
        self.assertEqual(a.documento_ticket(antigua['id'], 4), ('3_EDP47.pdf', b'%PDF-1.4\nRespaldo de prueba'))
