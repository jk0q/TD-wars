@echo off
REM Glissez un fichier CSV sur cette icone, ou double-cliquez pour analyser
REM tous les CSV du dossier.
setlocal
cd /d "%~dp0"

set PY=python
where python >nul 2>nul
if errorlevel 1 set PY=py
where %PY% >nul 2>nul
if errorlevel 1 goto NOPYTHON

echo.
echo ===============================================
echo   DIAGNOSTIC DE FICHIER
echo ===============================================
echo.

if "%~1"=="" (
    %PY% diagnostic.py *.csv
) else (
    %PY% diagnostic.py %*
)

echo.
echo ===============================================
echo   Termine. Faites une capture si besoin.
echo ===============================================
pause
exit /b

:NOPYTHON
echo.
echo   PYTHON N EST PAS INSTALLE ou pas dans le PATH.
echo.
echo   Allez sur python.org, telechargez, installez,
echo   et COCHEZ "Add Python to PATH" sur le premier ecran.
echo.
pause
exit /b
