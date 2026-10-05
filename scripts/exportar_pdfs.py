"""Reúne los PDF de Andina o El Salvador en un ZIP, sin iniciar el panel."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile


BASE = Path(__file__).resolve().parent.parent
UNIDADES = {
    'andina': ('Andina', 'Codelco Andina'),
    'salvador': ('El Salvador', 'Codelco El Salvador'),
}


def unidad_seleccionada(valor):
    texto = unicodedata.normalize('NFKD', valor).encode('ascii', 'ignore').decode()
    texto = ' '.join(texto.lower().split())
    if texto in ('1', 'andina', 'codelco andina'):
        return 'andina'
    if texto in ('2', 'salvador', 'el salvador', 'codelco el salvador'):
        return 'salvador'
    raise argparse.ArgumentTypeError('Selecciona Andina (1) o El Salvador (2).')


def pedir_unidad():
    print('Unidad cuyos PDF se incluirán en el ZIP:')
    print('  1. Andina')
    print('  2. El Salvador')
    while True:
        try:
            return unidad_seleccionada(input('Ingresa 1, 2 o el nombre de la unidad: '))
        except argparse.ArgumentTypeError as error:
            print(error)


def error_recorrido(error):
    # Un directorio inaccesible debe impedir que se entregue un ZIP incompleto.
    raise error


def exportar_pdfs(fuentes, salida, unidad):
    nombre, carpeta = UNIDADES[unidad]
    origen = fuentes / carpeta
    if not origen.is_dir():
        raise FileNotFoundError(f'No existe la carpeta de {nombre}: {origen}')

    pdfs = []
    for directorio, _, archivos in os.walk(origen, onerror=error_recorrido):
        for archivo in archivos:
            if Path(archivo).suffix.lower() == '.pdf':
                pdfs.append(Path(directorio) / archivo)
    pdfs.sort(key=lambda ruta: ruta.relative_to(origen).as_posix())
    if not pdfs:
        raise ValueError(f'No se encontraron PDF en {origen}. No se creó un ZIP.')

    salida.mkdir(parents=True, exist_ok=True)
    destino = salida / f'PDFs_{carpeta.replace(" ", "_")}_{datetime.now():%Y%m%d_%H%M%S_%f}.zip'
    print(f'Encontrados {len(pdfs)} PDF de {nombre}.', flush=True)
    # Solo se publica el ZIP cuando todos los archivos se copiaron correctamente.
    with TemporaryDirectory(prefix='.exportar_pdfs_', dir=salida) as temporal:
        provisional = Path(temporal) / 'pdfs.zip'
        with ZipFile(provisional, 'w', compression=ZIP_DEFLATED, allowZip64=True) as zip_pdf:
            for numero, pdf in enumerate(pdfs, 1):
                relativa = pdf.relative_to(fuentes).as_posix()
                print(f'[{numero}/{len(pdfs)}] {relativa}', flush=True)
                zip_pdf.write(pdf, arcname=relativa)
        provisional.replace(destino)
    return destino, len(pdfs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unidad', type=unidad_seleccionada,
                        help='Andina o Salvador. Si se omite, se pregunta al ejecutar.')
    parser.add_argument('--fuentes', type=Path, default=BASE / 'Fuentes',
                        help='Carpeta Fuentes (por defecto, la del proyecto).')
    parser.add_argument('--salida', type=Path, default=BASE,
                        help='Carpeta para el ZIP (por defecto, junto a scripts).')
    args = parser.parse_args()
    try:
        unidad = args.unidad or pedir_unidad()
        destino, cantidad = exportar_pdfs(args.fuentes.resolve(), args.salida.resolve(), unidad)
    except (EOFError, KeyboardInterrupt):
        print('\nExportación cancelada.', file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    print(f'\nZIP creado con {cantidad} PDF:\n{destino}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
