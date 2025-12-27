from __future__ import annotations
from typing import Optional, Callable
from datetime import datetime, timedelta
from PySide6.QtCore import QObject, Signal, QTimer, Qt
from .settings import Settings
from .storage import Storage


class ReminderManager(QObject):
    """Hatırlatmaları kontrol eder ve zamanı gelenleri bildirir"""
    
    reminder_triggered = Signal(dict)  # Hatırlatma tetiklendiğinde sinyal
    
    def __init__(self, storage: Storage, settings: Settings, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.settings = settings
        self.startup_time = datetime.now()  # Uygulama başlangıç zamanı
        
        # Hatırlatmaları sık aralıklarla kontrol et
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self._check_reminders)
        self.check_timer.setTimerType(Qt.PreciseTimer)
        self.check_timer.start(2000)  # 2 saniye
        
        # İlk kontrolü hemen yap (sadece gelecekteki hatırlatmalar için)
        QTimer.singleShot(1000, lambda: self._check_reminders(skip_past=True))
    
    def _check_reminders(self, skip_past: bool = False):
        """Aktif hatırlatmaları kontrol et
        
        Args:
            skip_past: True ise, uygulama başlangıcından önceki hatırlatmaları atla
        """
        try:
            now = datetime.now()
            reminders = self.storage.list_reminders(active_only=True)
            
            for reminder in reminders:
                reminder_time = datetime.fromisoformat(reminder["reminder_time"])
                reminder_id = reminder["id"]
                last_triggered = reminder.get("last_triggered")
                
                # Eğer skip_past aktifse ve hatırlatma zamanı uygulama başlangıcından önceyse atla
                if skip_past and hasattr(self, 'startup_time') and reminder_time < self.startup_time:
                    continue
                
                # Zaman geldi mi kontrol et
                if reminder_time <= now:
                    # Daha önce tetiklenmiş mi kontrol et (tekrar tetiklenmesini önle)
                    if last_triggered:
                        last_triggered_dt = datetime.fromisoformat(last_triggered)
                        # Eğer son 2 dakika içinde tetiklendiyse tekrar tetikleme
                        if (now - last_triggered_dt).total_seconds() < 120:
                            print(f"[REMINDER] ID {reminder_id} yakın zamanda tetiklendi, atlanıyor")
                            continue
                    
                    print(f"[REMINDER] Hatırlatma tetikleniyor: ID={reminder_id}, Title={reminder.get('title')}")
                    
                    # Bildirimi tetikle
                    self.reminder_triggered.emit(reminder)
                    
                    # Tetiklenme zamanını kaydet
                    self.storage.mark_reminder_triggered(reminder_id)
                    
                    # Tekrarlama varsa güncelle, yoksa switch'i kapat
                    repeat_type = reminder.get("repeat_type", "none")
                    if repeat_type and repeat_type != "none":
                        # Tekrarlayan hatırlatma - sonraki zamanı ayarla
                        self._schedule_next_repeat(reminder)
                    else:
                        # Tek seferlik hatırlatma - sadece switch'i kapat, KARTINI SILME!
                        self.storage.set_reminder_active(reminder_id, False)
                        print(f"[REMINDER] Tek seferlik hatırlatma pasif yapıldı: ID={reminder_id}")
        
        except Exception as e:
            print(f"Hatırlatma kontrol hatası: {e}")
            import traceback
            traceback.print_exc()
    
    def _schedule_next_repeat(self, reminder: dict):
        """Tekrarlayan hatırlatma için sonraki zamanı planla"""
        try:
            current_time = datetime.fromisoformat(reminder["reminder_time"])
            repeat_type = reminder.get("repeat_type", "none")
            now = datetime.now()

            # Sonraki tekrar zamanını hesapla
            next_time = current_time

            if repeat_type == "daily":
                # Bugünden sonraki ilk geçerli zamanı bul
                while next_time <= now:
                    next_time = next_time + timedelta(days=1)

            elif repeat_type == "weekly":
                # Haftadan sonraki ilk geçerli zamanı bul
                while next_time <= now:
                    next_time = next_time + timedelta(weeks=1)

            elif repeat_type == "monthly":
                # Aydan sonraki ilk geçerli zamanı bul
                while next_time <= now:
                    # Aynı günü koruyarak bir sonraki aya geç
                    if next_time.month == 12:
                        next_time = next_time.replace(year=next_time.year + 1, month=1)
                    else:
                        try:
                            next_time = next_time.replace(month=next_time.month + 1)
                        except ValueError:
                            # Örneğin 31 Ocak -> 28/29 Şubat gibi durumlar için
                            next_time = next_time.replace(month=next_time.month + 1, day=1)
            else:
                return

            # Yeni zamanı güncelle ve notified flag'ini sıfırla
            self.storage.update_reminder_time(reminder["id"], next_time.isoformat())
    
        except Exception as e:
            print(f"Hatırlatma tekrarlama hatası: {e}")
            import traceback
            traceback.print_exc()
    
    def start(self):
        """Hatırlatma kontrolünü başlat"""
        if not self.check_timer.isActive():
            self.check_timer.start(2000)
    
    def stop(self):
        """Hatırlatma kontrolünü durdur"""
        if self.check_timer.isActive():
            self.check_timer.stop()