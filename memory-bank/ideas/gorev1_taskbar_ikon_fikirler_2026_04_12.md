# Görev 1 - Taskbar ve Startup için ek fikirler

## Tarih: 12 Nisan 2026

- Installer eklenecekse startup kaydı uygulama içinden değil kurulum sırasında da yazılmalı.
- `TaxClip.exe` için code signing yapılırsa Windows SmartScreen ve görev yöneticisi görünümü daha güvenilir hale gelir.
- Gelecekte MSI/Inno Setup kurulumu eklenirse `AppUserModelID`, Start Menu kısayolu ve uninstall kaydı aynı paket içinde yönetilmeli.
- Uygulama sürümü artırıldığında `version_info.txt` ile `version.txt` tek kaynaktan üretilecek küçük bir build script eklenebilir.
