"""
Modern PIN Style Unlock Dialog - Windows Hello ile
"""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QWidget, QGridLayout
)
from PySide6.QtGui import QIcon, QFont, QCursor

from ..biometric_auth import get_biometric_auth
from ..utils import resource_path


class PinButton(QPushButton):
    """PIN tuş takımı butonu"""
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(70, 70)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet("""
            QPushButton {
                background: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 35px;
                font-size: 24px;
                font-weight: bold;
                color: #212529;
            }
            QPushButton:hover {
                background: #e9ecef;
                border: 2px solid #adb5bd;
            }
            QPushButton:pressed {
                background: #dee2e6;
            }
        """)


class ModernUnlockDialog(QDialog):
    """Modern PIN style unlock dialog"""
    
    unlocked = Signal()
    
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.biometric = get_biometric_auth()
        self.authenticated = False
        self.pin_input = ""
        self.max_pin_length = 6
        
        self.setWindowTitle("ClipStack - Kimlik Doğrulama")
        self.setModal(True)
        self.setFixedSize(450, 600)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)
        
        # Logo/İkon
        icon_label = QLabel("🔐")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 64px;")
        layout.addWidget(icon_label)
        
        # Başlık
        title = QLabel("ClipStack")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Alt başlık
        subtitle = QLabel("PIN kodunuzu girin veya Windows Hello kullanın")
        subtitle.setFont(QFont("Segoe UI", 11))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.9);")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        
        layout.addSpacing(20)
        
        # PIN göstergesi (noktalar)
        pin_container = QWidget()
        pin_container.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 25px;
                padding: 15px;
            }
        """)
        pin_layout = QHBoxLayout(pin_container)
        pin_layout.setSpacing(15)
        pin_layout.setContentsMargins(20, 10, 20, 10)
        
        self.pin_dots = []
        for i in range(self.max_pin_length):
            dot = QLabel("○")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 0.6);
                    font-size: 32px;
                    min-width: 20px;
                }
            """)
            pin_layout.addWidget(dot)
            self.pin_dots.append(dot)
        
        layout.addWidget(pin_container, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Hata mesajı
        self.lbl_error = QLabel("")
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_error.setStyleSheet("color: #ff6b6b; font-size: 12px; font-weight: bold;")
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)
        
        layout.addSpacing(10)
        
        # PIN pad
        grid = QGridLayout()
        grid.setSpacing(12)
        
        # Sayı butonları (1-9)
        for i in range(1, 10):
            btn = PinButton(str(i))
            btn.clicked.connect(lambda checked, num=i: self._on_number_pressed(num))
            row = (i - 1) // 3
            col = (i - 1) % 3
            grid.addWidget(btn, row, col)
        
        # 0 butonu (ortada)
        btn_0 = PinButton("0")
        btn_0.clicked.connect(lambda: self._on_number_pressed(0))
        grid.addWidget(btn_0, 3, 1)
        
        # Backspace butonu
        btn_back = PinButton("⌫")
        btn_back.clicked.connect(self._on_backspace)
        btn_back.setStyleSheet("""
            QPushButton {
                background: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 35px;
                font-size: 20px;
                color: #dc3545;
            }
            QPushButton:hover {
                background: #fee;
                border: 2px solid #dc3545;
            }
        """)
        grid.addWidget(btn_back, 3, 2)
        
        layout.addLayout(grid)
        
        layout.addSpacing(15)
        
        # Windows Hello butonu
        self.btn_windows_hello = QPushButton("🔑 Windows Hello")
        self.btn_windows_hello.setFixedHeight(50)
        self.btn_windows_hello.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_windows_hello.clicked.connect(self._try_windows_hello)
        self.btn_windows_hello.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.25);
                color: white;
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 25px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.35);
                border: 2px solid rgba(255, 255, 255, 0.5);
            }
        """)
        layout.addWidget(self.btn_windows_hello)
        
        # Windows Hello mevcut değilse butonu gizle
        if not self.biometric.is_available():
            self.btn_windows_hello.setVisible(False)
        
        # Otomatik Windows Hello denemesi
        if self.settings and self.settings.get("biometric_enabled", False):
            QTimer.singleShot(500, self._try_windows_hello)
    
    def _update_pin_display(self):
        """PIN göstergesini güncelle"""
        for i, dot in enumerate(self.pin_dots):
            if i < len(self.pin_input):
                dot.setText("●")
                dot.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 32px;
                        min-width: 20px;
                    }
                """)
            else:
                dot.setText("○")
                dot.setStyleSheet("""
                    QLabel {
                        color: rgba(255, 255, 255, 0.6);
                        font-size: 32px;
                        min-width: 20px;
                    }
                """)
    
    def _on_number_pressed(self, num: int):
        """Sayı butonuna basıldı"""
        if len(self.pin_input) < self.max_pin_length:
            self.pin_input += str(num)
            self._update_pin_display()
            self.lbl_error.setVisible(False)
            
            # PIN tamamlandıysa kontrol et
            if len(self.pin_input) == self.max_pin_length:
                QTimer.singleShot(200, self._check_pin)
    
    def _on_backspace(self):
        """Backspace basıldı"""
        if self.pin_input:
            self.pin_input = self.pin_input[:-1]
            self._update_pin_display()
            self.lbl_error.setVisible(False)
    
    def _check_pin(self):
        """PIN'i kontrol et"""
        # Demo: "123456" kabul edilir
        # Gerçek uygulamada settings'den encrypted PIN okunmalı
        correct_pin = self.settings.get("app_pin", "123456") if self.settings else "123456"
        
        if self.pin_input == correct_pin:
            self.authenticated = True
            self.unlocked.emit()
            self.accept()
        else:
            self.lbl_error.setText("❌ Hatalı PIN!")
            self.lbl_error.setVisible(True)
            self.pin_input = ""
            self._update_pin_display()
            
            # Shake animasyonu (opsiyonel)
            QTimer.singleShot(1500, lambda: self.lbl_error.setVisible(False))
    
    def _try_windows_hello(self):
        """Windows Hello ile kimlik doğrulama dene"""
        if not self.biometric.is_available():
            self.lbl_error.setText("⚠️ Windows Hello kullanılamıyor")
            self.lbl_error.setVisible(True)
            return
        
        self.btn_windows_hello.setEnabled(False)
        self.btn_windows_hello.setText("⏳ Doğrulanıyor...")
        
        # Biometric auth
        result = self.biometric.authenticate("ClipStack kilidi açılıyor...")
        
        if result:
            self.authenticated = True
            self.unlocked.emit()
            self.accept()
        else:
            self.lbl_error.setText("❌ Kimlik doğrulama başarısız!")
            self.lbl_error.setVisible(True)
            self.btn_windows_hello.setEnabled(True)
            self.btn_windows_hello.setText("🔑 Windows Hello")
            QTimer.singleShot(2000, lambda: self.lbl_error.setVisible(False))
    
    def keyPressEvent(self, event):
        """Klavye tuşları"""
        key = event.key()
        
        # Sayı tuşları
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            num = key - Qt.Key.Key_0
            self._on_number_pressed(num)
        
        # Numpad
        elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            num = key - Qt.Key.Key_0
            self._on_number_pressed(num)
        
        # Backspace
        elif key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._on_backspace()
        
        # Enter
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if len(self.pin_input) == self.max_pin_length:
                self._check_pin()
        
        # Escape
        elif key == Qt.Key.Key_Escape:
            pass  # Escape'i devre dışı bırak (kilitli kalmalı)
        
        else:
            super().keyPressEvent(event)
