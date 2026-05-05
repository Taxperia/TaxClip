"""
Video Control Widget - 3 button interface
Screenshot, Record, Instant Replay
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QCursor, QFont
from ..video_recorder import get_video_recorder


class VideoControlWidget(QWidget):
    """Video kontrol paneli"""
    
    def __init__(self, storage, settings, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.settings = settings
        self.video_recorder = get_video_recorder(settings, use_advanced=False)
        
        # Signals bağla
        self.video_recorder.screenshot_taken.connect(self._on_screenshot_taken)
        self.video_recorder.recording_started.connect(self._on_recording_started)
        self.video_recorder.recording_stopped.connect(self._on_recording_stopped)
        self.video_recorder.error_occurred.connect(self._on_error)
        
        self._init_ui()
        self._update_status()
    
    def _init_ui(self):
        """UI oluştur"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Başlık
        title = QLabel("📹 Video Kayıt Sistemi")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Açıklama
        desc = QLabel("NVIDIA ShadowPlay benzeri özellikler")
        desc.setStyleSheet("color: #7f8c8d; font-size: 11pt;")
        layout.addWidget(desc)
        
        layout.addSpacing(10)
        
        # Büyük butonlar
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        # Screenshot butonu
        self.btn_screenshot = QPushButton("📸\nEkran Görüntüsü")
        self.btn_screenshot.setFixedSize(180, 120)
        self.btn_screenshot.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_screenshot.clicked.connect(self._take_screenshot)
        self.btn_screenshot.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4facfe, stop:1 #00f2fe);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00d2ff, stop:1 #3a7bd5);
            }
            QPushButton:pressed {
                background: #3a7bd5;
            }
        """)
        buttons_layout.addWidget(self.btn_screenshot)
        
        # Video kayıt butonu
        self.btn_record = QPushButton("🔴\nKayıt Başlat")
        self.btn_record.setFixedSize(180, 120)
        self.btn_record.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_record.clicked.connect(self._toggle_recording)
        self.btn_record.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fa709a, stop:1 #fee140);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff6b6b, stop:1 #f9ca24);
            }
            QPushButton:pressed {
                background: #e74c3c;
            }
        """)
        buttons_layout.addWidget(self.btn_record)
        
        # Instant replay butonu
        self.btn_replay = QPushButton("⏮️\nInstant Replay")
        self.btn_replay.setFixedSize(180, 120)
        self.btn_replay.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_replay.clicked.connect(self._save_instant_replay)
        self.btn_replay.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #a8edea, stop:1 #fed6e3);
                color: #2c3e50;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7dd3c0, stop:1 #f9b9d0);
            }
            QPushButton:pressed {
                background: #6ab4a7;
            }
        """)
        buttons_layout.addWidget(self.btn_replay)
        
        layout.addLayout(buttons_layout)
        
        # Durum bilgisi
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        status_layout = QVBoxLayout(status_frame)
        
        self.lbl_status = QLabel("⚪ Hazır")
        self.lbl_status.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_status.setStyleSheet("color: #27ae60;")
        status_layout.addWidget(self.lbl_status)
        
        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color: #7f8c8d; font-size: 10pt;")
        self.lbl_info.setWordWrap(True)
        status_layout.addWidget(self.lbl_info)
        
        layout.addWidget(status_frame)
        
        # Ayarlar bilgisi
        settings_frame = QFrame()
        settings_frame.setStyleSheet("""
            QFrame {
                background: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        settings_layout = QVBoxLayout(settings_frame)
        
        info = self.video_recorder.get_recording_info()
        settings_text = f"""
📁 Kayıt Konumu: {info['output_dir']}
⚙️ FPS: {info['fps']} | Çözünürlük: {info['resolution']} | Bitrate: {info['bitrate']} kbps
⏱️ Instant Replay Buffer: {info['replay_buffer_seconds']} saniye
        """.strip()
        
        self.lbl_settings = QLabel(settings_text)
        self.lbl_settings.setStyleSheet("color: #856404; font-size: 9pt;")
        self.lbl_settings.setWordWrap(True)
        settings_layout.addWidget(self.lbl_settings)
        
        layout.addWidget(settings_frame)
        
        layout.addStretch()
        
        # Kayıt süre göstergesi
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self._update_recording_time)
        self.recording_start_time = 0
    
    def _take_screenshot(self):
        """Screenshot al"""
        self.btn_screenshot.setEnabled(False)
        self.lbl_status.setText("📸 Ekran görüntüsü alınıyor...")
        
        self.video_recorder.take_screenshot()
        
        QTimer.singleShot(500, lambda: self.btn_screenshot.setEnabled(True))
    
    def _toggle_recording(self):
        """Kayıt başlat/durdur"""
        if self.video_recorder.is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_recording(self):
        """Kayıt başlat"""
        self.video_recorder.start_recording()
    
    def _stop_recording(self):
        """Kayıt durdur"""
        self.video_recorder.stop_recording()
    
    def _save_instant_replay(self):
        """Instant replay kaydet"""
        self.btn_replay.setEnabled(False)
        self.lbl_status.setText("⏮️ Son 30 saniye kaydediliyor...")
        
        self.video_recorder.save_instant_replay()
        
        QTimer.singleShot(1000, lambda: self.btn_replay.setEnabled(True))
    
    def _on_screenshot_taken(self, filepath: str):
        """Screenshot alındı"""
        self.lbl_status.setText("✅ Ekran görüntüsü alındı!")
        self.lbl_info.setText(f"📁 {filepath}")
        QTimer.singleShot(3000, self._update_status)
    
    def _on_recording_started(self):
        """Kayıt başladı"""
        import time
        self.recording_start_time = time.time()
        self.recording_timer.start(1000)
        
        self.btn_record.setText("⏹️\nKayıt Durdur")
        self.btn_record.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e74c3c, stop:1 #c0392b);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #c0392b;
            }
        """)
        
        self.lbl_status.setText("🔴 Kayıt devam ediyor...")
        self.lbl_info.setText("00:00:00")
    
    def _on_recording_stopped(self, filepath: str):
        """Kayıt durdu"""
        self.recording_timer.stop()
        
        self.btn_record.setText("🔴\nKayıt Başlat")
        self.btn_record.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fa709a, stop:1 #fee140);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff6b6b, stop:1 #f9ca24);
            }
        """)
        
        if "replay" in filepath:
            self.lbl_status.setText("✅ Instant replay kaydedildi!")
        else:
            self.lbl_status.setText("✅ Video kaydedildi!")
        
        self.lbl_info.setText(f"📁 {filepath}")
        QTimer.singleShot(3000, self._update_status)
    
    def _on_error(self, error_msg: str):
        """Hata oluştu"""
        self.lbl_status.setText(f"❌ Hata!")
        self.lbl_info.setText(error_msg)
        QTimer.singleShot(5000, self._update_status)
    
    def _update_status(self):
        """Durum güncelle"""
        if self.video_recorder.is_recording:
            return
        
        self.lbl_status.setText("⚪ Hazır")
        self.lbl_info.setText("")
    
    def _update_recording_time(self):
        """Kayıt süresini güncelle"""
        import time
        elapsed = int(time.time() - self.recording_start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.lbl_info.setText(f"⏱️ {time_str}")
