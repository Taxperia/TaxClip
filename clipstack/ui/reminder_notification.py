from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame
)
from PySide6.QtGui import QFont
from ..i18n import i18n
from ..settings import Settings


class ReminderNotificationDialog(QDialog):
    """Hatırlatma popup bildirimi"""
    
    snooze_requested = Signal(int, int)  # reminder_id, minutes
    
    def __init__(self, reminder: dict, settings: Settings, parent=None):
        super().__init__(parent)
        self.reminder = reminder
        self.settings = settings
        self.reminder_id = reminder["id"]
        
        # Dialog ayarları
        self.setWindowTitle(self._tr("reminder.popup.title", "Hatırlatma"))
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMinimumWidth(400)
        self.setMaximumWidth(500)
        
        # Ana layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # İçerik container
        content = QFrame()
        content.setObjectName("ReminderNotificationContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(12)
        
        # İkon + Başlık
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        lbl_icon = QLabel("⏰")
        font_icon = QFont()
        font_icon.setPointSize(32)
        lbl_icon.setFont(font_icon)
        
        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("ReminderNotificationTitle")
        self.lbl_title.setWordWrap(True)
        font_title = QFont()
        font_title.setPointSize(14)
        font_title.setBold(True)
        self.lbl_title.setFont(font_title)
        
        header_layout.addWidget(lbl_icon)
        header_layout.addWidget(self.lbl_title, 1)
        
        content_layout.addLayout(header_layout)
        
        # Açıklama
        self.lbl_description = QLabel()
        self.lbl_description.setObjectName("ReminderNotificationDesc")
        self.lbl_description.setWordWrap(True)
        self.lbl_description.setMaximumHeight(100)
        content_layout.addWidget(self.lbl_description)
        
        # Ayırıcı
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("ReminderNotificationSeparator")
        content_layout.addWidget(separator)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.btn_snooze_5 = QPushButton(self._tr("reminder.snooze.5min", "5 dk"))
        self.btn_snooze_10 = QPushButton(self._tr("reminder.snooze.10min", "10 dk"))
        self.btn_snooze_30 = QPushButton(self._tr("reminder.snooze.30min", "30 dk"))
        self.btn_dismiss = QPushButton(self._tr("reminder.dismiss", "Kapat"))
        
        self.btn_snooze_5.setObjectName("ReminderSnoozeBtn")
        self.btn_snooze_10.setObjectName("ReminderSnoozeBtn")
        self.btn_snooze_30.setObjectName("ReminderSnoozeBtn")
        self.btn_dismiss.setObjectName("ReminderDismissBtn")
        
        btn_layout.addWidget(self.btn_snooze_5)
        btn_layout.addWidget(self.btn_snooze_10)
        btn_layout.addWidget(self.btn_snooze_30)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_dismiss)
        
        content_layout.addLayout(btn_layout)
        
        main_layout.addWidget(content)
        
        # İçeriği doldur
        self._load_content()
        
        # Bağlantılar
        self.btn_snooze_5.clicked.connect(lambda: self._on_snooze(5))
        self.btn_snooze_10.clicked.connect(lambda: self._on_snooze(10))
        self.btn_snooze_30.clicked.connect(lambda: self._on_snooze(30))
        self.btn_dismiss.clicked.connect(self.accept)
        
        # Dil değişimi
        i18n.languageChanged.connect(self._update_texts)
    
    def _tr(self, key: str, fallback: str) -> str:
        try:
            v = i18n.t(key)
        except Exception:
            v = ""
        return v if v and v != key else fallback
    
    def _load_content(self):
        """İçeriği yükle"""
        title = self.reminder.get("title", "")
        description = self.reminder.get("description", "")
        
        self.lbl_title.setText(title if title else self._tr("reminder.no_title", "Hatırlatma"))
        
        if description:
            self.lbl_description.setText(description)
            self.lbl_description.show()
        else:
            self.lbl_description.hide()
    
    def _update_texts(self):
        """Metinleri güncelle"""
        self.setWindowTitle(self._tr("reminder.popup.title", "Hatırlatma"))
        self.btn_snooze_5.setText(self._tr("reminder.snooze.5min", "5 dk"))
        self.btn_snooze_10.setText(self._tr("reminder.snooze.10min", "10 dk"))
        self.btn_snooze_30.setText(self._tr("reminder.snooze.30min", "30 dk"))
        self.btn_dismiss.setText(self._tr("reminder.dismiss", "Kapat"))
    
    def _on_snooze(self, minutes: int):
        """Erteleme butonuna basıldı"""
        self.snooze_requested.emit(self.reminder_id, minutes)
        self.accept()
    
    def showEvent(self, event):
        """Dialog gösterildiğinde ekranın ortasına yerleştir"""
        super().showEvent(event)
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)