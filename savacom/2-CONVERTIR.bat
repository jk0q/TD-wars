@echo off
REM Glissez l'export UBS sur cette icone, ou double-cliquez et indiquez le nom.
setlocal
cd /d "%~dp0"

set PY=python
where python >nul 2>nul
if errorlevel 1 set PY=py
where %PY% >nul 2>nul
if errorlevel 1 goto NOPYTHON

echo.
echo ===============================================
echo   CONVERSION UBS  --^>  WINBIZ
echo ===============================================
echo.

set FICHIER=%~1
if "%FICHIER%"=="" (
    set /p FICHIER="Nom du fichier UBS (ex: transactions.csv) : "
)
if not exist "%FICHIER%" (
    echo.
    echo   Fichier introuvable : %FICHIER%
    echo   Verifiez qu il est bien dans ce dossier.
    echo.
    pause
    exit /b
)

echo.
echo   Comptes a utiliser. Appuyez sur Entree pour garder la valeur par defaut.
echo.
set BANQUE=1020
set /p BANQUE="  Compte banque             [1020] : "
set ATTENTE=9999
set /p ATTENTE="  Compte d attente          [9999] : "
set JOURNAL=BQ
set /p JOURNAL="  Code journal              [BQ]   : "

echo.
set LIMITE=10
set /p LIMITE="  Combien d ecritures ? 10 pour un test, 0 pour tout [10] : "

set OPTLIM=--limite %LIMITE%
if "%LIMITE%"=="0" set OPTLIM=

echo.
echo -----------------------------------------------
%PY% ubs_vers_winbiz.py "%FICHIER%" --compte-banque %BANQUE% --compte-attente %ATTENTE% --journal %JOURNAL% %OPTLIM%
echo -----------------------------------------------
echo.
echo   LISEZ LE RAPPORT AVANT D IMPORTER DANS WINBIZ.
echo   Il doit afficher : Chaine des soldes OK, et aucune anomalie bloquante.
echo.
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
