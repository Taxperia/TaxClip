from __future__ import annotations

from pathlib import Path
from typing import Dict

from PySide6.QtCore import Qt, Signal, QUrl, QSize, QTimer, QThread
from PySide6.QtGui import QIcon, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTabWidget,
    QWidget,
    QFormLayout,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QLabel,
    QSpinBox,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QStyle,
    QFrame,
    QScrollArea,
)

from ..settings import Settings
from ..utils import resource_path, svg_icon
from ..i18n import i18n
from ..theme_manager import theme_manager
from .widgets.toggle_switch import ToggleSwitch
from ..sound_player import SoundPlayer, is_sound_backend_available, get_sound_backend_error


LANG_MAP: Dict[str, str] = {
    "tr": "Türkçe",
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "az": "Azərbaycanca",
    "ru": "Русский",
    "ja": "日本語",
    "zh": "中文",
}

THEMES = [
    ("default", "Default (Blue)"),
    ("dark", "Dark (Black)"),
    ("light", "Light (White)"),
    ("purple", "Purple"),
    ("cyberpunk", "🌆 Cyberpunk"),
    ("sunset", "🌅 Sunset"),
    ("matrix", "💚 Matrix"),
    ("ocean", "🌊 Ocean"),
    ("retro", "🎮 Retro (XP)"),
]


class GoogleDriveStatusThread(QThread):
    status_ready = Signal(bool)
    status_failed = Signal(str)

    def run(self):
        try:
            from clipstack.gdrive_sync import GoogleDriveSync

            sync = GoogleDriveSync()
            self.status_ready.emit(sync.is_connected())
        except Exception as exc:
            self.status_failed.emit(str(exc))


class VideoProbeThread(QThread):
    probe_ready = Signal(bool, str, list)
    probe_failed = Signal(str)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings

    def run(self):
        try:
            from clipstack.video_recorder import AdvancedVideoRecorder

            recorder = AdvancedVideoRecorder(self._settings)
            available = recorder.is_available()
            encoder_info = recorder.get_encoder_info()
            devices = recorder.list_audio_devices()
            self.probe_ready.emit(available, encoder_info, devices)
        except Exception as exc:
            self.probe_failed.emit(str(exc))


class KeyCaptureLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setClearButtonEnabled(True)
        self.refresh_placeholder()
        i18n.languageChanged.connect(self.refresh_placeholder)

    def refresh_placeholder(self):
        self.setPlaceholderText(self._tr("settings.general.hotkey.placeholder", "e.g., ctrl+shift+v"))

    def _tr(self, key: str, fallback: str) -> str:
        try:
            v = i18n.t(key)
        except Exception:
            v = ""
        return v if v and v != key else fallback

    @staticmethod
    def normalize_combo(combo: str) -> str:
        t = (combo or "").strip().lower()
        if not t:
            return ""
        parts = [p.strip() for p in t.split("+") if p.strip()]
        mods = set()
        key = ""
        alias = {
            "control": "ctrl",
            "cmd": "windows",
            "command": "windows",
            "super": "windows",
            "win": "windows",
            "option": "alt",
            "menu": "alt",
        }
        specials = {
            "space": "space", "tab": "tab", "insert": "insert", "delete": "delete",
            "home": "home", "end": "end", "page up": "pgup", "page down": "pgdn",
            "pgup": "pgup", "pgdn": "pgdn",
            "up": "up", "down": "down", "left": "left", "right": "right",
            "escape": "esc", "esc": "esc",
            "return": "enter", "enter": "enter", "backspace": "backspace",
        }
        for p in parts:
            p2 = alias.get(p, p)
            if p2 in ("ctrl", "shift", "alt", "windows"):
                mods.add(p2)
            else:
                if p2.startswith("f") and p2[1:].isdigit():
                    key = p2
                elif p2 in specials:
                    key = specials[p2]
                else:
                    key = p2
        ordered_mods = [m for m in ("ctrl", "shift", "alt", "windows") if m in mods]
        return "+".join(ordered_mods + ([key] if key else []))

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        mods = []
        if e.modifiers() & Qt.ControlModifier:
            mods.append("ctrl")
        if e.modifiers() & Qt.ShiftModifier:
            mods.append("shift")
        if e.modifiers() & Qt.AltModifier:
            mods.append("alt")
        if e.modifiers() & Qt.MetaModifier:
            mods.append("windows")

        key_text = QKeySequence(e.key()).toString().strip()
        special_map = {
            "Space": "space", "Tab": "tab", "Insert": "insert", "Delete": "delete",
            "Home": "home", "End": "end", "Page Up": "pgup", "Page Down": "pgdn",
            "Up": "up", "Down": "down", "Left": "left", "Right": "right",
            "Escape": "esc", "Return": "enter", "Enter": "enter", "Backspace": "backspace",
        }
        if key_text in special_map:
            key_part = special_map[key_text]
        elif key_text.upper().startswith("F") and key_text[1:].isdigit():
            key_part = key_text.lower()
        else:
            key_part = key_text.lower() if len(key_text) else ""

        combo = "+".join(mods + ([key_part] if key_part else [])) if mods or key_part else ""
        norm = self.normalize_combo(combo)
        if norm:
            self.setText(norm)


