# Gorev 4 - Sifreleme, Hassas Veri, OCR ve Video Dogrulama

Tarih: 2026-04-12

## Kapsam

- Sifreleme akislarini tekrar kontrol et
- Hassas veri korumasi ve TOTP erisimini yeniden degerlendir
- OCR tarafinda atlanan guvenlik akislarini kapat
- Video ayarlarinin gercek recorder komutuna yansidigini dogrula

## Yapilan Duzeltmeler

- `clipstack/storage.py`
  - `ocr_text` artik `encrypt_data` aciksa AES ile sifreleniyor.
  - `text_content`, `html_content`, `ocr_text` icin karma plaintext/sifreli veri toleransli cozumleme eklendi.
  - Zengin HTML icinde hassas veri maskelenirse kayit `TEXT` tipine dusurulup maskeli duz metin olarak saklaniyor.
  - OCR ile hassas veri tasiyan gorseller, `block_sensitive_data` aciksa tamamen reddediliyor.

- `clipstack/sensitive_detector.py`
  - Email ve telefon tespitleri block reason icine dahil edildi.
  - `contains_sensitive_data`, `requires_sensitive_access`, `ensure_sensitive_access` yardimcilari eklendi.

- `clipstack/ui/item_widget.py`
  - Hassas veri iceren kartlarda onizleme metni yerine korumali placeholder gosteriliyor.
  - Kopyalama, paylasma ve buyutme once TOTP dogrulamasindan geciyor.

- `clipstack/ui/item_preview_dialog.py`
  - Preview ekrani hassas veri icin dogrulama olmadan icerik gostermiyor.
  - Copy/share aksiyonlari erisim durumu ile uyumlu hale getirildi.
  - Paylasim akisi icindeki eksik import ve `self.item_row` hatasi da duzeltildi.

- `clipstack/ui/main_window.py`
  - Karttan kopyalama once kaydin hassas metin/OCR icerigine gore dogrulaniyor.

- `clipstack/app.py`
  - `paste_last_item()` artik hassas son ogeyi TOTP olmadan yapistirmiyor.
  - Screenshot/OCR callback'leri `add_item()` reddederse eski ogeyi yanlislikla tekrar UI'ya eklemiyor.

- `clipstack/ui/settings_dialog.py`
  - `mask_emails` ve `mask_phones` ayarlari UI'ya eklendi ve kaydediliyor.
  - FFmpeg goruluyorsa mikrofon listesi ayarlar ekranina yukleniyor.

- `clipstack/video_recorder.py`
  - Windows konsol encoding yuzunden encoder tespitini bozan Unicode loglar kaldirildi.
  - GPU encoder tespiti tekrar calisir hale geldi.
  - `video_record_mic` ve `video_microphone` artik FFmpeg komutuna gercek audio input olarak ekleniyor.
  - Instant Replay komutu da mikrofonlu/sessiz moda gore kuruluyor.
  - Ayarlardaki mikrofon listesi icin cihaz tarama yardimcisi eklendi.

- `clipstack/ocr_manager.py`
  - Windows OCR availability log'u konsol encoding yuzunden patlamayacak sekilde sadeleştirildi.

## Dogrulama

- `python -m py_compile` ile ilgili dosyalar derleme kontrolunden gecti.
- `clipstack.aes_validator.AESValidator` tum testlerde `%100` gecti.
- Gecici DB testi ile:
  - `ocr_text` alaninin sifreli yazildigi ve dogru cozuldugu dogrulandi.
  - Hassas email iceren HTML'in maskeli `TEXT` kaydina donustugu dogrulandi.
  - Hassas OCR metni olan gorselin `block_sensitive_data` acikken reddedildigi dogrulandi.
- `AdvancedVideoRecorder` uzerinden:
  - Encoder tespiti `NVIDIA NVENC (GPU)` olarak geldi.
  - Mikrofon listesi bulundu.
  - Uretilen FFmpeg komutunda hem `audio=...` input'u hem `-c:a aac` cikti ayarlari yer aldi.
- `OCRManager` uzerinden Windows OCR kullanilabilirligi tekrar kontrol edildi.

## Kalan Risk / Not

- Gorsel maskeleme pikseller seviyesinde yapilmiyor. Bu nedenle `block_sensitive_data` kapaliysa, hassas yazi iceren gorseller saklanabilir; erisim korumasi TOTP + OCR sinyaline dayanir.
