@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ===============================================
echo   CONVERSION UBS VERS WINBIZ
echo ===============================================
echo.

set SCRIPT=
if exist "%~dp0ubs_vers_winbiz.py" set SCRIPT=%~dp0ubs_vers_winbiz.py
if not defined SCRIPT if exist "%~dp0..\ubs_vers_winbiz.py" set SCRIPT=%~dp0..\ubs_vers_winbiz.py
if not defined SCRIPT goto PASDESCRIPT

set PY=
where python >nul 2>nul && set PY=python
if not defined PY where py >nul 2>nul && set PY=py
if not defined PY goto PASDEPYTHON

set FICHIER=%~1
if not defined FICHIER goto DEMANDER
goto VERIFIER

:DEMANDER
echo   Fichiers CSV disponibles ici :
dir /b *.csv 2>nul
echo.
set /p FICHIER="  Nom du fichier a convertir : "

:VERIFIER
if not defined FICHIER goto PASDEFICHIER
if not exist "!FICHIER!" goto PASDEFICHIER

echo.
echo   Comptes. Appuyez sur Entree pour garder la valeur entre crochets.
echo.
set BANQUE=1020
set /p BANQUE="  Compte banque        [1020] : "
set ATTENTE=9999
set /p ATTENTE="  Compte d attente     [9999] : "
set JOURNAL=BQ
set /p JOURNAL="  Code journal         [BQ]   : "
set LIMITE=10
set /p LIMITE="  Nb d ecritures, 0=tout  [10] : "

set OPTLIM=--limite !LIMITE!
if "!LIMITE!"=="0" set OPTLIM=

echo.
echo -----------------------------------------------
"%PY%" "!SCRIPT!" "!FICHIER!" --compte-banque !BANQUE! --compte-attente !ATTENTE! --journal !JOURNAL! !OPTLIM!
echo -----------------------------------------------
echo.
echo   LISEZ LE RAPPORT AVANT D IMPORTER DANS WINBIZ.
echo   Il doit afficher : Chaine des soldes OK, et aucune anomalie bloquante.
goto FINI

:PASDEFICHIER
echo.
echo   Fichier introuvable : !FICHIER!
echo   Il doit etre dans ce dossier :
echo   %~dp0
goto FINI

:PASDESCRIPT
echo   Fichier ubs_vers_winbiz.py INTROUVABLE.
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
