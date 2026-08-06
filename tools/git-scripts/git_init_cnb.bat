@echo off
rem ============================================================
rem  git_init_cnb.bat  init tools repo & push to cnb.cool
rem  Repo root: D:\Python\tools  ->  cnb.cool/leokous/Python-tools
rem  Double-click or run from a terminal. If not run inside the
rem  target project folder, it will ask for the project path.
rem ============================================================
chcp 65001 >nul
setlocal
echo.
echo Current folder: %CD%
set "PROJPATH="
set /p "PROJPATH=Project folder path (Enter = current folder): "
if "%PROJPATH%"=="" set "PROJPATH=%CD%"
if not exist "%PROJPATH%\.git" if not exist "%PROJPATH%" (
    echo Folder not found: "%PROJPATH%"
    pause
    exit /b 1
)
cd /d "%PROJPATH%"
echo.
echo Running init in: %CD%
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0git_init_cnb.ps1"
echo.
pause
