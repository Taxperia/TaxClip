"""
Recording Overlay Widget
Sağ altta minimal kayıt durumu chip'i gösterir.
"""
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPainter, QColor, QFontMetrics, QPixmap

from ..utils import icon_pixmap


class RecordingOverlay(QWidget):
    """Kayıt overlay widget'ı - sağ alt köşede"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Pencere ayarları
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Boyut
        self.setFixedSize(128, 38)
        
        # State
        self.show_mic = False
        self.is_instant_replay = False
        self._status_icon_path = "assets/icons/video_record.svg"
        self._time_text = "00:00"
        self._time_font = QFont("Segoe UI Semibold", 10)
        self._status_icon_pixmap = QPixmap()
        self._mic_icon_pixmap = QPixmap()
        
        # Opacity animasyonu
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_animation.finished.connect(self._handle_fade_finished)
        
        # Yanıp sönme timer
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self._blink)
        self.blink_state = True
        
        # Başlangıçta gizli
        self.hide()
        self._set_status_icon("assets/icons/video_record.svg")
        self._set_mic_icon(True)
    
    def paintEvent(self, event):
        """Özel çizim - nötr arka plan chip."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(18, 20, 24, 232))
        painter.drawRoundedRect(self.rect(), 11, 11)

        x = 12
        icon_y = (self.height() - 16) // 2
        if not self._status_icon_pixmap.isNull():
            painter.drawPixmap(x, icon_y, self._status_icon_pixmap)
        x += 26

        painter.setPen(QColor(244, 247, 251, 242))
        painter.setFont(self._time_font)
        metrics = QFontMetrics(self._time_font)
        text_y = (self.height() + metrics.ascent() - metrics.descent()) // 2
        painter.drawText(x, text_y, self._time_text)

        if self.show_mic and not self._mic_icon_pixmap.isNull():
            painter.drawPixmap(self.width() - 12 - 14, (self.height() - 14) // 2, self._mic_icon_pixmap)
    
    def show_recording(self, mic_enabled: bool = False, is_instant_replay: bool = False):
        """Kayıt overlay'ini göster"""
        self.show_mic = mic_enabled
        self.is_instant_replay = is_instant_replay
        self.blink_state = True
        
        # Mikrofon ikonunu göster/gizle
        if mic_enabled:
            self.setFixedWidth(146)
        else:
            self.setFixedWidth(112)
        
        if is_instant_replay:
            self._set_status_icon("assets/icons/video_replay.svg", dimmed=False)
        else:
            self._set_status_icon("assets/icons/video_record.svg", dimmed=False)
        
        # Ekran boyutunu al
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            # Sağ alt köşe
            x = screen_geometry.x() + screen_geometry.width() - self.width() - 20
            y = screen_geometry.y() + screen_geometry.height() - self.height() - 24
            self.move(x, y)
        
        # Fade in
        self.fade_animation.stop()
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
        
        # Göster
        self.show()
        
        # Repaint (renk güncellemesi için)
        self.update()
        
        # Yanıp sönme başlat
        self.blink_timer.start(1000)
    
    def hide_recording(self):
        """Kayıt overlay'ini gizle"""
        # Yanıp sönmeyi durdur
        self.blink_timer.stop()
        
        # Fade out
        self.fade_animation.stop()
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()
    
    def update_time(self, time_str: str):
        """Süreyi güncelle"""
        self._time_text = time_str
        self.update()
    
    def set_mic_active(self, active: bool):
        """Mikrofon durumunu güncelle"""
        self._set_mic_icon(active)
    
    def _blink(self):
        """İkonu renk yerine parlaklık ile nefes aldır."""
        self._set_status_icon(self._status_icon_path, dimmed=not self.blink_state)
        self.blink_state = not self.blink_state

    def _set_status_icon(self, icon_path: str, dimmed: bool = False):
        self._status_icon_path = icon_path
        color = "#7F8794" if dimmed else "#F4F7FB"
        self._status_icon_pixmap = icon_pixmap(icon_path, size=16, color=color)
        self.update()

    def _set_mic_icon(self, active: bool):
        color = "#D1D6E0" if active else "#6B7280"
        self._mic_icon_pixmap = icon_pixmap("assets/icons/video_mic.svg", size=14, color=color)
        self.update()

    def _handle_fade_finished(self):
        if self.fade_animation.endValue() == 0.0:
            self.hide()
