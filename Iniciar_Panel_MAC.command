#!/bin/bash

cd "$(dirname "$0")" || {
    echo "ERROR: No se pudo acceder a la carpeta del panel."
    read -p "Presiona Enter para cerrar..."
    exit 1
}

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
else
    echo "ERROR: Python no esta instalado."
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

$PYTHON_CMD -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if [ $? -ne 0 ]; then
    echo "ERROR: Se requiere Python 3.10 o superior."
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

$PYTHON_CMD -c "import openpyxl, reportlab" >/dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "ERROR: Faltan dependencias."
    echo "Ejecuta Iniciar_Primera_vez_MAC.command"
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

echo
echo "Iniciando el panel..."
echo
echo "Cuando aparezca 'Panel disponible', abre Panel.html o la URL indicada."
echo
echo "Mantén esta ventana abierta."
echo "Para detener el servidor presiona Control + C."
echo

$PYTHON_CMD reportabilidad.py "$@"

read -p "Presiona Enter para cerrar..."
