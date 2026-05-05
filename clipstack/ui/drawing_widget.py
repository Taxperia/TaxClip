"""
Drawing Canvas Widget - Çizim yapmak için canvas
"""
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QColorDialog, QSpinBox, QLabel, QFrame, QComboBox,
    QMessageBox
)
from datetime import datetime
import io


class DrawingCanvas(QWidget):
    """Çizim canvas'ı"""
    
    def __init__(self, parent=None, width=800, height=600):
        super().__init__(parent)
        self.setMinimumSize(width, height)
        
        # Canvas ayarları
        self.canvas = QPixmap(width, height)
        self.canvas.fill(Qt.white)
        
        # Çizim ayarları
        self.drawing = False
        self.brush_color = QColor(0, 0, 0)
        self.brush_size = 3
        self.last_point = QPoint()
        
        # Araçlar
        self.current_tool = "pen"  # pen, eraser, stroke_eraser, line, rect, circle
        
        # Undo/Redo için history
        self.history = [self.canvas.copy()]
        self.history_index = 0
        
        # Stroke silgi için stroke'ları kaydet
        self.strokes = []  # Her stroke: {"points": [QPoint], "color": QColor, "size": int}
        self.current_stroke_points = []
        
        self.setMouseTracking(True)
    
    def mousePressEvent(self, event):
        """Fare tıklandığında"""
        if event.button() == Qt.LeftButton:
            if self.current_tool == "stroke_eraser":
                # Stroke silgi: tıklanan noktaya yakın stroke'u bul ve sil
                self._erase_stroke_at(event.pos())
            else:
                self.drawing = True
                self.last_point = event.pos()
                self.current_stroke_points = [event.pos()]
    
    def mouseMoveEvent(self, event):
        """Fare hareket ettiğinde"""
        if event.buttons() & Qt.LeftButton and self.drawing:
            painter = QPainter(self.canvas)
            
            if self.current_tool == "pen":
                pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawLine(self.last_point, event.pos())
                self.current_stroke_points.append(event.pos())
            
            elif self.current_tool == "eraser":
                pen = QPen(Qt.white, self.brush_size * 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawLine(self.last_point, event.pos())
            
            self.last_point = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Fare bırakıldığında"""
        if event.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            
            # Stroke'u kaydet (pen için)
            if self.current_tool == "pen" and len(self.current_stroke_points) > 1:
                self.strokes.append({
                    "points": self.current_stroke_points.copy(),
                    "color": QColor(self.brush_color),
                    "size": self.brush_size
                })
            
            self.current_stroke_points = []
            
            # History'ye ekle
            self._save_to_history()
    
    def paintEvent(self, event):
        """Canvas'ı çiz"""
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.canvas)
    
    def set_pen_color(self, color: QColor):
        """Kalem rengini değiştir"""
        self.brush_color = color
    
    def set_pen_size(self, size: int):
        """Kalem kalınlığını değiştir"""
        self.brush_size = size
    
    def set_tool(self, tool: str):
        """Aracı değiştir"""
        self.current_tool = tool
    
    def clear_canvas(self):
        """Canvas'ı temizle"""
        self.canvas.fill(Qt.white)
        self.strokes.clear()  # Stroke listesini de temizle
        self._save_to_history()
        self.update()
    
    def undo(self):
        """Geri al"""
        if self.history_index > 0:
            self.history_index -= 1
            self.canvas = self.history[self.history_index].copy()
            # Stroke listesini de geri al
            if len(self.strokes) > 0:
                self.strokes.pop()
            self.update()
    
    def redo(self):
        """İleri al"""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.canvas = self.history[self.history_index].copy()
            # Not: Redo için stroke'lar zaten canvas'ta
            self.update()
    
    def _erase_stroke_at(self, point: QPoint):
        """Belirtilen noktaya yakın stroke'u sil"""
        THRESHOLD = 10  # Piksel cinsinden yakınlık eşiği
        
        # Tıklanan noktaya yakın stroke'u bul
        stroke_to_remove = None
        for stroke in self.strokes:
            for stroke_point in stroke["points"]:
                # Mesafe kontrolü
                dx = stroke_point.x() - point.x()
                dy = stroke_point.y() - point.y()
                distance = (dx * dx + dy * dy) ** 0.5
                
                if distance < THRESHOLD:
                    stroke_to_remove = stroke
                    break
            
            if stroke_to_remove:
                break
        
        # Stroke'u listeden çıkar ve canvas'ı yeniden çiz
        if stroke_to_remove:
            self.strokes.remove(stroke_to_remove)
            self._redraw_canvas()
            self._save_to_history()
    
    def _redraw_canvas(self):
        """Tüm stroke'ları kullanarak canvas'ı yeniden çiz"""
        # Canvas'ı temizle
        self.canvas.fill(Qt.white)
        
        # Tüm stroke'ları çiz
        painter = QPainter(self.canvas)
        for stroke in self.strokes:
            pen = QPen(stroke["color"], stroke["size"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            
            points = stroke["points"]
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])
        
        painter.end()
        self.update()
    
    def _save_to_history(self):
        """Mevcut durumu history'ye kaydet"""
        # Önce sonraki tüm history'yi temizle
        self.history = self.history[:self.history_index + 1]
        
        # Yeni durumu ekle
        self.history.append(self.canvas.copy())
        self.history_index = len(self.history) - 1
        
        # Maksimum 50 adım tut
        if len(self.history) > 50:
            self.history.pop(0)
            self.history_index -= 1
    
    def get_image_bytes(self) -> bytes:
        """Canvas'ı PNG byte array olarak döndür"""
        import tempfile
        import os
        
        # Geçici dosyaya kaydet
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name
        
        # Canvas'ı kaydet
        self.canvas.save(tmp_path, "PNG")
        
        # Dosyayı oku
        with open(tmp_path, 'rb') as f:
            data = f.read()
        
        # Geçici dosyayı sil
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        return data
    
    def load_from_bytes(self, image_bytes: bytes):
        """Byte array'den canvas'a yükle"""
        image = QImage()
        image.loadFromData(image_bytes)
        self.canvas = QPixmap.fromImage(image)
        self.strokes.clear()  # Yüklenen resim stroke bilgisi içermiyor
        self._save_to_history()
        self.update()


