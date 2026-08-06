@echo off
rem ============================================================
rem  git_push.bat  daily sync launcher for cnb.cool (tools repo)
rem  Double-click or run from a terminal in the project folder.
rem  Repo root: D:\Python\tools  ->  cnb.cool/leokous/Python-tools
rem ============================================================
setlocal
echo.
echo Current folder: %CD%
if exist ".git" goto :run
set "PROJPATH="
set /p "PROJPATH=Not a git repo here. Project folder path: "
if "%PROJPATH%"=="" ( echo No project path given. Exiting. & pause & exit /b 1 )
if not exist "%PROJPATH%\.git" ( echo No .git found in: "%PROJPATH%" & pause & exit /b 1 )
cd /d "%PROJPATH%"
:run
echo.
echo Running in: %CD%
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0git_push.ps1"
echo.
pause
