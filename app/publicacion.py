"""Publicación local de consulta; no expone cuentas ni requiere HTTP al leerla."""
import base64
import hashlib
import json
import mimetypes
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .base_datos import leer_reporte
from .densidades import BANDAS_POR_UNIDAD, leer_densidades
from .auditoria import crear_csv
from .auditoria_compartida import AuditoriaCompartida
from .auditoria_pdf import crear_pdf_unidad, tickets_completados
from .descargas import nombre_pdf
from .compilados import crear_zip

BASE = Path(__file__).resolve().parent.parent


def publicar(fuentes, bd, destino=None, auditorias=None):
    destino = Path(destino or BASE / 'web' / 'publicado' / 'datos.js')
    auditoria = AuditoriaCompartida(fuentes, auditorias or BASE / 'Datos' / 'Auditoria')
    catalogo = auditoria.catalogo()
    if catalogo.get('conexion_bd', {}).get('pendientes'):
        raise ValueError('Hay cambios de auditoría pendientes de sincronización. Espera a SharePoint y vuelve a publicar.')
    muestras = {m['id']: auditoria.obtener(m['id']) for m in catalogo['muestras']}
    archivos, reportes = {}, []

    def archivo(nombre, contenido, tipo):
        huella = hashlib.sha256(contenido).hexdigest()
        llave = huella + '-' + hashlib.sha256(nombre.encode('utf-8')).hexdigest()[:16]
        extension = Path(nombre).suffix or '.bin'
        carpeta = destino.parent / 'archivos'
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / (huella + extension)
        if not ruta.exists():
            descriptor, temporal = tempfile.mkstemp(dir=carpeta, suffix='.tmp')
            try:
                with os.fdopen(descriptor, 'wb') as salida:
                    salida.write(contenido)
                os.replace(temporal, ruta)
            finally:
                if os.path.exists(temporal):
                    os.unlink(temporal)
        archivos[llave] = {'nombre': nombre, 'tipo': tipo, 'ruta': 'archivos/' + ruta.name}
        return llave

    for muestra in muestras.values():
        muestra['csv_publicado'] = archivo('auditoria-' + muestra['id'][:8] + '.csv', crear_csv(muestra), 'text/csv; charset=utf-8')
        for ticket in muestra['tickets']:
            if ticket.get('respaldo_ticket'):
                nombre, contenido = auditoria.documento_ticket(muestra['id'], ticket['fila'])
                ticket['respaldo_publicado'] = archivo(nombre, contenido, mimetypes.guess_type(nombre)[0] or 'application/octet-stream')
    for unidad in catalogo['unidades']:
        registros = [r for r in catalogo['estados_pago'] if r['unidad'] == unidad]
        for registro in registros:
            revisiones = [m for m in muestras.values() if m['unidad'] == unidad and m['periodo'] == registro['periodo'] and str(m['edp']) == str(registro['edp'])]
            if not tickets_completados(revisiones):
                continue
            reporte = {'unidad': unidad, 'estados_pago': [registro], 'muestras': revisiones}
            nombre = nombre_pdf('auditoria-edp', [registro], unidad=unidad)
            contenido_pdf = crear_pdf_unidad(reporte, invariante=True)
            pdf = archivo(nombre, contenido_pdf, 'application/pdf')
            documentos = auditoria.archivos_respaldo(reporte)
            respaldos = [archivo(n, c, mimetypes.guess_type(n)[0] or 'application/octet-stream') for n, c in documentos]
            carpeta = nombre.removesuffix('.pdf')
            zip_id = archivo(carpeta + '.zip', crear_zip([(nombre, contenido_pdf),
                              *((carpeta + '/' + n, c) for n, c in documentos)], estable=True), 'application/zip')
            reportes.append({'registro': registro, 'pdf': pdf, 'zip': zip_id, 'respaldos': respaldos})
    datos = {'version': 1, 'actualizado': datetime.now(timezone.utc).isoformat(),
             'conciliacion': leer_reporte(bd),
             'densidades': {u: leer_densidades(bd, {'unidad': u}) for u in BANDAS_POR_UNIDAD},
             'auditoria': catalogo, 'muestras': muestras, 'archivos': archivos, 'reportes_auditoria': reportes,
             'imagenes': {n: base64.b64encode((BASE / 'web' / 'img' / n).read_bytes()).decode('ascii')
                          for n in ('logo_sin_fondo_resiter.png', 'logo_sin_fondo_codelco.png')}}
    # Una sola sustitución publica datos y descargas coherentes. Si falla, queda la publicación anterior.
    contenido = 'window.PanelPublicado = ' + json.dumps(datos, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + ';\n'
    destino.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=destino.parent, suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as salida:
            salida.write(contenido)
        os.replace(temporal, destino)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)
    return datos


if __name__ == '__main__':
    publicar(BASE / 'Fuentes', BASE / 'Datos' / 'conciliacion.sqlite3')
