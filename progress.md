# Progress

Son güncelleme: 2026-04-09

Bu dosya, proje ilerlemesini faz bazlı takip etmek için ana pano olarak kullanılır.
Görev numaraları `memory-bank` içindeki notlarla hizalanmıştır.

Durum anahtarı:
- [ ] Bekliyor
- [-] Aktif çalışma
- [~] Kısmen tamamlandı / tekrar test gerekli
- [x] Tamamlandı

## Çalışma Kuralları

- Her görev sonrası kod tekrar okunacak ve regresyon kontrolü yapılacak.
- Her görev için `memory-bank/` altında değişiklik notu tutulacak.
- Gerekirse `memory-bank/ideas/` altında fikir ve sonraki adım notları tutulacak.
- Faz kapatılmadan önce mümkünse kısa smoke test yapılacak.

## Faz Özeti

| Faz | Başlık | Durum | Referans |
|-----|--------|-------|----------|
| 0 | Planlama ve takip | [x] | `progress.md` |
| 1 | Uygulama kimliği, tray ve temel ayarlar | [~] | `memory-bank/gorev1_degisiklikler.md` |
| 2 | Veri, arama ve lazy loading | [~] | `memory-bank/gorev2_degisiklikler.md` |
| 3 | Hatırlatıcılar ve reminder kartları | [x] | `memory-bank/gorev3_degisiklikler.md` |
| 4 | Snippet/ikon/tooltip UI düzeltmeleri | [~] | `memory-bank/gorev4_degisiklikler.md` |
| 5 | Liste ve todo sistemi | [~] | `memory-bank/gorev5_degisiklikler.md` |
| 6 | Çizim modülü | [x] | `memory-bank/gorev6_degisiklikler.md` |
| 7 | Video kayıt ve instant replay | [~] | `memory-bank/gorev7_degisiklikler.md` |
| 8 | Ayarlar, güvenlik ve doğrulama | [~] | `memory-bank/gorev8_degisiklikler.md` |
| 9 | Senkronizasyon ve paylaşım | [~] | `memory-bank/gorev9_degisiklikler.md` |
| 10 | Ürün yol haritası | [x] | `memory-bank/ideas/gorev10_kapsamli_oneriler.md` |
| 11 | Stabilite ve performans backlogu | [ ] | Bu dosya |

## Faz 0 - Planlama ve Takip

- [x] `progress.md` oluşturuldu
- [x] Fazlar `memory-bank` notlarına göre yeniden hizalandı
- [x] Tamamlanan / açık fazlar ayrıştırıldı

## Faz 1 - Uygulama Kimliği, Tray ve Temel Ayarlar

Durum: [~]

Tamamlananlar:
- [x] 10 farklı tray ikonu eklendi
- [x] Hakkında alanı güncellendi
- [x] Buy Me a Coffee butonu eklendi
- [x] Dil dropdown görünümü düzeltildi
- [x] `toggle_todo` ve `ItemWidget` tarafındaki bazı hatalar düzeltildi

Açık maddeler:
- [ ] Görev çubuğunda ikon / `pythonw.exe` görünme sorununu exe build ile net kapat
- [ ] Tray ikonları için bağımsız renk seçici ekle
- [ ] Print Screen sonrası bazı görsellerin `Ctrl+V` ile yapışmama sorununu çöz
- [ ] Tray bildirimi tarafındaki bozuk label veya metin sorununu bul ve düzelt
- [ ] Faz 1 için genel kod taraması ve son hata temizliği yap

Kapanış kriteri:
- [ ] Uygulama exe olarak doğru ikon ve isimle görünmeli
- [ ] Seçilen tray tasarımı ve rengi kaydedilip uygulanmalı
- [ ] Screenshot kopyaları kararlı şekilde yapıştırılabilmeli

## Faz 2 - Veri, Arama ve Lazy Loading

Durum: [~]

Tamamlananlar:
- [x] Yüklü widget dışında veritabanı seviyesinde arama eklendi
- [x] Arama sırasında loading durumu eklendi
- [x] Sonuç bulunamadı görünümü eklendi
- [x] Lazy-loaded içerikleri aramada dinamik yükleme mantığı eklendi

