@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ===============================================
echo   DIAGNOSTIC DE FICHIER
echo ===============================================
echo.

set SCRIPT=
if exist "%~dp0diagnostic.py" set SCRIPT=%~dp0diagnostic.py
if not defined SCRIPT if exist "%~dp0..\diagnostic.py" set SCRIPT=%~dp0..\diagnostic.py
if not defined SCRIPT goto PASDESCRIPT

set PY=
where python >nul 2>nul
if not errorlevel 1 set PY=python
if defined PY goto PYOK
where py >nul 2>nul
if not errorlevel 1 set PY=py
:PYOK
if not defined PY goto PASDEPYTHON

if "%~1"=="" goto TOUS
"%PY%" "!SCRIPT!" %*
goto FINI

:TOUS
if not exist "*.csv" goto PASDECSV
"%PY%" "!SCRIPT!" *.csv
goto FINI

:PASDECSV
echo   Aucun fichier .csv dans ce dossier :
echo   %~dp0
echo.
echo   Copiez-y vos fichiers CSV, ou glissez un CSV sur cette icone.
goto FINI

:PASDESCRIPT
echo   Fichier diagnostic.py INTROUVABLE.
echo.
echo   Il doit se trouver dans le meme dossier que ce lanceur :
echo   %~dp0
echo.
echo   Deplacez diagnostic.py et ubs_vers_winbiz.py dans ce dossier.
goto FINI

:PASDEPYTHON
echo   PYTHON N EST PAS INSTALLE, ou pas dans le PATH.
echo.
echo   Allez sur python.org, telechargez, installez, et
echo   COCHEZ "Add Python to PATH" sur le premier ecran.
goto FINI

:FINI
echo.
echo ===============================================
pause
