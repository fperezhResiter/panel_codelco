#!/bin/bash

cd "$(dirname "$0")" || {
    echo "ERROR: No se pudo acceder a la carpeta del panel."
    read -p "Presiona Enter para cerrar..."
    exit 1
}

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: Python 3 no esta instalado."
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if [ $? -ne 0 ]; then
    echo "ERROR: Se requiere Python 3.10 o superior."
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

python3 -c "import openpyxl" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: Falta openpyxl. Ejecuta Iniciar_Primera_vez_MAC.command."
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

echo
python3 -B actualizar_BD.py "$@"
if [ $? -ne 0 ]; then
    echo
    echo "No se pudo actualizar la base de datos."
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

echo
echo "Puedes volver al panel y pulsar Recargar datos."
read -p "Presiona Enter para cerrar..."
