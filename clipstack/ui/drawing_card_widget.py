"""
Drawing Card Widget - ItemWidget tarzı çizim kartı
"""
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap


CARD_W = 260
CARD_H = 160


class DrawingCardWidget(QFrame):
    """Çizim kartı"""
    
    edit_requested = Signal(int)  # drawing_id
    delete_requested = Signal(int)  # drawing_id
    
    def __init__(self, drawing: dict, parent=None):
        super().__init__(parent)
        self.drawing = drawing
        self.drawing_id = drawing["id"]
        
        self.setObjectName("DrawingCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(CARD_W, CARD_H)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Thumbnail
        self.thumbnail = QLabel()
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setFixedSize(240, 90)
        self.thumbnail.setStyleSheet("""
            QLabel {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.thumbnail)
        
        # Tarih
        date_lbl = QLabel(self._format_date(drawing.get("created_at", "")))
        date_lbl.setFont(QFont("Segoe UI", 8))
        date_lbl.setStyleSheet("color: #6c757d;")
        layout.addWidget(date_lbl)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        
        btn_edit = self._create_button("✏️ Düzenle")
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.drawing_id))
        btn_layout.addWidget(btn_edit)
        
        btn_delete = self._create_button("🗑️ Sil")
        btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.drawing_id))
        btn_layout.addWidget(btn_delete)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        # Thumbnail yükle
        self._load_thumbnail()
    
    def _create_button(self, text: str) -> QPushButton:
        """Flat buton"""
        btn = QPushButton(text)
        btn.setFixedSize(115, 28)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                color: white;
                font-size: 11px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        return btn
    
    def _format_date(self, date_str: str) -> str:
        """Tarih formatla"""
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%d.%m.%Y %H:%M")
        except:
            return date_str
    
    def _load_thumbnail(self):
        """Thumbnail yükle"""
        try:
            import base64
            from PySide6.QtGui import QImage
            
            # image_data veya image key'ini kullan
            img_key = "image_data" if "image_data" in self.drawing else "image"
            img_b64 = self.drawing[img_key]
            
            # Base64 padding düzelt
            if isinstance(img_b64, str):
                padding = len(img_b64) % 4
                if padding:
                    img_b64 += '=' * (4 - padding)
            
            img_bytes = base64.b64decode(img_b64)
            img = QImage()
            img.loadFromData(img_bytes)
            
            # Ölçeklendir
            pixmap = QPixmap.fromImage(img)
            scaled = pixmap.scaled(
                240, 90,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.thumbnail.setPixmap(scaled)
            
        except Exception as e:
            self.thumbnail.setText("⚠️ Yüklenemedi")
            print(f"Thumbnail yükleme hatası: {e}")
