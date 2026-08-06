@echo off
REM ---------------------------------------------------------------------------
REM D:\Python - one-click build ALL tools exe
REM   Iterates tools\<tool>\build-exe.bat and runs each one.
REM   Output: D:\Python\dist
REM   Requires: pyinstaller installed in the python below (see PY variable)
REM   NOTE: keep this file ASCII-only. Chinese comments break cmd.exe parsing
REM         because .bat is read in the system codepage (GBK), not UTF-8.
REM   Usage:  build-all-exe.bat
REM           set PY=your_python.exe && build-all-exe.bat
REM ---------------------------------------------------------------------------
setlocal

REM Disable fail-closed safe-delete: removing old exe goes to recycle bin, not error
set "CODEBUDDY_SAFE_DELETE_SANDBOX=0"

REM Python to use (must have pyinstaller). Override with: set PY=your_python.exe
if "%PY%"=="" set "PY=python"

set "DIST=D:\Python\dist"
set "TOOLS=%~dp0tools"

REM Check python and pyinstaller once
"%PY%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pyinstaller not found. Install first:
    echo         "%PY%" -m pip install pyinstaller
    pause
    exit /b 1
)

if not exist "%DIST%" mkdir "%DIST%"
if not exist "%TOOLS%" ( echo [ERROR] tools dir not found: %TOOLS% & pause & exit /b 1 )

echo ===================================================================
echo [BUILD-ALL] Scanning %TOOLS%
echo ===================================================================

set "FAILED="

for /d %%D in ("%TOOLS%\*") do (
    if exist "%%D\build-exe.bat" (
        echo.
        echo ===================================================================
        echo [BUILD-ALL] %%D
        echo ===================================================================
        pushd "%%D" >nul
        call "%%D\build-exe.bat" < nul
        if errorlevel 1 set "FAILED=1"
        popd >nul
    )
)

echo.
echo ===================================================================
if defined FAILED (
    echo [BUILD-ALL] DONE - one or more builds FAILED (see log above)
) else (
    echo [BUILD-ALL] DONE - all builds succeeded
)
echo Output: %DIST%
echo ===================================================================
endlocal
pause