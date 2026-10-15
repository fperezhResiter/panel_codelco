@echo off
setlocal
title Panel de reportabilidad - Resiter Mineria

pushd "%~dp0"
if errorlevel 1 goto error_carpeta

echo Buscando Python 3.10 o superior...

py -3 -c "import sys; sys.exit(sys.version_info < (3,10))" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    goto validar
)

python -c "import sys; sys.exit(sys.version_info < (3,10))" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto validar
)

echo ERROR: No se encontro Python 3.10 o superior.
goto error

:validar
%PYTHON_CMD% -c "import openpyxl, reportlab" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Faltan dependencias.
    echo Ejecuta Iniciar_Primera_Vez.bat.
    goto error
)

echo.
echo Iniciando el panel.
echo Se abrira el navegador para iniciar sesion con tus permisos.
echo Si no se abre, usa la URL indicada. Panel.html con doble clic es solo consulta.
echo Mantén esta ventana abierta.
echo Para detener el servidor pulsa Ctrl+C.
echo.

%PYTHON_CMD% -B -m app.reportabilidad %*

if errorlevel 1 goto error

popd
endlocal
exit /b 0

:error
echo.
echo No se pudo iniciar el panel.
pause
popd
endlocal
exit /b 1

:error_carpeta
echo ERROR: No se pudo acceder a la carpeta del panel.
pause
endlocal
exit /b 1
