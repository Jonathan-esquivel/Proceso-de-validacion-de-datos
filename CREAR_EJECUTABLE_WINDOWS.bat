@echo off
title Empaquetando ProcesadorContactos.exe
color 0A
echo.
echo =========================================================
echo   Creando ejecutable para Windows...
echo =========================================================
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado.
    echo Descargalo de: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Instalar dependencias
echo [1/3] Instalando dependencias...
python -m pip install pyinstaller pandas openpyxl --quiet

:: Empaquetar usando "python -m pyinstaller" en lugar de "pyinstaller"
echo [2/3] Empaquetando aplicacion...
python -m PyInstaller --onefile --noconsole --name "ProcesadorContactos" procesar_contactos_gui.py

:: Resultado
if exist "dist\ProcesadorContactos.exe" (
    echo.
    echo [3/3] Ejecutable creado exitosamente!
    copy "dist\ProcesadorContactos.exe" "ProcesadorContactos.exe" >nul
    echo.
    echo Listo: ProcesadorContactos.exe esta en esta misma carpeta.
    echo Puedes copiarlo a cualquier PC sin instalar Python.
) else (
    echo [ERROR] No se pudo crear el ejecutable.
)
echo.
pause
