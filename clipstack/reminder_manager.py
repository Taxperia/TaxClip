from __future__ import annotations
from typing import Optional, Callable
from datetime import datetime, timedelta
from PySide6.QtCore import QObject, Signal, QTimer
from .settings import Settings
from .storage import Storage


class ReminderManager(QObject):
    """Hatırlatmaları kontrol eder ve zamanı gelenleri bildirir"""
    
    reminder_triggered = Signal(dict)  # Hatırlatma tetiklendiğinde sinyal
    
    def __init__(self, storage: Storage, settings: Settings, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.settings = settings
        
        # Her dakika kontrol et
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self._check_reminders)
        self.check_timer.start(60000)  # 60 saniye
        
        # İlk kontrolü hemen yap
        QTimer.singleShot(1000, self._check_reminders)
    
    def _check_reminders(self):
        """Aktif hatırlatmaları kontrol et"""
        try:
            now = datetime.now()
            reminders = self.storage.list_reminders(active_only=True)
            
            for reminder in reminders:
                reminder_time = datetime.fromisoformat(reminder["reminder_time"])
                
                # Zaman geldi mi?
                if reminder_time <= now:
                    # Bildirimi tetikle
                    self.reminder_triggered.emit(reminder)
                    
                    # Tekrarlama varsa güncelle, yoksa deaktif et
                    if reminder.get("repeat_type") and reminder["repeat_type"] != "none":
                        self._schedule_next_repeat(reminder)
                    else:
                        self.storage.set_reminder_active(reminder["id"], False)
        
        except Exception:
            pass
    
    def _schedule_next_repeat(self, reminder: dict):
        """Tekrarlayan hatırlatma için sonraki zamanı planla"""
        try:
            current_time = datetime.fromisoformat(reminder["reminder_time"])
            repeat_type = reminder.get("repeat_type", "none")
            
            if repeat_type == "daily":
                next_time = current_time + timedelta(days=1)
            elif repeat_type == "weekly":
                next_time = current_time + timedelta(weeks=1)
            elif repeat_type == "monthly":
                # Basit bir ay ekleme (30 gün)
                next_time = current_time + timedelta(days=30)
            else:
                return
            
            # Yeni zamanı güncelle
            self.storage.update_reminder_time(reminder["id"], next_time.isoformat())
        
        except Exception:
            pass
    
    def start(self):
        """Hatırlatma kontrolünü başlat"""
        if not self.check_timer.isActive():
            self.check_timer.start(60000)
    
    def stop(self):
        """Hatırlatma kontrolünü durdur"""
        if self.check_timer.isActive():
            self.check_timer.stop()