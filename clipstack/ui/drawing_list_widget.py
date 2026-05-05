"""
Çizim listesi widget'ı - kaydedilmiş çizimleri gösterir
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage
from datetime import datetime


class DrawingCardWidget(QFrame):
    """Tek bir çizimi gösteren kart widget'ı"""
    
    opened = Signal(int)  # drawing_id
    deleted = Signal(int)  # drawing_id
    favorite_toggled = Signal(int)  # drawing_id
    
    def __init__(self, drawing_data: dict, parent=None):
        super().__init__(parent)
        self.drawing_data = drawing_data
        self.drawing_id = drawing_data['id']
        
        self._init_ui()
        self._update_style()
    
    def _init_ui(self):
        """UI oluştur"""
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        self.setCursor(Qt.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Thumbnail (sabit boyut)
        self.lbl_thumbnail = QLabel()
        self.lbl_thumbnail.setFixedSize(200, 150)
        self.lbl_thumbnail.setScaledContents(True)
        self.lbl_thumbnail.setStyleSheet("border: 1px solid #ccc; background: white;")
        self.lbl_thumbnail.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_thumbnail, 0, Qt.AlignCenter)
        
        # Başlık
        self.lbl_title = QLabel(self.drawing_data.get('title', 'Çizim'))
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        font = self.lbl_title.font()
        font.setPointSize(10)
        font.setBold(True)
        self.lbl_title.setFont(font)
        layout.addWidget(self.lbl_title)
        
        # Tarih
        created_at = self.drawing_data.get('created_at', '')
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at)
                date_str = dt.strftime("%d.%m.%Y %H:%M")
            except:
                date_str = created_at
        else:
            date_str = ""
        
        self.lbl_date = QLabel(date_str)
        self.lbl_date.setAlignment(Qt.AlignCenter)
        self.lbl_date.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(self.lbl_date)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        
        self.btn_favorite = QPushButton("⭐" if self.drawing_data.get('favorite') else "☆")
        self.btn_favorite.setFixedSize(32, 28)
        self.btn_favorite.clicked.connect(self._on_favorite_clicked)
        self.btn_favorite.setToolTip("Favori")
        btn_layout.addWidget(self.btn_favorite)
        
        self.btn_open = QPushButton("✏️")
        self.btn_open.setFixedSize(32, 28)
        self.btn_open.clicked.connect(self._on_open_clicked)
        self.btn_open.setToolTip("Düzenle")
        btn_layout.addWidget(self.btn_open)
        
        self.btn_delete = QPushButton("🗑️")
        self.btn_delete.setFixedSize(32, 28)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_delete.setToolTip("Sil")
        btn_layout.addWidget(self.btn_delete)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.setFixedWidth(220)
    
    def set_thumbnail(self, image_data):
        """Thumbnail görselini ayarla (base64 string veya bytes)"""
        if not image_data:
            self.lbl_thumbnail.setText("Önizleme yok")
            return
        
        import base64
        
        # Eğer string ise base64 decode et
        if isinstance(image_data, str):
            try:
                # Padding düzelt
                padding = len(image_data) % 4
                if padding:
                    image_data += '=' * (4 - padding)
                image_bytes = base64.b64decode(image_data)
            except Exception as e:
                print(f"Base64 decode hatası: {e}")
                self.lbl_thumbnail.setText("Yüklenemedi")
                return
        else:
            image_bytes = image_data
        
        image = QImage()
        if image.loadFromData(image_bytes):
            pixmap = QPixmap.fromImage(image)
            # Aspect ratio koruyarak ölçeklendir
            scaled = pixmap.scaled(
                self.lbl_thumbnail.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.lbl_thumbnail.setPixmap(scaled)
        else:
            self.lbl_thumbnail.setText("Yüklenemedi")
    
    def _update_style(self):
        """Kart stilini güncelle"""
        if self.drawing_data.get('favorite'):
            self.setStyleSheet("""
                DrawingCardWidget {
                    background-color: #fffacd;
                    border: 2px solid #ffd700;
                    border-radius: 8px;
                }
                DrawingCardWidget:hover {
                    background-color: #ffffe0;
                    border: 2px solid #ffb300;
                }
            """)
        else:
            self.setStyleSheet("""
                DrawingCardWidget {
                    background-color: #f9f9f9;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                }
                DrawingCardWidget:hover {
                    background-color: #f0f0f0;
                    border: 2px solid #aaa;
                }
            """)
    
    def _on_open_clicked(self):
        """Düzenle butonuna tıklandı"""
        self.opened.emit(self.drawing_id)
    
    def _on_delete_clicked(self):
        """Sil butonuna tıklandı"""
        reply = QMessageBox.question(
            self,
            "Çizimi Sil",
            "Bu çizimi silmek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.deleted.emit(self.drawing_id)
    
    def _on_favorite_clicked(self):
        """Favori butonuna tıklandı"""
        self.favorite_toggled.emit(self.drawing_id)
        
        # Görsel geri bildirim
        self.drawing_data['favorite'] = not self.drawing_data.get('favorite', False)
        self.btn_favorite.setText("⭐" if self.drawing_data['favorite'] else "☆")
        self._update_style()


class DrawingListWidget(QWidget):
    """Çizim listesi yönetici widget'ı"""
    
    drawing_opened = Signal(int)  # drawing_id
    
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.drawing_cards = []
        
        self._init_ui()
        self._load_drawings()
    
    def _init_ui(self):
        """UI oluştur"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Üst bar
        top_bar = QHBoxLayout()
        
        self.lbl_stats = QLabel("0 çizim")
        self.lbl_stats.setStyleSheet("font-size: 11pt; color: gray;")
        top_bar.addWidget(self.lbl_stats)
        
        top_bar.addStretch()
        
        self.btn_refresh = QPushButton("🔄 Yenile")
        self.btn_refresh.clicked.connect(self._load_drawings)
        top_bar.addWidget(self.btn_refresh)
        
        layout.addLayout(top_bar)
        
        # Scroll alan
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        self.grid_layout = QHBoxLayout(scroll_widget)
        self.grid_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
    
    def _load_drawings(self):
        """Çizimleri veritabanından yükle"""
        # Eski kartları temizle
        for card in self.drawing_cards:
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        
        self.drawing_cards.clear()
        
        # Yeni çizimleri yükle
        drawings = self.storage.list_drawings(limit=100)
        
        for drawing_data in drawings:
            card = DrawingCardWidget(drawing_data, self)
            card.opened.connect(self._on_drawing_opened)
            card.deleted.connect(self._on_drawing_deleted)
            card.favorite_toggled.connect(self._on_favorite_toggled)
            
            # Thumbnail yükle (optimize edilmiş, tam veri çekmiyoruz)
            drawing_full = self.storage.get_drawing(drawing_data['id'])
            if drawing_full and drawing_full.get('image_data'):
                card.set_thumbnail(drawing_full['image_data'])
            
            self.grid_layout.addWidget(card)
            self.drawing_cards.append(card)
        
        # İstatistikleri güncelle
        self._update_stats()
    
    def _update_stats(self):
        """İstatistikleri güncelle"""
        total = len(self.drawing_cards)
        fav_count = sum(1 for card in self.drawing_cards if card.drawing_data.get('favorite'))
        
        if fav_count > 0:
            self.lbl_stats.setText(f"{total} çizim ({fav_count} favori)")
        else:
            self.lbl_stats.setText(f"{total} çizim")
    
    def _on_drawing_opened(self, drawing_id: int):
        """Çizim açıldı"""
        self.drawing_opened.emit(drawing_id)
    
    def _on_drawing_deleted(self, drawing_id: int):
        """Çizim silindi"""
        try:
            self.storage.delete_drawing(drawing_id)
            self._load_drawings()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Çizim silinemedi: {e}")
    
    def _on_favorite_toggled(self, drawing_id: int):
        """Favori durumu değişti"""
        try:
            self.storage.toggle_drawing_favorite(drawing_id)
            # Listeyi yenile (sıralama değişebilir)
            self._load_drawings()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Favori güncellenemedi: {e}")
    
    def refresh(self):
        """Dışarıdan yenileme için"""
        self._load_drawings()