class DrawingWidget(QFrame):
    """Çizim widget'ı - toolbar + canvas"""
    
    drawing_saved = Signal(int)  # drawing_id
    
    def __init__(self, storage, parent=None, drawing_id=None):
        super().__init__(parent)
        self.storage = storage
        self.drawing_id = drawing_id
        
        self.setObjectName("DrawingWidget")
        self.setFrameStyle(QFrame.StyledPanel)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        
        # Araçlar
        self.btn_pen = QPushButton("🖊️ Kalem")
        self.btn_pen.setCheckable(True)
        self.btn_pen.setChecked(True)
        self.btn_pen.clicked.connect(lambda: self._set_tool("pen"))
        toolbar.addWidget(self.btn_pen)
        
        self.btn_eraser = QPushButton("🧹 Silgi")
        self.btn_eraser.setCheckable(True)
        self.btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))
        toolbar.addWidget(self.btn_eraser)
        
        toolbar.addWidget(QLabel("|"))
        
        # Renk seçici
        self.btn_color = QPushButton("🎨 Renk")
        self.btn_color.clicked.connect(self._choose_color)
        toolbar.addWidget(self.btn_color)
        
        # Kalınlık
        toolbar.addWidget(QLabel("Kalınlık:"))
        self.spn_size = QSpinBox()
        self.spn_size.setRange(1, 50)
        self.spn_size.setValue(3)
        self.spn_size.valueChanged.connect(self._on_size_changed)
        toolbar.addWidget(self.spn_size)
        
        toolbar.addWidget(QLabel("|"))
        
        # Geri al / İleri al
        self.btn_undo = QPushButton("↶ Geri")
        self.btn_undo.clicked.connect(self._undo)
        toolbar.addWidget(self.btn_undo)
        
        self.btn_redo = QPushButton("↷ İleri")
        self.btn_redo.clicked.connect(self._redo)
        toolbar.addWidget(self.btn_redo)
        
        toolbar.addWidget(QLabel("|"))
        
        # Temizle
        self.btn_clear = QPushButton("🗑️ Temizle")
        self.btn_clear.clicked.connect(self._clear)
        toolbar.addWidget(self.btn_clear)
        
        toolbar.addStretch()
        
        # Kaydet
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.clicked.connect(self._save_drawing)
        toolbar.addWidget(self.btn_save)
        
        layout.addLayout(toolbar)
        
        # Canvas
        self.canvas = DrawingCanvas(self)
        layout.addWidget(self.canvas, 1)
        
        # Eğer mevcut bir çizim varsa yükle
        if drawing_id:
            self._load_drawing(drawing_id)
    
    def _set_tool(self, tool: str):
        """Araç seç"""
        self.btn_pen.setChecked(tool == "pen")
        self.btn_eraser.setChecked(tool == "eraser")
        self.canvas.set_tool(tool)
    
    def _choose_color(self):
        """Renk seç"""
        color = QColorDialog.getColor(self.canvas.brush_color, self, "Renk Seç")
        if color.isValid():
            self.canvas.set_pen_color(color)
            self.btn_color.setStyleSheet(f"background-color: {color.name()};")
    
    def _on_size_changed(self, value):
        """Kalınlık değişti"""
        self.canvas.set_pen_size(value)
    
    def _undo(self):
        """Geri al"""
        self.canvas.undo()
    
    def _redo(self):
        """İleri al"""
        self.canvas.redo()
    
    def _clear(self):
        """Temizle"""
        reply = QMessageBox.question(
            self,
            "Temizle",
            "Canvas'ı temizlemek istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.canvas.clear_canvas()
    
    def _save_drawing(self):
        """Çizimi kaydet"""
        try:
            import base64
            
            image_bytes = self.canvas.get_image_bytes()
            # Base64 encode (storage string bekliyor)
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            title = datetime.now().strftime("Çizim %Y-%m-%d %H:%M")
            
            if self.drawing_id:
                # Güncelle - base64 string gönder
                self.storage.update_drawing(self.drawing_id, image_data=image_b64)
            else:
                # Yeni kayıt
                self.drawing_id = self.storage.add_drawing(image_b64, title)
            
            self.drawing_saved.emit(self.drawing_id)
            
            QMessageBox.information(self, "Başarılı", "Çizim kaydedildi!")
        
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Çizim kaydedilemedi:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def _load_drawing(self, drawing_id: int):
        """Çizimi yükle"""
        try:
            import base64
            
            drawing = self.storage.get_drawing(drawing_id)
            if drawing and drawing.get("image_data"):
                img_data = drawing["image_data"]
                # Eğer string ise base64 decode et
                if isinstance(img_data, str):
                    img_bytes = base64.b64decode(img_data)
                else:
                    img_bytes = img_data
                self.canvas.load_from_bytes(img_bytes)
        except Exception as e:
            print(f"[DRAWING] Yükleme hatası: {e}")
            import traceback
            traceback.print_exc()
