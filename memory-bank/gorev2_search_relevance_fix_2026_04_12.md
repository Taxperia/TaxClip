# Görev 2 - Arama Alaka Düzeyi Düzeltmesi

## Tarih: 12 Nisan 2026

### Sorun

- Arama kutusuna yazılan ifade yerine alakasız veya farklı içerikler görünüyordu.
- Özellikle kısa aramalarda kelimenin ortası/sonundaki benzer parçalar yanlış eşleşme üretiyordu.
- Türkçe karakter farkları (`cizim` / `çizim`, `sifre` / `şifre`) arama kalitesini düşürüyordu.

### Yapılan değişiklikler

- `clipstack/storage.py` içindeki arama normalizasyonu güçlendirildi.
- Arama metni artık Unicode normalize ediliyor ve Türkçe karakter farkları daha toleranslı ele alınıyor.
- Kısa sorgular için gevşek `substring contains` eşleşmesi kapatıldı.
  - Artık kısa sorgular öncelikle tam kelime veya kelime başı eşleşmesi istiyor.
  - Böylece `tal` yazınca `italy` gibi alakasız sonuçlar gelmiyor.
- Uzun sorgular için kontrollü fuzzy arama korundu.
- `clipstack/ui/main_window.py` içinde:
  - Normal arama için varsayılan fuzzy threshold sıkılaştırıldı.
  - Ekrandaki widget filtresi ile veritabanı araması aynı normalize mantığına taşındı.

### Beklenen sonuç

- Kullanıcının yazdığı terimle gerçekten ilgili kayıtlar üstte görünmeli.
- Kısa aramalarda yanlış/dağınık sonuçlar ciddi şekilde azalmalı.
- Türkçe karakterli içerikler ASCII benzeri girişlerle daha tutarlı bulunmalı.
