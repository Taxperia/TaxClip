# Görev 9 - Senkronizasyon (Paylaşım) Değişiklikleri

## Tarih: 2025-01-XX

## Yapılan Değişiklikler

### 1. Senkronizasyon Sekmesi (settings_dialog.py)
Ayarlar modalına yeni "Senkronizasyon" sekmesi eklendi:

- **tab_sync** widget'ı oluşturuldu (line ~186)
- TabWidget'a 7. sekme olarak eklendi
- refresh_texts() metodunda index 6 olarak eklendi

### 2. Senkronizasyon Sekmesi UI Bileşenleri
```
├── Yerel Yedekleme
│   ├── btn_export_json - "📤 JSON'a Aktar" butonu
│   └── btn_import_json - "📥 JSON'dan İçe Aktar" butonu
│
├── Google Drive
│   ├── lbl_gdrive_status - Bağlantı durumu etiketi
│   └── btn_gdrive_connect - "🔗 Google Drive'a Bağlan" butonu
│
├── Otomatik Senkronizasyon
│   ├── tgl_auto_sync - Toggle switch
│   └── cmb_sync_interval - Senkronizasyon aralığı (5dk, 15dk, 30dk, 1sa, 6sa, 24sa)
│
├── btn_sync_now - "🔄 Şimdi Senkronize Et" butonu
│
└── Paylaşım Sunucusu
    └── txt_share_server - URL input alanı
```

### 3. Yeni Metodlar (settings_dialog.py)

#### _export_to_json()
- Tüm verileri (clips, notes, reminders, snippets, todos, drawings) JSON dosyasına aktarır
- Dosya adı: `taxclip_backup_YYYYMMDD_HHMMSS.json`
- Hassas ayarları (password, secret, key, token içerenler) filtreler
- Başarı/hata mesajı gösterir

#### _import_from_json()
- JSON dosyasından verileri içe aktarır
- Mevcut verileri korur, yeni verileri ekler
- Kullanıcıdan onay ister
- Her kategori için import sayısını gösterir

#### _connect_google_drive()
- Şimdilik "Yakında" mesajı gösterir
- Google OAuth entegrasyonu için placeholder

#### _check_gdrive_status()
- settings.gdrive_connected değerini kontrol eder
- Duruma göre UI'ı günceller (bağlı/bağlı değil)
- Sync butonunu aktif/pasif yapar

#### _sync_now()
- Manuel senkronizasyon başlatır
- Şimdilik bilgi mesajı gösterir

### 4. Storage Metod Uyumluluğu
Export/Import metodları storage.py ile uyumlu hale getirildi:
- `list_notes()` → notlar
- `list_reminders()` → hatırlatıcılar
- `list_snippets()` → snippetlar
- `list_todos()` → todolar (content alanı)
- `list_drawings()` → çizimler (image alanı)
- `add_note(content, created_at)` parametreleri
- `add_reminder(title, description, reminder_time, repeat_type)` parametreleri
- `add_snippet(title, code, language, tags)` parametreleri
- `add_todo(list_id, content)` parametreleri
- `add_drawing(image_data, title)` parametreleri

## Test Edilmesi Gerekenler
1. ✅ Ayarlar modalında Senkronizasyon sekmesi görünüyor
2. ⏳ JSON dışa aktarma çalışıyor
3. ⏳ JSON içe aktarma çalışıyor
4. ✅ Google Drive butonu "Yakında" mesajı gösteriyor
5. ✅ Auto sync toggle çalışıyor
6. ✅ Sync interval dropdown çalışıyor

## Gelecek İyileştirmeler
- [ ] Google Drive OAuth 2.0 entegrasyonu (google-auth-oauthlib paketi)
- [ ] Otomatik senkronizasyon timer'ı
- [ ] Paylaşım sunucusu REST API entegrasyonu
- [ ] Çakışma çözümleme (conflict resolution)
- [ ] Delta sync (sadece değişen verileri senkronize etme)
