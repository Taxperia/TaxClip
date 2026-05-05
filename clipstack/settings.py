from __future__ import annotations
import json
from pathlib import Path

class Settings:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._data = {
            "first_run": True,
            "language": "tr",
            "theme": "default",
            "hide_after_copy": False,
            "stay_on_top": False,
            "animations": True,
            "max_items": 1000,
            "dedupe_window_ms": 1200,
            "confirm_delete": True,
            "show_toast": True,
            "tray_icon": "assets/icons/tray/tray1.svg",  # .svg olarak güncellendi
            "tray_notifications": True,
            "launch_at_startup": True,
            "hotkey": "windows+v",
            "hotkey_screenshot": "ctrl+shift+s",  # Tam ekran screenshot
            "pause_recording": False,
            "encrypt_data": False,                # Şifreleme aktif mi?
            "save_images_externally": False,      # Resimleri harici klasöre kaydet
            "external_images_path": "",           # Harici resim klasörü yolu
            "auto_delete_enabled": False,          # Otomatik silme switch
            "auto_delete_days": 7,                 # Gün seçimi (varsayılan 7)
            "auto_delete_keep_fav": True,          # Favoriler korunsun mu? (varsayılan açık)
            "share_server_url": "https://taxclip.com",   # veya test için https://localhost:5000
            "share_api_key": "",  # API anahtarı (kötüye kullanıma karşı)              
            "reminder_sound_enabled": True,           # Ses çalsın mı?
            "reminder_sound_file": "default",         # Ses dosyası yolu (default = sistem sesi)
            "reminder_notification_type": "system",   # "system" veya "app" (uygulama içi)
            "reminder_show_popup": True,              # Popup pencere göster
            "reminder_auto_snooze": False,            # Otomatik erteleme
            "reminder_snooze_minutes": 5,             # Erteleme süresi (dakika)
            "ocr_enabled": False,                     # OCR (Optik Karakter Tanıma) aktif mi?
            "ocr_language": "tur+eng",                # OCR dili (tur=Türkçe, eng=İngilizce)
            "tesseract_path": "",                     # Tesseract yolu (boşsa otomatik bulur)
            "hotkey_ocr": "ctrl+shift+t",             # Ekran bölgesinden OCR kısayolu
            "windows_hello_enabled": False,           # Windows Hello ile iki faktörlü doğrulama
            "biometric_lock_on_startup": True,        # Başlangıçta kilit ekranı göster
            "biometric_lock_timeout": 15,             # Süre (dakika) sonra tekrar kilitle (0=kapalı)
            "sensitive_data_detection": True,         # Hassas veri algılama aktif
            "mask_credit_cards": True,                # Kredi kartlarını maskele
            "mask_passwords": True,                   # Şifreleri maskele
            "mask_api_keys": True,                    # API anahtarlarını maskele
            "mask_emails": False,                     # Email adreslerini maskele
            "mask_phones": False,                     # Telefon numaralarını maskele
            "mask_tc_ids": True,                      # TC kimlik numaralarını maskele
            "mask_ibans": True,                       # IBAN numaralarını maskele
            "block_sensitive_data": False,            # Hassas veri içeren metinleri hiç kaydetme
        }

    def load(self):
        if self.path.exists():
            try:
                self._data.update(json.loads(self.path.read_text("utf-8")))
            except Exception:
                pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
