@echo off
setlocal

REM Çalışan süreçleri kapat (kilitlenme olmasın)
taskkill /IM TaxClip.exe /F >nul 2>&1
taskkill /IM pythonw.exe /F >nul 2>&1
taskkill /IM python.exe /F >nul 2>&1

REM Temizle
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM _internal yerine runtime kullanarak derle
pyinstaller --noconfirm --onedir ^
--noconsole ^
 --name TaxClip ^
 --contents-directory runtime ^
 --icon assets/icons/image.png ^
 --add-data "assets;assets" ^
 --add-data "styles;styles" ^
 --collect-submodules PySide6.QtSvg ^
 main.py

echo.
echo Cikti: dist\TaxClip\TaxClip.exe ve dist\TaxClip\runtime\
pause