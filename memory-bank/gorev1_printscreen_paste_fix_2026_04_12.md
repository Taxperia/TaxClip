# Görev 1 - Print Screen Sonrası Yapıştırma Düzeltmesi

## Tarih: 12 Nisan 2026

### Sorun

- Windows `Print Screen` / ekran alıntısı sonrası görüntü bazen panoda görünse bile `Ctrl+V` ile hedef uygulamaya yapışmıyordu.
- Aynı görsel TaxClip geçmişine düştüğü için kullanıcı uygulamadan tekrar kopyalayınca yapıştırma çalışıyordu.

### Kök neden

- Dış kaynaktan gelen bazı ekran görüntüleri panoya ham bitmap formatlarıyla düşüyor.
- Bu durumda bazı uygulamalar `Ctrl+V` tarafında daha kararlı çalışan `PNG + imageData` kombinasyonunu göremeyebiliyor.
- TaxClip içinden tekrar kopyalama zaten bu güvenli formatları yazdığı için ikinci denemede yapıştırma başarılı oluyordu.

### Yapılan değişiklik

- `clipstack/clipboard_watcher.py` güncellendi.
- Watcher artık dışarıdan gelen resim clipboard içeriğini aldıktan sonra formatları kontrol ediyor.
- Eğer panoda PNG benzeri bir format yoksa kısa bir gecikmeyle aynı görselin hâlâ panoda olup olmadığını doğruluyor.
- İçerik değişmemişse görseli `copy_to_clipboard_safely()` ile yeniden yazarak clipboard'u stabilize ediyor.

### Beklenen sonuç

- `Print Screen` veya benzeri ekran alıntılarından sonra ilk `Ctrl+V` daha tutarlı çalışmalı.
- Kullanıcının TaxClip içinden tekrar kopyalama ihtiyacı belirgin şekilde azalmalı.
- Clipboard geçmişine ekleme davranışı korunmalı.
