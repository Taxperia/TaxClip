from __future__ import annotations
from datetime import datetime
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame
)
from ..ui.widgets.toggle_switch import ToggleSwitch
from ..utils import resource_path
from ..i18n import i18n


class ReminderWidget(QWidget):
    """Hatırlatma kartı widget'ı"""
    
    on_edit_requested = Signal(int)
    on_delete_requested = Signal(int)
    on_toggle_requested = Signal(int, bool)
    
    def __init__(self, reminder: dict, parent=None):
        super().__init__(parent)
        self.reminder = reminder
        self.reminder_id = reminder["id"]
        
        self.setObjectName("ReminderCard")
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        self.setMinimumHeight(140)
        
        # Ana layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(8)
        
        # Üst kısım: Başlık + Switch
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        
        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("ReminderTitle")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setMaximumHeight(60)
        
        self.switch = ToggleSwitch(checked=bool(reminder.get("is_active", 1)))
        self.switch.onToggled(self._on_switch_toggled)
        
        top_layout.addWidget(self.lbl_title, 1)
        top_layout.addWidget(self.switch)
        
        main_layout.addLayout(top_layout)
        
        # Açıklama
        self.lbl_description = QLabel()
        self.lbl_description.setObjectName("ReminderDescription")
        self.lbl_description.setWordWrap(True)
        self.lbl_description.setMaximumHeight(50)
        main_layout.addWidget(self.lbl_description)
        
        # Zaman ve tekrar bilgisi
        info_layout = QHBoxLayout()
        info_layout.setSpacing(6)
        
        self.lbl_time = QLabel()
        self.lbl_time.setObjectName("ReminderTime")
        
        self.lbl_repeat = QLabel()
        self.lbl_repeat.setObjectName("ReminderRepeat")
        
        info_layout.addWidget(self.lbl_time)
        info_layout.addStretch()
        info_layout.addWidget(self.lbl_repeat)
        
        main_layout.addLayout(info_layout)
        
        # Ayırıcı çizgi
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("ReminderSeparator")
        separator.setFixedHeight(1)
        main_layout.addWidget(separator)
        
        # Alt butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        
        self.btn_edit = QPushButton()
        self.btn_edit.setObjectName("ReminderActionBtn")
        self.btn_edit.setFixedSize(32, 32)
        self.btn_edit.clicked.connect(lambda: self.on_edit_requested.emit(self.reminder_id))
        try:
            icon_path = resource_path("assets/icons/edit.svg")
            if icon_path.exists():
                self.btn_edit.setIcon(QIcon(str(icon_path)))
                self.btn_edit.setIconSize(QSize(18, 18))
        except Exception:
            self.btn_edit.setText("✏️")
        
        self.btn_delete = QPushButton()
        self.btn_delete.setObjectName("ReminderActionBtn")
        self.btn_delete.setFixedSize(32, 32)
        self.btn_delete.clicked.connect(lambda: self.on_delete_requested.emit(self.reminder_id))
        try:
            icon_path = resource_path("assets/icons/delete.svg")
            if icon_path.exists():
                self.btn_delete.setIcon(QIcon(str(icon_path)))
                self.btn_delete.setIconSize(QSize(18, 18))
        except Exception:
            self.btn_delete.setText("🗑️")
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        
        main_layout.addLayout(btn_layout)
        
        # İçeriği güncelle
        self._update_content()
        
        # Dil değişimini dinle
        i18n.languageChanged.connect(self._update_content)
    
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
        if description:
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
                time_str = dt.strftime("%d.%m.%Y %H:%M") + " (" + self._tr("reminder.past", "Geçmiş") + ")"
            else:
                diff = dt - now
                if diff.days > 0:
                    time_str = dt.strftime("%d.%m.%Y %H:%M")
                else:
                    hours = diff.seconds // 3600
                    minutes = (diff.seconds % 3600) // 60
                    if hours > 0:
                        time_str = f"{hours}s {minutes}d " + self._tr("reminder.later", "sonra")
                    else:
                        time_str = f"{minutes}d " + self._tr("reminder.later", "sonra")
            
            self.lbl_time.setText("🕐 " + time_str)
        except Exception:
            self.lbl_time.setText("🕐 " + reminder_time_str)
        
        # Tekrar türü
        repeat_labels = {
            "none": self._tr("reminder.repeat.none", "Tekrar yok"),
            "daily": self._tr("reminder.repeat.daily", "Günlük"),
            "weekly": self._tr("reminder.repeat.weekly", "Haftalık"),
            "monthly": self._tr("reminder.repeat.monthly", "Aylık")
        }
        repeat_text = repeat_labels.get(repeat_type, repeat_type)
        
        if repeat_type != "none":
            self.lbl_repeat.setText("🔄 " + repeat_text)
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