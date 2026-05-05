# Görev 1 - Fikirler ve Öneriler

## Tarih: 27 Aralık 2025

### Tepsi İkonu İyileştirmeleri

#### 1. Animasyonlu İkonlar
- Yeni kopyalama yapıldığında ikon kısa süreliğine animasyon gösterebilir
- Windows 10/11'de desteklenen overlay icon özelliği kullanılabilir

#### 2. Bildirim Sayacı
- Tray ikonunun üzerinde okunmamış öğe sayısı gösterilebilir
- Windows'ta overlay badge ile yapılabilir

#### 3. Dinamik Renk
- Sistemin accent rengine göre ikon rengi otomatik değişebilir
- Windows'tan QSettings ile alınabilir

### Hakkında Sekmesi

#### 1. Sürüm Kontrolü
- "Güncelleme Kontrol Et" butonu eklenebilir
- GitHub releases API ile karşılaştırma

#### 2. İstatistikler
- Toplam kopyalanan öğe sayısı
- En çok kopyalanan metin
- Kullanım süresi

#### 3. Sosyal Medya Linkleri
- Twitter/X
- Discord
- GitHub

### Genel İyileştirmeler

#### 1. Tema Önizleme
- Tema seçerken canlı önizleme
- Küçük bir demo pencere

#### 2. Ayar Profilleri
- Farklı profiller kaydetme (İş, Ev, vb.)
- Hızlı profil değiştirme

#### 3. Klavye Kısayolları Referansı
- Tüm kısayolları gösteren popup
- ? tuşu ile açılabilir

### Teknik Öneriler

#### 1. ICO Dosyası
- Windows için .ico formatında tray ikonu daha iyi performans gösterir
- SVG render yerine direkt ICO kullanılabilir

#### 2. Görev Çubuğu İkonu
- PyInstaller ile build edildiğinde --icon parametresi kullanılmalı
- .spec dosyasına icon= eklenmeli

#### 3. Uygulama İsmi
- Task Manager'da "TaxClip" görünmesi için:
  - `multiprocessing.set_start_method()` kullanılabilir
  - ya da .spec dosyasında name= düzenlenmeli
