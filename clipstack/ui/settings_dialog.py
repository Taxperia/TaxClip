from __future__ import annotations
from pathlib import Path
from typing import Dict

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QComboBox,
    QHBoxLayout, QPushButton, QFileDialog, QLabel, QSpinBox, QGroupBox
)

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
    ("default", "Default (Blue)"),
    ("dark", "Dark (#181818)"),
    ("light", "Light"),
    ("purple", "Purple (#0e0c16)"),
]

TRAY_ICONS = [f"assets/icons/tray/tray{i}.svg" for i in range(1, 11)]


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.setWindowIcon(QIcon(str(resource_path("assets/icons/gear.svg"))))
        self.resize(700, 520)
        self.settings = settings

        self.tabs = QTabWidget(self)

        self.tab_general = QWidget()
        self.tab_appearance = QWidget()
        self.tab_behavior = QWidget()
        self.tab_tray = QWidget()
        self.tab_about = QWidget()

        self.tabs.addTab(self.tab_general, "Genel")
        self.tabs.addTab(self.tab_appearance, "Görünüm")
        self.tabs.addTab(self.tab_behavior, "Davranış")
        self.tabs.addTab(self.tab_tray, "Tepsi & Bildirim")
        self.tabs.addTab(self.tab_about, "Hakkında")

        root = QVBoxLayout(self)
        root.addWidget(self.tabs)

        # Genel
        form_g = QFormLayout(self.tab_general)
        self.cmb_lang = QComboBox()
        self.cmb_lang.setObjectName("ModernCombo")
        for code, label in LANG_MAP.items():
            self.cmb_lang.addItem(label, code)
        self.cmb_lang.setCurrentIndex(max(0, self.cmb_lang.findData(settings.get("language", "tr"))))
        form_g.addRow("Uygulama dili", self.cmb_lang)

        self.tgl_startup = ToggleSwitch(checked=bool(settings.get("launch_at_startup", True)))
        form_g.addRow("Windows ile başlat", self.tgl_startup)

        self.hotkey_info = QLabel("Kısayol: Ayarlar > Gelişmiş ile eklenebilir (şimdilik sabit).")
        form_g.addRow(self.hotkey_info)

        # Görünüm
        form_a = QFormLayout(self.tab_appearance)
        self.cmb_theme = QComboBox()
        for key, label in THEMES:
            self.cmb_theme.addItem(label, key)
        self.cmb_theme.setCurrentIndex(max(0, self.cmb_theme.findData(settings.get("theme", "default"))))
        form_a.addRow("Tema", self.cmb_theme)

        self.tgl_animations = ToggleSwitch(checked=bool(settings.get("animations", True)))
        form_a.addRow("Animasyonlar açık", self.tgl_animations)

        # Davranış
        form_b = QFormLayout(self.tab_behavior)
        self.tgl_hide_after_copy = ToggleSwitch(checked=bool(settings.get("hide_after_copy", False)))
        form_b.addRow("Kopyalayınca pencereyi gizle", self.tgl_hide_after_copy)

        self.tgl_stay_on_top = ToggleSwitch(checked=bool(settings.get("stay_on_top", False)))
        form_b.addRow("Pencereyi üstte tut", self.tgl_stay_on_top)

        self.spn_max_items = QSpinBox()
        self.spn_max_items.setRange(100, 5000)
        self.spn_max_items.setValue(int(settings.get("max_items", 1000)))
        form_b.addRow("Maks. öğe sayısı", self.spn_max_items)

        self.spn_dedupe_ms = QSpinBox()
        self.spn_dedupe_ms.setRange(0, 10000)
        self.spn_dedupe_ms.setValue(int(settings.get("dedupe_window_ms", 1200)))
        form_b.addRow("Aynı içeriği yoksayma penceresi (ms)", self.spn_dedupe_ms)

        self.tgl_confirm_delete = ToggleSwitch(checked=bool(settings.get("confirm_delete", True)))
        form_b.addRow("Silmeden önce onay sor", self.tgl_confirm_delete)

        self.tgl_toast = ToggleSwitch(checked=bool(settings.get("show_toast", True)))
        form_b.addRow("Uygulama içi bildirim (toast)", self.tgl_toast)

        # Tepsi & Bildirim
        lay_t = QVBoxLayout(self.tab_tray)
        form_t = QFormLayout()
        self.cmb_tray = QComboBox()
        for i, rel in enumerate(TRAY_ICONS, start=1):
            self.cmb_tray.addItem(f"İkon {i}", rel)
        self.cmb_tray.addItem("Özel ikon seç…", "__custom__")
        sel = self.settings.get("tray_icon", TRAY_ICONS[0])
        idx = self.cmb_tray.findData(sel)
        if idx < 0:
            idx = 0
        self.cmb_tray.setCurrentIndex(idx)
        form_t.addRow("Tepsi ikonu", self.cmb_tray)

        btn_preview = QPushButton("Önizleme")
        btn_preview.clicked.connect(self._preview_tray_icon)
        form_t.addRow("", btn_preview)

        self.tgl_tray_notifications = ToggleSwitch(checked=bool(settings.get("tray_notifications", True)))
        form_t.addRow("Tepside bildirim göster", self.tgl_tray_notifications)
        lay_t.addLayout(form_t)

        # Hakkında
        lay_ab = QVBoxLayout(self.tab_about)
        lbl_title = QLabel("<b>ClipStack</b> – Pano Geçmişi")
        lbl_desc = QLabel("Metin, bağlantı ve görselleri toplayan hızlı bir pano yöneticisi.")
        lbl_desc.setWordWrap(True)
        lay_ab.addWidget(lbl_title)
        lay_ab.addWidget(lbl_desc)

        links = QHBoxLayout()
        btn_site = QPushButton("Website")
        btn_site.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://miyotu.com/")))
        btn_pat = QPushButton("Patreon")
        btn_pat.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.patreon.com/c/Taxperia")))
        links.addWidget(btn_site)
        links.addWidget(btn_pat)
        links.addStretch(1)
        lay_ab.addLayout(links)

        grp_authors = QGroupBox("Yapımcılar")
        la = QVBoxLayout(grp_authors)
        la.addWidget(QLabel("• Developer: Your Name"))
        la.addWidget(QLabel("• Designer: Your Friend"))
        lay_ab.addWidget(grp_authors)
        lay_ab.addStretch(1)

        # Alt butonlar
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_ok = QPushButton("Kaydet")
        self.btn_cancel = QPushButton("İptal")
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_ok)
        root.addLayout(btns)

        # Etkileşimler
        self.btn_ok.clicked.connect(self._apply_and_close)
        self.btn_cancel.clicked.connect(self.reject)
        self.cmb_tray.currentIndexChanged.connect(self._on_tray_select)

        # Modern combobox stili (sadece dil seçimi için)
        try:
            qss_path = resource_path("styles/widgets/combobox_modern.qss")
            if qss_path.exists():
                self.cmb_lang.setStyleSheet(qss_path.read_text("utf-8"))
        except Exception:
            pass

    def _on_tray_select(self, idx: int):
        data = self.cmb_tray.currentData()
        if data == "__custom__":
            file, _ = QFileDialog.getOpenFileName(self, "İkon seç (.ico önerilir)", "", "Icon (*.ico *.png *.svg)")
            if file:
                self.settings.set("tray_icon", file)
                self.cmb_tray.setItemText(idx, f"Özel: {Path(file).name}")
                self.cmb_tray.setCurrentIndex(idx)
            else:
                self.cmb_tray.setCurrentIndex(0)

    def _preview_tray_icon(self):
        # Seçili ikonu küçük bir modal pencerede göster
        data = self.cmb_tray.currentData()
        path = self.settings.get("tray_icon", "") if data == "__custom__" else data
        if not path:
            return
        p = Path(path)
        if not p.is_absolute():
            p = resource_path(path)
        icon = QIcon(str(p))
        pix = icon.pixmap(64, 64)
        dlg = QDialog(self)
        dlg.setWindowTitle("İkon önizleme")
        v = QVBoxLayout(dlg)
        lbl = QLabel()
        if not pix.isNull():
            lbl.setPixmap(pix)
        else:
            lbl.setText("İkon yüklenemedi.")
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)
        btn = QPushButton("Kapat")
        btn.clicked.connect(dlg.accept)
        v.addWidget(btn, alignment=Qt.AlignCenter)
        dlg.exec()

    def _apply_and_close(self):
        # Genel
        self.settings.set("language", self.cmb_lang.currentData())
        self.settings.set("launch_at_startup", self.tgl_startup.isChecked())

        # Görünüm
        self.settings.set("theme", self.cmb_theme.currentData())
        self.settings.set("animations", self.tgl_animations.isChecked())

        # Davranış
        self.settings.set("hide_after_copy", self.tgl_hide_after_copy.isChecked())
        self.settings.set("stay_on_top", self.tgl_stay_on_top.isChecked())
        self.settings.set("max_items", self.spn_max_items.value())
        self.settings.set("dedupe_window_ms", self.spn_dedupe_ms.value())
        self.settings.set("confirm_delete", self.tgl_confirm_delete.isChecked())
        self.settings.set("show_toast", self.tgl_toast.isChecked())

        # Tepsi
        data = self.cmb_tray.currentData()
        if data and data != "__custom__":
            self.settings.set("tray_icon", data)
        self.settings.set("tray_notifications", self.tgl_tray_notifications.isChecked())

        self.settings.save()
        self.accept()