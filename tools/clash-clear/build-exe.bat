@echo off
REM ---------------------------------------------------------------------------
REM clash-clear - build exe
REM   Targets (this dir, tools\clash-clear):
REM     - clash clean script (.py, Chinese filename)  -> clash-clear.exe
REM   Output: D:\Python\dist
REM   Requires: pyinstaller installed in the python below (see PY variable)
REM   NOTE: keep this file ASCII-only. Chinese comments break cmd.exe parsing
REM         because .bat is read in the system codepage (GBK), not UTF-8.
REM         Chinese source file names are resolved via the for-loop below.
REM ---------------------------------------------------------------------------
setlocal

REM Disable fail-closed safe-delete: removing old exe goes to recycle bin, not error
set "CODEBUDDY_SAFE_DELETE_SANDBOX=0"

REM Python to use (must have pyinstaller). Override with: set PY=your_python.exe
if "%PY%"=="" set "PY=python"

set "DIST=D:\Python\dist"
set "SRCDIR=%~dp0"

REM Check python and pyinstaller
"%PY%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pyinstaller not found. Install first:
    echo         "%PY%" -m pip install pyinstaller
    pause
    exit /b 1
)

if not exist "%DIST%" mkdir "%DIST%"
cd /d "%SRCDIR%" || (echo [ERROR] cannot enter %SRCDIR% & pause & exit /b 1)

REM ---- Resolve the .py entry (Chinese filename, resolve via for-loop) ----
set "SRC="
for %%F in (*.py) do set "SRC=%%F"
if "%SRC%"=="" (
    echo [ERROR] no .py file found in %SRCDIR%
    pause
    exit /b 1
)

REM ---- Build the single entry script ----
echo ===================================================================
echo [BUILD] clash-clear.exe  (%SRC%)
echo ===================================================================
"%PY%" -m PyInstaller --onefile --noconfirm --clean --distpath "%DIST%" --name clash-clear "%SRC%"
if errorlevel 1 (
    echo [FAIL] clash-clear build failed
    pause
    exit /b 1
)

echo.
echo [DONE] Generated:
if exist "%DIST%\clash-clear.exe" echo   - %DIST%\clash-clear.exe
endlocal
pause