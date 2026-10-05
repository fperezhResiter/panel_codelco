@echo off
setlocal
title Preparacion inicial - Panel Codelco

pushd "%~dp0"
if errorlevel 1 goto error_carpeta

if not exist "config\requirements.txt" goto error_archivos
if not exist "app\reportabilidad.py" goto error_archivos
if not exist "app\servidor.py" goto error_archivos

echo Buscando Python 3.10 o superior...

py -3 -c "import sys; sys.exit(sys.version_info < (3,10))" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    goto instalar
)

python -c "import sys; sys.exit(sys.version_info < (3,10))" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto instalar
)

echo ERROR: Instala Python 3.10 o superior y agregalo al PATH.
goto error

:instalar
echo Actualizando pip...
%PYTHON_CMD% -m pip install --upgrade pip
if errorlevel 1 goto error

echo Instalando dependencias...
%PYTHON_CMD% -m pip install -r "config\requirements.txt"
if errorlevel 1 goto error

echo Verificando instalacion...
%PYTHON_CMD% -m pip check
if errorlevel 1 goto error

%PYTHON_CMD% -B -m app.reportabilidad --help >nul
if errorlevel 1 goto error

echo.
echo Preparacion completada.
echo Para abrir el portal ejecuta Iniciar_Panel.bat.
pause

popd
endlocal
exit /b 0

:error_archivos
echo ERROR: Faltan archivos del portal.
goto error

:error
echo.
echo No se completo la preparacion.
pause
popd
endlocal
exit /b 1

:error_carpeta
echo ERROR: No se pudo acceder a la carpeta del panel.
pause
endlocal
exit /b 1