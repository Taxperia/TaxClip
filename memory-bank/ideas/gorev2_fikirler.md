# Görev 2 - Fikirler ve Öneriler

## Tarih: 27 Aralık 2025

### Arama Sistemi İyileştirmeleri

#### 1. Arama Geçmişi
- Son aramaları kaydet
- Arama kutusunda dropdown olarak göster
- "Son aramalar" başlığı altında

#### 2. Arama Filtreleri Kısayolları
- `type:text` → sadece metinlerde ara
- `type:image` → sadece resimlerde ara
- `date:today` → bugünkü içeriklerde ara
- `fav:true` → sadece favorilerde ara

#### 3. Regex Desteği
- `/pattern/` formatında regex araması
- Gelişmiş kullanıcılar için

#### 4. Etiket (Tag) Sistemi
- İçeriklere etiket eklenebilir
- `#tag` ile etiketlerde arama
- Otomatik etiket önerileri

#### 5. Önizleme Modu
- Arama sonuçlarında içerik önizlemesi
- Bulunan metni vurgulama (highlight)

### Performans İyileştirmeleri

#### 1. Önbellek (Cache)
- Sık aranan terimleri önbelleğe al
- Son 10-20 arama sonucunu sakla

#### 2. Arka Plan Araması
- Yazarken arama yapmak yerine debounce kullan
- 300ms bekleme süresi (mevcut)

#### 3. Sanal Liste (Virtual List)
- Binlerce sonuç için sanal scroll
- Sadece görünür öğeleri render et

### UX İyileştirmeleri

#### 1. Arama İpuçları
- İlk açılışta kısa arama ipuçları göster
- "Fuzzy search desteklenir" gibi

#### 2. Klavye Kısayolları
- `Ctrl+F` → Arama kutusuna odaklan
- `Esc` → Aramayı temizle
- `Enter` → İlk sonucu seç

#### 3. Sesli Geri Bildirim
- Sonuç bulunduğunda kısa ses
- Sonuç bulunamadığında farklı ses

### OCR Entegrasyonu

#### 1. Resim İçeriklerinde Arama
- Tesseract ile OCR yapılmış metinlerde de ara
- "OCR sonuçlarında da ara" seçeneği

#### 2. Otomatik OCR
- Her resim kaydedildiğinde otomatik OCR
- Arka planda yapılabilir