Açık maddeler:
- [ ] Arama kutusuna yazılanla gelen sonuçların alakasız olabildiği durumu incele
- [ ] Fuzzy search eşiği fazla agresifse daralt
- [ ] Arama davranışını büyük veri setinde tekrar test et
- [ ] Faz 2 memory-bank ve fikir notlarını gerekiyorsa güncelle

Kapanış kriteri:
- [ ] Aynı sorgu tekrarlandığında tutarlı sonuç dönmeli
- [ ] Yüklenmemiş içerik bulunabiliyor olmalı
- [ ] Sonuç yoksa boş durum, sonuç varsa doğru kartlar görünmeli

## Faz 3 - Hatırlatıcılar ve Reminder Kartları

Durum: [x]

Tamamlananlar:
- [x] Reminder ikon renkleri düzeltildi
- [x] Tema arka plan şeffaflık sorunları giderildi
- [x] Kalan süre yazısına canlı güncelleme eklendi
- [x] Snooze akışı doğrulandı

Kapanış kriteri:
- [x] Kart görünümü tüm temalarda okunaklı
- [x] Kalan süre metni canlı güncelleniyor
- [x] Erteleme akışı çalışıyor

## Faz 4 - Snippet, İkon ve Tooltip UI Düzeltmeleri

Durum: [~]

Tamamlananlar:
- [x] Snippet hover toolbar hizası düzeltildi
- [x] VSCode açma butonu ve entegrasyonu eklendi
- [x] `assets/icons/vscode.svg` eklendi
- [x] Snippet ekleme ikonu güncellendi

Açık maddeler:
- [ ] Tooltip arka plan / kontrast sorununu tüm temalarda düzelt
- [ ] VSCode ikonunun gerçek kullanımda görünümünü kontrol et
- [ ] Hover aksiyonlarının tema bağımsız tutarlılığını tekrar test et

Kapanış kriteri:
- [ ] Tooltip metinleri okunaklı olmalı
- [ ] VSCode aksiyonu ve ikon görünümü kararlı olmalı

## Faz 5 - Liste ve Todo Sistemi

Durum: [~]

Tamamlananlar:
- [x] Edit butonu eklendi
- [x] `Tümünü Sil` butonu eklendi
- [x] Kart içi görev ekleme ve modal düzenleme akışı korundu

Açık maddeler:
- [ ] Yeni liste oluşturma akışında kullanıcı deneyimini netleştir
- [ ] İkinci liste eklenince ilkinin kaybolma sorununu doğrula ve düzelt
- [ ] Liste ekranında veri yenileme senaryolarını test et
- [ ] Faz 5 memory-bank ve fikir notlarını gerekiyorsa güncelle

Kapanış kriteri:
- [ ] Birden fazla liste kaybolmadan aynı anda görünmeli
- [ ] Düzenleme, ekleme ve toplu silme akışları sorunsuz çalışmalı

## Faz 6 - Çizim Modülü

Durum: [x]

Tamamlananlar:
- [x] Çizimlerin yanlış formatta kaydedilmesi düzeltildi
- [x] Base64 thumbnail / önizleme akışı düzeltildi
- [x] İlk çizimlerin kaybolması ve üst üste binme problemi çözüldü
- [x] Çift `Yeni Çizim` butonu temizlendi
- [x] Üst bar görünürlük mantığı düzeltildi

Kapanış kriteri:
- [x] Yeni çizimler doğru kaydediliyor
- [x] Eski çizimler doğru yükleniyor
- [x] Çizim sekmesindeki aksiyon düzeni net

## Faz 7 - Video Kayıt ve Instant Replay

Durum: [~]

Tamamlananlar:
- [x] Ayar değişince video recorder yeniden yüklenebilir hale getirildi
- [x] Instant Replay thread ve circular buffer mantığı eklendi
- [x] Overlay'e mikrofon ve replay durumu eklendi
- [x] Runtime ayar değişim bildirimi bağlandı

Açık maddeler:
- [ ] Gerçek video dosyasının neden kaydedilmediğini çöz
- [ ] Ses kayması senaryolarını gerçek kullanımda test et
- [ ] FFmpeg / OpenCV eksikliği varsa fallback davranışını netleştir
- [ ] Faz 7 memory-bank ve fikir notlarını güncelle

