"""Muestras de EDP y respaldos persistentes. La conformidad es siempre manual."""
import base64
import csv
import hashlib
import json
import re
import secrets
import sqlite3
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from openpyxl.utils.cell import get_column_letter
from .excel import FuenteExcel, clave
from .reportes import MESES, UNIDADES, PATRON_RESIDUOS, limites_tickets, metadatos, fila_plantilla_ticket

MAX_ARCHIVO = 30 * 1024 * 1024
MAX_SOLICITUD = ((MAX_ARCHIVO + 2) // 3) * 4 + 65536
EXT_DOCUMENTOS = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.tif', '.tiff', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.txt'}


def ahora():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def texto(valor):
    if valor is None:
        return ''
    if isinstance(valor, (datetime, date)):
        return valor.isoformat(sep=' ') if isinstance(valor, datetime) else valor.isoformat()
    return str(valor)


def nombre_respaldo_edp(unidad):
    return '1.1 Retiro RINSP.pdf' if unidad == 'Andina' else '2.5a TICKET INTERNO.pdf'


def leer_excel(contenido, unidad=None):
    # Los límites se revisan antes de descomprimir el libro.
    try:
        with ZipFile(BytesIO(contenido)) as archivo:
            if sum(x.file_size for x in archivo.infolist()) > 150 * 1024 * 1024:
                raise ValueError('El Excel descomprimido supera los 150 MB permitidos.')
    except BadZipFile as exc:
        raise ValueError('El archivo no es un Excel .xlsx o .xlsm válido.') from exc
    libro = FuenteExcel(BytesIO(contenido))
    try:
        andina = unidad == 'Andina'
        hoja = libro.hoja(r'11' if andina else PATRON_RESIDUOS)
        formulas = libro.formulas[hoja.title]
        inicio, fin, col_peso, col_ticket, tabla = limites_tickets(hoja, andina, formulas)
        col_fecha = next((c.column for c in hoja[inicio] if clave(c.value) == 'FECHA'), None)
        columnas = [c for c in range(1, hoja.max_column + 1)
                    if hoja.cell(inicio, c).value is not None or
                    any(hoja.cell(f, c).value is not None for f in range(inicio + 1, fin + 1))]
        campos = [{'columna': get_column_letter(c),
                   'nombre': texto(hoja.cell(inicio, c).value) or 'Sin encabezado'} for c in columnas]
        tickets, avisos = [], []
        for fila in range(inicio + 1, fin + 1):
            if andina and fila_plantilla_ticket(hoja, formulas, fila, col_ticket, col_peso, col_fecha):
                continue
            if not any(hoja.cell(fila, c).value is not None or
                       libro.formulas[hoja.title].cell(fila, c).value is not None for c in columnas):
                continue
            identificador = texto(hoja.cell(fila, col_ticket).value)
            valores = []
            for c, campo in zip(columnas, campos):
                celda = hoja.cell(fila, c)
                original = libro.formulas[hoja.title].cell(fila, c)
                valor = texto(celda.value)
                # Mantener ceros iniciales en identificadores formateados como 000000.
                if c == col_ticket and isinstance(celda.value, int) and re.fullmatch('0+', celda.number_format):
                    valor = str(celda.value).zfill(len(celda.number_format))
                    identificador = valor
                formula = original.value if original.data_type == 'f' else None
                valores.append({**campo, **({'unidad': 't'} if andina and c == col_peso else {}),
                                'valor': valor, 'celda': celda.coordinate, 'formula': formula,
                                'sin_resultado': bool(formula and celda.value is None)})
            tickets.append({'fila': fila, 'ticket': identificador, 'campos': valores})
        if not tickets:
            raise ValueError(f'La hoja {hoja.title} no contiene tickets.')
        ids = Counter(t['ticket'] for t in tickets)
        if any(n > 1 for k, n in ids.items() if k):
            avisos.append('Hay números de ticket repetidos. El sorteo distingue cada registro por su fila Excel.')
        if '' in ids:
            avisos.append('Hay filas sin número de ticket; permanecen en la población para revisión manual.')
        if any(c['sin_resultado'] for t in tickets for c in t['campos']):
            avisos.append('Hay fórmulas sin resultado guardado; se muestran como pendientes de recalcular en Excel.')
        return {'hoja': hoja.title, 'tabla': tabla, 'item': '1.1' if andina else '2.5.a',
                'tickets': tickets, 'avisos': avisos,
                'sha256': hashlib.sha256(contenido).hexdigest()}
    finally:
        libro.cerrar()


