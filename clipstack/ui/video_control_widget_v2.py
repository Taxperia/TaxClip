"""
Video Control Widget v2 - Minimal tasarım, SVG iconlar
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont

from ..utils import icon_pixmap


class VideoControlWidgetV2(QWidget):
    """Video kontrol - Minimal tasarım"""
    
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        
        self.settings = settings
        self.is_recording = False
        self.recording_time = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_timer)
        
        # Kayıt yolunu al
        from pathlib import Path
        if settings and settings.get("video_save_path"):
            self.output_dir = Path(settings.get("video_save_path"))
        else:
            self.output_dir = Path.home() / "Videos" / "ClipStack"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Video recorder instance
        from ..video_recorder import get_video_recorder
        self.video_recorder = get_video_recorder(settings, use_advanced=True)
        
        # Video recorder sinyallerini bağla
        self.video_recorder.recording_started.connect(self._on_recording_started)
        self.video_recorder.recording_stopped.connect(self._on_recording_stopped)
        self.video_recorder.screenshot_taken.connect(self._on_screenshot_taken)
        self.video_recorder.error_occurred.connect(self._on_error)
        
        # Recording overlay (NVIDIA ShadowPlay gibi)
        from .recording_overlay import RecordingOverlay
        self.recording_overlay = RecordingOverlay()
        self._icon_specs = {}
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        # Spacer üst
        layout.addStretch(1)
        
        # Butonlar - ortalanmış
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(30)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Screenshot butonu
        self.btn_screenshot = self._create_icon_button(
            "camera",
            "Ekran Görüntüsü",
            "#00D9FF"  # Cyan - modern ve profesyonel
        )
        self.btn_screenshot.clicked.connect(self._take_screenshot)
        btn_layout.addWidget(self.btn_screenshot)
        
        # Kayıt butonu
        self.btn_record = self._create_icon_button(
            "record",
            "Kayıt Başlat",
            "#FF3366"  # Parlak kırmızı - NVIDIA gibi
        )
        self.btn_record.clicked.connect(self._toggle_recording)
        btn_layout.addWidget(self.btn_record)
        
        # Instant replay butonu
        self.btn_instant = self._create_icon_button(
            "replay",
            "Instant Replay",
            "#FFB800"  # Altın sarısı - dikkat çekici
        )
        self.btn_instant.setCheckable(True)
        self.btn_instant.clicked.connect(self._toggle_instant_replay)
        btn_layout.addWidget(self.btn_instant)
        
        layout.addLayout(btn_layout)
        
        # Status
        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setFont(QFont("Segoe UI", 11))
        self.status_lbl.setStyleSheet("color: #6c757d;")
        layout.addWidget(self.status_lbl)
        
        # Timer
        self.timer_lbl = QLabel("")
        self.timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.timer_lbl.setStyleSheet("color: #F44336; margin-top: 20px;")
        self.timer_lbl.hide()
        layout.addWidget(self.timer_lbl)
        
        # Spacer alt
        layout.addStretch(1)

    def _create_icon_button(self, icon_name: str, tooltip: str, color: str) -> QPushButton:
        """Asset tabanlı ikon butonu."""
        btn = QPushButton()
        btn.setFixedSize(100, 100)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        icon_map = {
            "camera": "assets/icons/video_camera.svg",
            "record": "assets/icons/video_record.svg",
            "replay": "assets/icons/video_replay.svg",
        }
        self._icon_specs[btn] = {
            "default_icon": icon_map.get(icon_name, "assets/icons/video_camera.svg"),
            "active_icon": "assets/icons/video_stop.svg" if icon_name == "record" else icon_map.get(icon_name, "assets/icons/video_camera.svg"),
            "accent": color,
            "tooltip": tooltip,
            "active_tooltip": "Kayıt Durdur" if icon_name == "record" else tooltip,
        }
        self._apply_button_visuals(btn, active=False)
        return btn

    def _apply_button_visuals(self, btn: QPushButton, *, active: bool):
        spec = self._icon_specs[btn]
        accent = spec["accent"]
        icon_path = spec["active_icon"] if active else spec["default_icon"]
        icon_color = "#F8FAFC" if active else accent
        border_alpha = 1.0 if active else 0.78
        idle_bg = "rgba(15, 23, 42, 0.22)"
        hover_bg = "rgba(255, 255, 255, 0.08)"
        pressed_bg = "rgba(255, 255, 255, 0.14)"
        active_bg = accent
        active_hover = self._adjust_color(accent, 1.08)
        active_pressed = self._adjust_color(accent, 0.92)

        pixmap = icon_pixmap(icon_path, size=60, color=icon_color)
        btn.setIcon(pixmap)
        btn.setIconSize(pixmap.size())
        btn.setText("")
        btn.setToolTip(spec["active_tooltip"] if active else spec["tooltip"])
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {active_bg if active else idle_bg};
                border: 2px solid {self._with_alpha(accent, border_alpha)};
                border-radius: 20px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {active_hover if active else hover_bg};
                border: 2px solid {accent};
            }}
            QPushButton:pressed {{
                background: {active_pressed if active else pressed_bg};
            }}
            QPushButton:checked {{
                background: {active_bg};
                border: 2px solid {accent};
            }}
        """)

    @staticmethod
    def _with_alpha(color: str, alpha: float) -> str:
        qcolor = QColor(color)
        qcolor.setAlphaF(max(0.0, min(alpha, 1.0)))
        return qcolor.name(QColor.NameFormat.HexArgb)

    @staticmethod
    def _adjust_color(color: str, factor: float) -> str:
        qcolor = QColor(color)
        if not qcolor.isValid():
            return color
        if factor >= 1.0:
            return qcolor.lighter(int(factor * 100)).name()
        return qcolor.darker(int((1 / max(factor, 0.01)) * 100)).name()
    
    def _take_screenshot(self):
        """Ekran görüntüsü al"""
        filepath = self.video_recorder.take_screenshot()
        # Sinyal handler'ı zaten mesaj gösterecek
    
    def _on_screenshot_taken(self, filepath: str):
        """Screenshot alındı sinyali"""
        from pathlib import Path
        filename = Path(filepath).name
        self.status_lbl.setText(f"✅ Kaydedildi: {filename}")
        QTimer.singleShot(3000, lambda: self.status_lbl.setText(""))
    
    def _on_error(self, error_msg: str):
        """Hata oluştu sinyali"""
        QMessageBox.critical(self, "Hata", error_msg)
    
    def _toggle_recording(self):
        """Kayıt başlat/durdur"""
        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()
    
    def _start_recording(self):
        """Kayıt başlat"""
        self.video_recorder.start_recording()
        # Sinyal handler'ı UI'yi güncelleyecek
    
    def _on_recording_started(self):
        """Kayıt başladı sinyali"""
        self.is_recording = True
        self.recording_time = 0
        self._apply_button_visuals(self.btn_record, active=True)
        
        self.status_lbl.setText("🔴 Kayıt ediliyor...")
        self.timer_lbl.show()
        self.timer.start(1000)
        
        # Overlay'i göster - mikrofon durumunu da gönder
        mic_enabled = self.settings.get("video_record_mic", False) if self.settings else False
        self.recording_overlay.show_recording(mic_enabled=mic_enabled, is_instant_replay=False)
    
    def _stop_recording(self):
        """Kayıt durdur"""
        filepath = self.video_recorder.stop_recording()
        # Sinyal handler'ı UI'yi güncelleyecek
    
    def _on_recording_stopped(self, filepath: str):
        """Kayıt durdu sinyali"""
        self.is_recording = False
        self.timer.stop()
        self._apply_button_visuals(self.btn_record, active=False)
        
        from pathlib import Path
        filename = Path(filepath).name if filepath else "recording.mp4"
        self.status_lbl.setText(f"✅ Kaydedildi: {filename}")
        self.timer_lbl.hide()
        
        # Overlay'i gizle
        self.recording_overlay.hide_recording()
        
        QTimer.singleShot(3000, lambda: self.status_lbl.setText(""))
    
    def _update_timer(self):
        """Timer güncelle"""
        self.recording_time += 1
        minutes = self.recording_time // 60
        seconds = self.recording_time % 60
        time_str = f"{minutes:02d}:{seconds:02d}"
        self.timer_lbl.setText(time_str)
        
        # Overlay'i de güncelle
        if hasattr(self, 'recording_overlay'):
            self.recording_overlay.update_time(time_str)
    
    def _toggle_instant_replay(self):
        """Instant replay aç/kapat"""
        if self.btn_instant.isChecked():
            self._apply_button_visuals(self.btn_instant, active=True)
            self.status_lbl.setText("🔄 Instant Replay aktif")
            self._start_instant_replay()
        else:
            self._apply_button_visuals(self.btn_instant, active=False)
            self.status_lbl.setText("⏸️ Instant Replay pasif")
            self._stop_instant_replay()
        
        QTimer.singleShot(2000, lambda: self.status_lbl.setText(""))
    
    def _start_instant_replay(self):
        """Instant Replay arka plan kaydını başlat"""
        try:
            # Video recorder'ı instant replay moduna al
            if hasattr(self.video_recorder, 'start_instant_replay_buffer'):
                self.video_recorder.start_instant_replay_buffer()
            
            # Overlay göster
            mic_enabled = self.settings.get("video_record_mic", False) if self.settings else False
            self.recording_overlay.show_recording(mic_enabled=mic_enabled, is_instant_replay=True)
            
            print("[INSTANT REPLAY] Buffer kaydı başladı")
        except Exception as e:
            print(f"[INSTANT REPLAY] Hata: {e}")
            self.btn_instant.setChecked(False)
            self._apply_button_visuals(self.btn_instant, active=False)
    
    def _stop_instant_replay(self):
        """Instant Replay arka plan kaydını durdur"""
        try:
            if hasattr(self.video_recorder, 'stop_instant_replay_buffer'):
                self.video_recorder.stop_instant_replay_buffer()
            
            # Overlay gizle
            self.recording_overlay.hide_recording()
            
            print("[INSTANT REPLAY] Buffer kaydı durduruldu")
        except Exception as e:
            print(f"[INSTANT REPLAY] Durdurma hatası: {e}")
    
    def save_instant_replay(self):
        """Instant Replay'i kaydet (hotkey ile çağrılabilir)"""
        try:
            if self.btn_instant.isChecked():
                filepath = self.video_recorder.save_instant_replay()
                if filepath:
                    from pathlib import Path
                    filename = Path(filepath).name
                    self.status_lbl.setText(f"✅ Replay kaydedildi: {filename}")
                    QTimer.singleShot(3000, lambda: self.status_lbl.setText(""))
        except Exception as e:
            print(f"[INSTANT REPLAY] Kaydetme hatası: {e}")
    
    def reload_settings(self):
        """Ayarları yeniden yükle"""
        if hasattr(self.video_recorder, 'reload_settings'):
            self.video_recorder.reload_settings()
