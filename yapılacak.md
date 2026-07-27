# Yapılacak — Uygulama Durumu (27 Temmuz 2026)

Bu listedeki maddeler koda işlendi. Özet:

## 1. Dosya ve klasör kopyalama geçmişi — TAMAMLANDI
- `ClipItemType.FILE` eklendi
- CF_HDROP / `hasUrls()` ile dosya yolları yakalanıyor (yalnızca yol saklanır)
- Kart: simge, ad, boyut, “mevcut değil” uyarısı
- Sağ tık: Dosyayı aç, Klasörde göster, Yolu kopyala
- “Dosyalar” sekmesi eklendi

## 2. Akıllı pano kartları — TAMAMLANDI
- `smart_content.py`: URL, JSON, HEX renk, e-posta, telefon, dosya yolu, kod, base64, markdown, uzun metin
- Kart başlığı + tür ikonu + akıllı bağlam menüsü eylemleri
- Meta: kaynak uygulama, kullanım sayısı, koleksiyon, hassas işaret

## 3. Gizli Pano Modu — TAMAMLANDI
- Tepsi: 5/15/30 dk ve “yeniden başlatılana kadar” duraklat
- Hariç tutulan uygulamalar (ayarlar + varsayılan parola yöneticileri)
- Hassas veri panodan otomatik temizleme (15/30/60 sn)
- Windows Hello / biyometrik kilit ayarlara ve başlangıç/idle akışına bağlandı

## 4. Klavye ile hızlı kullanım — TAMAMLANDI
- ↑↓ seçim, Enter kopyala, Ctrl+Enter yapıştır, Delete, Ctrl+P sabitle, Ctrl+F ara, Alt+1-9, Tab, Esc
- Kompakt panel (tepssi menü → “Kompakt panel”)

## 5. Sabitlenen içerikler ve koleksiyonlar — TAMAMLANDI
- `pinned` ile üstte sabitleme; favori koruması
- İsim, etiket, koleksiyon (sağ tık)
- “Snippet olarak kaydet”

## Teknik temizlik — TAMAMLANDI
- Kullanılmayan UI/spec dosyaları `legacy/` ve `clipstack/ui/legacy/` altına taşındı
- Tek aktif PyInstaller spec: `TaxClip.spec`
