"""Actualiza la base SQLite con la lectura actual de la carpeta Fuentes."""
import argparse
from pathlib import Path
from time import perf_counter

from app.base_datos import actualizar_base_datos

BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fuentes', type=Path, default=BASE / 'Fuentes',
                        help='Carpeta con unidades, períodos y archivos EDP.')
    parser.add_argument('--bd', type=Path, default=BASE / 'Datos' / 'conciliacion.sqlite3',
                        help='Archivo SQLite que usará el panel.')
    args = parser.parse_args()
    inicio = perf_counter()
    print(f'Actualizando la base de datos desde: {args.fuentes.resolve()}', flush=True)
    print('Se comparan las fuentes. Los Excel sin cambios se reutilizan cuando ya existe la base.', flush=True)
    try:
        reporte = actualizar_base_datos(args.fuentes, args.bd)
    except Exception as error:
        print(f'ERROR: No se pudo actualizar la base de datos: {error}', flush=True)
        raise SystemExit(1) from error
    segundos = perf_counter() - inicio
    tickets = sum(len(r.get('tickets', [])) for r in reporte['registros'])
    incompletos = sum(r.get('estado') == 'incompleto' for r in reporte['registros'])
    print(f"Base actualizada: {args.bd.resolve()}", flush=True)
    print(f"{len(reporte['registros'])} EDP, {tickets} filas de tickets, {incompletos} EDP sin conciliar.", flush=True)
    print(f'Tiempo: {segundos:.1f} segundos.', flush=True)


if __name__ == '__main__':
    main()
