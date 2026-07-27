from __future__ import annotations
import json
from pathlib import Path

# Bellekte tutulan, asla diske yazılmayan anahtarlar
_EPHEMERAL_KEYS = frozenset({
    "encryption_key",
})

# Diskte kalmaması gereken hassas ayar anahtarları (yüklemede temizlenir)
_SENSITIVE_PERSIST_KEYS = frozenset({
    "encryption_key",
    "google_client_secret",
})


class Settings:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._ephemeral: dict = {}  # yalnızca bellek
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
            "biometric_lock_on_startup": False,       # Başlangıçta kilit ekranı göster
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
            "exclude_apps_enabled": True,
            "excluded_apps": "keepass.exe,keepassxc.exe,1password.exe,bitwarden.exe,lastpass.exe",
            "auto_clear_clipboard_seconds": 30,       # 0=kapalı
            "pause_until": "",
            "compact_mode_default": False,
        }

    def load(self):
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text("utf-8"))
                if isinstance(loaded, dict):
                    # Diskte kalmış hassas anahtarları temizle
                    dirty = False
                    for key in list(loaded.keys()):
                        if key in _SENSITIVE_PERSIST_KEYS or key in _EPHEMERAL_KEYS:
                            loaded.pop(key, None)
                            dirty = True
                    self._data.update(loaded)
                    if dirty:
                        self.save()
            except Exception:
                pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Ephemeral ve hassas anahtarları diske yazma
        to_save = {
            k: v for k, v in self._data.items()
            if k not in _EPHEMERAL_KEYS and k not in _SENSITIVE_PERSIST_KEYS
        }
        self.path.write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key, default=None):
        if key in _EPHEMERAL_KEYS:
            return self._ephemeral.get(key, default)
        return self._data.get(key, default)

    def set(self, key, value):
        if key in _EPHEMERAL_KEYS:
            self._ephemeral[key] = value
            # Eski disk kalıntısını temizle
            self._data.pop(key, None)
            return
        self._data[key] = value

    def clear_ephemeral(self):
        """Oturum sonunda bellek anahtarlarını temizle."""
        self._ephemeral.clear()
