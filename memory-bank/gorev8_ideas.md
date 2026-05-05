# Ayarlar Görünüm ve Güvenlik İyileştirme Fikirleri

## Görünüm Ayarları Önerileri

### 1. Yazı Tipi Ayarları
- Font ailesi seçimi (Segoe UI, Consolas, Arial, vb.)
- Font boyutu (küçük, normal, büyük)
- Kod snippet'leri için monospace font

### 2. Kart Görünümü
- Kart boyutu (kompakt, normal, geniş)
- Thumbnail boyutu (küçük, orta, büyük)
- Grid vs Liste görünümü

### 3. Renk Özelleştirme
- Accent rengi seçici
- Özel tema oluşturma
- Koyu/açık mod zamanlanmış geçiş

### 4. Animasyonlar
- Animasyonları aç/kapat
- Animasyon hızı (yavaş, normal, hızlı)

### 5. Pencere Ayarları
- Varsayılan pencere boyutu
- Açılış pozisyonu (merkez, son konum, imleç yanı)
- Şeffaflık seviyesi

### 6. Sekme Düzeni
- Sekme sıralaması özelleştirme
- Gizlenecek sekmeler
- Varsayılan sekme

## Güvenlik İyileştirme Önerileri

### 1. Google Authenticator / TOTP Entegrasyonu
```
Kullanım Senaryoları:
1. Uygulama açılışında kod isteme
2. Hassas verileri görüntülerken kod isteme
3. Ayarlar değişikliğinde kod isteme

Implementasyon:
- pyotp kütüphanesi kullanılabilir
- QR kod ile setup (qrcode kütüphanesi)
- Secret key güvenli saklanmalı (Windows Credential Manager)
```

### 2. Biyometrik Kimlik Doğrulama (Windows Hello)
- Yüz tanıma ile giriş
- Parmak izi ile giriş
- PIN yedek seçeneği

### 3. Otomatik Kilit
- X dakika işlem yapılmayınca kilitle
- Minimeze edilince kilitle
- Ekran kilitlenince kilitle

### 4. Şifre Politikası
- Minimum şifre uzunluğu
- Karmaşıklık gereksinimleri
- Şifre süresi dolumu

### 5. Audit Log
- Kim ne zaman erişti
- Hangi öğeler kopyalandı/silindi
- Başarısız giriş denemeleri

### 6. Veri Temizleme
- Belirli yaştan büyük öğeleri otomatik sil
- Çıkışta geçmişi temizle seçeneği
- Güvenli silme (overwrite)

### 7. Export/Import Güvenliği
- Export dosyasını şifrele
- Import öncesi doğrulama
- Şifreli yedekleme

## OCR Alternatifleri

### Eğer Tesseract Kurulmak İstenmiyorsa:
1. **Windows OCR API** - Windows 10+ ile birlikte gelir
2. **EasyOCR** - PyTorch tabanlı, kolay kurulum
3. **PaddleOCR** - Çince/İngilizce için iyi
4. **Online API** - Google Vision, Azure OCR (internet gerekli)

### Windows OCR Implementasyonu:
```python
# Windows.Media.Ocr kullanarak
import winrt.windows.media.ocr as ocr
import winrt.windows.graphics.imaging as imaging

async def windows_ocr(image_path):
    engine = await ocr.OcrEngine.try_create_from_language(...)
    result = await engine.recognize_async(...)
    return result.text
```

## Öncelik Sıralaması

1. **Google Authenticator** - Güvenlik için kritik
2. **Otomatik kilit** - UX güvenlik dengesi
3. **Font boyutu** - Erişilebilirlik
4. **Kart boyutu** - Görünüm tercihi
5. **Windows OCR** - Tesseract alternatifi

## Teknik Notlar

### TOTP İmplementasyonu için:
```bash
pip install pyotp qrcode[pil]
```

```python
import pyotp
import qrcode

# Setup
secret = pyotp.random_base32()
totp = pyotp.TOTP(secret)

# QR oluştur
uri = totp.provisioning_uri(name="user@email.com", issuer_name="TaxClip")
qr = qrcode.make(uri)
qr.save("totp_setup.png")

# Doğrulama
is_valid = totp.verify("123456")
```