def decodificar(datos, extensiones):
    nombre = datos.get('nombre', '')
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre) > 240 or '/' in nombre or '\\' in nombre or any(ord(c) < 32 for c in nombre):
        raise ValueError('Nombre de archivo inválido.')
    if Path(nombre).suffix.lower() not in extensiones:
        raise ValueError('Formato de archivo no admitido.')
    try:
        contenido = base64.b64decode(datos.get('contenido', ''), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError('No se pudo leer el archivo adjunto.') from exc
    if not 0 < len(contenido) <= MAX_ARCHIVO:
        raise ValueError('Cada archivo debe contener datos y pesar como máximo 30 MB.')
    return nombre, contenido


class Auditoria:
    def __init__(self, fuentes, carpeta):
        self.fuentes = Path(fuentes)
        self.carpeta = Path(carpeta)

    @contextmanager
    def conexion(self):
        self.carpeta.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.carpeta / 'auditoria.sqlite3', timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS fuentes (id TEXT PRIMARY KEY, datos TEXT NOT NULL, contenido BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS muestras (id TEXT PRIMARY KEY, fuente TEXT NOT NULL, datos TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documentos (id TEXT PRIMARY KEY, muestra TEXT NOT NULL,
                    fila INTEGER NOT NULL, nombre TEXT NOT NULL, creado TEXT NOT NULL, contenido BLOB NOT NULL);
            ''')
            with db:
                yield db
        finally:
            db.close()

    def catalogo(self):
        fuentes, avisos = [], []
        if self.fuentes.is_dir():
            for ruta in sorted(self.fuentes.rglob('*')):
                if not ruta.is_file() or ruta.name.startswith('~$') or ruta.suffix.lower() not in ('.xlsx', '.xlsm') or ruta.parent == self.fuentes:
                    continue
                relativa = ruta.relative_to(self.fuentes).as_posix()
                try:
                    datos = metadatos(ruta, self.fuentes)
                    fuentes.append({**datos, 'id': 'local-' + hashlib.sha256(relativa.encode()).hexdigest(),
                                    'archivo': relativa, 'nombre': ruta.name, 'origen': 'Fuentes'})
                except ValueError as exc:
                    avisos.append(f'{relativa}: {exc}')
        with self.conexion() as db:
            fuentes.extend(json.loads(r['datos']) for r in db.execute('SELECT datos FROM fuentes ORDER BY rowid'))
            muestras = [json.loads(r['datos']) for r in db.execute('SELECT datos FROM muestras ORDER BY rowid DESC')]
        resumen = [{k: m[k] for k in ('id', 'fuente', 'creado', 'unidad', 'anio', 'mes', 'periodo', 'edp', 'archivo')}
                   | {'cantidad': len(m['tickets']), 'comprobados': sum(t['comprobado'] for t in m['tickets'])} for m in muestras]
        return {'fuentes': fuentes, 'muestras': resumen, 'avisos': avisos, 'unidades': list(UNIDADES)}

    def importar(self, datos):
        nombre, contenido = decodificar(datos, {'.xlsx', '.xlsm'})
        unidad = datos.get('unidad')
        anio, mes = datos.get('anio'), datos.get('mes')
        edp = datos.get('edp')
        if unidad not in UNIDADES or type(anio) is not int or not 2000 <= anio <= 2100 or type(mes) is not int or not 1 <= mes <= 12:
            raise ValueError('Selecciona unidad, año y mes válidos para el Excel.')
        if type(edp) is not int or edp < 0:
            raise ValueError('Indica el número de EDP.')
        libro = leer_excel(contenido, unidad)
        identificador = 'carga-' + hashlib.sha256(f'{unidad}|{anio}|{mes}|{edp}|{libro["sha256"]}'.encode()).hexdigest()
        fuente = {'id': identificador, 'unidad': unidad, 'anio': anio, 'mes': mes, 'mes_nombre': MESES[mes],
                  'periodo': f'{anio}-{mes:02d}', 'edp': edp, 'nombre': nombre, 'archivo': nombre, 'origen': 'Cargado'}
        with self.conexion() as db:
            db.execute('INSERT OR IGNORE INTO fuentes VALUES (?,?,?)', (identificador, json.dumps(fuente), contenido))
        return fuente

    def obtener(self, identificador, db=None):
        if db is None:
            with self.conexion() as conexion:
                return self.obtener(identificador, conexion)
        fila = db.execute('SELECT datos FROM muestras WHERE id=?', (identificador,)).fetchone()
        if fila is None:
            raise ValueError('No se encontró la muestra seleccionada.')
        muestra = json.loads(fila['datos'])
        for ticket in muestra['tickets']:
            ticket['documentos'] = [dict(r) for r in db.execute(
                'SELECT id,nombre,creado,length(contenido) AS bytes FROM documentos WHERE muestra=? AND fila=? ORDER BY rowid',
                (identificador, ticket['fila']))]
        muestra['respaldo_edp'] = self.respaldo_edp(muestra, db)
        return muestra

    def respaldo_edp(self, muestra, db):
        """Un PDF común del mismo EDP habilita la comprobación, nunca la marca."""
        guardado = db.execute('SELECT id,nombre,creado,length(contenido) AS bytes FROM documentos '
                              'WHERE muestra=? AND fila=0 ORDER BY rowid LIMIT 1', (muestra['id'],)).fetchone()
        if guardado:
            return {**dict(guardado), 'guardado': True}
        if muestra.get('origen') != 'Fuentes':
            return None
        carpeta = (self.fuentes / muestra['archivo']).resolve().parent
        raiz = self.fuentes.resolve()
        if not carpeta.is_relative_to(raiz) or not carpeta.is_dir():
            return None
        nombres = {'11RETIRORINSP', '11RETIRORINP'} if muestra['unidad'] == 'Andina' else {'25ATICKETINTERNO'}
        for ruta in sorted(carpeta.iterdir()):
            if (ruta.suffix.lower() == '.pdf' and clave(ruta.stem) in nombres
                    and ruta.resolve().is_relative_to(carpeta) and ruta.is_file() and ruta.stat().st_size > 0):
                return {'nombre': ruta.name, 'archivo': ruta.relative_to(raiz).as_posix(),
                        'bytes': ruta.stat().st_size, 'guardado': False}
        return None

    def leer_respaldo_edp(self, muestra, db):
        respaldo = self.respaldo_edp(muestra, db)
        if not respaldo:
            nombre = nombre_respaldo_edp(muestra['unidad'])
            raise ValueError(f'No se encuentra el PDF {nombre} en la carpeta de este EDP. Actualiza la revisión o adjunta un respaldo.')
        if respaldo['guardado']:
            fila = db.execute('SELECT contenido FROM documentos WHERE id=?', (respaldo['id'],)).fetchone()
            return respaldo['nombre'], fila[0]
        ruta = (self.fuentes / respaldo['archivo']).resolve()
        carpeta = (self.fuentes / muestra['archivo']).resolve().parent
        if not ruta.is_relative_to(carpeta) or not ruta.is_relative_to(self.fuentes.resolve()):
            raise ValueError('El respaldo debe pertenecer a la carpeta del EDP.')
        contenido = ruta.read_bytes()
        if not contenido:
            raise ValueError('El PDF del EDP está vacío. Adjunta un respaldo o revisa el archivo.')
        return respaldo['nombre'], contenido

    def documento_edp(self, identificador):
        with self.conexion() as db:
            return self.leer_respaldo_edp(self.obtener(identificador, db), db)

    def guardar(self, db, muestra):
        muestra['actualizado'] = ahora()
        db.execute('UPDATE muestras SET datos=? WHERE id=?', (json.dumps(muestra, ensure_ascii=False), muestra['id']))

    def leer_fuente(self, identificador):
        fuente = next((f for f in self.catalogo()['fuentes'] if f['id'] == identificador), None)
        if fuente is None:
            raise ValueError('Selecciona un Excel EDP disponible.')
        if fuente['origen'] == 'Fuentes':
            ruta = (self.fuentes / fuente['archivo']).resolve()
            if not ruta.is_relative_to(self.fuentes.resolve()):
                raise ValueError('Ruta de fuente inválida.')
            if ruta.stat().st_size > MAX_ARCHIVO:
                raise ValueError('El Excel supera los 30 MB permitidos.')
            contenido = ruta.read_bytes()
        else:
            with self.conexion() as db:
                contenido = db.execute('SELECT contenido FROM fuentes WHERE id=?', (fuente['id'],)).fetchone()[0]
        return fuente, leer_excel(contenido, fuente['unidad'])

    def listar_tickets(self, identificador):
        fuente, libro = self.leer_fuente(identificador)
        return {'fuente': fuente['id'], 'sha256': libro['sha256'], 'hoja': libro['hoja'], 'item': libro['item'],
                'tickets': [{'fila': t['fila'], 'ticket': t['ticket'],
                             'fecha': next((c['valor'] for c in t['campos'] if clave(c['nombre']) == 'FECHA'), '')}
                            for t in libro['tickets']]}

    def seleccionar(self, datos):
        if type(datos.get('fila')) is not int:
            raise ValueError('Selecciona un ticket de la lista.')
        fuente, libro = self.leer_fuente(datos.get('fuente'))
        if datos.get('sha256') != libro['sha256']:
            raise ValueError('El Excel cambió desde que se listaron los tickets. Vuelve a cargar la lista.')
        ticket = next((t for t in libro['tickets'] if t['fila'] == datos['fila']), None)
        if ticket is None:
            raise ValueError('El ticket seleccionado no pertenece a este EDP.')
        return self.crear_muestra(fuente, libro, [ticket], 'manual')

    def sortear(self, datos):
        cantidad = datos.get('cantidad')
        if type(cantidad) is not int or cantidad not in (3, 4, 5):
            raise ValueError('Elige una muestra de 3, 4 o 5 tickets.')
        fuente, libro = self.leer_fuente(datos.get('fuente'))
        if len(libro['tickets']) < cantidad:
            raise ValueError(f'Este EDP tiene {len(libro["tickets"])} registros; no alcanza para sortear {cantidad} sin repetir filas.')
        tickets = secrets.SystemRandom().sample(libro['tickets'], cantidad)
        return self.crear_muestra(fuente, libro, tickets, 'aleatoria')

    def crear_muestra(self, fuente, libro, tickets, modo):
        for t in tickets:
            t.update(comprobado=False, comprobado_en=None, documentos=[])
        muestra = {**fuente, 'id': uuid.uuid4().hex, 'fuente': fuente['id'], 'creado': ahora(), 'actualizado': ahora(),
                   'hoja': libro['hoja'], 'item': libro['item'], 'sha256': libro['sha256'], 'poblacion': len(libro['tickets']),
                   'avisos': libro['avisos'], 'tickets': tickets, 'modo': modo}
        with self.conexion() as db:
            db.execute('INSERT INTO muestras VALUES (?,?,?)', (muestra['id'], fuente['id'], json.dumps(muestra, ensure_ascii=False)))
        return self.obtener(muestra['id'])

    def modificar(self, datos, accion):
        identificador = datos.get('muestra')
        fila = datos.get('fila')
        if type(fila) is not int:
            raise ValueError('Fila de ticket inválida.')
        archivo = decodificar(datos, EXT_DOCUMENTOS) if accion == 'adjuntar' else None
        with self.conexion() as db:
            # Serializar cambios concurrentes para no perder casillas ni respaldos.
            db.execute('BEGIN IMMEDIATE')
            muestra = self.obtener(identificador, db)
            ticket = next((t for t in muestra['tickets'] if t['fila'] == fila), None)
            if ticket is None:
                raise ValueError('El ticket no pertenece a esta muestra.')
            if accion == 'comprobar':
                if type(datos.get('comprobado')) is not bool:
                    raise ValueError('La comprobación debe ser una casilla válida.')
                if datos['comprobado'] and not ticket['documentos']:
                    if not muestra['respaldo_edp']:
                        nombre = nombre_respaldo_edp(muestra['unidad'])
                        raise ValueError(f'Adjunta un documento o coloca {nombre} en la carpeta del EDP antes de confirmar la revisión manual.')
                    # Conservar una sola copia por muestra del PDF que respalda la revisión.
                    if not muestra['respaldo_edp']['guardado']:
                        nombre, contenido = self.leer_respaldo_edp(muestra, db)
                        db.execute('INSERT INTO documentos VALUES (?,?,?,?,?,?)',
                                   (uuid.uuid4().hex, identificador, 0, nombre, ahora(), contenido))
                ticket['comprobado'] = datos['comprobado']
                ticket['comprobado_en'] = ahora() if ticket['comprobado'] else None
            elif accion == 'adjuntar':
                nombre, contenido = archivo
                db.execute('INSERT INTO documentos VALUES (?,?,?,?,?,?)',
                           (uuid.uuid4().hex, identificador, fila, nombre, ahora(), contenido))
                ticket.update(comprobado=False, comprobado_en=None)
            elif accion == 'quitar':
                cursor = db.execute('DELETE FROM documentos WHERE id=? AND muestra=? AND fila=?', (datos.get('documento'), identificador, fila))
                if cursor.rowcount != 1:
                    raise ValueError('No se encontró el documento en este ticket.')
                ticket.update(comprobado=False, comprobado_en=None)
            else:
                raise ValueError('Acción no reconocida.')
            self.guardar(db, muestra)
            return self.obtener(identificador, db)

    def documento(self, identificador):
        with self.conexion() as db:
            fila = db.execute('SELECT nombre,contenido FROM documentos WHERE id=?', (identificador,)).fetchone()
            if fila is None:
                raise ValueError('Documento no encontrado.')
            return fila['nombre'], fila['contenido']


def crear_csv(muestra):
    salida = StringIO(newline='')
    escritor = csv.writer(salida, delimiter=';', lineterminator='\r\n')
    def segura(v):
        v = texto(v)
        return "'" + v if v.lstrip().startswith(('=', '+', '-', '@')) or v.startswith(('\t', '\r', '\n')) else v
    columnas = [(c['columna'], c['nombre']) for c in muestra['tickets'][0]['campos']]
    escritor.writerow(['Unidad', 'Año', 'Mes', 'Período', 'EDP', 'Excel', 'Hoja', 'Muestra', 'Creada el',
                       'Población', 'Tamaño muestra', 'SHA256 Excel', 'Fila Excel', 'Ticket'] +
                      [segura(f'{n}' + (' (t)' if clave(n) == 'CANTIDAD' and muestra['unidad'] == 'Andina' else '') + f' [{c}]') for c, n in columnas] +
                      ['Estado revisión manual', 'Comprobado el', 'Documentos', 'Observaciones de lectura', 'Tipo de selección', 'Respaldo del EDP', 'Ítem'])
    for t in muestra['tickets']:
        campos = {c['columna']: c for c in t['campos']}
        valores = [campos[c]['valor'] if not campos[c]['sin_resultado'] else 'Sin resultado guardado' for c, _ in columnas]
        escritor.writerow([segura(v) for v in [muestra['unidad'], muestra['anio'], muestra['mes'], muestra['periodo'],
            muestra['edp'], muestra['archivo'], muestra['hoja'], muestra['id'], muestra['creado'], muestra['poblacion'],
            len(muestra['tickets']), muestra['sha256'], t['fila'], t['ticket'], *valores,
            'Comprobado manualmente' if t['comprobado'] else 'Pendiente de comprobación', t['comprobado_en'],
            ' | '.join(d['nombre'] for d in t['documentos']), ' | '.join(muestra['avisos']),
            muestra.get('modo', 'aleatoria'), (muestra.get('respaldo_edp') or {}).get('nombre', ''),
            muestra.get('item') or ('1.1' if clave(muestra['hoja']) == '11' else '2.5.a')]])
    return ('\ufeff' + salida.getvalue()).encode('utf-8')
