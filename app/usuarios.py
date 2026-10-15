"""Usuarios locales y permisos. Las sesiones nunca aceptan roles del navegador."""
import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
import re
from pathlib import Path
from contextlib import contextmanager

ROLES = {
    'general': {'nombre': 'General', 'permisos': ['consultar', 'descargar']},
    'auditor': {'nombre': 'Auditor', 'permisos': ['consultar', 'descargar', 'revisar', 'comprobar']},
    'administrador': {'nombre': 'Administrador', 'permisos': ['consultar', 'descargar', 'revisar', 'comprobar', 'modificar', 'configurar']},
}
DURACION_SESION = 8 * 60 * 60


class Usuarios:
    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self.lock = threading.RLock()
        self.sesiones = {}
        self.intentos = {}

    @contextmanager
    def conexion(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.ruta)
        db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE IF NOT EXISTS usuarios (nombre TEXT PRIMARY KEY, rol TEXT NOT NULL, sal TEXT NOT NULL, clave TEXT NOT NULL)')
        try:
            with db:
                yield db
        finally:
            db.close()

    def configurado(self):
        with self.lock, self.conexion() as db:
            return bool(db.execute("SELECT 1 FROM usuarios WHERE instr(nombre,'@')>0 LIMIT 1").fetchone())

    @staticmethod
    def clave(password, sal):
        return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(sal), 600_000).hex()

    def inicializar(self, datos):
        registro = self.preparar({**datos, 'rol': 'administrador'})
        with self.lock, self.conexion() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM usuarios WHERE instr(nombre,'@')>0 LIMIT 1").fetchone():
                raise ValueError('Los usuarios ya están configurados.')
            db.execute('INSERT INTO usuarios VALUES (?,?,?,?)', registro)

    @staticmethod
    def identidad(datos):
        correo = datos.get('correo')
        rol = datos.get('rol')
        if not isinstance(correo, str) or len(correo) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', correo.strip()):
            raise ValueError('Ingresa un correo válido.')
        if not isinstance(rol, str) or rol not in ROLES:
            raise ValueError('Selecciona un rol válido.')
        return correo.strip().lower(), rol

    def preparar(self, datos):
        correo, rol = self.identidad(datos)
        password = datos.get('password')
        if not isinstance(password, str) or not 10 <= len(password) <= 256:
            raise ValueError('La contraseña debe tener entre 10 y 256 caracteres.')
        sal = secrets.token_hex(16)
        return correo, rol, sal, self.clave(password, sal)

    def agregar(self, datos):
        registro = self.preparar(datos)
        with self.lock, self.conexion() as db:
            try:
                db.execute('INSERT INTO usuarios VALUES (?,?,?,?)', registro)
            except sqlite3.IntegrityError:
                raise ValueError('Ya existe un usuario con ese correo.') from None
        return self.publico({'nombre': registro[0], 'rol': registro[1]})

    def listar(self):
        with self.lock, self.conexion() as db:
            # Las cuentas antiguas por nombre de rol se conservan, pero ya no dan acceso.
            return [self.publico(u) for u in db.execute("SELECT nombre,rol FROM usuarios WHERE instr(nombre,'@')>0 ORDER BY nombre")]

    def editar(self, datos):
        correo, rol = self.identidad(datos)
        password = datos.get('password', '')
        if not isinstance(password, str) or (password and not 10 <= len(password) <= 256):
            raise ValueError('La nueva contraseña debe tener entre 10 y 256 caracteres.')
        sal = secrets.token_hex(16) if password else None
        clave = self.clave(password, sal) if password else None
        with self.lock:
            with self.conexion() as db:
                db.execute('BEGIN IMMEDIATE')
                anterior = db.execute('SELECT * FROM usuarios WHERE nombre=?', (correo,)).fetchone()
                if not anterior:
                    raise ValueError('No se encontró el usuario que quieres editar.')
                if anterior['rol'] == 'administrador' and rol != 'administrador':
                    admins = db.execute("SELECT count(*) FROM usuarios WHERE rol='administrador' AND instr(nombre,'@')>0").fetchone()[0]
                    if admins <= 1:
                        raise ValueError('Debe quedar al menos un usuario Admin. Crea otro Admin antes de cambiar este rol.')
                cambio = rol != anterior['rol'] or bool(password)
                db.execute('UPDATE usuarios SET rol=?,sal=?,clave=? WHERE nombre=?',
                           (rol, sal or anterior['sal'], clave or anterior['clave'], correo))
            if cambio:
                self.sesiones = {t: s for t, s in self.sesiones.items() if s['cuenta']['correo'] != correo}
                self.intentos.pop(correo, None)
        return self.publico({'nombre': correo, 'rol': rol})

    def cambiar_password(self, token, actual, nueva):
        if not isinstance(actual, str) or not 0 < len(actual) <= 256:
            raise ValueError('Ingresa tu contraseña actual.')
        if not isinstance(nueva, str) or not 10 <= len(nueva) <= 256:
            raise ValueError('La nueva contraseña debe tener entre 10 y 256 caracteres.')
        with self.lock:
            sesion = self.sesion(token)
            if not sesion:
                raise PermissionError('Inicia sesión para cambiar tu contraseña.')
            correo = sesion['cuenta']['correo']
            ahora = time.time()
            fallos, hasta = self.intentos.get(correo, (0, 0))
            if hasta > ahora:
                raise ValueError('Demasiados intentos. Vuelve a intentar en unos minutos.')
            if hasta:
                fallos = 0
            with self.conexion() as db:
                db.execute('BEGIN IMMEDIATE')
                usuario = db.execute('SELECT * FROM usuarios WHERE nombre=?', (correo,)).fetchone()
                if not usuario or not hmac.compare_digest(self.clave(actual, usuario['sal']), usuario['clave']):
                    self.intentos[correo] = (fallos + 1, ahora + 300 if fallos + 1 >= 5 else 0)
                    raise ValueError('La contraseña actual es incorrecta.')
                sal = secrets.token_hex(16)
                db.execute('UPDATE usuarios SET sal=?,clave=? WHERE nombre=?', (sal, self.clave(nueva, sal), correo))
            self.sesiones = {t: s for t, s in self.sesiones.items() if s['cuenta']['correo'] != correo}
            self.intentos.pop(correo, None)

    def ingresar(self, nombre, password):
        if not isinstance(nombre, str) or not isinstance(password, str) or len(nombre) > 254 or len(password) > 256:
            raise ValueError('Usuario o contraseña incorrectos.')
        nombre = nombre.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', nombre):
            raise ValueError('Usuario o contraseña incorrectos.')
        with self.lock:
            ahora = time.time()
            fallos, hasta = self.intentos.get(nombre, (0, 0))
            if hasta > ahora:
                raise ValueError('Demasiados intentos. Vuelve a intentar en unos minutos.')
            if hasta:
                fallos = 0
            with self.conexion() as db:
                usuario = db.execute('SELECT * FROM usuarios WHERE nombre=?', (nombre,)).fetchone()
            sal = usuario['sal'] if usuario else '00' * 16
            calculada = self.clave(password, sal)
            if not usuario or not hmac.compare_digest(calculada, usuario['clave']):
                self.intentos[nombre] = (fallos + 1, ahora + 300 if fallos + 1 >= 5 else 0)
                raise ValueError('Usuario o contraseña incorrectos.')
            self.intentos.pop(nombre, None)
            self.sesiones = {k: v for k, v in self.sesiones.items() if v['vence'] > ahora}
            token = secrets.token_urlsafe(32)
            cuenta = self.publico(usuario)
            self.sesiones[token] = {'cuenta': cuenta, 'usuario': cuenta, 'vence': ahora + DURACION_SESION, 'preview': None}
            return token

    @staticmethod
    def publico(usuario):
        rol = usuario['rol']
        return {'nombre': usuario['nombre'], 'correo': usuario['nombre'], 'rol': rol, 'rol_real': rol,
                'vista_general': False, 'rol_nombre': ROLES[rol]['nombre'], 'permisos': list(ROLES[rol]['permisos'])}

    def cambiar_vista(self, token, general):
        with self.lock:
            sesion = self.sesion(token)
            if not sesion or sesion['cuenta']['rol'] != 'administrador':
                raise PermissionError('Solo Admin puede cambiar su vista.')
            if type(general) is not bool:
                raise ValueError('Selecciona una vista válida.')
            cuenta = sesion['cuenta']
            sesion['usuario'] = {**cuenta, 'vista_general': True, 'rol': 'general', 'rol_nombre': 'General (vista de Admin)',
                                 'permisos': list(ROLES['general']['permisos'])} if general else cuenta
            sesion['preview'] = None
            return sesion['usuario']

    def sesion(self, token):
        with self.lock:
            sesion = self.sesiones.get(token)
            if sesion and sesion['vence'] > time.time():
                return sesion
            self.sesiones.pop(token, None)
            return None

    def salir(self, token):
        with self.lock:
            self.sesiones.pop(token, None)
