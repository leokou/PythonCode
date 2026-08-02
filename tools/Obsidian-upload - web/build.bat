@echo off
chcp 65001 >nul
rem ============================================
rem Obsidian-upload EXE Build Script
rem Output: dist\Obsidian-upload.exe (single file, no console)
rem Dependencies: pyinstaller, pywebview, Pillow, requests, pystray, keyboard
rem ============================================
cd /d "%~dp0"

pyinstaller --noconfirm --clean ^
  --onefile ^
  --windowed ^
  --name Obsidian-upload ^
  --icon app.ico ^
  --hidden-import=keyboard ^
  --hidden-import=pystray ^
  --hidden-import=webview ^
  --hidden-import=webview.platforms.edgechromium ^
  --hidden-import=commands ^
  --hidden-import=commands.logger ^
  --hidden-import=commands.app_utils ^
  --hidden-import=commands.hotkey_manager ^
  --hidden-import=storage ^
  --hidden-import=pages ^
  --hidden-import=settings ^
  --hidden-import=file_assoc ^
  --hidden-import=window_manager ^
  --hidden-import=layout_store ^
  --hidden-import=history ^
  --hidden-import=workspace ^
  --hidden-import=file_tree ^
  --hidden-import=file_explorer ^
  --hidden-import=file_ops ^
  --hidden-import=search_engine ^
  --hidden-import=capture ^
  --collect-submodules=keyboard ^
  --collect-submodules=pystray ^
  --add-data "web;web" ^
  --add-data "tools;tools" ^
  --add-data "config.json;." ^
  --add-data "commands;commands" ^
  --add-data "app.ico;." ^
  main.py

if errorlevel 1 (
  echo [ERROR] Build failed
  pause
  exit /b 1
)

echo.
echo [OK] dist\Obsidian-upload.exe generated successfully
echo Tip: config.json is embedded, copy beside EXE to customize.
pause