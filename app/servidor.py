"""Servidor HTTP local del portal."""
import argparse
import json
import os
import socket
from datetime import date, datetime
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from dotenv import load_dotenv
from .rutas import ARCHIVOS_WEB
from .reportes import crear_reporte
from .api import API_RUTAS

BASE = Path(__file__).resolve().parent.parent
BASE_DOCUMENTOS = Path(__file__).resolve().parents[4]
load_dotenv(BASE / ".env", encoding="utf-8-sig")
LIBRO_EQUIPOS = Path(
    os.environ.get("LIBRO_EQUIPOS")
    or BASE_DOCUMENTOS
    / "06. Mantenimiento"
    / "Forms"
    / "Control de Equipos Móviles – Minería.xlsx"
)

class ServidorPanel(ThreadingHTTPServer):
    """Evita que dos instancias atiendan el mismo puerto en Windows."""
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    
    parser.add_argument('--excel', type=Path, default=LIBRO_EQUIPOS,
                        help='Libro de formularios (hoja Sheet1).')
    parser.add_argument('--maestro', type=Path, default=LIBRO_EQUIPOS,
                        help='Libro de activos (hoja BD ACTIVOS MOVILES).')
    parser.add_argument('--puerto', type=int, default=8765)
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def responder(self, status, contenido, tipo):
            self.send_response(status)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(contenido)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(contenido)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path in ARCHIVOS_WEB:
                nombre, tipo = ARCHIVOS_WEB[url.path]
                try:
                    contenido = (BASE / nombre).read_bytes()
                except OSError:
                    self.responder(404, b'Archivo del panel no disponible.', 'text/plain; charset=utf-8')
                    return
                self.responder(200, contenido, tipo)
            elif url.path in API_RUTAS:
                try:
                    datos = API_RUTAS[url.path](args.excel, args.maestro, parse_qs(url.query))
                    self.responder(200, json.dumps(datos, ensure_ascii=False).encode(), 'application/json; charset=utf-8')
                except (ValueError, OverflowError) as error:
                    self.responder(400, json.dumps({'error': str(error)}).encode(), 'application/json')
                except Exception as error:
                    mensaje = f'No se pudo leer el Excel ({type(error).__name__}). Verifique los archivos, su disponibilidad local y sus permisos.'
                    self.responder(500, json.dumps({'error': mensaje}).encode(), 'application/json')
            else:
                self.responder(404, b'No encontrado', 'text/plain')

    try:
        servidor = ServidorPanel(('127.0.0.1', args.puerto), Handler)
    except OSError as error:
        print(f'No se pudo iniciar el panel en el puerto {args.puerto}: {error}', flush=True)
        print('Si hay otro panel abierto, detén esa instancia antes de iniciar una nueva. '
              'También puedes elegir otro puerto con --puerto 8766.', flush=True)
        raise SystemExit(1)
    print(f'Panel disponible en http://127.0.0.1:{servidor.server_address[1]} | Reporte v2 | Ctrl+C para detener', flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == '__main__':
    """ fecha = "22/09/2026"
    BASE = Path(__file__).parent
    # Convertir la fecha a objeto date
    fecha = datetime.strptime(fecha, "%d/%m/%Y").date()
    datos = crear_reporte(BASE / 'PruebaForm.xlsx', BASE / 'BD ACTIVOS MOBILES.xlsx', fecha)

    # Imprimir cada linea del json
    for linea in json.dumps(datos, ensure_ascii=False, indent=4).splitlines():
        print(linea) """
    main()
