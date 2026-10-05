"""BD local reconstruible y cambios inmutables para carpetas OneDrive/SharePoint."""
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .auditoria import Auditoria, ahora


def serializar(datos):
    return json.dumps(datos, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def escribir_atomico(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name('.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporal.open('xb') as archivo:
            archivo.write(contenido)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
    finally:
        temporal.unlink(missing_ok=True)


class AuditoriaCompartida(Auditoria):
    def __init__(self, fuentes, carpeta, cache=None):
        self.compartida = Path(carpeta).resolve()
        llave = hashlib.sha256(str(self.compartida).encode()).hexdigest()[:24]
        # La caché queda fuera de OneDrive: cada equipo escribe únicamente su SQLite.
        local = Path(cache) if cache is not None else Path(tempfile.gettempdir()) / 'panel-codelco-auditoria' / llave
        super().__init__(fuentes, local)
        self.eventos = self.compartida / 'Compartido' / 'eventos'
        self.archivos = self.compartida / 'Compartido' / 'archivos'
        self._inicio = False
        self._lock = threading.RLock()
        self._pendientes = 0
        self._consulta = None

    @contextmanager
    def conexion(self):
        with self._lock, super().conexion() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS cambios_aplicados (id TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS versiones_tickets (muestra TEXT, fila INTEGER, version TEXT,
                    PRIMARY KEY (muestra, fila));
            ''')
            self.eventos.mkdir(parents=True, exist_ok=True)
            self.archivos.mkdir(parents=True, exist_ok=True)
            if not self._inicio:
                self.migrar_anteriores(db)
                self._inicio = True
            self.sincronizar(db)
            db.commit()
            with db:
                yield db

    def guardar_archivo(self, contenido):
        huella = hashlib.sha256(contenido).hexdigest()
        ruta = self.archivos / (huella + '.bin')
        if not ruta.exists():
            escribir_atomico(ruta, contenido)
        return huella

    def documentos_evento(self, db, muestra, fila=None):
        documentos = []
        consulta = 'SELECT * FROM documentos WHERE muestra=?'
        parametros = [muestra]
        if fila is not None:
            consulta += ' AND (fila=? OR fila=0)'
            parametros.append(fila)
        for r in db.execute(consulta, parametros):
            documentos.append({k: r[k] for k in ('id', 'fila', 'nombre', 'creado')} |
                              {'sha256': self.guardar_archivo(r['contenido'])})
        return documentos

    def publicar_cambio(self, db, muestra, fila=None):
        limpio = {k: v for k, v in muestra.items() if k != 'respaldo_edp'}
        evento = {'tipo': 'muestra' if fila is None else 'ticket', 'muestra': limpio,
                  'fila': fila, 'documentos': self.documentos_evento(db, muestra['id'], fila),
                  'creado': datetime.now(timezone.utc).isoformat(timespec='microseconds'),
                  'id': uuid.uuid4().hex, 'version': 1}
        ultima = db.execute('SELECT max(version) FROM versiones_tickets').fetchone()[0]
        if ultima and evento['creado'] <= ultima.split('|')[0]:
            evento['creado'] = (datetime.fromisoformat(ultima.split('|')[0]) + timedelta(microseconds=1)).isoformat(timespec='microseconds')
        if fila is not None:
            evento['ticket'] = next(t for t in limpio['tickets'] if t['fila'] == fila)
            # Solo el ticket modificado viaja: otro equipo puede cambiar otra fila a la vez.
            evento['muestra'] = {k: limpio[k] for k in ('id', 'actualizado')}
        escribir_atomico(self.eventos / (evento['id'] + '.json'), serializar(evento))
        # Aplicar por la misma vía que en los demás equipos.
        self.aplicar(db, evento)

    def migrar_anteriores(self, db):
        """Preservar tanto la BD original como sus copias en conflicto, sin escribirlas."""
        for ruta in sorted(self.compartida.glob('auditoria*.sqlite3')):
            anterior = None
            try:
                anterior = sqlite3.connect(ruta.as_uri() + '?mode=ro', uri=True)
                anterior.row_factory = sqlite3.Row
                with anterior:
                    # Las cargas antiguas siguen accesibles; la API actual usa Fuentes.
                    for r in anterior.execute('SELECT * FROM fuentes'):
                        datos = json.loads(r['datos'])
                        contenido = self.guardar_archivo(r['contenido'])
                        evento = {'tipo': 'fuente', 'fuente': datos, 'sha256': contenido,
                                  'version': 1, 'creado': '2000-01-01T00:00:00+00:00'}
                        evento['id'] = hashlib.sha256(serializar(evento)).hexdigest()
                        if not (self.eventos / (evento['id'] + '.json')).exists():
                            escribir_atomico(self.eventos / (evento['id'] + '.json'), serializar(evento))
                    for r in anterior.execute('SELECT datos FROM muestras'):
                        muestra = json.loads(r['datos'])
                        evento = {'tipo': 'muestra', 'muestra': muestra, 'fila': None,
                                  'documentos': self.documentos_evento(anterior, muestra['id']),
                                  'creado': muestra.get('actualizado', muestra['creado']),
                                  'version': 1, 'migracion': True}
                        evento['id'] = hashlib.sha256(serializar(evento)).hexdigest()
                        if not (self.eventos / (evento['id'] + '.json')).exists():
                            escribir_atomico(self.eventos / (evento['id'] + '.json'), serializar(evento))
            except (sqlite3.Error, ValueError, KeyError) as exc:
                raise ValueError(f'No se pudieron recuperar las revisiones de {ruta.name}: {exc}') from exc
            finally:
                if anterior is not None:
                    anterior.close()

    def leer_documentos(self, evento):
        documentos = []
        for d in evento.get('documentos', []):
            huella = d['sha256']
            if not re.fullmatch(r'[a-f0-9]{64}', huella):
                raise ValueError('Huella de respaldo inválida.')
            ruta = self.archivos / (huella + '.bin')
            if not ruta.is_file():
                return None  # OneDrive puede recibir el evento antes que su respaldo.
            contenido = ruta.read_bytes()
            if hashlib.sha256(contenido).hexdigest() != huella:
                return None
            documentos.append((d, contenido))
        return documentos

    def aplicar(self, db, evento):
        if evento.get('version') != 1 or evento.get('tipo') not in ('fuente', 'muestra', 'ticket'):
            raise ValueError('Formato de cambio compartido inválido.')
        if db.execute('SELECT 1 FROM cambios_aplicados WHERE id=?', (evento['id'],)).fetchone():
            return True
        if evento['tipo'] == 'fuente':
            contenido = self.leer_documentos({'documentos': [{'sha256': evento['sha256']}]})
            if contenido is None:
                return False
            db.execute('INSERT OR IGNORE INTO fuentes VALUES (?,?,?)',
                       (evento['fuente']['id'], json.dumps(evento['fuente']), contenido[0][1]))
        else:
            documentos = self.leer_documentos(evento)
            if documentos is None:
                return False
            m = evento['muestra']
            actual = db.execute('SELECT datos FROM muestras WHERE id=?', (m['id'],)).fetchone()
            if evento['tipo'] == 'muestra':
                if not actual:
                    actual_m = m
                    db.execute('INSERT INTO muestras VALUES (?,?,?)', (m['id'], m['fuente'], json.dumps(m)))
                else:
                    actual_m = json.loads(actual['datos'])
                    # Al recuperar copias en conflicto, conservar los checks confirmados.
                    # Un cambio explícito posterior (incluido desmarcar) tiene prioridad.
                    for t in m['tickets']:
                        version = db.execute('SELECT 1 FROM versiones_tickets WHERE muestra=? AND fila=?',
                                             (m['id'], t['fila'])).fetchone()
                        destino = next((x for x in actual_m['tickets'] if x['fila'] == t['fila']), None)
                        if destino and not version and t['comprobado']:
                            destino.update(comprobado=True, comprobado_en=t['comprobado_en'])
                    actual_m['actualizado'] = max(actual_m['actualizado'], m['actualizado'])
                # Los respaldos de las copias históricas se combinan, no se eliminan.
            else:
                if not actual:
                    return False  # Esperar la muestra si OneDrive entrega fuera de orden.
                actual_m = json.loads(actual['datos'])
                version = evento['creado'] + '|' + evento['id']
                anterior = db.execute('SELECT version FROM versiones_tickets WHERE muestra=? AND fila=?',
                                      (m['id'], evento['fila'])).fetchone()
                if anterior and anterior['version'] >= version:
                    db.execute('INSERT INTO cambios_aplicados VALUES (?)', (evento['id'],))
                    return True
                destino = next(t for t in actual_m['tickets'] if t['fila'] == evento['fila'])
                destino.update(evento['ticket'])
                actual_m['actualizado'] = max(actual_m['actualizado'], m['actualizado'])
                db.execute('DELETE FROM documentos WHERE muestra=? AND fila=?', (m['id'], evento['fila']))
                db.execute('INSERT OR REPLACE INTO versiones_tickets VALUES (?,?,?)',
                           (m['id'], evento['fila'], version))
            for d, contenido in documentos:
                # No restaurar adjuntos antiguos sobre un ticket modificado explícitamente.
                if evento['tipo'] == 'muestra' and d['fila'] and db.execute(
                        'SELECT 1 FROM versiones_tickets WHERE muestra=? AND fila=?', (m['id'], d['fila'])).fetchone():
                    continue
                db.execute('INSERT OR IGNORE INTO documentos VALUES (?,?,?,?,?,?)',
                           (d['id'], m['id'], d['fila'], d['nombre'], d['creado'], contenido))
            db.execute('UPDATE muestras SET datos=? WHERE id=?', (json.dumps(actual_m, ensure_ascii=False), m['id']))
        db.execute('INSERT INTO cambios_aplicados VALUES (?)', (evento['id'],))
        return True

    def sincronizar(self, db):
        db.execute('BEGIN IMMEDIATE')
        self._pendientes = 0
        aplicados = {r[0] for r in db.execute('SELECT id FROM cambios_aplicados')}
        nuevos = []
        for ruta in sorted(self.eventos.glob('*.json')):
            if ruta.stem in aplicados:
                continue
            try:
                evento = json.loads(ruta.read_text(encoding='utf-8'))
                if (not isinstance(evento, dict) or evento.get('tipo') not in ('fuente', 'muestra', 'ticket')
                        or not isinstance(evento.get('creado'), str)):
                    raise ValueError('Formato compartido inválido.')
                if evento['id'] != ruta.stem:
                    raise ValueError('Identificador compartido inválido.')
                nuevos.append(evento)
            except (ValueError, KeyError, OSError, TypeError):
                # Un archivo aún no descargado o incompleto se vuelve a intentar.
                self._pendientes += 1
        for evento in sorted(nuevos, key=lambda e: (e['tipo'] == 'ticket', e.get('creado', ''), e['id'])):
            db.execute('SAVEPOINT importar_cambio')
            try:
                if not self.aplicar(db, evento):
                    db.execute('ROLLBACK TO importar_cambio')
                    self._pendientes += 1
            except (ValueError, KeyError, TypeError, OSError, StopIteration, sqlite3.Error):
                db.execute('ROLLBACK TO importar_cambio')
                self._pendientes += 1
            finally:
                db.execute('RELEASE importar_cambio')
        self._consulta = ahora()

    def estado_conexion(self):
        return {'modo': 'carpeta_compartida', 'conectada': True, 'carpeta': str(self.compartida),
                'mensaje': 'BD conectada · Cambios compartidos por SharePoint/OneDrive',
                'pendientes': self._pendientes, 'consultada': self._consulta,
                'nota': 'Los otros equipos reciben los chequeos cuando OneDrive sincroniza esta carpeta.'}
