@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title SLIME FORUM
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$sig='[DllImport(\"kernel32.dll\")]public static extern IntPtr GetConsoleWindow();[DllImport(\"user32.dll\")]public static extern bool ShowWindow(IntPtr hWnd,int nCmdShow);'; Add-Type -MemberDefinition $sig -Name Win32 -Namespace SlimeForum -ErrorAction SilentlyContinue; $h=[SlimeForum.Win32]::GetConsoleWindow(); if($h -ne [IntPtr]::Zero){[SlimeForum.Win32]::ShowWindow($h,3)|Out-Null}" >nul 2>nul




echo ==========================================
echo          SLIME FORUM - DEMARRAGE
echo ==========================================
echo.

REM Ne jamais lancer depuis l'interieur du ZIP
if not exist "client.py" (
    echo [ERREUR] client.py est introuvable.
    echo.
    echo Decompresse d'abord tout le ZIP dans un dossier,
    echo puis lance ce fichier .bat depuis ce dossier.
    echo.
    pause
    exit /b 1
)

REM Cherche Python 3
set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
    py -3 --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info.major == 3 else 1)" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo [ERREUR] Python 3 n'est pas installe ou n'est pas dans le PATH.
    echo.
    echo Installe Python 3 depuis python.org en cochant:
    echo "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [OK] Python detecte.

REM Cree un environnement local pour eviter les problemes de droits/dependances
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Preparation de SLIME FORUM pour la premiere utilisation...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo.
        echo [ERREUR] Impossible de creer l'environnement Python.
        pause
        exit /b 1
    )
)

set "VPY=.venv\Scripts\python.exe"

echo [INFO] Verification des dependances...
"%VPY%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERREUR] Impossible d'installer les dependances.
    echo Verifie ta connexion Internet.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Connexion au serveur SLIME FORUM...
echo.

"%VPY%" client.py 2>"SLIME_FORUM_ERREUR.txt"
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo ==========================================
    echo [ERREUR] SLIME FORUM s'est arrete.
    echo ==========================================
    echo.
    if exist "SLIME_FORUM_ERREUR.txt" (
        type "SLIME_FORUM_ERREUR.txt"
    )
    echo.
    echo Une copie de l'erreur est dans:
    echo SLIME_FORUM_ERREUR.txt
    echo.
    pause
    exit /b %EXITCODE%
)

del "SLIME_FORUM_ERREUR.txt" >nul 2>nul
endlocal
