"""
Drawing Modal - Çizim düzenleme
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QColorDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from clipstack.ui.drawing_widget import DrawingCanvas


class DrawingModal(QDialog):
    """Çizim düzenleme modal'ı"""
    
    saved = Signal(int)  # drawing_id
    
    def __init__(self, drawing_id: int, storage, parent=None):
        super().__init__(parent)
        self.drawing_id = drawing_id
        self.storage = storage
        
        self.setWindowTitle("Çizim Düzenle")
        self.setModal(True)
        self.resize(900, 700)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        # Pen
        self.btn_pen = QPushButton("🖊️ Kalem")
        self.btn_pen.setCheckable(True)
        self.btn_pen.setChecked(True)
        self.btn_pen.setStyleSheet("color: white;")
        self.btn_pen.clicked.connect(lambda: self._set_tool("pen"))
        toolbar.addWidget(self.btn_pen)
        
        # Eraser
        self.btn_eraser = QPushButton("🧹 Silgi")
        self.btn_eraser.setCheckable(True)
        self.btn_eraser.setStyleSheet("color: white;")
        self.btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))
        toolbar.addWidget(self.btn_eraser)
        
        # Stroke Eraser
        self.btn_stroke_eraser = QPushButton("✂️ Çizgi Sil")
        self.btn_stroke_eraser.setCheckable(True)
        self.btn_stroke_eraser.setStyleSheet("color: white;")
        self.btn_stroke_eraser.clicked.connect(lambda: self._set_tool("stroke_eraser"))
        toolbar.addWidget(self.btn_stroke_eraser)
        
        # Color
        self.btn_color = QPushButton("🎨 Renk")
        self.btn_color.setStyleSheet("color: white;")
        self.btn_color.clicked.connect(self._choose_color)
        toolbar.addWidget(self.btn_color)
        
        # Undo/Redo
        self.btn_undo = QPushButton("↶ Geri")
        self.btn_undo.setStyleSheet("color: white;")
        self.btn_undo.clicked.connect(self._undo)
        toolbar.addWidget(self.btn_undo)
        
        self.btn_redo = QPushButton("↷ İleri")
        self.btn_redo.setStyleSheet("color: white;")
        self.btn_redo.clicked.connect(self._redo)
        toolbar.addWidget(self.btn_redo)
        
        # Clear
        self.btn_clear = QPushButton("🗑️ Temizle")
        self.btn_clear.setStyleSheet("color: white;")
        self.btn_clear.clicked.connect(self._clear)
        toolbar.addWidget(self.btn_clear)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Canvas
        self.canvas = DrawingCanvas()
        self.canvas.setMinimumSize(850, 550)
        layout.addWidget(self.canvas)
        
        # Butonlar
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        
        btn_save = QPushButton("💾 Kaydet")
        btn_save.setFixedSize(120, 36)
        btn_save.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #218838;
            }
            QPushButton:pressed {
                background: #1e7e34;
            }
        """)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)
        
        btn_cancel = QPushButton("İptal")
        btn_cancel.setFixedSize(120, 36)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #5a6268;
            }
            QPushButton:pressed {
                background: #545b62;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        
        layout.addLayout(btn_row)
        
        # Mevcut çizimi yükle
        self._load_drawing()
    
    def _load_drawing(self):
        """Mevcut çizimi yükle"""
        try:
            drawing = self.storage.get_drawing_by_id(self.drawing_id)
            if drawing:
                import base64
                from PySide6.QtGui import QPixmap
                
                img_key = "image_data" if "image_data" in drawing else "image"
                img_b64 = drawing[img_key]
                
                # Base64 padding düzelt
                if isinstance(img_b64, str):
                    padding = len(img_b64) % 4
                    if padding:
                        img_b64 += '=' * (4 - padding)
                
                img_bytes = base64.b64decode(img_b64)
                pixmap = QPixmap()
                pixmap.loadFromData(img_bytes)
                
                if not pixmap.isNull():
                    self.canvas.canvas = pixmap
                    self.canvas.update()
        except Exception as e:
            print(f"Çizim yükleme hatası: {e}")
    
    def _set_tool(self, tool: str):
        """Araç seç"""
        self.canvas.set_tool(tool)
        
        self.btn_pen.setChecked(tool == "pen")
        self.btn_eraser.setChecked(tool == "eraser")
        self.btn_stroke_eraser.setChecked(tool == "stroke_eraser")
    
    def _choose_color(self):
        """Renk seç"""
        color = QColorDialog.getColor(self.canvas.brush_color, self)
        if color.isValid():
            self.canvas.set_pen_color(color)
    
    def _undo(self):
        """Geri al"""
        self.canvas.undo()
    
    def _redo(self):
        """İleri al"""
        self.canvas.redo()
    
    def _clear(self):
        """Temizle"""
        reply = QMessageBox.question(
            self, "Temizle",
            "Çizimi tamamen silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.canvas.clear_canvas()
    
    def _save(self):
        """Kaydet"""
        try:
            import tempfile
            import base64
            import os
            
            # Tempfile ile kaydet
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            
            # QPixmap'i kaydet
            self.canvas.canvas.save(tmp_path, "PNG")
            
            with open(tmp_path, "rb") as f:
                img_bytes = f.read()
            
            os.remove(tmp_path)
            
            # Base64 encode
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            
            # Veritabanına kaydet
            self.storage.update_drawing(self.drawing_id, img_b64)
            
            self.saved.emit(self.drawing_id)
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {e}")
