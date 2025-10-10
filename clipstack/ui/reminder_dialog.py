from __future__ import annotations
from datetime import datetime, timedelta
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDateTimeEdit, QComboBox, QPushButton,
    QHBoxLayout, QLabel
)
from ..i18n import i18n


class ReminderDialog(QDialog):
    """Hatırlatma ekleme/düzenleme dialog'u"""
    
    def __init__(self, parent=None, reminder: dict = None):
        super().__init__(parent)
        self.reminder = reminder
        self.is_edit = reminder is not None
        
        self.setMinimumWidth(480)
        self.setMinimumHeight(400)
        
        # Ana layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # Form
        form = QFormLayout()
        form.setSpacing(10)
        
        # Başlık
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText(self._tr("reminder.dialog.title_placeholder", "Hatırlatma başlığı"))
        self.txt_title.setMinimumHeight(36)
        form.addRow(self._tr("reminder.dialog.title", "Başlık:"), self.txt_title)
        
        # Açıklama
        self.txt_description = QTextEdit()
        self.txt_description.setPlaceholderText(self._tr("reminder.dialog.desc_placeholder", "Açıklama (opsiyonel)"))
        self.txt_description.setMaximumHeight(100)
        form.addRow(self._tr("reminder.dialog.description", "Açıklama:"), self.txt_description)
        
        # Tarih ve saat
        self.dt_reminder = QDateTimeEdit()
        self.dt_reminder.setCalendarPopup(True)
        self.dt_reminder.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.dt_reminder.setMinimumHeight(36)
        
        # Varsayılan: 1 saat sonra
        default_time = QDateTime.currentDateTime().addSecs(3600)
        self.dt_reminder.setDateTime(default_time)
        self.dt_reminder.setMinimumDateTime(QDateTime.currentDateTime())
        
        form.addRow(self._tr("reminder.dialog.datetime", "Tarih ve Saat:"), self.dt_reminder)
        
        # Hızlı seçim butonları
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(6)
        
        btn_1h = QPushButton(self._tr("reminder.quick.1h", "1 saat"))
        btn_3h = QPushButton(self._tr("reminder.quick.3h", "3 saat"))
        btn_tomorrow = QPushButton(self._tr("reminder.quick.tomorrow", "Yarın"))
        btn_1week = QPushButton(self._tr("reminder.quick.1week", "1 hafta"))
        
        btn_1h.clicked.connect(lambda: self._set_quick_time(hours=1))
        btn_3h.clicked.connect(lambda: self._set_quick_time(hours=3))
        btn_tomorrow.clicked.connect(lambda: self._set_quick_time(days=1))
        btn_1week.clicked.connect(lambda: self._set_quick_time(days=7))
        
        quick_layout.addWidget(btn_1h)
        quick_layout.addWidget(btn_3h)
        quick_layout.addWidget(btn_tomorrow)
        quick_layout.addWidget(btn_1week)
        quick_layout.addStretch()
        
        form.addRow("", quick_layout)
        
        # Tekrar türü
        self.cmb_repeat = QComboBox()
        self.cmb_repeat.setMinimumHeight(36)
        self.cmb_repeat.addItem(self._tr("reminder.repeat.none", "Tekrar yok"), "none")
        self.cmb_repeat.addItem(self._tr("reminder.repeat.daily", "Her gün"), "daily")
        self.cmb_repeat.addItem(self._tr("reminder.repeat.weekly", "Her hafta"), "weekly")
        self.cmb_repeat.addItem(self._tr("reminder.repeat.monthly", "Her ay"), "monthly")
        form.addRow(self._tr("reminder.dialog.repeat", "Tekrar:"), self.cmb_repeat)
        
        main_layout.addLayout(form)
        main_layout.addStretch()
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton(self._tr("common.cancel", "İptal"))
        self.btn_save = QPushButton(self._tr("common.save", "Kaydet"))
        self.btn_save.setDefault(True)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        
        main_layout.addLayout(btn_layout)
        
        # Bağlantılar
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)
        
        # Düzenleme modundaysa verileri doldur
        if self.is_edit and reminder:
            self._load_reminder_data()
        
        # Dil değişimi
        i18n.languageChanged.connect(self._update_texts)
        self._update_texts()
    
    def _tr(self, key: str, fallback: str) -> str:
        try:
            v = i18n.t(key)
        except Exception:
            v = ""
        return v if v and v != key else fallback
    
    def _update_texts(self):
        """Metinleri güncelle"""
        if self.is_edit:
            self.setWindowTitle(self._tr("reminder.dialog.edit_title", "Hatırlatmayı Düzenle"))
        else:
            self.setWindowTitle(self._tr("reminder.dialog.new_title", "Yeni Hatırlatma"))
    
    def _set_quick_time(self, hours: int = 0, days: int = 0):
        """Hızlı zaman ayarla"""
        dt = QDateTime.currentDateTime()
        if hours:
            dt = dt.addSecs(hours * 3600)
        if days:
            dt = dt.addDays(days)
            # Saat 09:00 yap
            dt.setTime(dt.time().fromString("09:00", "HH:mm"))
        self.dt_reminder.setDateTime(dt)
    
    def _load_reminder_data(self):
        """Mevcut hatırlatma verilerini yükle"""
        self.txt_title.setText(self.reminder.get("title", ""))
        self.txt_description.setPlainText(self.reminder.get("description", ""))
        
        try:
            dt_iso = self.reminder.get("reminder_time", "")
            dt = datetime.fromisoformat(dt_iso)
            qdt = QDateTime.fromString(dt.isoformat(), Qt.ISODate)
            self.dt_reminder.setDateTime(qdt)
        except Exception:
            pass
        
        repeat_type = self.reminder.get("repeat_type", "none")
        idx = self.cmb_repeat.findData(repeat_type)
        if idx >= 0:
            self.cmb_repeat.setCurrentIndex(idx)
    
    def _on_save(self):
        """Kaydet butonuna basıldı"""
        title = self.txt_title.text().strip()
        if not title:
            # Hata göster
            return
        
        self.accept()
    
    def get_data(self) -> dict:
        """Dialog'dan verileri al"""
        dt = self.dt_reminder.dateTime().toPython()
        
        return {
            "title": self.txt_title.text().strip(),
            "description": self.txt_description.toPlainText().strip(),
            "reminder_time": dt.isoformat(),
            "repeat_type": self.cmb_repeat.currentData()
        }