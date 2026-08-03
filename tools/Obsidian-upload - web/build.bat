@echo off
chcp 65001 >nul
rem ============================================
rem Obsidian-upload EXE Build Script
rem Output: dist\Obsidian-upload.exe (single file, no console)
rem
rem Optimization:
rem   - exclude-module numpy   : not used, saves ~30 MB
rem   - removed collect-all pkg_resources / copy-metadata setuptools : saves ~6 MB
rem   - UPX compression (auto-detect) : saves 30-50% on final EXE
rem
rem Dependencies: pyinstaller, pywebview, Pillow, requests, pystray, keyboard
rem Structure: lib/core (main/api/window_manager/settings)
rem            lib/backend (storage/markdown/uploader/capture/search_engine)
rem            lib/modules (theme_manager/layout_store/workspace/pages/history/...)
rem            frontend (HTML/CSS/JS) / commands / tools / config
rem ============================================
cd /d "%~dp0"

pyinstaller --noconfirm --clean ^
  --onefile ^
  --windowed ^
  --name Obsidian-upload ^
  --icon app.ico ^
  --paths . ^
  --upx-dir "C:\Users\leokou\AppData\Local\upx\upx-5.2.0-win64" ^
  --exclude-module numpy ^
  --exclude-module cryptography ^
  --exclude-module PIL._avif ^
  --paths tools\to-do ^
  --hidden-import=pystray ^
  --hidden-import=webview ^
  --hidden-import=webview.platforms.edgechromium ^
  --hidden-import=commands ^
  --hidden-import=commands.logger ^
  --hidden-import=commands.app_utils ^
  --hidden-import=commands.hotkey_manager ^
  --hidden-import=commands.performance ^
  --hidden-import=lib ^
  --hidden-import=lib.core ^
  --hidden-import=lib.backend ^
  --hidden-import=lib.modules ^
  --hidden-import=lib.core.api ^
  --hidden-import=lib.core.main ^
  --hidden-import=lib.core.window_manager ^
  --hidden-import=lib.core.settings ^
  --hidden-import=lib.backend.storage ^
  --hidden-import=lib.backend.markdown ^
  --hidden-import=lib.backend.uploader ^
  --hidden-import=lib.backend.capture ^
  --hidden-import=lib.backend.search_engine ^
  --hidden-import=lib.backend.clipboard_parser ^
  --hidden-import=lib.backend.html_converter ^
  --hidden-import=lib.backend.image_handler ^
  --hidden-import=lib.modules.pages ^
  --hidden-import=lib.modules.file_assoc ^
  --hidden-import=lib.modules.layout_store ^
  --hidden-import=lib.modules.history ^
  --hidden-import=lib.modules.workspace ^
  --hidden-import=lib.modules.file_tree ^
  --hidden-import=lib.modules.file_explorer ^
  --hidden-import=lib.modules.file_ops ^
  --hidden-import=lib.modules.favorites ^
  --hidden-import=lib.modules.theme_manager ^
  --hidden-import=lib.modules.canvas_server ^
  --hidden-import=lib.modules.todo_window ^
  --hidden-import=msal ^
  --collect-submodules=pystray ^
  --collect-submodules=lib ^
  --add-data "frontend;frontend" ^
  --add-data "tools\drawnix;tools\drawnix" ^
  --add-data "tools\clean_empty_lines;tools\clean_empty_lines" ^
  --add-data "tools\to-do;tools\to-do" ^
  --add-data "tools\tools.json;tools" ^
  --add-data "config/config.json;config" ^
  --add-data "commands;commands" ^
  --add-data "app.ico;." ^
  lib\core\main.py

if errorlevel 1 (
  echo [ERROR] Build failed
  pause
  exit /b 1
)

rem 归档 spec 文件到 spec/ 目录（保持项目根整洁）
if not exist spec mkdir spec
if exist Obsidian-upload.spec move /Y Obsidian-upload.spec spec\ >nul 2>&1

echo.
echo [OK] dist\Obsidian-upload.exe generated successfully
echo Tip: config.json is embedded, copy beside EXE to customize.
pause
