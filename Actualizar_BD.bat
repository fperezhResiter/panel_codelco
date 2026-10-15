@echo off
setlocal
title Actualizar base de datos - Panel Codelco

pushd "%~dp0"
if errorlevel 1 goto error_carpeta

py -3 -c "import sys; sys.exit(sys.version_info < (3,10))" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    goto actualizar
)

python -c "import sys; sys.exit(sys.version_info < (3,10))" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto actualizar
)

echo ERROR: Se requiere Python 3.10 o superior.
goto error

:actualizar
%PYTHON_CMD% -c "import openpyxl, reportlab" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Faltan dependencias. Ejecuta Iniciar_Primera_Vez.bat.
    goto error
)

echo.
%PYTHON_CMD% -B -m app.actualizar_BD %*
if errorlevel 1 goto error

echo.
echo BD y publicacion actualizadas. Abre Panel.html o recarga la pagina de consulta.
pause
popd
endlocal
exit /b 0

:error
echo.
echo No se pudo completar la actualizacion y publicacion. Revisa el mensaje anterior.
pause
popd
endlocal
exit /b 1

:error_carpeta
echo ERROR: No se pudo acceder a la carpeta del panel.
pause
endlocal
exit /b 1