Kapanış kriteri:
- [ ] Normal kayıt dosya üretmeli
- [ ] Instant Replay son N saniyeyi kaydedebilmeli
- [ ] Overlay durumu kayıt moduyla uyumlu görünmeli

## Faz 8 - Ayarlar, Güvenlik ve Doğrulama

Durum: [~]

Tamamlananlar:
- [x] AES-256 şifreleme mantığı doğrulandı
- [x] Hassas veri algılama ve maskeleme kontrol edildi
- [x] `dedupe_window_ms` ayarlara bağlandı
- [x] `max_items` kuralı storage tarafında uygulanır hale getirildi
- [x] OCR sisteminin Tesseract bağımlılığı not edildi
- [x] Görünüm ve güvenlik fikirleri notlandı

Açık maddeler:
- [ ] Genel ayarlardaki hızlı aksiyon hotkey'lerini uçtan uca test et
- [ ] Menü dizilimlerini tüm modüllerde standartlaştır
- [ ] OCR gerçekten kullanılacaksa kurulum geri bildirimi ekle, kullanılmayacaksa kaldırmayı değerlendir
- [ ] TOTP / Google Authenticator entegrasyonu kararını netleştir

Kapanış kriteri:
- [ ] Tüm ayar ekranları aynı düzen mantığını kullanmalı
- [ ] Hotkey ayarları gerçekten çalışmalı
- [ ] Güvenlik seçeneklerinin ne yaptığı kullanıcıya net görünmeli

## Faz 9 - Senkronizasyon ve Paylaşım

Durum: [~]

Tamamlananlar:
- [x] Senkronizasyon sekmesi eklendi
- [x] JSON dışa / içe aktarma akışı eklendi
- [x] Auto sync toggle ve interval alanları eklendi
- [x] Google Drive bağlantısı için placeholder eklendi

Açık maddeler:
- [ ] Google Drive OAuth akışını tamamla
- [ ] Manuel senkronizasyonu gerçek işlemle bağla
- [ ] Sunucu tabanlı paylaşım mimarisini netleştir
- [ ] Çakışma çözümü ve delta sync ihtiyacını değerlendir

Kapanış kriteri:
- [ ] En az bir gerçek sync sağlayıcısı çalışmalı
- [ ] Export/import veri kaybı olmadan çalışmalı
- [ ] Kullanıcı bağlantı durumunu net görebilmeli

## Faz 10 - Ürün Yol Haritası

Durum: [x]

Tamamlananlar:
- [x] Kapsamlı öneri dokümanı oluşturuldu
- [x] Yeni özellikler, güvenlik, UX, teknik ve entegrasyon başlıkları yazıldı

Kapanış kriteri:
- [x] Uzun vadeli geliştirme alanları dokümante edildi

## Faz 11 - Stabilite ve Performans Backlogu

Durum: [ ]

Açık maddeler:
- [ ] Ayarlar modalı açılırken yaşanan kasma ve donmayı profil et
- [ ] Genel uygulama hız optimizasyonları yap
- [ ] Büyük veri setlerinde ilk açılış, scroll ve filtre performansını ölç
- [ ] Gereksiz tekrar render / widget üretimlerini azalt

Kapanış kriteri:
- [ ] Ayarlar modalı hissedilir gecikme olmadan açılmalı
- [ ] Uzun kullanımda UI akıcılığı korunmalı

## Öncelikli Sıra

Önerilen çalışma sırası:
1. Faz 1: exe ikon, screenshot paste ve tray kalan işleri kapat
2. Faz 2: arama doğruluğunu netleştir
3. Faz 7: video dosyası üretilmeme sorununu çöz
4. Faz 5: çoklu liste kaybolma hatasını kapat
5. Faz 8 ve 11: ayar ekranı tutarlılığı ve performans

## Hızlı Komutlar

Bana şu şekilde görev verebilirsin:

- `Faz 1'i kapat`
- `Faz 2'de arama neden yanlış sonuç veriyor ona bak`
- `Faz 7'de video neden kaydetmiyor çöz`
- `Faz 11 performans backlogunu başlat`
