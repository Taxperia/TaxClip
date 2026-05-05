# Görev 1 - Taskbar ve Exe Kimliği Düzeltmesi

## Tarih: 12 Nisan 2026

### Yapılan değişiklikler

- `clipstack/startup.py` içinde startup çözümleme akışı güçlendirildi.
- Uygulama kaynak koddan çalışsa bile proje içinde `dist/TaxClip/TaxClip.exe` varsa startup kısayolu artık doğrudan bu exe'yi hedefliyor.
- `python -c` gibi senaryolarda `sys.argv[0]` geçersiz olduğunda fallback olarak proje kökündeki `main.py` seçiliyor.
- Startup kısayolu için ikon kaynağı iyileştirildi:
  - Önce doğrudan `assets/icons/clipboard.ico` kopyalanıyor.
  - Bu yoksa eski SVG -> ICO üretim fallback'i devreye giriyor.
  - Hedef `TaxClip.exe` ise kısayol ikonu doğrudan exe'den alınıyor.
- `clipstack/app.py` içinde görev çubuğu/pencere ikonu ile tray ikonu ayrıldı.
  - Görev çubuğu ve pencere ikonu artık sabit uygulama ikonu (`clipboard.ico` / `clipboard.svg`).
  - Kullanıcı seçtiği tray ikonu sadece sistem tepsisinde kullanılıyor.
- Uygulama her açılışta startup ayarını yeniden senkronlayacak şekilde güncellendi.
  - Eski klasöre bakan veya `pythonw.exe` hedefleyen kısayollar otomatik olarak güncellenebilecek.
- PyInstaller çıktısına Windows dosya metadata bilgileri eklendi.
  - `version_info.txt` oluşturuldu.
  - `ClipStack.spec`, `TaxClip.spec` ve `build_with_runtime_dir.bat` bu metadata'yı kullanacak şekilde güncellendi.

### Beklenen sonuç

- Windows başlangıcında çalışan süreç `pythonw.exe` yerine `TaxClip.exe` olacak.
- Görev çubuğunda ve kısayol ikonunda generic/boş ikon yerine uygulama ikonu görünecek.
- Taşınmış klasörler veya eski sürüm yolları yüzünden bozuk kalan startup kısayolu mevcut açılışta kendini düzeltebilecek.

### Doğrulama notu

- Bu makinede mevcut startup kısayolunun eski `copyv6.1` klasörüne ve `pythonw.exe`ye baktığı doğrulandı.
- Düzeltme sonrası hedefin `copyv6.2\\dist\\TaxClip\\TaxClip.exe` olması beklenir.
