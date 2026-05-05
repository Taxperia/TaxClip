@echo off
setlocal

REM Sadece uygulamanin exe surecini kapat
taskkill /IM TaxClip.exe /F >nul 2>&1

REM Temizle
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM ICO ikonunu üret
python tools\make_icon.py

REM _internal yerine runtime kullanarak derle
python -m PyInstaller --noconfirm --onedir ^
 --noconsole ^
 --name TaxClip ^
 --contents-directory runtime ^
 --icon assets/icons/logo.ico ^
 --version-file version_info.txt ^
 --add-data "assets;assets" ^
 --add-data "styles;styles" ^
 --add-data "version.txt;." ^
 --collect-submodules PySide6.QtSvg ^
 --collect-submodules PySide6.QtMultimedia ^
 main.py

echo.
echo Cikti: dist\TaxClip\TaxClip.exe ve dist\TaxClip\runtime\
pause
