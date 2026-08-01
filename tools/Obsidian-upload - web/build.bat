@echo off
chcp 65001 >nul
rem ============================================
rem Obsidian-upload EXE 打包脚本
rem 输出: dist\Obsidian-upload.exe （单文件，无控制台）
rem 依赖: pyinstaller, pywebview, Pillow, requests, pystray, keyboard
rem ============================================
cd /d "%~dp0"

pyinstaller --noconfirm --clean ^
  --onefile ^
  --windowed ^
  --name Obsidian-upload ^
  --add-data "web;web" ^
  --add-data "config.json;." ^
  main.py

if errorlevel 1 (
  echo [ERROR] 打包失败
  pause
  exit /b 1
)

echo.
echo [OK] 已生成 dist\Obsidian-upload.exe
echo 提示: config.json 会一并打入，可复制到 EXE 旁边自定义配置。
pause
