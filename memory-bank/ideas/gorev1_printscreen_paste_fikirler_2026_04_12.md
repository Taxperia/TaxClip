# Görev 1 - Print Screen / Clipboard için ek fikirler

## Tarih: 12 Nisan 2026

- Ayarlara isteğe bağlı bir `clipboard normalization` toggle eklenebilir; varsayılan açık kalır.
- Debug modunda clipboard image formatları (`mimeData().formats()`) kısa log olarak yazdırılabilir; farklı Windows araçları daha hızlı ayrıştırılır.
- Çok büyük ekran görüntülerinde memory baskısını azaltmak için normalize etmeden önce boyut eşiği kontrolü eklenebilir.
