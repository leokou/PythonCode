@echo off
REM ---------------------------------------------------------------------------
REM sync-GitHub - build exe
REM   Targets (this dir, tools\sync-GitHub):
REM     - skill-sync-GitHub.py      -> skill-sync-GitHub.exe
REM     - skill-sync-agentcode.py   -> skill-sync-agentcode.exe
REM     - python-code-sync-GitHub.py-> python-code-sync-GitHub.exe
REM     - python-local-backup.py    -> python-local-backup.exe
REM   Output: D:\Python\dist
REM   Requires: pyinstaller installed in the python below (see PY variable)
REM   NOTE: keep this file ASCII-only. Chinese comments break cmd.exe parsing
REM         because .bat is read in the system codepage (GBK), not UTF-8.
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

REM ---- Build all four entry scripts ----
for %%S in (skill-sync-GitHub skill-sync-agentcode python-code-sync-GitHub python-local-backup) do (
    echo ===================================================================
    echo [BUILD] %%S.exe
    echo ===================================================================
    "%PY%" -m PyInstaller --onefile --noconfirm --clean --distpath "%DIST%" "%%S.py"
    if errorlevel 1 (
        echo [FAIL] %%S build failed
        pause
        exit /b 1
    )
)

echo.
echo [DONE] Generated in %DIST%:
for %%S in (skill-sync-GitHub skill-sync-agentcode python-code-sync-GitHub python-local-backup) do (
    if exist "%DIST%\%%S.exe" echo   - %DIST%\%%S.exe
)
endlocal
pause