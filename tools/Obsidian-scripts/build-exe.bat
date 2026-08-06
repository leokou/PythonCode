@echo off
REM ---------------------------------------------------------------------------
REM Obsidian scripts - one-click EXE packaging
REM   Targets (this dir, tools\Obsidian-scripts):
REM     - home-to-mulu-sync.py  -> home-to-mulu-sync.exe
REM     - index-updater.py      -> index-updater.exe
REM     - mulu-to-home-sync.py  -> mulu-to-home-sync.exe
REM   obsidian_common.py is a shared module, bundled into each EXE automatically.
REM   obsidian_common.py and README.md are also copied to the output dir.
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

REM ---- Build the entry scripts (obsidian_common auto-bundled) ----
for %%S in (home-to-mulu-sync index-updater mulu-to-home-sync rename-check) do (
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

REM ---- Copy shared module and docs ----
echo ===================================================================
echo [COPY] obsidian_common.py / README.md
echo ===================================================================
copy /y "obsidian_common.py" "%DIST%" >nul
copy /y "README.md" "%DIST%" >nul

echo.
echo [DONE] Generated in %DIST%:
for %%S in (home-to-mulu-sync index-updater mulu-to-home-sync rename-check) do (
    if exist "%DIST%\%%S.exe" echo   - %DIST%\%%S.exe
)
if exist "%DIST%\obsidian_common.py" echo   - %DIST%\obsidian_common.py
if exist "%DIST%\README.md" echo   - %DIST%\README.md
endlocal
pause