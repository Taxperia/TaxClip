# ClipStack (Windows 10 Clipboard Geçmişi)

Basit, modern görünümlü bir pano geçmişi uygulaması:
- Metin ve görselleri otomatik kaydeder (SQLite).
- Global kısayol ile geçmiş penceresini açar (varsayılan: Win+V; gerekirse Ctrl+Shift+V).
- Sistem tepsisinde çalışır, Windows başlangıcında otomatik başlatılabilir.
- Kart tasarımlı arayüz: hover ile kopyala, büyüt, favori, sil.

## Kurulum

1) Python 3.10+ kurulu olsun.
2) Bağımlılıklar:
```bash
pip install -r requirements.txt
```

3) Çalıştır:
```bash
python main.py
```

İlk çalıştırmada, Windows ile otomatik başlatma etkinleştirilir (tepsi menüsünden kapatabilirsiniz).

## Kısayol Hakkında

- Windows 10'da `Win+V`, Windows'un kendi pano geçmişi için ayrılmıştır. Uygulama önce `Win+V` kaydı dener.
- Eğer başarısız olursa veya OS tarafından engellenirse otomatik olarak `Ctrl+Shift+V`'ye geri döner ve tepsi bildirimi gösterir.
- Yönetici olarak çalıştırmak, bazı sistemlerde kısayol bastırmayı kolaylaştırır.

Kısayolu değiştirmek isterseniz:
- `%AppData%/ClipStack/settings.json` dosyasındaki `"hotkey"` değerini değiştirip uygulamayı yeniden başlatın.
- Örnek: `"hotkey": "ctrl+alt+h"`

Desteklenen örnekler için `keyboard` kütüphanesi formatına bakın (örn. `windows+v`, `ctrl+shift+v`, `alt+space`).

## Kullanım

- Uygulama arka planda çalışır ve sistem tepsisinde bir ikon olarak görünür.
- Global kısayola bastığınızda geçmiş penceresi açılır.
- Kartın üzerine gelince kopyala, büyüt, sil, favori butonları görünür.
- Kartın kendisine tıklamak, öğeyi panoya kopyalar ve varsayılan olarak pencereyi kapatır (settings.json'da `"hide_after_copy": true/false`).

Arama çubuğu ile metin/HTML içeriğinde arama yapabilirsiniz.

## Kalıcılık

- Veritabanı dosyası: `%AppData%/ClipStack/clipstack.db`
- Ayarlar dosyası: `%AppData%/ClipStack/settings.json`

## Windows ile Başlatma

- Tepsi menüsünden "Windows ile Başlat" seçeneği ile aç/kapat.
- Kayıt defteri: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` altında `ClipStack` değeri.

## Derleme (EXE)

PyInstaller ile tek dosya exe üretmek için:

```bash
pip install pyinstaller
pyinstaller --noconsole --name ClipStack --icon assets/icons/clipboard.ico main.py
```

Notlar:
- `--noconsole` konsol penceresini gizler.
- İkon için `.ico` dosyasına ihtiyacınız var. SVG'den dönüştürüp `assets/icons/clipboard.ico` ekleyebilirsiniz.

## Bilinen Sınırlamalar

- `Win+V` işletim sistemi tarafından rezerve edilebilir; bu durumda bastırmak her sistemde mümkün olmayabilir.
- `keyboard` kütüphanesi bazı durumlarda global kancalar için yönetici izni gerektirebilir.
- Şimdilik pano dosya listeleri (CF_HDROP) gibi gelişmiş türler desteklenmiyor. Metin/HTML/görsel odaklıdır.
