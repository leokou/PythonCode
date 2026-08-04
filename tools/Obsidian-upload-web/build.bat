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

rem ============================================
rem 清理旧环境：杀掉运行中的程序 + 删除 dist 旧 EXE
rem 原因：正在运行的 Obsidian-upload.exe 会锁定 dist\Obsidian-upload.exe，
rem       导致 PyInstaller 覆盖失败（build\ 产物生成但 dist 不更新）。
rem 注意：强制结束进程，最后几秒未保存内容可能丢失（程序 3s/60s 自动保存已兜底）。
rem ============================================
echo [1/3] 关闭运行中的 Obsidian-upload 进程...
taskkill /IM Obsidian-upload.exe /F >nul 2>&1
echo [1/3] 删除 dist 旧 EXE...
if exist "dist\Obsidian-upload.exe" del /F /Q "dist\Obsidian-upload.exe" >nul 2>&1
echo [2/3] 开始打包（PyInstaller）...

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
echo [3/3] dist\Obsidian-upload.exe generated successfully
echo Tip: config.json is embedded, copy beside EXE to customize.
pause
