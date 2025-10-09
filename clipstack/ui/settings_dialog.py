from __future__ import annotations

from pathlib import Path
from typing import Dict

from PySide6.QtCore import Qt, Signal, QUrl
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
)
from clipstack.ui.widgets.toggle_switch import ToggleSwitch

from ..settings import Settings
from ..utils import resource_path
from ..i18n import i18n
from ..theme_manager import theme_manager
from .widgets.toggle_switch import ToggleSwitch


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
    ("default", "Default"),
    ("dark", "Dark"),
    ("light", "Light"),
    ("purple", "Purple"),
]


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
        """
        windows/win -> windows, ctrl/control -> ctrl, menü -> alt vb.
        Modifier sırası: ctrl, shift, alt, windows. Tekrarlı modları düşürür.
        """
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
        # Sadece modifier basıldıysa bekle (ana tuşla birlikte yazacağız)
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

        self.setWindowTitle("Settings")
        try:
            self.setWindowIcon(QIcon(str(resource_path("assets/icons/gear.svg"))))
        except Exception:
            pass
        self.resize(760, 560)

        # Tabs
        self.tabs = QTabWidget(self)
        self.tab_general = QWidget()
        self.tab_appearance = QWidget()
        self.tab_behavior = QWidget()
        self.tab_tray = QWidget()
        self.tab_about = QWidget()

        self.tabs.addTab(self.tab_general, "")
        self.tabs.addTab(self.tab_appearance, "")
        self.tabs.addTab(self.tab_behavior, "")
        self.tabs.addTab(self.tab_tray, "")
        self.tabs.addTab(self.tab_about, "")

        root = QVBoxLayout(self)
        root.addWidget(self.tabs)

        # Genel
        form_g = QFormLayout(self.tab_general)
        form_g.setContentsMargins(12, 12, 12, 12)
        form_g.setSpacing(10)

        self.cmb_lang = QComboBox()
        self.cmb_lang.setObjectName("ModernCombo")
        for code, label in LANG_MAP.items():
            self.cmb_lang.addItem(label, code)
        self.cmb_lang.setCurrentIndex(max(0, self.cmb_lang.findData(settings.get("language", "tr"))))

        self.tgl_startup = ToggleSwitch(checked=bool(settings.get("launch_at_startup", True)))

        self.txt_hotkey = KeyCaptureLineEdit()
        # Kaydedilmiş değeri normalize ederek göster
        self.txt_hotkey.setText(KeyCaptureLineEdit.normalize_combo(str(settings.get("hotkey", "ctrl+shift+v"))))
        self.btn_clear_hk = QPushButton()

        # Layout for hotkey row
        hk_row = QHBoxLayout()
        hk_row.addWidget(self.txt_hotkey, 1)
        hk_row.addWidget(self.btn_clear_hk)

        self.lbl_hotkey_help = QLabel()
        form_g.addRow(self.lbl_hotkey_help)
        form_g.addRow(self._tr("settings.general.hotkey.label", "Global hotkey"), hk_row)
        form_g.addRow(self._tr("settings.general.language", "App language"), self.cmb_lang)
        form_g.addRow(self._tr("settings.general.launch_at_startup", "Launch with Windows"), self.tgl_startup)

        # Görünüm
        form_a = QFormLayout(self.tab_appearance)
        form_a.setContentsMargins(12, 12, 12, 12)
        form_a.setSpacing(10)
        self.cmb_theme = QComboBox()
        for key, label in THEMES:
            self.cmb_theme.addItem(label, key)
        self.cmb_theme.setCurrentIndex(max(0, self.cmb_theme.findData(settings.get("theme", "default"))))
        self.tgl_animations = ToggleSwitch(checked=bool(settings.get("animations", True)))
        form_a.addRow(self._tr("settings.appearance.theme", "Theme"), self.cmb_theme)
        form_a.addRow(self._tr("settings.appearance.animations", "Enable animations"), self.tgl_animations)

        # Davranış
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

        form_b.addRow(self._tr("settings.behavior.hide_after_copy", "Hide window after copy"), self.tgl_hide_after_copy)
        form_b.addRow(self._tr("settings.behavior.stay_on_top", "Keep window on top"), self.tgl_stay_on_top)
        form_b.addRow(self._tr("settings.behavior.max_items", "Max items"), self.spn_max_items)
        form_b.addRow(self._tr("settings.behavior.dedupe_ms", "De-duplication window (ms)"), self.spn_dedupe_ms)
        form_b.addRow(self._tr("settings.behavior.confirm_delete", "Ask confirmation before delete"), self.tgl_confirm_delete)
        form_b.addRow(self._tr("settings.behavior.show_toast", "Show in-app toast"), self.tgl_toast)

        self.tgl_encrypt = ToggleSwitch(checked=bool(settings.get("encrypt_data", False)))
        form_g.addRow("Panoyu ve notları şifrele (AES-256)", self.tgl_encrypt)

        self.tgl_auto_delete = ToggleSwitch(checked=bool(settings.get("auto_delete_enabled", False)))
        self.cmb_auto_delete = QComboBox()
        for d in [7, 10, 14, 30, 60, 90, 120, 180, 365]:
            self.cmb_auto_delete.addItem(f"{d} gün", d)
        self.cmb_auto_delete.setCurrentIndex([7, 10, 14, 30, 60, 90, 120, 180, 365].index(settings.get("auto_delete_days", 7)))
        self.cmb_auto_delete.setEnabled(self.tgl_auto_delete.isChecked())
        form_g.addRow("Otomatik silme", self.tgl_auto_delete)
        form_g.addRow("Silme süresi", self.cmb_auto_delete)

        self.tgl_keep_fav = ToggleSwitch(checked=bool(settings.get("auto_delete_keep_fav", True)))
        form_g.addRow("Favoriler silinmesin", self.tgl_keep_fav)

        # Switch açıldığında dropdownu aktif et
        def _on_auto_delete_toggle(val):
            self.cmb_auto_delete.setEnabled(val)
        self.tgl_auto_delete.onToggled(_on_auto_delete_toggle)

        # Tepsi & Bildirim
        lay_t = QVBoxLayout(self.tab_tray)
        lay_t.setContentsMargins(12, 12, 12, 12)
        lay_t.setSpacing(10)

        form_t = QFormLayout()
        self.cmb_tray = QComboBox()
        # 10 varsayılan ikon
        for i in range(1, 11):
            self.cmb_tray.addItem(f"Icon {i}", f"assets/icons/tray/tray{i}.svg")
        self.cmb_tray.addItem(self._tr("settings.tray.icon.custom", "Choose custom…"), "__custom__")
        sel = self.settings.get("tray_icon", "assets/icons/tray/tray1.svg")
        idx = self.cmb_tray.findData(sel)
        if idx < 0:
            idx = 0
        self.cmb_tray.setCurrentIndex(idx)
        form_t.addRow(self._tr("settings.tray.icon", "Tray icon"), self.cmb_tray)

        self.btn_preview = QPushButton()
        form_t.addRow("", self.btn_preview)

        self.tgl_tray_notifications = ToggleSwitch(checked=bool(settings.get("tray_notifications", True)))
        form_t.addRow(self._tr("settings.tray.notifications", "Show tray notifications"), self.tgl_tray_notifications)
        lay_t.addLayout(form_t)

        # Hakkında
        lay_ab = QVBoxLayout(self.tab_about)
        lay_ab.setContentsMargins(14, 14, 14, 14)
        lay_ab.setSpacing(8)

        self.lbl_title = QLabel()
        self.lbl_desc = QLabel()
        self.lbl_desc.setWordWrap(True)
        lay_ab.addWidget(self.lbl_title)
        lay_ab.addWidget(self.lbl_desc)

        links = QHBoxLayout()
        links.setSpacing(8)
        self.btn_site = QPushButton()
        self.btn_site.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://miyotu.com/")))
        self.btn_pat = QPushButton()
        self.btn_pat.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.patreon.com/c/Taxperia")))
        links.addWidget(self.btn_site)
        links.addWidget(self.btn_pat)
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

        # Alt butonlar
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_apply = QPushButton()
        self.btn_cancel = QPushButton()
        self.btn_ok = QPushButton()
        btns.addWidget(self.btn_apply)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_ok)
        root.addLayout(btns)

        # Etkileşimler
        self.btn_apply.clicked.connect(self._apply_and_emit)
        self.btn_ok.clicked.connect(self._apply_and_close)
        self.btn_cancel.clicked.connect(self.reject)
        self.cmb_tray.currentIndexChanged.connect(self._on_tray_select)
        # Reset -> ctrl+shift+v
        self.btn_clear_hk.clicked.connect(lambda: self.txt_hotkey.setText("ctrl+shift+v"))
        self.btn_preview.clicked.connect(self._preview_tray_icon)

        # Modern combobox stili
        try:
            qss_path = resource_path("styles/widgets/combobox_modern.qss")
            if qss_path.exists():
                self.cmb_lang.setStyleSheet(qss_path.read_text("utf-8"))
        except Exception:
            pass

        # Dil değişince metinleri tazele
        i18n.languageChanged.connect(self.refresh_texts)
        self.refresh_texts()

    def _tr(self, key: str, fallback: str) -> str:
        try:
            v = i18n.t(key)
        except Exception:
            v = ""
        return v if v and v != key else fallback

    def refresh_texts(self):
        self.setWindowTitle(self._tr("settings.title", "Settings"))
        self.tabs.setTabText(0, self._tr("settings.tab.general", "General"))
        self.tabs.setTabText(1, self._tr("settings.tab.appearance", "Appearance"))
        self.tabs.setTabText(2, self._tr("settings.tab.behavior", "Behavior"))
        self.tabs.setTabText(3, self._tr("settings.tab.tray", "Tray & Notifications"))
        self.tabs.setTabText(4, self._tr("settings.tab.about", "About"))

        self.lbl_hotkey_help.setText(self._tr("settings.general.hotkey.help", "Global hotkey (e.g., windows+v, ctrl+shift+v, alt+space)"))
        self.btn_clear_hk.setText(self._tr("settings.general.hotkey.reset", "Reset"))

        self.btn_preview.setText(self._tr("settings.tray.preview", "Preview"))
        self.grp_authors.setTitle(self._tr("about.authors", "Authors"))
        self.lbl_title.setText(self._tr("about.title", "<b>ClipStack</b> – Clipboard History"))
        self.lbl_desc.setText(self._tr("about.desc", "A fast clipboard manager for text, links and images."))
        self.btn_site.setText(self._tr("about.website", "Website"))
        self.btn_pat.setText(self._tr("about.patreon", "Patreon"))

        self.btn_apply.setText(self._tr("settings.buttons.apply", "Apply"))
        self.btn_cancel.setText(self._tr("settings.buttons.cancel", "Cancel"))
        self.btn_ok.setText(self._tr("settings.buttons.save", "Save"))

    def _on_tray_select(self, idx: int):
        data = self.cmb_tray.currentData()
        if data == "__custom__":
            file, _ = QFileDialog.getOpenFileName(
                self, self._tr("settings.tray.choose_icon", "Choose icon (.ico recommended)"), "", "Icon (*.ico *.png *.svg)"
            )
            if file:
                self.settings.set("tray_icon", file)
                self.cmb_tray.setItemText(idx, f"{self._tr('settings.tray.custom_prefix', 'Custom')}: {Path(file).name}")
                self.cmb_tray.setCurrentIndex(idx)
            else:
                self.cmb_tray.setCurrentIndex(0)

    def _preview_tray_icon(self):
        data = self.cmb_tray.currentData()
        path = self.settings.get("tray_icon", "") if data == "__custom__" else data
        if not path:
            return
        p = resource_path(path) if not Path(path).is_absolute() else Path(path)
        icon = QIcon(str(p))
        pix = icon.pixmap(64, 64)

        dlg = QDialog(self)
        dlg.setWindowTitle(self._tr("settings.tray.preview_title", "Icon preview"))
        v = QVBoxLayout(dlg)
        lbl = QLabel()
        if not pix.isNull():
            lbl.setPixmap(pix)
        else:
            lbl.setText(self._tr("settings.tray.preview_failed", "Icon could not be loaded."))
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)
        btn = QPushButton(self._tr("common.close", "Close"))
        btn.clicked.connect(dlg.accept)
        v.addWidget(btn, alignment=Qt.AlignCenter)
        dlg.exec()

    def _apply_common(self):
        # Genel
        self.settings.set("language", self.cmb_lang.currentData())
        self.settings.set("launch_at_startup", self.tgl_startup.isChecked())
        # Hotkey’i normalize ederek ve boşsa varsayılanla kaydet
        hk = KeyCaptureLineEdit.normalize_combo(self.txt_hotkey.text() or "ctrl+shift+v")
        self.settings.set("hotkey", hk or "ctrl+shift+v")

        # Görünüm
        theme_key = self.cmb_theme.currentData()
        self.settings.set("theme", theme_key)
        self.settings.set("animations", self.tgl_animations.isChecked())

        # Davranış
        self.settings.set("hide_after_copy", self.tgl_hide_after_copy.isChecked())
        self.settings.set("stay_on_top", self.tgl_stay_on_top.isChecked())
        self.settings.set("max_items", self.spn_max_items.value())
        self.settings.set("dedupe_window_ms", self.spn_dedupe_ms.value())
        self.settings.set("confirm_delete", self.tgl_confirm_delete.isChecked())
        self.settings.set("show_toast", self.tgl_toast.isChecked())

        self.settings.set("encrypt_data", self.tgl_encrypt.isChecked())
        self.settings.set("auto_delete_enabled", self.tgl_auto_delete.isChecked())
        self.settings.set("auto_delete_days", self.cmb_auto_delete.currentData())
        self.settings.set("auto_delete_keep_fav", self.tgl_keep_fav.isChecked())
        self.settings.save()

        # Tepsi
        data = self.cmb_tray.currentData()
        if data and data != "__custom__":
            self.settings.set("tray_icon", data)
        self.settings.set("tray_notifications", self.tgl_tray_notifications.isChecked())

        # Kaydet + temayı anında uygula
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