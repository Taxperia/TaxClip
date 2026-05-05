"""
TOTP Verification Dialog - Google Authenticator kod doğrulama
Modern & polished UI
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QMessageBox, QFrame,
    QSpacerItem, QSizePolicy, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPixmap, QColor, QPainter, QPainterPath, QLinearGradient
from datetime import datetime

from ..totp_manager import TOTPManager


# Son kullanilan kodlari takip et (replay attack onleme)
_used_codes = {}  # {code: timestamp}


def _is_code_recently_used(code: str) -> bool:
    global _used_codes
    now = datetime.now()
    expired = [c for c, t in _used_codes.items() if (now - t).total_seconds() > 120]
    for c in expired:
        del _used_codes[c]
    return code in _used_codes


def _mark_code_used(code: str):
    global _used_codes
    _used_codes[code] = datetime.now()


class TOTPVerifyDialog(QDialog):
    verified = Signal()
    
    def __init__(self, settings=None, parent=None, title="Doğrulama Gerekli"):
        super().__init__(parent)
        self.settings = settings
        self.totp = TOTPManager(settings)
        self._verified = False
        
        self.setWindowTitle(title)
        self.setFixedSize(440, 380)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._setup_ui()
    
    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        
        container = QFrame()
        container.setObjectName("totpContainer")
        container.setStyleSheet("""
            QFrame#totpContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 120))
        container.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(40, 35, 40, 30)
        
        accent_line = QFrame()
        accent_line.setFixedHeight(3)
        accent_line.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4CAF50, stop:0.5 #00BCD4, stop:1 #4CAF50);
            border-radius: 1px;
        """)
        layout.addWidget(accent_line)
        
        layout.addSpacing(8)
        
        icon_label = QLabel("\U0001f6e1\ufe0f")
        icon_label.setFont(QFont("Segoe UI Emoji", 32))
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)
        
        title = QLabel("İki Faktörlü Doğrulama")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #e0e0e0; margin: 0; padding: 0;")
        layout.addWidget(title)
        
        desc = QLabel("Google Authenticator uygulamanızdaki\n6 haneli kodu girin")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px; margin-bottom: 8px;")
        layout.addWidget(desc)
        
        code_frame = QFrame()
        code_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.05);
                border: 2px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
                padding: 6px;
            }
        """)
        code_layout = QVBoxLayout(code_frame)
        code_layout.setContentsMargins(8, 8, 8, 8)
        
        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("...... ")
        self.txt_code.setMaxLength(6)
        self.txt_code.setAlignment(Qt.AlignCenter)
        self.txt_code.setFont(QFont("Consolas", 30, QFont.Bold))
        self.txt_code.setFixedHeight(65)
        self.txt_code.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #4CAF50;
                letter-spacing: 16px;
                padding-left: 20px;
                selection-background-color: rgba(76, 175, 80, 0.3);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.2);
                letter-spacing: 10px;
            }
        """)
        self.txt_code.textChanged.connect(self._on_code_changed)
        self.txt_code.returnPressed.connect(self._verify)
        code_layout.addWidget(self.txt_code)
        
        layout.addWidget(code_frame)
        
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #ff5252; font-size: 11px; font-weight: 500;")
        self.lbl_error.setAlignment(Qt.AlignCenter)
        self.lbl_error.setFixedHeight(20)
        layout.addWidget(self.lbl_error)
        
        layout.addSpacing(4)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_cancel = QPushButton("İptal")
        btn_cancel.setFixedHeight(44)
        btn_cancel.setMinimumWidth(110)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.25);
                color: white;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        self.btn_verify = QPushButton("✓  Doğrula")
        self.btn_verify.setFixedHeight(44)
        self.btn_verify.setMinimumWidth(150)
        self.btn_verify.setEnabled(False)
        self.btn_verify.setCursor(Qt.PointingHandCursor)
        self.btn_verify.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #45a049);
                border: none;
                border-radius: 10px;
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5CBF60, stop:1 #4CAF50);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.3);
            }
        """)
        self.btn_verify.clicked.connect(self._verify)
        btn_layout.addWidget(self.btn_verify)
        
        layout.addLayout(btn_layout)
        outer.addWidget(container)
    
    def _on_code_changed(self, text: str):
        filtered = ''.join(c for c in text if c.isdigit())
        if filtered != text:
            self.txt_code.setText(filtered)
            return
        self.lbl_error.setText("")
        self.btn_verify.setEnabled(len(text) == 6)
        if len(text) == 6:
            QTimer.singleShot(200, self._verify)
    
    def _verify(self):
        code = self.txt_code.text().strip()
        if len(code) != 6:
            return
        if _is_code_recently_used(code):
            self.lbl_error.setText("⚠️ Bu kod zaten kullanıldı, yeni kod bekleyin")
            self.txt_code.selectAll()
            self.txt_code.setFocus()
            return
        if self.totp.verify(code):
            _mark_code_used(code)
            self._verified = True
            self.verified.emit()
            self.accept()
        else:
            self.lbl_error.setText("❌ Geçersiz kod, tekrar deneyin")
            self.txt_code.selectAll()
            self.txt_code.setFocus()
            self._shake()
    
    def _shake(self):
        try:
            anim = QPropertyAnimation(self, b"pos")
            anim.setDuration(300)
            anim.setLoopCount(1)
            pos = self.pos()
            anim.setKeyValueAt(0, pos)
            anim.setKeyValueAt(0.1, pos + type(pos)(10, 0))
            anim.setKeyValueAt(0.2, pos + type(pos)(-10, 0))
            anim.setKeyValueAt(0.3, pos + type(pos)(8, 0))
            anim.setKeyValueAt(0.4, pos + type(pos)(-8, 0))
            anim.setKeyValueAt(0.5, pos + type(pos)(4, 0))
            anim.setKeyValueAt(0.6, pos + type(pos)(-4, 0))
            anim.setKeyValueAt(1.0, pos)
            anim.setEasingCurve(QEasingCurve.OutElastic)
            self._shake_anim = anim
            anim.start()
        except Exception:
            pass
    
    def is_verified(self) -> bool:
        return self._verified
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()


