from __future__ import annotations
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QSizePolicy
)
from ..ui.widgets.toggle_switch import ToggleSwitch
from ..utils import resource_path
from ..i18n import i18n


class ReminderWidget(QWidget):
    """Hatırlatma kartı widget'ı - Modern uzunlamasına tasarım"""
    
    on_edit_requested = Signal(int)
    on_delete_requested = Signal(int)
    on_toggle_requested = Signal(int, bool)
    
    def __init__(self, reminder: dict, parent=None):
        super().__init__(parent)
        self.reminder = reminder
        self.reminder_id = reminder["id"]
        
        self.setObjectName("ReminderCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        # Uzunlamasına kart - tam genişlik, kompakt yükseklik
        self.setMinimumHeight(68)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Ana layout - Horizontal (sol taraf bilgi, sağ taraf butonlar)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(16)

        # SOL TARAF: Bilgiler
        left_layout = QVBoxLayout()
        left_layout.setSpacing(6)

        # Başlık ve zaman aynı satırda
        title_time_layout = QHBoxLayout()
        title_time_layout.setSpacing(6)

        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("ReminderTitle")
        self.lbl_title.setWordWrap(False)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        self.lbl_title.setFont(title_font)

        self.lbl_time = QLabel()
        self.lbl_time.setObjectName("ReminderTime")
        time_font = QFont()
        time_font.setPointSize(9)
        self.lbl_time.setFont(time_font)
        self.lbl_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        title_time_layout.addWidget(self.lbl_title)
        title_time_layout.addWidget(self.lbl_time)
        title_time_layout.addStretch()

        left_layout.addLayout(title_time_layout)

        # Açıklama (varsa)
        self.lbl_description = QLabel()
        self.lbl_description.setObjectName("ReminderDescription")
        self.lbl_description.setWordWrap(True)
        self.lbl_description.setContentsMargins(0, 2, 0, 0)
        self.lbl_description.setMaximumHeight(60)
        desc_font = QFont()
        desc_font.setPointSize(9)
        self.lbl_description.setFont(desc_font)
        left_layout.addWidget(self.lbl_description)

        # Tekrar bilgisi
        self.lbl_repeat = QLabel()
        self.lbl_repeat.setObjectName("ReminderRepeat")
        repeat_font = QFont()
        repeat_font.setPointSize(9)
        self.lbl_repeat.setFont(repeat_font)
        self.lbl_repeat.setContentsMargins(0, 2, 0, 0)
        left_layout.addWidget(self.lbl_repeat)

        left_layout.addStretch()
        main_layout.addLayout(left_layout, 1)  # Sol taraf esnek

        # SAĞ TARAF: Kontroller
        right_layout = QHBoxLayout()
        right_layout.setSpacing(8)
        right_layout.setAlignment(Qt.AlignVCenter)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Düzenle butonu
        self.btn_edit = QPushButton()
        self.btn_edit.setObjectName("ReminderEditBtn")
        self.btn_edit.setFixedSize(32, 32)
        self.btn_edit.setToolTip(self._tr("reminder.edit", "Düzenle"))
        self.btn_edit.clicked.connect(lambda: self.on_edit_requested.emit(self.reminder_id))
        try:
            icon_path = resource_path("assets/icons/edit_reminder.svg")
            if icon_path.exists():
                self.btn_edit.setIcon(QIcon(str(icon_path)))
                self.btn_edit.setIconSize(QSize(18, 18))
            else:
                self.btn_edit.setText("✏️")
                edit_font = QFont()
                edit_font.setPointSize(13)
                self.btn_edit.setFont(edit_font)
        except Exception:
            self.btn_edit.setText("✏️")
            edit_font = QFont()
            edit_font.setPointSize(13)
            self.btn_edit.setFont(edit_font)

        # Sil butonu
        self.btn_delete = QPushButton()
        self.btn_delete.setObjectName("ReminderDeleteBtn")
        self.btn_delete.setFixedSize(32, 32)
        self.btn_delete.setToolTip(self._tr("reminder.delete", "Sil"))
        self.btn_delete.clicked.connect(lambda: self.on_delete_requested.emit(self.reminder_id))
        try:
            icon_path = resource_path("assets/icons/delete_reminder.svg")
            if icon_path.exists():
                self.btn_delete.setIcon(QIcon(str(icon_path)))
                self.btn_delete.setIconSize(QSize(18, 18))
            else:
                self.btn_delete.setText("🗑️")
                delete_font = QFont()
                delete_font.setPointSize(13)
                self.btn_delete.setFont(delete_font)
        except Exception:
            self.btn_delete.setText("🗑️")
            delete_font = QFont()
            delete_font.setPointSize(13)
            self.btn_delete.setFont(delete_font)

        # Switch EN SAĞDA
        self.switch = ToggleSwitch(checked=bool(reminder.get("is_active", 1)))
        self.switch.onToggled(self._on_switch_toggled)
        self.switch.setToolTip(self._tr("reminder.active", "Aktif/Pasif"))

        right_layout.addWidget(self.btn_edit)
        right_layout.addWidget(self.btn_delete)
        right_layout.addWidget(self.switch)

        main_layout.addLayout(right_layout)
        
        # İçeriği güncelle
        self._update_content()
        
        # Dil değişimini dinle
        i18n.languageChanged.connect(self._update_content)
        
        # Widget'ı görünür yap
        self.setVisible(True)
        self.show()
    
    def _tr(self, key: str, fallback: str) -> str:
        try:
            v = i18n.t(key)
        except Exception:
            v = ""
        return v if v and v != key else fallback
    
    def _update_content(self):
        """Widget içeriğini güncelle"""
        title = self.reminder.get("title", "")
        description = self.reminder.get("description", "")
        reminder_time_str = self.reminder.get("reminder_time", "")
        repeat_type = self.reminder.get("repeat_type", "none")
        
        # Başlık
        self.lbl_title.setText(title if title else self._tr("reminder.no_title", "Başlıksız"))
        
        # Açıklama
        if description and description.strip():
            self.lbl_description.setText(description)
            self.lbl_description.show()
        else:
            self.lbl_description.hide()
        
        # Zaman
        try:
            dt = datetime.fromisoformat(reminder_time_str)
            now = datetime.now()
            
            # Geçmiş mi gelecek mi?
            if dt < now:
                time_str = "⏰ " + dt.strftime("%d.%m.%Y %H:%M")
                self.lbl_time.setStyleSheet("color: #f59e0b;")  # Turuncu - geçmiş
            else:
                diff = dt - now
                if diff.days > 0:
                    time_str = "⏰ " + dt.strftime("%d.%m.%Y %H:%M")
                else:
                    hours = diff.seconds // 3600
                    minutes = (diff.seconds % 3600) // 60
                    if hours > 0:
                        time_str = f"⏰ {hours}s {minutes}d sonra"
                    else:
                        time_str = f"⏰ {minutes}d sonra"
                self.lbl_time.setStyleSheet("")  # Normal renk
            
            self.lbl_time.setText(time_str)
        except Exception:
            self.lbl_time.setText("⏰ " + reminder_time_str)
        
        # Tekrar türü
        repeat_labels = {
            "none": "",
            "daily": self._tr("reminder.repeat.daily", "🔄 Günlük"),
            "weekly": self._tr("reminder.repeat.weekly", "🔄 Haftalık"),
            "monthly": self._tr("reminder.repeat.monthly", "🔄 Aylık")
        }
        repeat_text = repeat_labels.get(repeat_type, "")
        
        if repeat_text:
            self.lbl_repeat.setText(repeat_text)
            self.lbl_repeat.show()
        else:
            self.lbl_repeat.hide()
    
    def _on_switch_toggled(self, state: bool):
        """Switch değiştiğinde"""
        self.on_toggle_requested.emit(self.reminder_id, state)
    
    def set_active(self, is_active: bool):
        """Dışarıdan aktif durumu güncelle"""
        old = self.switch.blockSignals(True)
        try:
            self.switch.setChecked(is_active)
            self.reminder["is_active"] = 1 if is_active else 0
        finally:
            self.switch.blockSignals(old)