class SettingsDialog(QDialog):
    applied = Signal()

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        self._sound_tester: SoundPlayer | None = None
        if is_sound_backend_available():
            try:
                self._sound_tester = SoundPlayer(self)
                try:
                    self._sound_tester.playbackFailed.connect(self._on_sound_test_failed)
                except Exception:
                    pass
            except Exception as exc:
                print(f"[SETTINGS SOUND] Tester init failed: {exc}")
        else:
            print(f"[SETTINGS SOUND] QtMultimedia backend unavailable: {get_sound_backend_error()}; WAV-only fallback will be used for testing.")

        self.setWindowTitle("Settings")
        try:
            self.setWindowIcon(svg_icon("assets/icons/gear.svg"))
        except Exception:
            pass
        self.resize(760, 640)

        self.tabs = QTabWidget(self)
        self.tab_general = QWidget()
        self.tab_appearance = QWidget()
        self.tab_behavior = QWidget()
        self.tab_security = QWidget()
        self.tab_video = QWidget()
        self.tab_reminders = QWidget()
        self.tab_sync = QWidget()  # Senkronizasyon ve Paylaşım
        self.tab_tray = QWidget()
        self.tab_about = QWidget()

        self.tabs.addTab(self.tab_general, "")
        self.tabs.addTab(self.tab_appearance, "")
        self.tabs.addTab(self.tab_behavior, "")
        self.tabs.addTab(self.tab_security, "")
        self.tabs.addTab(self.tab_video, "")
        self.tabs.addTab(self.tab_reminders, "")
        self.tabs.addTab(self.tab_sync, "")
        self.tabs.addTab(self.tab_tray, "")
        self.tabs.addTab(self.tab_about, "")

        root = QVBoxLayout(self)
        root.addWidget(self.tabs)

        form_g = QFormLayout(self.tab_general)
        form_g.setContentsMargins(12, 12, 12, 12)
        form_g.setSpacing(10)

        self.cmb_lang = QComboBox()
        self.cmb_lang.setMinimumHeight(36)
        for code, label in LANG_MAP.items():
            self.cmb_lang.addItem(label, code)
        self.cmb_lang.setCurrentIndex(max(0, self.cmb_lang.findData(settings.get("language", "tr"))))

        self.tgl_startup = ToggleSwitch(checked=bool(settings.get("launch_at_startup", True)))

        self.txt_hotkey = KeyCaptureLineEdit()
        self.txt_hotkey.setText(KeyCaptureLineEdit.normalize_combo(str(settings.get("hotkey", "ctrl+shift+v"))))
        self.btn_clear_hk = QPushButton()

        hk_row = QHBoxLayout()
        hk_row.addWidget(self.txt_hotkey, 1)
        hk_row.addWidget(self.btn_clear_hk)

        self.txt_hotkey_paste = KeyCaptureLineEdit()
        self.txt_hotkey_paste.setText(KeyCaptureLineEdit.normalize_combo(str(settings.get("hotkey_paste_last", ""))))
        self.btn_clear_hk_paste = QPushButton()

        hk_paste_row = QHBoxLayout()
        hk_paste_row.addWidget(self.txt_hotkey_paste, 1)
        hk_paste_row.addWidget(self.btn_clear_hk_paste)

        self.txt_hotkey_quick_note = KeyCaptureLineEdit()
        self.txt_hotkey_quick_note.setText(KeyCaptureLineEdit.normalize_combo(str(settings.get("hotkey_quick_note", ""))))
        self.btn_clear_hk_quick_note = QPushButton()

        self.txt_hotkey_screenshot = KeyCaptureLineEdit()
        self.txt_hotkey_screenshot.setText(KeyCaptureLineEdit.normalize_combo(str(settings.get("hotkey_screenshot", ""))))
        self.btn_clear_hk_screenshot = QPushButton()
        
        self.txt_hotkey_ocr = KeyCaptureLineEdit()
        self.txt_hotkey_ocr.setText(KeyCaptureLineEdit.normalize_combo(str(settings.get("hotkey_ocr", ""))))
        self.btn_clear_hk_ocr = QPushButton()

        self.txt_hotkey_snip = KeyCaptureLineEdit()
        self.txt_hotkey_snip.setText(KeyCaptureLineEdit.normalize_combo(str(settings.get("hotkey_snip", ""))))
        self.btn_clear_hk_snip = QPushButton()

        try:
            reset_icon = self.style().standardIcon(QStyle.SP_LineEditClearButton)
            for btn in (self.btn_clear_hk, self.btn_clear_hk_paste, self.btn_clear_hk_quick_note, self.btn_clear_hk_screenshot, self.btn_clear_hk_ocr, self.btn_clear_hk_snip):
                btn.setIcon(reset_icon)
                btn.setIconSize(QSize(18, 18))
                btn.setCursor(Qt.PointingHandCursor)
        except Exception:
            pass

        hk_quick_note_row = QHBoxLayout()
        hk_quick_note_row.addWidget(self.txt_hotkey_quick_note, 1)
        hk_quick_note_row.addWidget(self.btn_clear_hk_quick_note)

        hk_screenshot_row = QHBoxLayout()
        hk_screenshot_row.addWidget(self.txt_hotkey_screenshot, 1)
        hk_screenshot_row.addWidget(self.btn_clear_hk_screenshot)
        
        hk_ocr_row = QHBoxLayout()
        hk_ocr_row.addWidget(self.txt_hotkey_ocr, 1)
        hk_ocr_row.addWidget(self.btn_clear_hk_ocr)

        hk_snip_row = QHBoxLayout()
        hk_snip_row.addWidget(self.txt_hotkey_snip, 1)
        hk_snip_row.addWidget(self.btn_clear_hk_snip)

        self.lbl_hotkey_help = QLabel()
        form_g.addRow(self.lbl_hotkey_help)
        form_g.addRow(self._tr("settings.general.hotkey.label", "Ana kısayol tuşu"), hk_row)
        form_g.addRow(self._tr("settings.general.hotkey_paste.label", "Son içeriği yapıştır"), hk_paste_row)
        form_g.addRow(self._tr("settings.general.hotkey_quick_note.label", "Hızlı not al"), hk_quick_note_row)
        form_g.addRow(self._tr("settings.general.hotkey_screenshot.label", "Tam ekran görüntüsü al"), hk_screenshot_row)
        form_g.addRow(self._tr("settings.general.hotkey_ocr.label", "Ekran OCR (Yazı tanı)"), hk_ocr_row)
        form_g.addRow(self._tr("settings.general.hotkey_snip.label", "Ekran Alıntısı (Lightshot)"), hk_snip_row)
        form_g.addRow(self._tr("settings.general.language", "Dil"), self.cmb_lang)
        form_g.addRow(self._tr("settings.general.launch_at_startup", "Windows ile başlat"), self.tgl_startup)

        form_a = QFormLayout(self.tab_appearance)
        form_a.setContentsMargins(12, 12, 12, 12)
        form_a.setSpacing(10)
        self.cmb_theme = QComboBox()
        for key, label in THEMES:
            self.cmb_theme.addItem(label, key)
        self.cmb_theme.setCurrentIndex(max(0, self.cmb_theme.findData(settings.get("theme", "default"))))
        self.tgl_animations = ToggleSwitch(checked=bool(settings.get("animations", True)))
        form_a.addRow(self._tr("settings.appearance.theme", "Tema"), self.cmb_theme)
        form_a.addRow(self._tr("settings.appearance.animations", "Animasyonları etkinleştir"), self.tgl_animations)

        form_b = QFormLayout(self.tab_behavior)
        form_b.setContentsMargins(12, 12, 12, 12)
        form_b.setSpacing(10)
        self.tgl_hide_after_copy = ToggleSwitch(checked=bool(settings.get("hide_after_copy", False)))
        self.tgl_stay_on_top = ToggleSwitch(checked=bool(settings.get("stay_on_top", False)))
        self.spn_max_items = QSpinBox()
        self.spn_max_items.setRange(100, 5000)
        self.spn_max_items.setValue(int(settings.get("max_items", 1000)))
        self.spn_dedupe_ms = QSpinBox()
        self.spn_dedupe_ms.setRange(0, 10000)
        self.spn_dedupe_ms.setValue(int(settings.get("dedupe_window_ms", 1200)))
        self.tgl_confirm_delete = ToggleSwitch(checked=bool(settings.get("confirm_delete", True)))
        self.tgl_toast = ToggleSwitch(checked=bool(settings.get("show_toast", True)))

        form_b.addRow(self._tr("settings.behavior.hide_after_copy", "Kopyalama sonrası gizle"), self.tgl_hide_after_copy)
        form_b.addRow(self._tr("settings.behavior.stay_on_top", "Pencereyi üstte tut"), self.tgl_stay_on_top)
        form_b.addRow(self._tr("settings.behavior.max_items", "Maksimum öğe sayısı"), self.spn_max_items)
        form_b.addRow(self._tr("settings.behavior.dedupe_ms", "Tekrar engelleme süresi (ms)"), self.spn_dedupe_ms)
        form_b.addRow(self._tr("settings.behavior.confirm_delete", "Silmeden önce onayla"), self.tgl_confirm_delete)
        form_b.addRow(self._tr("settings.behavior.show_toast", "Uygulama içi bildirimleri göster"), self.tgl_toast)

        # Güvenlik tab'ı için scroll area
        security_scroll = QScrollArea(self.tab_security)
        security_scroll.setWidgetResizable(True)
        security_scroll.setFrameShape(QFrame.Shape.NoFrame)
        security_content = QWidget()
        form_s = QFormLayout(security_content)
        form_s.setContentsMargins(12, 12, 12, 12)
        form_s.setSpacing(10)
        security_scroll.setWidget(security_content)
        
        security_layout = QVBoxLayout(self.tab_security)
        security_layout.setContentsMargins(0, 0, 0, 0)
        security_layout.addWidget(security_scroll)

        self.tgl_encrypt = ToggleSwitch(checked=bool(settings.get("encrypt_data", False)))
        form_s.addRow("Panoyu ve notları şifrele (AES-256)", self.tgl_encrypt)
        
        # Google Authenticator (TOTP)
        form_s.addRow(QLabel(""))  # Boşluk
        totp_header = QLabel("<b>📱 Google Authenticator (TOTP)</b>")
        form_s.addRow(totp_header)
        
        # TOTP durum etiketi
        self.lbl_totp_status = QLabel("⏳ Kontrol ediliyor...")
        form_s.addRow("Durum:", self.lbl_totp_status)
        
        # TOTP kurulum/kaldır butonu
        totp_btn_layout = QHBoxLayout()
        self.btn_totp_setup = QPushButton("🔐 2FA Kur")
        self.btn_totp_setup.clicked.connect(self._setup_totp)
        totp_btn_layout.addWidget(self.btn_totp_setup)
        
        self.btn_totp_remove = QPushButton("🗑️ 2FA Kaldır")
        self.btn_totp_remove.clicked.connect(self._remove_totp)
        self.btn_totp_remove.hide()
        totp_btn_layout.addWidget(self.btn_totp_remove)
        
        self.btn_totp_test = QPushButton("🧪 Test Et")
        self.btn_totp_test.clicked.connect(self._test_totp)
        self.btn_totp_test.hide()
        totp_btn_layout.addWidget(self.btn_totp_test)
        
        totp_btn_layout.addStretch()
        form_s.addRow("", totp_btn_layout)
        
        # TOTP seçenekleri
        self.tgl_totp_on_startup = ToggleSwitch(checked=bool(settings.get("totp_on_startup", False)))
        self.tgl_totp_on_startup.setEnabled(False)
        form_s.addRow("Uygulama açılışında kod iste", self.tgl_totp_on_startup)
        
        self.tgl_totp_hourly_lock = ToggleSwitch(checked=bool(settings.get("totp_hourly_lock", False)))
        self.tgl_totp_hourly_lock.setEnabled(False)
        form_s.addRow("Her saat başı kod iste", self.tgl_totp_hourly_lock)
        
        self.tgl_totp_for_sensitive = ToggleSwitch(checked=bool(settings.get("totp_for_sensitive", True)))
        self.tgl_totp_for_sensitive.setEnabled(False)
        form_s.addRow("Hassas verileri göstermek için kod iste", self.tgl_totp_for_sensitive)
        
        self.lbl_totp_info = QLabel("ℹ️ Google Authenticator uygulamasıyla ek güvenlik katmanı ekleyin.")
        self.lbl_totp_info.setWordWrap(True)
        self.lbl_totp_info.setStyleSheet("color: #666; font-size: 10px;")
        form_s.addRow("", self.lbl_totp_info)
        
        # TOTP durumunu kontrol et (defer)
        # self._check_totp_status() will be called in showEvent
        
        # Hassas Veri Koruması
        form_s.addRow(QLabel(""))  # Boşluk
        sensitive_header = QLabel("<b>🛡️ Hassas Veri Koruması</b>")
        form_s.addRow(sensitive_header)
        
        self.tgl_sensitive_detection = ToggleSwitch(checked=bool(settings.get("sensitive_data_detection", True)))
        form_s.addRow("Hassas veri algılamayı aktifleştir", self.tgl_sensitive_detection)
        
        self.tgl_mask_credit_cards = ToggleSwitch(checked=bool(settings.get("mask_credit_cards", True)))
        form_s.addRow("Kredi kartlarını maskele", self.tgl_mask_credit_cards)
        
        self.tgl_mask_passwords = ToggleSwitch(checked=bool(settings.get("mask_passwords", True)))
        form_s.addRow("Şifreleri maskele", self.tgl_mask_passwords)
        
        self.tgl_mask_api_keys = ToggleSwitch(checked=bool(settings.get("mask_api_keys", True)))
        form_s.addRow("API anahtarlarını maskele", self.tgl_mask_api_keys)

        self.tgl_mask_emails = ToggleSwitch(checked=bool(settings.get("mask_emails", False)))
        form_s.addRow("E-posta adreslerini maskele", self.tgl_mask_emails)

        self.tgl_mask_phones = ToggleSwitch(checked=bool(settings.get("mask_phones", False)))
        form_s.addRow("Telefon numaralarını maskele", self.tgl_mask_phones)
        
        self.tgl_mask_tc_ids = ToggleSwitch(checked=bool(settings.get("mask_tc_ids", True)))
        form_s.addRow("TC kimlik no maskele", self.tgl_mask_tc_ids)
        
        self.tgl_mask_ibans = ToggleSwitch(checked=bool(settings.get("mask_ibans", True)))
        form_s.addRow("IBAN numaralarını maskele", self.tgl_mask_ibans)
        
        self.tgl_block_sensitive = ToggleSwitch(checked=bool(settings.get("block_sensitive_data", False)))
        form_s.addRow("Hassas veriyi hiç kaydetme", self.tgl_block_sensitive)
        
        self.lbl_sensitive_info = QLabel("ℹ️ Hassas veriler otomatik maskelenir veya tamamen engellenir.")
        self.lbl_sensitive_info.setWordWrap(True)
        self.lbl_sensitive_info.setStyleSheet("color: #666; font-size: 10px;")
        form_s.addRow("", self.lbl_sensitive_info)

        self.tgl_auto_delete = ToggleSwitch(checked=bool(settings.get("auto_delete_enabled", False)))
        self.cmb_auto_delete = QComboBox()
        for d in [7, 10, 14, 30, 60, 90, 120, 180, 365]:
            self.cmb_auto_delete.addItem(f"{d} gün", d)
        self.cmb_auto_delete.setCurrentIndex([7, 10, 14, 30, 60, 90, 120, 180, 365].index(settings.get("auto_delete_days", 7)))
        self.cmb_auto_delete.setEnabled(self.tgl_auto_delete.isChecked())
        form_s.addRow("Otomatik silme", self.tgl_auto_delete)
        form_s.addRow("Silme süresi", self.cmb_auto_delete)

        self.tgl_keep_fav = ToggleSwitch(checked=bool(settings.get("auto_delete_keep_fav", True)))
        form_s.addRow("Favoriler silinmesin", self.tgl_keep_fav)

        # Resimleri harici klasöre kaydetme
        self.tgl_save_images_externally = ToggleSwitch(checked=bool(settings.get("save_images_externally", False)))
        form_s.addRow("Resimleri ayrı klasöre kaydet", self.tgl_save_images_externally)

        img_path_layout = QHBoxLayout()
        self.txt_external_images_path = QLineEdit()
        self.txt_external_images_path.setText(settings.get("external_images_path", ""))
        self.txt_external_images_path.setEnabled(self.tgl_save_images_externally.isChecked())
        self.btn_browse_images_path = QPushButton("...")
        self.btn_browse_images_path.setMaximumWidth(40)
        self.btn_browse_images_path.setEnabled(self.tgl_save_images_externally.isChecked())
        self.btn_browse_images_path.clicked.connect(self._browse_images_folder)
        img_path_layout.addWidget(self.txt_external_images_path, 1)
        img_path_layout.addWidget(self.btn_browse_images_path)
        form_s.addRow("Resim klasörü", img_path_layout)

        self.lbl_images_warning = QLabel("⚠️ Bu ayar açıksa resimler şifrelenmeyecek ve klasöre doğrudan kaydedilecektir.")
        self.lbl_images_warning.setWordWrap(True)
        self.lbl_images_warning.setStyleSheet("color: orange; font-size: 10px;")
        self.lbl_images_warning.setVisible(self.tgl_save_images_externally.isChecked())
        form_s.addRow("", self.lbl_images_warning)

        # OCR (Optik Karakter Tanıma) Ayarları
        form_s.addRow(QLabel(""))  # Boşluk
        ocr_header = QLabel("<b>🔍 OCR (Optik Karakter Tanıma)</b>")
        form_s.addRow(ocr_header)
        
        self.tgl_ocr = ToggleSwitch(checked=bool(settings.get("ocr_enabled", False)))
        form_s.addRow("Resimlerdeki yazıları tanı", self.tgl_ocr)
        
        self.cmb_ocr_language = QComboBox()
        self.cmb_ocr_language.addItem("Türkçe + İngilizce", "tur+eng")
        self.cmb_ocr_language.addItem("Sadece Türkçe", "tur")
        self.cmb_ocr_language.addItem("Sadece İngilizce", "eng")
        self.cmb_ocr_language.addItem("Tüm Diller", "")
        ocr_lang = settings.get("ocr_language", "tur+eng")
        idx = self.cmb_ocr_language.findData(ocr_lang)
        if idx >= 0:
            self.cmb_ocr_language.setCurrentIndex(idx)
        self.cmb_ocr_language.setEnabled(self.tgl_ocr.isChecked())
        form_s.addRow("OCR Dili", self.cmb_ocr_language)
        
        ocr_path_layout = QHBoxLayout()
        self.txt_tesseract_path = QLineEdit()
        self.txt_tesseract_path.setText(settings.get("tesseract_path", ""))
        self.txt_tesseract_path.setPlaceholderText("Boş bırakılırsa otomatik bulunur")
        self.txt_tesseract_path.setEnabled(self.tgl_ocr.isChecked())
        self.btn_browse_tesseract = QPushButton("...")
        self.btn_browse_tesseract.setMaximumWidth(40)
        self.btn_browse_tesseract.setEnabled(self.tgl_ocr.isChecked())
        self.btn_browse_tesseract.clicked.connect(self._browse_tesseract_path)
        ocr_path_layout.addWidget(self.txt_tesseract_path, 1)
        ocr_path_layout.addWidget(self.btn_browse_tesseract)
        form_s.addRow("Tesseract Yolu", ocr_path_layout)
        
        self.lbl_ocr_info = QLabel("ℹ️ Tesseract OCR kurulu değilse <a href='https://github.com/UB-Mannheim/tesseract/wiki'>buradan</a> indirebilirsiniz.")
        self.lbl_ocr_info.setWordWrap(True)
        self.lbl_ocr_info.setOpenExternalLinks(True)
        self.lbl_ocr_info.setStyleSheet("color: #666; font-size: 10px;")
        self.lbl_ocr_info.setVisible(self.tgl_ocr.isChecked())
        form_s.addRow("", self.lbl_ocr_info)

        def _on_auto_delete_toggle(val):
            self.cmb_auto_delete.setEnabled(val)
        self.tgl_auto_delete.onToggled(_on_auto_delete_toggle)
        
        def _on_ocr_toggle(val):
            self.cmb_ocr_language.setEnabled(val)
            self.txt_tesseract_path.setEnabled(val)
            self.btn_browse_tesseract.setEnabled(val)
            self.lbl_ocr_info.setVisible(val)
        self.tgl_ocr.onToggled(_on_ocr_toggle)

        def _on_save_images_externally_toggle(val):
            self.txt_external_images_path.setEnabled(val)
            self.btn_browse_images_path.setEnabled(val)
            self.lbl_images_warning.setVisible(val)
        self.tgl_save_images_externally.onToggled(_on_save_images_externally_toggle)

        # Video Tab with scroll
        scroll_video = QScrollArea()
        scroll_video.setWidgetResizable(True)
        scroll_video.setFrameShape(QFrame.Shape.NoFrame)
        
        video_content = QWidget()
        form_v = QFormLayout(video_content)
        form_v.setContentsMargins(12, 12, 12, 12)
        form_v.setSpacing(10)
        
        # Video Kalitesi
        video_header = QLabel("<b>📹 Video Kayıt Ayarları</b>")
        form_v.addRow(video_header)
        
        # FFmpeg durum bilgisi (lazy - defer to after dialog shows)
        self._ffmpeg_status_label = QLabel("⏳ FFmpeg kontrol ediliyor...")
        self._ffmpeg_status_label.setStyleSheet("color: #888; padding: 6px;")
        form_v.addRow(self._ffmpeg_status_label)
        self._form_v = form_v  # keep ref for later
        
        # Kaydetme yolu
        save_path_layout = QHBoxLayout()
        self.txt_video_save_path = QLineEdit()
        default_path = str(Path.home() / "Videos" / "ClipStack")
        self.txt_video_save_path.setText(settings.get("video_save_path", default_path))
        self.txt_video_save_path.setReadOnly(True)
        save_path_layout.addWidget(self.txt_video_save_path)
        
        self.btn_browse_video_path = QPushButton("📂")
        self.btn_browse_video_path.setFixedWidth(40)
        self.btn_browse_video_path.setToolTip("Kaydetme klasörünü seç")
        self.btn_browse_video_path.clicked.connect(self._browse_video_save_path)
        save_path_layout.addWidget(self.btn_browse_video_path)
        
        form_v.addRow("Kaydetme Yolu:", save_path_layout)
        
        self.cmb_video_quality = QComboBox()
        self.cmb_video_quality.addItem("🎬 4K (3840x2160)", "4K")
        self.cmb_video_quality.addItem("📺 1440p (2K)", "1440p")
        self.cmb_video_quality.addItem("✨ 1080p (Full HD)", "1080p")
        self.cmb_video_quality.addItem("📹 720p (HD)", "720p")
        self.cmb_video_quality.addItem("📱 480p (SD)", "480p")
        video_quality = settings.get("video_quality", "1080p")
        idx = self.cmb_video_quality.findData(video_quality)
        if idx >= 0:
            self.cmb_video_quality.setCurrentIndex(idx)
        form_v.addRow("Çözünürlük:", self.cmb_video_quality)
        
        # FPS - FFmpeg GPU ile 60 FPS destekleniyor
        self.cmb_video_fps = QComboBox()
        self.cmb_video_fps.addItem("📹 30 FPS (Standart)", 30)
        self.cmb_video_fps.addItem("🎮 60 FPS (Akıcı)", 60)
        self.cmb_video_fps.addItem("🐌 15 FPS (Düşük)", 15)
        video_fps = settings.get("video_fps", 30)
        idx_fps = self.cmb_video_fps.findData(video_fps)
        if idx_fps >= 0:
            self.cmb_video_fps.setCurrentIndex(idx_fps)
        else:
            self.cmb_video_fps.setCurrentIndex(0)  # 30 FPS varsayılan
        form_v.addRow("Kare Hızı (FPS):", self.cmb_video_fps)
        
        # Bitrate - GPU encoder için daha yüksek değerler
        self.spn_video_bitrate = QSpinBox()
        self.spn_video_bitrate.setRange(1000, 50000)
        self.spn_video_bitrate.setValue(int(settings.get("video_bitrate", 8000)))
        self.spn_video_bitrate.setSuffix(" kbps")
        self.spn_video_bitrate.setSingleStep(1000)
        form_v.addRow("Bit Hızı:", self.spn_video_bitrate)
        
        # Mikrofon
        form_v.addRow(QLabel(""))
        mic_header = QLabel("<b>🎤 Mikrofon Ayarları</b>")
        form_v.addRow(mic_header)
        
        self.tgl_record_mic = ToggleSwitch(checked=bool(settings.get("video_record_mic", False)))
        form_v.addRow("Mikrofon kaydet:", self.tgl_record_mic)
        
        self.cmb_microphone = QComboBox()
        self.cmb_microphone.addItem("Varsayılan Mikrofon", "default")
        mic_device = settings.get("video_microphone", "default")
        idx = self.cmb_microphone.findData(mic_device)
        if idx >= 0:
            self.cmb_microphone.setCurrentIndex(idx)
        self.cmb_microphone.setEnabled(self.tgl_record_mic.isChecked())
        form_v.addRow("Mikrofon:", self.cmb_microphone)
        
        # Hotkeys
        form_v.addRow(QLabel(""))
        hotkey_header = QLabel("<b>⌨️ Kısayol Tuşları</b>")
        form_v.addRow(hotkey_header)
        
        self.txt_hotkey_video_record = KeyCaptureLineEdit()
        self.txt_hotkey_video_record.setText(KeyCaptureLineEdit.normalize_combo(str(settings.get("hotkey_video_record", ""))))
        self.btn_clear_hk_video_record = QPushButton()
        try:
            reset_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_LineEditClearButton)
            self.btn_clear_hk_video_record.setIcon(reset_icon)
            self.btn_clear_hk_video_record.setIconSize(QSize(18, 18))
            self.btn_clear_hk_video_record.setCursor(Qt.CursorShape.PointingHandCursor)
        except Exception:
            pass
        hk_video_record_row = QHBoxLayout()
        hk_video_record_row.addWidget(self.txt_hotkey_video_record, 1)
        hk_video_record_row.addWidget(self.btn_clear_hk_video_record)
        form_v.addRow("Kayıt Başlat/Durdur:", hk_video_record_row)
        
        self.txt_hotkey_instant_replay = KeyCaptureLineEdit()
        self.txt_hotkey_instant_replay.setText(KeyCaptureLineEdit.normalize_combo(str(settings.get("hotkey_instant_replay", ""))))
        self.btn_clear_hk_instant_replay = QPushButton()
        try:
            reset_icon2 = self.style().standardIcon(QStyle.StandardPixmap.SP_LineEditClearButton)
            self.btn_clear_hk_instant_replay.setIcon(reset_icon2)
            self.btn_clear_hk_instant_replay.setIconSize(QSize(18, 18))
            self.btn_clear_hk_instant_replay.setCursor(Qt.CursorShape.PointingHandCursor)
        except Exception:
            pass
        hk_instant_replay_row = QHBoxLayout()
        hk_instant_replay_row.addWidget(self.txt_hotkey_instant_replay, 1)
        hk_instant_replay_row.addWidget(self.btn_clear_hk_instant_replay)
        form_v.addRow("Instant Replay Kaydet:", hk_instant_replay_row)
        
        # Instant Replay
        form_v.addRow(QLabel(""))
        instant_header = QLabel("<b>⏪ Instant Replay</b>")
        form_v.addRow(instant_header)
        
        self.spn_replay_buffer = QSpinBox()
        self.spn_replay_buffer.setRange(15, 300)
        self.spn_replay_buffer.setValue(int(settings.get("instant_replay_buffer_seconds", 30)))
        self.spn_replay_buffer.setSuffix(" saniye")
        form_v.addRow("Buffer Süresi:", self.spn_replay_buffer)
        
        self.lbl_replay_info = QLabel("ℹ️ Instant Replay son N saniyeyi sürekli buffer'da tutar. Hotkey ile kaydettiğinizde son buffer kaydedilir.")
        self.lbl_replay_info.setWordWrap(True)
        self.lbl_replay_info.setStyleSheet("color: #666; font-size: 10px;")
        form_v.addRow("", self.lbl_replay_info)
        
        scroll_video.setWidget(video_content)
        
        video_layout = QVBoxLayout(self.tab_video)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.addWidget(scroll_video)
        
        def _on_record_mic_toggle(val):
            self.cmb_microphone.setEnabled(val)
        self.tgl_record_mic.onToggled(_on_record_mic_toggle)
        self.btn_clear_hk_video_record.clicked.connect(lambda: self.txt_hotkey_video_record.clear())
        self.btn_clear_hk_instant_replay.clicked.connect(lambda: self.txt_hotkey_instant_replay.clear())

        lay_t = QVBoxLayout(self.tab_tray)
        lay_t.setContentsMargins(12, 12, 12, 12)
        lay_t.setSpacing(10)

        form_t = QFormLayout()
        self.cmb_tray = QComboBox()
        # 10 farklı tasarımlı ikon
        tray_icons = [
            ("📋 Klasik Pano", "assets/icons/tray/tray1.svg"),
            ("📄 Kağıt Yığını", "assets/icons/tray/tray2.svg"),
            ("📝 Kopyalama Oku", "assets/icons/tray/tray3.svg"),
            ("💾 Bellek Çipi", "assets/icons/tray/tray4.svg"),
            ("📁 Klasör", "assets/icons/tray/tray5.svg"),
            ("📌 Raptiyeli Not", "assets/icons/tray/tray6.svg"),
            ("✨ Sihirli Pano", "assets/icons/tray/tray7.svg"),
            ("☁️ Bulut Sync", "assets/icons/tray/tray8.svg"),
            ("🛡️ Güvenli Pano", "assets/icons/tray/tray9.svg"),
            ("⚡ Şimşek Hızı", "assets/icons/tray/tray10.svg"),
        ]
        for label, path in tray_icons:
            self.cmb_tray.addItem(label, path)
        
        # Tema varyantları
        tray_variants = [
            ("🌙 Midnight", "assets/icons/tray/tray_default.svg"),
            ("⚫ Carbon", "assets/icons/tray/tray_dark.svg"),
            ("⚪ Polar", "assets/icons/tray/tray_light.svg"),
            ("💜 Royal", "assets/icons/tray/tray_purple.svg"),
            ("🌆 Neon", "assets/icons/tray/tray_cyberpunk.svg"),
            ("🌅 Sunset", "assets/icons/tray/tray_sunset.svg"),
            ("💚 Matrix", "assets/icons/tray/tray_matrix.svg"),
            ("🌊 Ocean", "assets/icons/tray/tray_ocean.svg"),
            ("🎮 Retro", "assets/icons/tray/tray_retro.svg"),
            ("⬜ Minimal", "assets/icons/tray/tray_minimal.svg"),
        ]
        for label, rel in tray_variants:
            self.cmb_tray.addItem(label, rel)
        self.cmb_tray.addItem(self._tr("settings.tray.icon.custom", "Özel seç…"), "__custom__")
        sel = self.settings.get("tray_icon", "assets/icons/tray/tray1.svg")
        idx = self.cmb_tray.findData(sel)
        if idx < 0:
            idx = 0
        self.cmb_tray.setCurrentIndex(idx)
        form_t.addRow(self._tr("settings.tray.icon", "Tepsi ikonu"), self.cmb_tray)

        self.btn_preview = QPushButton()
        form_t.addRow("", self.btn_preview)

        self.tgl_tray_notifications = ToggleSwitch(checked=bool(settings.get("tray_notifications", True)))
        form_t.addRow(self._tr("settings.tray.notifications", "Tepsi bildirimlerini göster"), self.tgl_tray_notifications)
        lay_t.addLayout(form_t)

        form_r = QFormLayout(self.tab_reminders)
        form_r.setContentsMargins(12, 12, 12, 12)
        form_r.setSpacing(10)

        # Bildirim türü
        self.cmb_notification_type = QComboBox()
        self.cmb_notification_type.setMinimumHeight(36)
        self.cmb_notification_type.addItem(self._tr("settings.reminders.notif_system", "Sistem Bildirimi"), "system")
        self.cmb_notification_type.addItem(self._tr("settings.reminders.notif_app", "Uygulama Bildirimi"), "app")
        notif_type = settings.get("reminder_notification_type", "system")
        idx = self.cmb_notification_type.findData(notif_type)
        if idx >= 0:
            self.cmb_notification_type.setCurrentIndex(idx)
        form_r.addRow(self._tr("settings.reminders.notification_type", "Bildirim Türü:"), self.cmb_notification_type)

        # Popup göster
        self._last_app_popup_choice = bool(settings.get("reminder_show_popup", True))
        self.tgl_show_popup = ToggleSwitch(checked=self._last_app_popup_choice)
        self.tgl_show_popup.onToggled(self._on_show_popup_toggle)
        form_r.addRow(self._tr("settings.reminders.show_popup", "Popup pencere göster"), self.tgl_show_popup)

        # Ses etkin
        self.tgl_sound = ToggleSwitch(checked=bool(settings.get("reminder_sound_enabled", True)))
        form_r.addRow(self._tr("settings.reminders.sound_enabled", "Bildirim sesi çal"), self.tgl_sound)

        # Ses dosyası seçimi
        sound_layout = QHBoxLayout()
        sound_layout.setSpacing(8)
        sound_layout.setContentsMargins(0, 0, 0, 0)
        self.cmb_sound = QComboBox()
        self.cmb_sound.setMinimumHeight(36)
        self.cmb_sound.addItem(self._tr("settings.reminders.sound_default", "Varsayılan (Sistem)"), "default")

        from ..utils import resource_path
        sounds_dir = resource_path("assets/sounds")
        audio_exts = {".mp3", ".wav", ".ogg", ".m4a"}
        if sounds_dir.exists():
            for sound_path in sorted(sounds_dir.iterdir()):
                if not sound_path.is_file():
                    continue
                if sound_path.suffix.lower() not in audio_exts:
                    continue
                display_name = self._format_sound_label(sound_path)
                self.cmb_sound.addItem(display_name, str(sound_path))
        
        # Özel ses seçimi
        self.cmb_sound.addItem(self._tr("settings.reminders.sound_custom", "➕ Özel Ses Seç..."), "__custom__")
        
        # Mevcut ayarı yükle
        current_sound = settings.get("reminder_sound_file", "default")
        if current_sound and current_sound != "default":
            # Hazır seslerden biri mi kontrol et
            found = False
            for i in range(self.cmb_sound.count()):
                if self.cmb_sound.itemData(i) == current_sound:
                    self.cmb_sound.setCurrentIndex(i)
                    found = True
                    break
            
            # Hazır ses değilse, özel ses olarak ekle
            if not found and current_sound != "__custom__":
                custom_index = self.cmb_sound.count() - 1  # "Özel Ses Seç..." öncesi
                self.cmb_sound.insertItem(custom_index, f"⭐ Özel: {Path(current_sound).name}", current_sound)
                self.cmb_sound.setCurrentIndex(custom_index)
        else:
            self.cmb_sound.setCurrentIndex(0)  # Default
        
        self.btn_test_sound = QPushButton(self._tr("settings.reminders.test_sound", "Test"))
        self.btn_test_sound.setMinimumHeight(36)
        self.btn_test_sound.clicked.connect(self._test_reminder_sound)
        self.btn_test_sound.setCursor(Qt.PointingHandCursor)
        try:
            self.btn_test_sound.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.btn_test_sound.setIconSize(QSize(20, 20))
        except Exception:
            pass
        self.btn_test_sound.setProperty("class", "accent")
        
        sound_layout.addWidget(self.cmb_sound, 1)
        sound_layout.addWidget(self.btn_test_sound)
        form_r.addRow(self._tr("settings.reminders.sound_file", "Ses Dosyası:"), sound_layout)

        # Ses dosyası değişimini dinle
        self.cmb_sound.currentIndexChanged.connect(self._on_sound_select)
        self.cmb_notification_type.currentIndexChanged.connect(self._on_notification_type_change)

        # Otomatik erteleme
        self.tgl_auto_snooze = ToggleSwitch(checked=bool(settings.get("reminder_auto_snooze", False)))
        form_r.addRow(self._tr("settings.reminders.auto_snooze", "Otomatik erteleme"), self.tgl_auto_snooze)

        # Erteleme süresi
        self.spn_snooze_minutes = QSpinBox()
        self.spn_snooze_minutes.setRange(1, 60)
        self.spn_snooze_minutes.setValue(int(settings.get("reminder_snooze_minutes", 5)))
        self.spn_snooze_minutes.setSuffix(" " + self._tr("common.minutes", "dakika"))
        self.spn_snooze_minutes.setEnabled(self.tgl_auto_snooze.isChecked())
        form_r.addRow(self._tr("settings.reminders.snooze_duration", "Erteleme süresi:"), self.spn_snooze_minutes)

        def _on_auto_snooze_toggle(val):
            self.spn_snooze_minutes.setEnabled(val)
        self.tgl_auto_snooze.onToggled(_on_auto_snooze_toggle)

        # Ses kontrolü
        def _on_sound_toggle(val):
            self.cmb_sound.setEnabled(val)
            self.btn_test_sound.setEnabled(val)
        self.tgl_sound.onToggled(_on_sound_toggle)

        # ==================== SENKRONİZASYON SEKMESİ ====================
        sync_scroll = QScrollArea(self.tab_sync)
        sync_scroll.setWidgetResizable(True)
        sync_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sync_content = QWidget()
        form_sync = QFormLayout(sync_content)
        form_sync.setContentsMargins(12, 12, 12, 12)
        form_sync.setSpacing(10)
        sync_scroll.setWidget(sync_content)
        
        sync_layout = QVBoxLayout(self.tab_sync)
        sync_layout.setContentsMargins(0, 0, 0, 0)
        sync_layout.addWidget(sync_scroll)
        
        # Export/Import Başlık
        export_header = QLabel("<b>📦 Veri Aktarımı</b>")
        form_sync.addRow(export_header)
        
        # Export butonları
        export_btns = QHBoxLayout()
        export_btns.setSpacing(8)
        
        self.btn_export_json = QPushButton("📤 JSON Olarak Dışa Aktar")
        self.btn_export_json.setMinimumHeight(36)
        self.btn_export_json.setCursor(Qt.PointingHandCursor)
        self.btn_export_json.clicked.connect(self._export_to_json)
        export_btns.addWidget(self.btn_export_json)
        
        self.btn_import_json = QPushButton("📥 JSON'dan İçe Aktar")
        self.btn_import_json.setMinimumHeight(36)
        self.btn_import_json.setCursor(Qt.PointingHandCursor)
        self.btn_import_json.clicked.connect(self._import_from_json)
        export_btns.addWidget(self.btn_import_json)
        
        form_sync.addRow("", export_btns)
        
        # Export Info
        export_info = QLabel("ℹ️ JSON formatında tüm pano geçmişi, notlar, hatırlatmalar ve snippet'ler dışa aktarılır.")
        export_info.setWordWrap(True)
        export_info.setStyleSheet("color: #666; font-size: 11px;")
        form_sync.addRow("", export_info)
        
        # Ayırıcı
        form_sync.addRow(QLabel(""))
        
        # Cloud Sync Başlık
        cloud_header = QLabel("<b>☁️ Bulut Senkronizasyonu</b>")
        form_sync.addRow(cloud_header)
        
        # Google Drive
        gdrive_layout = QHBoxLayout()
        gdrive_layout.setSpacing(8)
        
        self.btn_gdrive_connect = QPushButton("🔗 Google Drive Bağla")
        self.btn_gdrive_connect.setMinimumHeight(36)
        self.btn_gdrive_connect.setCursor(Qt.PointingHandCursor)
        self.btn_gdrive_connect.clicked.connect(self._connect_google_drive)
        gdrive_layout.addWidget(self.btn_gdrive_connect)
        
        self.lbl_gdrive_status = QLabel("❌ Bağlı değil")
        self.lbl_gdrive_status.setStyleSheet("color: #888;")
        gdrive_layout.addWidget(self.lbl_gdrive_status)
        gdrive_layout.addStretch()
        
        form_sync.addRow("Google Drive:", gdrive_layout)
        
        # Otomatik sync
        self.tgl_auto_sync = ToggleSwitch(checked=bool(settings.get("auto_sync_enabled", False)))
        self.tgl_auto_sync.setEnabled(False)  # Bağlı değilken devre dışı
        form_sync.addRow("Otomatik senkronizasyon:", self.tgl_auto_sync)
        
        # Sync sıklığı
        self.cmb_sync_interval = QComboBox()
        self.cmb_sync_interval.setMinimumHeight(36)
        self.cmb_sync_interval.addItem("Her 5 dakikada", 5)
        self.cmb_sync_interval.addItem("Her 15 dakikada", 15)
        self.cmb_sync_interval.addItem("Her 30 dakikada", 30)
        self.cmb_sync_interval.addItem("Her saat", 60)
        self.cmb_sync_interval.setEnabled(False)
        sync_interval = settings.get("sync_interval_minutes", 15)
        idx = self.cmb_sync_interval.findData(sync_interval)
        if idx >= 0:
            self.cmb_sync_interval.setCurrentIndex(idx)
        form_sync.addRow("Senkronizasyon sıklığı:", self.cmb_sync_interval)
        
        # Son sync
        self.lbl_last_sync = QLabel("Son senkronizasyon: Hiç")
        self.lbl_last_sync.setStyleSheet("color: #888; font-size: 11px;")
        form_sync.addRow("", self.lbl_last_sync)
        
        # Manuel sync
        self.btn_sync_now = QPushButton("🔄 Şimdi Senkronize Et")
        self.btn_sync_now.setMinimumHeight(36)
        self.btn_sync_now.setEnabled(False)
        self.btn_sync_now.setCursor(Qt.PointingHandCursor)
        self.btn_sync_now.clicked.connect(self._sync_now)
        form_sync.addRow("", self.btn_sync_now)
        
        # Ayırıcı
        form_sync.addRow(QLabel(""))
        
        # Paylaşım Başlık
        share_header = QLabel("<b>🔗 Paylaşım</b>")
        form_sync.addRow(share_header)
        
        # Paylaşım sunucusu
        self.txt_share_server = QLineEdit()
        self.txt_share_server.setPlaceholderText("https://taxclip.com")
        self.txt_share_server.setText(settings.get("share_server_url", ""))
        self.txt_share_server.setMinimumHeight(36)
        form_sync.addRow("Paylaşım sunucusu:", self.txt_share_server)
        
        share_info = QLabel("ℹ️ Paylaşım özelliği için sunucu URL'si. Boş bırakılırsa paylaşım devre dışı kalır.")
        share_info.setWordWrap(True)
        share_info.setStyleSheet("color: #666; font-size: 11px;")
        form_sync.addRow("", share_info)
        
        # Google Drive durumunu kontrol et (defer)
        # self._check_gdrive_status() will be called in showEvent

        lay_ab = QVBoxLayout(self.tab_about)
        lay_ab.setContentsMargins(14, 14, 14, 14)
        lay_ab.setSpacing(8)

        self.lbl_title = QLabel()
        self.lbl_desc = QLabel()
        self.lbl_desc.setWordWrap(True)
        self.lbl_ai_badge = QLabel()
        self.lbl_ai_badge.setWordWrap(True)
        lay_ab.addWidget(self.lbl_title)
        lay_ab.addWidget(self.lbl_desc)
        lay_ab.addWidget(self.lbl_ai_badge)
        
        # Versiyon bilgisi ve güncelleme kontrolü
        from ..updater import get_current_version
        version_layout = QHBoxLayout()
        version_layout.setSpacing(10)
        
        self.lbl_version = QLabel(f"📦 Versiyon: v{get_current_version()}")
        self.lbl_version.setStyleSheet("font-size: 11pt; font-weight: bold;")
        version_layout.addWidget(self.lbl_version)
        
        self.btn_check_update = QPushButton("🔄 Güncelleme Kontrol Et")
        self.btn_check_update.setMinimumHeight(32)
        self.btn_check_update.setCursor(Qt.PointingHandCursor)
        self.btn_check_update.clicked.connect(self._check_for_updates)
        version_layout.addWidget(self.btn_check_update)
        
        self.lbl_update_status = QLabel("")
        self.lbl_update_status.setStyleSheet("color: #888;")
        version_layout.addWidget(self.lbl_update_status)
        version_layout.addStretch()
        
        lay_ab.addLayout(version_layout)

        links = QHBoxLayout()
        links.setSpacing(8)
        self.btn_site = QPushButton()
        self.btn_site.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://miyotu.com/")))
        self.btn_pat = QPushButton()
        self.btn_pat.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.patreon.com/c/Taxperia")))
        self.btn_coffee = QPushButton("☕ Buy Me a Coffee")
        self.btn_coffee.setCursor(Qt.PointingHandCursor)
        self.btn_coffee.setStyleSheet("""
            QPushButton {
                background-color: #FFDD00;
                color: #000000;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFE433;
            }
        """)
        self.btn_coffee.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.buymeacoffee.com/taxperia")))
        links.addWidget(self.btn_site)
        links.addWidget(self.btn_pat)
        links.addWidget(self.btn_coffee)
        links.addStretch(1)
        lay_ab.addLayout(links)

        self.grp_authors = QGroupBox()
        la = QVBoxLayout(self.grp_authors)
        la.setContentsMargins(5, 20, 5, 10)
        la.setSpacing(6)
        self.dev = QLabel("• Developer: Taxperia")
        self.des = QLabel("• Designer: Miyotu")
        self.dev.setWordWrap(True)
        self.des.setWordWrap(True)
        la.addWidget(self.dev)
        la.addWidget(self.des)
        lay_ab.addWidget(self.grp_authors)
        lay_ab.addStretch(1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_apply = QPushButton()
        self.btn_cancel = QPushButton()
        self.btn_ok = QPushButton()
        btns.addWidget(self.btn_apply)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_ok)
        root.addLayout(btns)

        self.btn_apply.clicked.connect(self._apply_and_emit)
        self.btn_ok.clicked.connect(self._apply_and_close)
        self.btn_cancel.clicked.connect(self.reject)
        self.cmb_tray.currentIndexChanged.connect(self._on_tray_select)
        self.btn_clear_hk.clicked.connect(lambda: self.txt_hotkey.setText("ctrl+shift+v"))
        self.btn_clear_hk_paste.clicked.connect(lambda: self.txt_hotkey_paste.setText(""))
        self.btn_clear_hk_quick_note.clicked.connect(lambda: self.txt_hotkey_quick_note.setText(""))
        self.btn_clear_hk_screenshot.clicked.connect(lambda: self.txt_hotkey_screenshot.setText(""))
        self.btn_clear_hk_ocr.clicked.connect(lambda: self.txt_hotkey_ocr.setText(""))
        self.btn_clear_hk_snip.clicked.connect(lambda: self.txt_hotkey_snip.setText(""))
        self.btn_preview.clicked.connect(self._preview_tray_icon)

        i18n.languageChanged.connect(self.refresh_texts)
        self._update_show_popup_state()
        self.refresh_texts()

        # Defer heavy checks to after dialog is visible
        self._deferred_inited = False
        self._gdrive_status_thread: GoogleDriveStatusThread | None = None
        self._video_probe_thread: VideoProbeThread | None = None

    def showEvent(self, event):
        super().showEvent(event)
        if not self._deferred_inited:
            self._deferred_inited = True
            QTimer.singleShot(50, self._run_deferred_init)

    def _run_deferred_init(self):
        """Heavy checks deferred to after dialog is visible."""
        self._check_totp_status()
        self._check_gdrive_status_async()
        self._check_ffmpeg_deferred()

    def _check_ffmpeg_deferred(self):
        """FFmpeg check deferred to after dialog is shown."""
        if self._video_probe_thread and self._video_probe_thread.isRunning():
            return

        self._ffmpeg_status_label.setText("⏳ FFmpeg ve mikrofonlar kontrol ediliyor...")
        self._ffmpeg_status_label.setStyleSheet("color: #888; padding: 6px;")

        thread = VideoProbeThread(self.settings, self)
        thread.probe_ready.connect(self._apply_video_probe_result)
        thread.probe_failed.connect(self._apply_video_probe_failure)
        thread.finished.connect(thread.deleteLater)
        self._video_probe_thread = thread
        thread.start()

    def _reload_microphone_devices(self, device_names=None):
        """FFmpeg ile görülen mikrofonları ayarlar ekranına doldur."""
        current_value = self.cmb_microphone.currentData() or self.settings.get("video_microphone", "default")
        self.cmb_microphone.clear()
        self.cmb_microphone.addItem("Varsayılan Mikrofon", "default")

        seen = set()
        for device_name in device_names or []:
            if not device_name or device_name in seen:
                continue
            seen.add(device_name)
            self.cmb_microphone.addItem(device_name, device_name)

        idx = self.cmb_microphone.findData(current_value)
        if idx < 0 and current_value and current_value != "default":
            self.cmb_microphone.addItem(f"Özel cihaz: {current_value}", current_value)
            idx = self.cmb_microphone.findData(current_value)
        self.cmb_microphone.setCurrentIndex(max(idx, 0))
        self.cmb_microphone.setEnabled(self.tgl_record_mic.isChecked())

    def _apply_video_probe_result(self, available: bool, encoder_info: str, device_names: list):
        if available:
            self._ffmpeg_status_label.setText(f"✅ FFmpeg: Hazır  |  Encoder: {encoder_info}")
            self._ffmpeg_status_label.setStyleSheet("color: #27ae60; font-weight: bold; padding: 6px; background: rgba(39,174,96,0.1); border-radius: 4px;")
        else:
            self._ffmpeg_status_label.setText("⚠️ FFmpeg bulunamadı! Video kayıt çalışmayacak.\nİndirin: https://www.gyan.dev/ffmpeg/builds/")
            self._ffmpeg_status_label.setStyleSheet("color: #e74c3c; font-weight: bold; padding: 6px; background: rgba(231,76,60,0.1); border-radius: 4px;")
            self._ffmpeg_status_label.setWordWrap(True)
            self._ffmpeg_status_label.setOpenExternalLinks(True)

        self._reload_microphone_devices(device_names)
        self._video_probe_thread = None

    def _apply_video_probe_failure(self, error: str):
        print(f"[VIDEO] FFmpeg probe hatası: {error}")
        self._ffmpeg_status_label.setText("⚠️ FFmpeg durumu kontrol edilemedi")
        self._ffmpeg_status_label.setStyleSheet("color: #888; padding: 6px;")
        self._reload_microphone_devices([])
        self._video_probe_thread = None

    def _browse_images_folder(self):
        """Resim klasörü seç"""
        folder = QFileDialog.getExistingDirectory(
            self,
            self._tr("settings.security.choose_images_folder", "Resim klasörü seç"),
            self.txt_external_images_path.text() or str(Path.home())
        )
        if folder:
            self.txt_external_images_path.setText(folder)
        """Resim klasörü seç"""
        folder = QFileDialog.getExistingDirectory(
            self,
            self._tr("settings.security.choose_images_folder", "Resim klasörü seç"),
            self.txt_external_images_path.text() or str(Path.home())
        )
        if folder:
            self.txt_external_images_path.setText(folder)
    
    def _browse_tesseract_path(self):
        """Tesseract.exe dosyasını seç"""
        file, _ = QFileDialog.getOpenFileName(
            self,
            "Tesseract.exe dosyasını seç",
            self.txt_tesseract_path.text() or "C:/Program Files/Tesseract-OCR",
            "Executable Files (*.exe)"
        )
        if file:
            self.txt_tesseract_path.setText(file)
    
    def _browse_video_save_path(self):
        """Video kaydetme yolunu seç"""
        current_path = self.txt_video_save_path.text() or str(Path.home() / "Videos" / "ClipStack")
        path = QFileDialog.getExistingDirectory(
            self,
            "Video Kaydetme Klasörünü Seç",
            current_path
        )
        if path:
            self.txt_video_save_path.setText(path)
    
    def _check_totp_status(self):
        """TOTP durumunu kontrol et"""
        from ..totp_manager import TOTPManager
        
        totp = TOTPManager(self.settings)
        
        if not totp.is_available():
            self.lbl_totp_status.setText("❌ pyotp yüklü değil")
            self.lbl_totp_status.setStyleSheet("color: #f44336;")
            self.btn_totp_setup.setEnabled(False)
            self.lbl_totp_info.setText("ℹ️ Kurulum için: pip install pyotp qrcode[pil]")
            return
        
        if totp.is_enabled():
            self.lbl_totp_status.setText("✅ Aktif")
            self.lbl_totp_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.btn_totp_setup.hide()
            self.btn_totp_remove.show()
            self.btn_totp_test.show()
            self.tgl_totp_on_startup.setEnabled(True)
            self.tgl_totp_hourly_lock.setEnabled(True)
            self.tgl_totp_for_sensitive.setEnabled(True)
        else:
            self.lbl_totp_status.setText("❌ Kapalı")
            self.lbl_totp_status.setStyleSheet("color: #888;")
            self.btn_totp_setup.show()
            self.btn_totp_remove.hide()
            self.btn_totp_test.hide()
            self.tgl_totp_on_startup.setEnabled(False)
            self.tgl_totp_hourly_lock.setEnabled(False)
            self.tgl_totp_for_sensitive.setEnabled(False)
    
    def _setup_totp(self):
        """TOTP kurulumu başlat"""
        from .totp_dialog import TOTPSetupDialog
        
        dialog = TOTPSetupDialog(self.settings, self)
        dialog.setup_complete.connect(self._check_totp_status)
        dialog.exec()
    
    def _remove_totp(self):
        """TOTP'yi kaldır"""
        from ..totp_manager import TOTPManager
        from .totp_dialog import TOTPVerifyDialog
        
        # Önce doğrulama iste
        verify_dialog = TOTPVerifyDialog(self.settings, self, "2FA Kaldırma Onayı")
        if verify_dialog.exec() and verify_dialog.is_verified():
            totp = TOTPManager(self.settings)
            if totp.disable():
                QMessageBox.information(
                    self,
                    "Başarılı",
                    "✅ İki faktörlü doğrulama kaldırıldı."
                )
                self._check_totp_status()
            else:
                QMessageBox.warning(
                    self,
                    "Hata",
                    "❌ 2FA kaldırılamadı."
                )
    
    def _test_totp(self):
        """TOTP doğrulamasını test et"""
        from .totp_dialog import TOTPVerifyDialog
        
        dialog = TOTPVerifyDialog(self.settings, self, "2FA Test")
        if dialog.exec() and dialog.is_verified():
            QMessageBox.information(
                self,
                "Başarılı",
                "✅ Doğrulama başarılı!"
            )

    def _on_sound_select(self, idx: int):
        """Ses dosyası seçimi değişti"""
        data = self.cmb_sound.currentData()
        print(f"[SETTINGS] Ses seçimi değişti: idx={idx}, data={data}")
        
        if data == "__custom__":
            file, _ = QFileDialog.getOpenFileName(
                self, 
                self._tr("settings.reminders.choose_sound", "Ses dosyası seç"), 
                "", 
                "Audio Files (*.mp3 *.wav *.ogg)"
            )
            if file:
                print(f"[SETTINGS] Özel ses seçildi: {file}")
                # Sonsuz döngüyü önlemek için signal'i geçici olarak kes
                self.cmb_sound.blockSignals(True)
                
                # "__custom__" itemını kaldır ve yeni özel ses olarak ekle
                custom_idx = self.cmb_sound.count() - 1
                self.cmb_sound.removeItem(custom_idx)
                
                # Özel sesi ekle
                self.cmb_sound.addItem(f"⭐ Özel: {Path(file).name}", file)
                # "__custom__" seçeneğini tekrar ekle
                self.cmb_sound.addItem(self._tr("settings.reminders.sound_custom", "➕ Özel Ses Seç..."), "__custom__")
                
                # Yeni eklenen özel sesi seç (sondan 2. item)
                self.cmb_sound.setCurrentIndex(self.cmb_sound.count() - 2)
                
                # Signal'i tekrar aç
                self.cmb_sound.blockSignals(False)
                
                # Ayarlara kaydet VE HEMEN DISKE YAZ
                self.settings.set("reminder_sound_file", file)
                self.settings.save()  # ← HEMEN KAYDET!
                print(f"[SETTINGS] Ses kaydedildi ve diske yazıldı: {file}")
            else:
                print("[SETTINGS] Özel ses seçimi iptal edildi, default'a dönüyoruz")
                self.cmb_sound.blockSignals(True)
                self.cmb_sound.setCurrentIndex(0)
                self.cmb_sound.blockSignals(False)

    def _on_notification_type_change(self, idx: int):
        self._update_show_popup_state()

    def _on_show_popup_toggle(self, state: bool):
        if self.cmb_notification_type.currentData() == "app":
            self._last_app_popup_choice = state

    def _update_show_popup_state(self):
        notif_type = self.cmb_notification_type.currentData()
        is_app = notif_type == "app"
        self.tgl_show_popup.setEnabled(is_app)
        if not is_app:
            self.tgl_show_popup.setChecked(False)
        else:
            self.tgl_show_popup.setChecked(self._last_app_popup_choice)

    @staticmethod
    def _format_sound_label(sound_path: Path) -> str:
        name = sound_path.stem.replace("_", " ").replace("-", " ").strip()
        if name:
            name = " ".join(part.capitalize() for part in name.split())
        else:
            name = sound_path.name
        return f"🔔 {name}"

    def _test_reminder_sound(self):
        """Bildirim sesini test et"""
        try:
            sound_file = self.cmb_sound.currentData()
            current_text = self.cmb_sound.currentText()
            current_index = self.cmb_sound.currentIndex()
            
            print(f"[SETTINGS TEST] Test ediliyor:")
            print(f"  - Index: {current_index}")
            print(f"  - Text: {current_text}")
            print(f"  - Data: {sound_file}")
            
            if sound_file == "default" or not sound_file or sound_file == "":
                # Windows sistem sesi
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
                print("[SETTINGS TEST] Windows default ses çalındı")
            elif sound_file == "__custom__":
                # Özel dosya seçilmemiş
                print("[SETTINGS TEST] UYARI: Özel ses seçilmemiş!")
                QMessageBox.information(
                    self,
                    "Bilgi",
                    "Lütfen önce bir ses dosyası seçin."
                )
            else:
                # Özel ses dosyası
                from pathlib import Path
                sound_path = Path(sound_file)
                
                print(f"[SETTINGS TEST] Ses dosyası kontrol ediliyor:")
                print(f"  - Path: {sound_path}")
                print(f"  - Absolute: {sound_path.absolute()}")
                print(f"  - Exists: {sound_path.exists()}")
                
                if not sound_path.exists():
                    print(f"[SETTINGS TEST] HATA: Ses dosyası bulunamadı!")
                    QMessageBox.warning(
                        self,
                        self._tr("error.title", "Hata"),
                        self._tr("error.sound_not_found", "Ses dosyası bulunamadı:\n{file}", file=sound_file)
                    )
                    return
                
                if self._sound_tester is not None:
                    try:
                        print("[SETTINGS TEST] QtMultimedia ile ses çalınıyor...")
                        self._sound_tester.stop()
                        self._sound_tester.play(sound_path)
                        return
                    except Exception as play_error:
                        print(f"[SETTINGS TEST] QtMultimedia hata verdi: {play_error}")
                        QMessageBox.warning(
                            self,
                            self._tr("error.sound_play", "Ses çalınamadı"),
                            str(play_error),
                        )
                        return

                if sound_path.suffix.lower() != ".wav":
                    print("[SETTINGS TEST] WAV olmayan dosya winsound ile çalınamaz.")
                    QMessageBox.information(
                        self,
                        self._tr("error.sound_unsupported", "Desteklenmeyen format"),
                        self._tr(
                            "error.sound_unsupported.detail",
                            "Bu sistemde yalnızca WAV dosyaları test edilebilir. QtMultimedia backend'i kullanılamıyor.",
                        ),
                    )
                    return

                import winsound
                print("[SETTINGS TEST] winsound ile WAV çalınıyor...")
                winsound.PlaySound(str(sound_path), winsound.SND_FILENAME)
                print("[SETTINGS TEST] ✓ Özel ses çalındı (winsound)")
        except Exception as e:
            print(f"[SETTINGS TEST] HATA: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(
                self,
                self._tr("error.title", "Hata"),
                self._tr("error.sound_play", "Ses çalınamadı:\n{error}", error=str(e))
            )

    def _on_sound_test_failed(self, message: str) -> None:
        QMessageBox.warning(
            self,
            self._tr("settings.reminders.sound_error_title", "Ses çalınamadı"),
            self._tr(
                "settings.reminders.sound_error_body",
                "Seçilen ses dosyası çalınamadı:\n{error}",
                error=message,
            ),
        )

    def _tr(self, key: str, fallback: str) -> str:
        try:
            v = i18n.t(key)
        except Exception:
            v = ""
        return v if v and v != key else fallback

    def refresh_texts(self):
        self.setWindowTitle(self._tr("settings.title", "Ayarlar"))
        self.tabs.setTabText(0, self._tr("settings.tab.general", "Genel"))
        self.tabs.setTabText(1, self._tr("settings.tab.appearance", "Görünüm"))
        self.tabs.setTabText(2, self._tr("settings.tab.behavior", "Davranış"))
        self.tabs.setTabText(3, self._tr("settings.tab.security", "Güvenlik"))
        self.tabs.setTabText(4, self._tr("settings.tab.video", "Video"))
        self.tabs.setTabText(5, self._tr("settings.tab.reminders", "Hatırlatmalar"))
        self.tabs.setTabText(6, self._tr("settings.tab.sync", "Senkronizasyon"))
        self.tabs.setTabText(7, self._tr("settings.tab.tray", "Tepsi & Bildirimler"))
        self.tabs.setTabText(8, self._tr("settings.tab.about", "Hakkında"))

        self.lbl_hotkey_help.setText(self._tr("settings.general.hotkey.help", "Genel kısayol tuşu (örn: windows+v, ctrl+shift+v, alt+space)"))
        self.btn_clear_hk.setText(self._tr("settings.general.hotkey.reset", "Sıfırla"))
        self.btn_clear_hk_paste.setText(self._tr("settings.general.hotkey.reset", "Sıfırla"))
        self.btn_clear_hk_quick_note.setText(self._tr("settings.general.hotkey.reset", "Sıfırla"))
        self.btn_clear_hk_screenshot.setText(self._tr("settings.general.hotkey.reset", "Sıfırla"))
        self.btn_clear_hk_ocr.setText(self._tr("settings.general.hotkey.reset", "Sıfırla"))
        self.btn_clear_hk_snip.setText(self._tr("settings.general.hotkey.reset", "Sıfırla"))

        self.btn_preview.setText(self._tr("settings.tray.preview", "Önizle"))
        self.btn_test_sound.setText(self._tr("settings.reminders.test_sound", "Test"))
        self.btn_test_sound.setToolTip(self._tr("settings.reminders.test_sound_hint", "Seçili hatırlatma sesini çal"))
        self.grp_authors.setTitle(self._tr("about.authors", "Yazarlar"))
        self.lbl_title.setText(self._tr("about.title", "<b>TaxClip</b> – Gelişmiş Pano Yöneticisi"))
        self.lbl_desc.setText(self._tr("about.desc", 
            "Metin, resim, snippet, hatırlatma, liste ve çizimler için güçlü bir pano yöneticisi. "
            "Video kayıt, OCR, hassas veri koruması ve Windows Hello desteği ile tam donanımlı."))
        self.lbl_ai_badge.setText(self._tr("about.ai_badge", 
            "🤖 <i>Bu proje yapay zeka (Claude AI) yardımıyla geliştirilmiştir.</i>"))
        self.btn_site.setText(self._tr("about.website", "Website"))
        self.btn_pat.setText(self._tr("about.patreon", "Patreon"))

        self.btn_apply.setText(self._tr("settings.buttons.apply", "Uygula"))
        self.btn_cancel.setText(self._tr("settings.buttons.cancel", "İptal"))
        self.btn_ok.setText(self._tr("settings.buttons.save", "Kaydet"))

    def _on_tray_select(self, idx: int):
        data = self.cmb_tray.currentData()
        if data == "__custom__":
            file, _ = QFileDialog.getOpenFileName(
                self, self._tr("settings.tray.choose_icon", "İkon seç (.ico önerilir)"), "", "Icon (*.ico *.png *.svg)"
            )
            if file:
                self.settings.set("tray_icon", file)
                self.cmb_tray.setItemText(idx, f"{self._tr('settings.tray.custom_prefix', 'Özel')}: {Path(file).name}")
                self.cmb_tray.setCurrentIndex(idx)
            else:
                self.cmb_tray.setCurrentIndex(0)

    def _current_tray_icon_path(self) -> str:
        data = self.cmb_tray.currentData()
        if data == "__custom__":
            return str(self.settings.get("tray_icon", "") or "")
        return str(data or self.settings.get("tray_icon", "") or "")

    def _preview_tray_icon(self):
        path = self._current_tray_icon_path()
        if not path:
            return
        icon = svg_icon(path, 64)
        pix = icon.pixmap(64, 64)

        dlg = QDialog(self)
        dlg.setWindowTitle(self._tr("settings.tray.preview_title", "İkon önizleme"))
        v = QVBoxLayout(dlg)
        lbl = QLabel()
        if not pix.isNull():
            lbl.setPixmap(pix)
        else:
            lbl.setText(self._tr("settings.tray.preview_failed", "İkon yüklenemedi."))
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)
        btn = QPushButton(self._tr("common.close", "Kapat"))
        btn.clicked.connect(dlg.accept)
        v.addWidget(btn, alignment=Qt.AlignCenter)
        dlg.exec()

    def _apply_common(self):
        self.settings.set("language", self.cmb_lang.currentData())
        self.settings.set("launch_at_startup", self.tgl_startup.isChecked())
        hk = KeyCaptureLineEdit.normalize_combo(self.txt_hotkey.text() or "ctrl+shift+v")
        self.settings.set("hotkey", hk or "ctrl+shift+v")

        hk_paste = KeyCaptureLineEdit.normalize_combo(self.txt_hotkey_paste.text() or "")
        self.settings.set("hotkey_paste_last", hk_paste)

        hk_quick = KeyCaptureLineEdit.normalize_combo(self.txt_hotkey_quick_note.text() or "")
        self.settings.set("hotkey_quick_note", hk_quick)

        hk_screenshot = KeyCaptureLineEdit.normalize_combo(self.txt_hotkey_screenshot.text() or "")
        self.settings.set("hotkey_screenshot", hk_screenshot)
        
        hk_ocr = KeyCaptureLineEdit.normalize_combo(self.txt_hotkey_ocr.text() or "")
        self.settings.set("hotkey_ocr", hk_ocr)

        hk_snip = KeyCaptureLineEdit.normalize_combo(self.txt_hotkey_snip.text() or "")
        self.settings.set("hotkey_snip", hk_snip)

        theme_key = self.cmb_theme.currentData()
        self.settings.set("theme", theme_key)
        self.settings.set("animations", self.tgl_animations.isChecked())

        self.settings.set("hide_after_copy", self.tgl_hide_after_copy.isChecked())
        self.settings.set("stay_on_top", self.tgl_stay_on_top.isChecked())
        self.settings.set("max_items", self.spn_max_items.value())
        self.settings.set("dedupe_window_ms", self.spn_dedupe_ms.value())
        self.settings.set("confirm_delete", self.tgl_confirm_delete.isChecked())
        self.settings.set("show_toast", self.tgl_toast.isChecked())

        self.settings.set("encrypt_data", self.tgl_encrypt.isChecked())
        
        # TOTP ayarları
        self.settings.set("totp_on_startup", self.tgl_totp_on_startup.isChecked())
        self.settings.set("totp_hourly_lock", self.tgl_totp_hourly_lock.isChecked())
        self.settings.set("totp_for_sensitive", self.tgl_totp_for_sensitive.isChecked())
        
        # Hassas veri ayarları
        self.settings.set("sensitive_data_detection", self.tgl_sensitive_detection.isChecked())
        self.settings.set("mask_credit_cards", self.tgl_mask_credit_cards.isChecked())
        self.settings.set("mask_passwords", self.tgl_mask_passwords.isChecked())
        self.settings.set("mask_api_keys", self.tgl_mask_api_keys.isChecked())
        self.settings.set("mask_emails", self.tgl_mask_emails.isChecked())
        self.settings.set("mask_phones", self.tgl_mask_phones.isChecked())
        self.settings.set("mask_tc_ids", self.tgl_mask_tc_ids.isChecked())
        self.settings.set("mask_ibans", self.tgl_mask_ibans.isChecked())
        self.settings.set("block_sensitive_data", self.tgl_block_sensitive.isChecked())
        
        self.settings.set("save_images_externally", self.tgl_save_images_externally.isChecked())
        self.settings.set("external_images_path", self.txt_external_images_path.text())
        self.settings.set("auto_delete_enabled", self.tgl_auto_delete.isChecked())
        self.settings.set("auto_delete_days", self.cmb_auto_delete.currentData())
        self.settings.set("auto_delete_keep_fav", self.tgl_keep_fav.isChecked())
        
        # OCR ayarları
        self.settings.set("ocr_enabled", self.tgl_ocr.isChecked())
        self.settings.set("ocr_language", self.cmb_ocr_language.currentData())
        self.settings.set("tesseract_path", self.txt_tesseract_path.text())
        
        # Video ayarları
        self.settings.set("video_save_path", self.txt_video_save_path.text())
        self.settings.set("video_quality", self.cmb_video_quality.currentData())
        self.settings.set("video_fps", self.cmb_video_fps.currentData())
        self.settings.set("video_bitrate", self.spn_video_bitrate.value())
        self.settings.set("video_record_mic", self.tgl_record_mic.isChecked())
        self.settings.set("video_microphone", self.cmb_microphone.currentData())
        
        hk_video_record = KeyCaptureLineEdit.normalize_combo(self.txt_hotkey_video_record.text() or "")
        self.settings.set("hotkey_video_record", hk_video_record)
        
        hk_instant_replay = KeyCaptureLineEdit.normalize_combo(self.txt_hotkey_instant_replay.text() or "")
        self.settings.set("hotkey_instant_replay", hk_instant_replay)
        
        self.settings.set("instant_replay_buffer_seconds", self.spn_replay_buffer.value())

        data = self.cmb_tray.currentData()
        if data and data != "__custom__":
            self.settings.set("tray_icon", data)
        self.settings.set("tray_notifications", self.tgl_tray_notifications.isChecked())

        # Hatırlatma ayarları
        self.settings.set("reminder_notification_type", self.cmb_notification_type.currentData())
        self.settings.set("reminder_show_popup", self.tgl_show_popup.isChecked())
        self.settings.set("reminder_sound_enabled", self.tgl_sound.isChecked())
        
        sound_data = self.cmb_sound.currentData()
        if sound_data and sound_data != "__custom__":
            self.settings.set("reminder_sound_file", sound_data)
        
        self.settings.set("reminder_auto_snooze", self.tgl_auto_snooze.isChecked())
        self.settings.set("reminder_snooze_minutes", self.spn_snooze_minutes.value())

        self.settings.save()
        try:
            theme_manager.apply(theme_key)
        except Exception:
            pass

    def _apply_and_emit(self):
        self._apply_common()
        self.applied.emit()

    def _apply_and_close(self):
        self._apply_common()
        self.accept()

    # ==================== SENKRONİZASYON METODLARI ====================
    
    def _export_to_json(self):
        """Tüm verileri JSON dosyasına aktar"""
        import json
        from datetime import datetime
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("settings.sync.export_title", "Verileri Dışa Aktar"),
            f"taxclip_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        
        if not file_path:
            return
            
        try:
            # Storage'dan verileri al
            from pathlib import Path
            from clipstack.storage import Storage
            data_dir = Path.home() / "AppData" / "Roaming" / "TaxClip"
            storage = Storage(data_dir / "taxclip.db", self.settings)
            
            export_data = {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "clips": [],
                "notes": [],
                "reminders": [],
                "snippets": [],
                "todos": [],
                "drawings": [],
                "settings": {}
            }
            
            # Klipleri al
            clips = storage.list_items(limit=10000)
            for clip in clips:
                clip_entry = {
                    "id": clip.get("id"),
                    "item_type": clip.get("item_type"),
                    "text_content": clip.get("text_content"),
                    "html_content": clip.get("html_content"),
                    "favorite": clip.get("favorite"),
                    "created_at": clip.get("created_at"),
                    "ocr_text": clip.get("ocr_text")
                }
                # Resimleri base64 olarak ekle
                if clip.get("image_blob"):
                    import base64
                    clip_entry["image_base64"] = base64.b64encode(clip["image_blob"]).decode("utf-8")
                export_data["clips"].append(clip_entry)
            
            # Notları al
            notes = storage.list_notes(limit=10000)
            for note in notes:
                export_data["notes"].append({
                    "id": note.get("id"),
                    "title": note.get("title", ""),
                    "content": note.get("content"),
                    "created_at": note.get("created_at"),
                    "updated_at": note.get("updated_at")
                })
            
            # Hatırlatıcıları al
            reminders = storage.list_reminders(limit=10000)
            for rem in reminders:
                export_data["reminders"].append({
                    "id": rem.get("id"),
                    "title": rem.get("title"),
                    "description": rem.get("description"),
                    "reminder_time": rem.get("reminder_time"),
                    "repeat": rem.get("repeat_type"),
                    "completed": rem.get("completed")
                })
            
            # Snippetları al
            snippets = storage.list_snippets(limit=10000)
            for snip in snippets:
                export_data["snippets"].append({
                    "id": snip.get("id"),
                    "title": snip.get("title"),
                    "content": snip.get("code"),
                    "language": snip.get("language"),
                    "tags": snip.get("tags"),
                    "created_at": snip.get("created_at")
                })
            
            # Todoları al
            todos = storage.list_todos()
            for todo in todos:
                export_data["todos"].append({
                    "id": todo.get("id"),
                    "title": todo.get("content"),  # todos tablosunda 'content' kullanılıyor
                    "completed": todo.get("completed"),
                    "list_id": todo.get("list_id"),
                    "created_at": todo.get("created_at")
                })
            
            # Çizimleri al
            drawings = storage.list_drawings(limit=10000)
            for drawing in drawings:
                export_data["drawings"].append({
                    "id": drawing.get("id"),
                    "title": drawing.get("title"),
                    "image_data": drawing.get("image"),  # list_drawings 'image' olarak dönüyor
                    "created_at": drawing.get("created_at")
                })
            
            # Ayarları al
            all_settings = self.settings._data.copy() if hasattr(self.settings, '_data') else {}
            # Hassas verileri çıkar
            safe_settings = {k: v for k, v in all_settings.items() 
                           if not any(x in k.lower() for x in ['password', 'secret', 'key', 'token'])}
            export_data["settings"] = safe_settings
            
            # JSON'a yaz
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            
            total_items = (len(export_data["clips"]) + len(export_data["notes"]) + 
                          len(export_data["reminders"]) + len(export_data["snippets"]) + 
                          len(export_data["todos"]) + len(export_data["drawings"]))
            
            QMessageBox.information(
                self,
                self._tr("settings.sync.export_success", "Dışa Aktarma Başarılı"),
                f"✅ {total_items} öğe başarıyla dışa aktarıldı!\n\n📁 {file_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                self._tr("settings.sync.export_error", "Dışa Aktarma Hatası"),
                f"❌ Dışa aktarma başarısız:\n{str(e)}"
            )
    
    def _import_from_json(self):
        """JSON dosyasından verileri içe aktar"""
        import json
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("settings.sync.import_title", "Verileri İçe Aktar"),
            "",
            "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        # Onay iste
        reply = QMessageBox.question(
            self,
            self._tr("settings.sync.import_confirm_title", "İçe Aktarma Onayı"),
            self._tr("settings.sync.import_confirm_msg", 
                    "⚠️ Mevcut verileriniz korunacak, yeni veriler eklenecek.\n\nDevam etmek istiyor musunuz?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            from pathlib import Path
            from clipstack.storage import Storage
            data_dir = Path.home() / "AppData" / "Roaming" / "TaxClip"
            storage = Storage(data_dir / "taxclip.db", self.settings)
            
            imported_counts = {
                "clips": 0,
                "notes": 0,
                "reminders": 0,
                "snippets": 0,
                "todos": 0,
                "drawings": 0
            }
            
            # Klipleri içe aktar
            from clipstack.storage import ClipItemType
            for clip in import_data.get("clips", []):
                try:
                    item_type_val = clip.get("item_type", 1)
                    item_type = ClipItemType(item_type_val) if isinstance(item_type_val, int) else ClipItemType.TEXT
                    text_content = clip.get("text_content") or clip.get("content", "")
                    html_content = clip.get("html_content")
                    image_bytes = None
                    if clip.get("image_base64"):
                        import base64
                        image_bytes = base64.b64decode(clip["image_base64"])
                    created_at = clip.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    storage.add_item(
                        item_type=item_type,
                        text=text_content,
                        image_bytes=image_bytes,
                        html=html_content,
                        created_at=created_at,
                        ocr_text=clip.get("ocr_text")
                    )
                    imported_counts["clips"] += 1
                except Exception:
                    pass
            
            # Notları içe aktar
            for note in import_data.get("notes", []):
                try:
                    from datetime import datetime
                    storage.add_note(
                        content=note.get("content", ""),
                        created_at=note.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    imported_counts["notes"] += 1
                except:
                    pass
            
            # Hatırlatıcıları içe aktar
            for rem in import_data.get("reminders", []):
                try:
                    storage.add_reminder(
                        title=rem.get("title", "İçe Aktarılan Hatırlatıcı"),
                        description=rem.get("description", ""),
                        reminder_time=rem.get("reminder_time"),
                        repeat_type=rem.get("repeat", "none")
                    )
                    imported_counts["reminders"] += 1
                except:
                    pass
            
            # Snippetları içe aktar
            for snip in import_data.get("snippets", []):
                try:
                    storage.add_snippet(
                        title=snip.get("title", "İçe Aktarılan Snippet"),
                        code=snip.get("content", ""),
                        language=snip.get("language", "text"),
                        tags=snip.get("tags", "")
                    )
                    imported_counts["snippets"] += 1
                except:
                    pass
            
            # Todoları içe aktar (varsayılan liste id=1)
            for todo in import_data.get("todos", []):
                try:
                    storage.add_todo(
                        list_id=1,  # Varsayılan liste
                        content=todo.get("title", "") or todo.get("content", "İçe Aktarılan Görev")
                    )
                    imported_counts["todos"] += 1
                except:
                    pass
            
            # Çizimleri içe aktar
            for drawing in import_data.get("drawings", []):
                try:
                    storage.add_drawing(
                        image_data=drawing.get("image_data", ""),
                        title=drawing.get("title", "İçe Aktarılan Çizim")
                    )
                    imported_counts["drawings"] += 1
                except:
                    pass
            
            total = sum(imported_counts.values())
            
            QMessageBox.information(
                self,
                self._tr("settings.sync.import_success", "İçe Aktarma Başarılı"),
                f"✅ Toplam {total} öğe başarıyla içe aktarıldı!\n\n"
                f"📋 Klipler: {imported_counts['clips']}\n"
                f"📝 Notlar: {imported_counts['notes']}\n"
                f"⏰ Hatırlatıcılar: {imported_counts['reminders']}\n"
                f"💻 Snippetlar: {imported_counts['snippets']}\n"
                f"✅ Görevler: {imported_counts['todos']}\n"
                f"🎨 Çizimler: {imported_counts['drawings']}"
            )
            
        except json.JSONDecodeError:
            QMessageBox.critical(
                self,
                self._tr("settings.sync.import_error", "İçe Aktarma Hatası"),
                "❌ Geçersiz JSON dosyası!"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                self._tr("settings.sync.import_error", "İçe Aktarma Hatası"),
                f"❌ İçe aktarma başarısız:\n{str(e)}"
            )
    
    def _connect_google_drive(self):
        """Google Drive'a bağlan/bağlantıyı kes"""
        from clipstack.gdrive_sync import GoogleDriveSync
        
        sync = GoogleDriveSync(self.settings)
        
        if sync.is_connected():
            # Bağlantıyı kes
            reply = QMessageBox.question(
                self,
                self._tr("settings.sync.gdrive_disconnect_title", "Bağlantıyı Kes"),
                self._tr("settings.sync.gdrive_disconnect_msg", "Google Drive bağlantısını kesmek istediğinize emin misiniz?"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                success, msg = sync.disconnect()
                if success:
                    QMessageBox.information(self, "Başarılı", "✅ Bağlantı kesildi")
                else:
                    QMessageBox.warning(self, "Hata", f"❌ {msg}")
        else:
            # Bağlan
            if not sync.is_available():
                QMessageBox.warning(
                    self,
                    self._tr("settings.sync.gdrive_not_available", "Eksik Kütüphane"),
                    "Google Drive entegrasyonu için aşağıdaki kütüphaneler gerekli:\n\n"
                    "pip install google-auth-oauthlib google-api-python-client\n\n"
                    "Şimdilik JSON dışa/içe aktarma özelliklerini kullanabilirsiniz."
                )
                return
            
            # OAuth akışını başlat
            success, msg = sync.connect()
            
            if success:
                QMessageBox.information(
                    self,
                    self._tr("settings.sync.gdrive_connected", "Bağlandı"),
                    f"✅ {msg}"
                )
            else:
                QMessageBox.warning(
                    self,
                    self._tr("settings.sync.gdrive_error", "Bağlantı Hatası"),
                    f"❌ {msg}"
                )
        
        self._check_gdrive_status()
    
    def _check_gdrive_status(self):
        """Google Drive bağlantı durumunu kontrol et"""
        from clipstack.gdrive_sync import GoogleDriveSync
        
        sync = GoogleDriveSync(self.settings)
        gdrive_connected = sync.is_connected()
        
        if gdrive_connected:
            self.lbl_gdrive_status.setText("✅ Bağlı")
            self.lbl_gdrive_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.btn_gdrive_connect.setText("🔓 Bağlantıyı Kes")
            self.btn_sync_now.setEnabled(True)
        else:
            self.lbl_gdrive_status.setText("❌ Bağlı Değil")
            self.lbl_gdrive_status.setStyleSheet("color: #f44336; font-weight: bold;")
            self.btn_gdrive_connect.setText("🔗 Google Drive'a Bağlan")
            self.btn_sync_now.setEnabled(False)

    def _check_gdrive_status_async(self):
        if self._gdrive_status_thread and self._gdrive_status_thread.isRunning():
            return

        self.lbl_gdrive_status.setText("⏳ Durum kontrol ediliyor...")
        self.lbl_gdrive_status.setStyleSheet("color: #888;")

        thread = GoogleDriveStatusThread(self)
        thread.status_ready.connect(self._apply_gdrive_status)
        thread.status_failed.connect(self._apply_gdrive_status_failure)
        thread.finished.connect(thread.deleteLater)
        self._gdrive_status_thread = thread
        thread.start()

    def _apply_gdrive_status(self, connected: bool):
        if connected:
            self.lbl_gdrive_status.setText("✅ Bağlı")
            self.lbl_gdrive_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.btn_gdrive_connect.setText("🔓 Bağlantıyı Kes")
            self.btn_sync_now.setEnabled(True)
        else:
            self.lbl_gdrive_status.setText("❌ Bağlı Değil")
            self.lbl_gdrive_status.setStyleSheet("color: #f44336; font-weight: bold;")
            self.btn_gdrive_connect.setText("🔗 Google Drive'a Bağlan")
            self.btn_sync_now.setEnabled(False)
        self._gdrive_status_thread = None

    def _apply_gdrive_status_failure(self, error: str):
        print(f"[GDRIVE] Durum kontrol hatası: {error}")
        self.lbl_gdrive_status.setText("❌ Bağlı Değil")
        self.lbl_gdrive_status.setStyleSheet("color: #f44336; font-weight: bold;")
        self.btn_gdrive_connect.setText("🔗 Google Drive'a Bağlan")
        self.btn_sync_now.setEnabled(False)
        self._gdrive_status_thread = None
    
    def _sync_now(self):
        """Manuel senkronizasyon başlat - Google Drive'a yedekle"""
        from clipstack.gdrive_sync import GoogleDriveSync
        
        sync = GoogleDriveSync(self.settings)
        
        if not sync.is_connected():
            QMessageBox.warning(
                self,
                self._tr("settings.sync.not_connected", "Bağlı Değil"),
                "Önce Google Drive'a bağlanmalısınız."
            )
            return
        
        try:
            # Export verilerini hazırla
            import json
            from datetime import datetime
            from pathlib import Path
            from clipstack.storage import Storage
            
            data_dir = Path.home() / "AppData" / "Roaming" / "TaxClip"
            storage = Storage(data_dir / "taxclip.db", self.settings)
            
            export_data = {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "clips": [],
                "notes": [],
                "reminders": [],
                "snippets": [],
                "todos": [],
                "drawings": []
            }
            
            # Verileri topla
            clips = storage.list_items(limit=10000)
            for clip in clips:
                clip_entry = {
                    "id": clip.get("id"),
                    "item_type": clip.get("item_type"),
                    "text_content": clip.get("text_content"),
                    "html_content": clip.get("html_content"),
                    "favorite": clip.get("favorite"),
                    "created_at": clip.get("created_at"),
                    "ocr_text": clip.get("ocr_text")
                }
                if clip.get("image_blob"):
                    import base64
                    clip_entry["image_base64"] = base64.b64encode(clip["image_blob"]).decode("utf-8")
                export_data["clips"].append(clip_entry)
            
            export_data["notes"] = storage.list_notes(limit=10000)
            export_data["reminders"] = storage.list_reminders(limit=10000)
            export_data["snippets"] = storage.list_snippets(limit=10000)
            export_data["todos"] = storage.list_todos()
            export_data["drawings"] = storage.list_drawings(limit=10000)
            
            json_data = json.dumps(export_data, ensure_ascii=False, indent=2, default=str)
            
            # Google Drive'a yükle
            success, result = sync.upload_backup(json_data)
            
            if success:
                QMessageBox.information(
                    self,
                    self._tr("settings.sync.sync_success", "Senkronizasyon Başarılı"),
                    f"✅ Veriler Google Drive'a yedeklendi!\n\nDosya ID: {result}"
                )
            else:
                QMessageBox.warning(
                    self,
                    self._tr("settings.sync.sync_error", "Senkronizasyon Hatası"),
                    f"❌ {result}"
                )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                self._tr("settings.sync.sync_error", "Senkronizasyon Hatası"),
                f"❌ Senkronizasyon başarısız:\n{str(e)}"
            )

    def _check_for_updates(self):
        """GitHub'dan güncelleme kontrolü yap"""
        from ..updater import Updater, show_update_dialog
        
        self.btn_check_update.setEnabled(False)
        self.lbl_update_status.setText("⏳ Kontrol ediliyor...")
        
        self._updater = Updater(self.settings, self)
        
        def on_update_available(update_info):
            self.btn_check_update.setEnabled(True)
            self.lbl_update_status.setText(f"✅ v{update_info['version']} mevcut!")
            self.lbl_update_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
            show_update_dialog(self, update_info, self._updater)
        
        def on_no_update():
            self.btn_check_update.setEnabled(True)
            self.lbl_update_status.setText("✓ Güncel")
            self.lbl_update_status.setStyleSheet("color: #4CAF50;")
        
        def on_check_failed(error):
            self.btn_check_update.setEnabled(True)
            self.lbl_update_status.setText("❌ Kontrol başarısız")
            self.lbl_update_status.setStyleSheet("color: #f44336;")
            print(f"[UPDATE] Kontrol hatası: {error}")
        
        # Sinyalleri Updater üzerinden bağla (thread check_for_updates'te oluşturulur)
        self._updater.update_available.connect(on_update_available)
        self._updater.update_failed.connect(on_check_failed)
        
        # Önce check başlat (thread oluşturulur)
        self._updater.check_for_updates(silent=False)
        
        # Şimdi thread oluşturuldu, no_update sinyalini bağla
        if self._updater._checker_thread:
            self._updater._checker_thread.no_update.connect(on_no_update)
            self._updater._checker_thread.check_failed.connect(on_check_failed)