class TOTPSetupDialog(QDialog):
    setup_complete = Signal()
    
    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.totp = TOTPManager(settings)
        self._secret = None
        
        self.setWindowTitle("2FA Kurulumu")
        self.setFixedSize(500, 680)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._setup_ui()
    
    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        
        container = QFrame()
        container.setObjectName("setupContainer")
        container.setStyleSheet("""
            QFrame#setupContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 120))
        container.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        layout.setContentsMargins(35, 30, 35, 25)
        
        accent_line = QFrame()
        accent_line.setFixedHeight(3)
        accent_line.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #FF9800, stop:0.5 #4CAF50, stop:1 #2196F3);
            border-radius: 1px;
        """)
        layout.addWidget(accent_line)
        
        layout.addSpacing(6)
        
        title = QLabel("2FA Kurulumu")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(title)
        
        steps_style = "color: rgba(255,255,255,0.6); font-size: 12px; padding: 2px 0;"
        
        step1 = QLabel("1. Google Authenticator'ı telefonunuza indirin")
        step1.setStyleSheet(steps_style)
        layout.addWidget(step1)
        
        step2 = QLabel("2. Aşağıdaki QR kodu tarayın veya kodu girin")
        step2.setStyleSheet(steps_style)
        layout.addWidget(step2)
        
        qr_frame = QFrame()
        qr_frame.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 14px;
                border: 2px solid rgba(255, 255, 255, 0.15);
            }
        """)
        qr_frame_layout = QVBoxLayout(qr_frame)
        qr_frame_layout.setContentsMargins(10, 10, 10, 10)
        
        self.lbl_qr = QLabel()
        self.lbl_qr.setFixedSize(180, 180)
        self.lbl_qr.setAlignment(Qt.AlignCenter)
        self.lbl_qr.setStyleSheet("background: transparent; border: none;")
        qr_frame_layout.addWidget(self.lbl_qr, alignment=Qt.AlignCenter)
        
        qr_container = QHBoxLayout()
        qr_container.addStretch()
        qr_container.addWidget(qr_frame)
        qr_container.addStretch()
        layout.addLayout(qr_container)
        
        self.lbl_manual = QLabel("")
        self.lbl_manual.setAlignment(Qt.AlignCenter)
        self.lbl_manual.setStyleSheet("""
            color: rgba(255,255,255,0.5); 
            font-size: 11px; 
            font-family: Consolas, monospace;
            padding: 4px;
            background: rgba(255,255,255,0.03);
            border-radius: 6px;
        """)
        self.lbl_manual.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.lbl_manual)
        
        layout.addSpacing(4)
        
        step3 = QLabel("3. Doğrulama kodunu girin")
        step3.setStyleSheet(steps_style)
        layout.addWidget(step3)
        
        code_frame = QFrame()
        code_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.05);
                border: 2px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
                padding: 4px;
            }
        """)
        code_layout = QVBoxLayout(code_frame)
        code_layout.setContentsMargins(6, 4, 6, 4)
        
        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("......")
        self.txt_code.setMaxLength(6)
        self.txt_code.setAlignment(Qt.AlignCenter)
        self.txt_code.setFont(QFont("Consolas", 24, QFont.Bold))
        self.txt_code.setFixedHeight(55)
        self.txt_code.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #FF9800;
                letter-spacing: 14px;
                padding-left: 16px;
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.2);
            }
        """)
        self.txt_code.textChanged.connect(self._on_code_changed)
        self.txt_code.returnPressed.connect(self._activate)
        code_layout.addWidget(self.txt_code)
        
        layout.addWidget(code_frame)
        
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #ff5252; font-size: 11px; font-weight: 500;")
        self.lbl_error.setAlignment(Qt.AlignCenter)
        self.lbl_error.setFixedHeight(18)
        layout.addWidget(self.lbl_error)
        
        layout.addSpacing(4)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_cancel = QPushButton("İptal")
        btn_cancel.setFixedHeight(44)
        btn_cancel.setMinimumWidth(110)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        self.btn_activate = QPushButton("✓  Aktifleştir")
        self.btn_activate.setFixedHeight(44)
        self.btn_activate.setMinimumWidth(150)
        self.btn_activate.setEnabled(False)
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF9800, stop:1 #F57C00);
                border: none;
                border-radius: 10px;
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FFB74D, stop:1 #FF9800);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.3);
            }
        """)
        self.btn_activate.clicked.connect(self._activate)
        btn_layout.addWidget(self.btn_activate)
        
        layout.addLayout(btn_layout)
        outer.addWidget(container)
        
        self._generate_qr()
    
    def _generate_qr(self):
        if not self.totp.is_available():
            self.lbl_qr.setText("pyotp yüklü değil\npip install pyotp")
            return
        
        self._secret = self.totp.generate_secret()
        
        formatted = ' '.join([self._secret[i:i+4] for i in range(0, len(self._secret), 4)])
        self.lbl_manual.setText(f"Manuel kod: {formatted}")
        
        if self.totp.is_qrcode_available():
            qr_bytes = self.totp.get_qrcode_image()
            if qr_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(qr_bytes)
                scaled = pixmap.scaled(170, 170, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_qr.setPixmap(scaled)
            else:
                self.lbl_qr.setText("QR oluşturulamadı")
        else:
            self.lbl_qr.setText("qrcode yüklü değil\npip install qrcode[pil]")
    
    def _on_code_changed(self, text: str):
        filtered = ''.join(c for c in text if c.isdigit())
        if filtered != text:
            self.txt_code.setText(filtered)
            return
        self.lbl_error.setText("")
        self.btn_activate.setEnabled(len(text) == 6)
    
    def _activate(self):
        code = self.txt_code.text().strip()
        if len(code) != 6 or not self._secret:
            return
        
        import pyotp
        totp = pyotp.TOTP(self._secret)
        
        if totp.verify(code, valid_window=1):
            if self.totp.save_secret(self._secret):
                _mark_code_used(code)
                QMessageBox.information(
                    self,
                    "Başarılı",
                    "✅ İki faktörlü doğrulama aktifleştirildi!\n\n"
                    "Artık hassas verilere erişmek için\nGoogle Authenticator kodunuz gerekecek."
                )
                self.setup_complete.emit()
                self.accept()
            else:
                self.lbl_error.setText("❌ Kaydetme hatası")
        else:
            self.lbl_error.setText("❌ Geçersiz kod, tekrar deneyin")
            self.txt_code.selectAll()
            self.txt_code.setFocus()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
