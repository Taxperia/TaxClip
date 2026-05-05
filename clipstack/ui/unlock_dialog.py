"""
Biometric Unlock Dialog
Windows Hello ile uygulama kilidi açma
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QWidget
)
from PySide6.QtGui import QFont

from ..biometric_auth import get_biometric_auth
from ..utils import resource_path, svg_icon


class UnlockDialog(QDialog):
    """Biometric unlock dialog"""
    
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.biometric = get_biometric_auth()
        self.authenticated = False
        
        self.setWindowTitle("ClipStack Kilidi")
        self.setModal(True)
        self.setFixedSize(400, 300)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # İkon
        icon_label = QLabel()
        try:
            icon = svg_icon("assets/icons/tray/tray1.svg")
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(64, 64))
        except:
            pass
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)
        
        # Başlık
        title = QLabel("ClipStack Kilitli")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Açıklama
        self.lbl_description = QLabel()
        self.lbl_description.setWordWrap(True)
        self.lbl_description.setAlignment(Qt.AlignCenter)
        self.lbl_description.setStyleSheet("color: #666;")
        layout.addWidget(self.lbl_description)
        
        layout.addStretch()
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_biometric = QPushButton("🔐 Windows Hello ile Aç")
        self.btn_biometric.setMinimumHeight(40)
        self.btn_biometric.clicked.connect(self._authenticate_biometric)
        btn_layout.addWidget(self.btn_biometric)
        
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        # Alternatif: Master password alanı (gizli)
        self.password_widget = QWidget()
        password_layout = QVBoxLayout(self.password_widget)
        password_layout.setContentsMargins(0, 10, 0, 0)
        password_layout.setSpacing(5)
        
        lbl_alt = QLabel("Alternatif: Master Password")
        lbl_alt.setStyleSheet("color: #888; font-size: 11px;")
        lbl_alt.setAlignment(Qt.AlignCenter)
        password_layout.addWidget(lbl_alt)
        
        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("Master password giriniz...")
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.returnPressed.connect(self._authenticate_password)
        password_layout.addWidget(self.txt_password)
        
        self.btn_password = QPushButton("🔑 Şifre ile Aç")
        self.btn_password.clicked.connect(self._authenticate_password)
        password_layout.addWidget(self.btn_password)
        
        self.password_widget.setVisible(False)
        layout.addWidget(self.password_widget)
        
        # Şifre göster linki
        self.btn_show_password = QPushButton("Şifre ile aç")
        self.btn_show_password.setFlat(True)
        self.btn_show_password.setStyleSheet("QPushButton { color: #4A90E2; text-decoration: underline; border: none; }")
        self.btn_show_password.clicked.connect(self._toggle_password_widget)
        layout.addWidget(self.btn_show_password, alignment=Qt.AlignCenter)
        
        # Duruma göre UI güncelle
        self._update_ui()
        
        # Otomatik Windows Hello başlat
        if self.biometric.is_available():
            QTimer.singleShot(500, self._authenticate_biometric)
    
    def _update_ui(self):
        """UI durumunu güncelle"""
        if not self.biometric.is_available():
            self.lbl_description.setText(
                "Windows Hello kullanılamıyor.\n"
                "Master password ile devam edin."
            )
            self.btn_biometric.setEnabled(False)
            self.password_widget.setVisible(True)
            self.btn_show_password.setVisible(False)
        else:
            available_types = self.biometric.get_available_types()
            if available_types:
                types_str = ", ".join(available_types)
                self.lbl_description.setText(
                    f"Uygulamayı açmak için Windows Hello kullanın.\n"
                    f"Mevcut: {types_str}"
                )
            else:
                self.lbl_description.setText(
                    "Windows Hello ile devam etmek için\n"
                    "butona tıklayın."
                )
    
    def _toggle_password_widget(self):
        """Şifre widget'ını göster/gizle"""
        visible = self.password_widget.isVisible()
        self.password_widget.setVisible(not visible)
        self.btn_show_password.setText("Gizle" if not visible else "Şifre ile aç")
    
    def _authenticate_biometric(self):
        """Windows Hello ile doğrula"""
        if not self.biometric.is_available():
            self.lbl_description.setText(
                "⚠️ Windows Hello kullanılamıyor.\n"
                f"{self.biometric.get_error_message()}"
            )
            return
        
        self.btn_biometric.setEnabled(False)
        self.btn_biometric.setText("Doğrulanıyor...")
        
        # Windows Hello dialog'u göster
        success, error_msg = self.biometric.authenticate("ClipStack kilidini açmak için")
        
        if success:
            self.authenticated = True
            self.accept()
        else:
            self.btn_biometric.setEnabled(True)
            self.btn_biometric.setText("🔐 Windows Hello ile Aç")
            
            if "iptal" in error_msg.lower():
                self.lbl_description.setText("❌ Doğrulama iptal edildi.")
            else:
                self.lbl_description.setText(f"❌ Doğrulama başarısız:\n{error_msg}")
            
            # Şifre widget'ını göster
            if not self.password_widget.isVisible():
                self.password_widget.setVisible(True)
                self.btn_show_password.setVisible(False)
    
    def _authenticate_password(self):
        """Master password ile doğrula"""
        password = self.txt_password.text().strip()
        
        if not password:
            self.lbl_description.setText("⚠️ Lütfen şifrenizi girin.")
            return
        
        # TODO: Master password kontrolü
        # Şimdilik basit kontrol (gerçek uygulamada hash kontrolü yapılmalı)
        stored_password = self.settings.get("master_password", "") if self.settings else ""
        
        if password == stored_password or not stored_password:
            self.authenticated = True
            self.accept()
        else:
            self.lbl_description.setText("❌ Yanlış şifre!")
            self.txt_password.clear()
            self.txt_password.setFocus()
    
    def is_authenticated(self) -> bool:
        """Doğrulama başarılı mı?"""
        return self.authenticated
