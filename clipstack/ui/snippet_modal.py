"""
Snippet Modal - Loader ile içerik gösterimi
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QTabWidget, QWidget
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, Property
from PySide6.QtGui import QFont, QPainter, QColor, QPen

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False


class LoaderWidget(QWidget):
    """CSS-style spinning loader"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self._rotation = 0
        
        # Animasyon
        self.animation = QPropertyAnimation(self, b"rotation")
        self.animation.setDuration(1000)
        self.animation.setStartValue(0)
        self.animation.setEndValue(360)
        self.animation.setLoopCount(-1)
        self.animation.start()
    
    def get_rotation(self):
        return self._rotation
    
    def set_rotation(self, value):
        self._rotation = value
        self.update()
    
    rotation = Property(int, get_rotation, set_rotation)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Merkez
        cx, cy = self.width() // 2, self.height() // 2
        radius = 20
        
        painter.translate(cx, cy)
        painter.rotate(self._rotation)
        
        # Çember (border)
        pen = QPen(QColor("#4A90E2"))
        pen.setWidth(5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # 3/4 çizgi (bottom transparent)
        painter.drawArc(-radius, -radius, radius*2, radius*2, 90*16, 270*16)


class SnippetModal(QDialog):
    """Snippet görüntüleme modal'ı"""
    
    def __init__(self, snippet: dict, storage, parent=None):
        super().__init__(parent)
        self.snippet = snippet
        self.storage = storage
        self.is_multi_file = bool(snippet.get("is_multi_file", 0))
        
        self.setWindowTitle(snippet["title"])
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Başlık
        title = QLabel(snippet["title"])
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # İçerik container (önce HTML kutusu oluştur)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.content_widget, 1)
        
        # HTML kutusunu hemen oluştur
        self.txt_editor = QTextEdit()
        self.txt_editor.setReadOnly(True)
        self.txt_editor.setFont(QFont("Consolas", 10))
        self.txt_editor.setStyleSheet("""
            QTextEdit {
                background: #282c34;
                color: #abb2bf;
                border: 1px solid #4b5263;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        self.content_layout.addWidget(self.txt_editor)
        
        # Loader ortada (content üzerinde)
        self.loader = LoaderWidget(self.content_widget)
        self.loader.move(
            (self.content_widget.width() - 80) // 2,
            (self.content_widget.height() - 80) // 2
        )
        self.loader.raise_()
        
        # Butonlar
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)
        
        layout.addLayout(btn_row)
        
        # İçeriği yükle (100ms sonra - daha hızlı)
        QTimer.singleShot(100, self._load_content)
    
    def resizeEvent(self, event):
        """Loader'ı her zaman ortala"""
        super().resizeEvent(event)
        if hasattr(self, 'loader') and self.loader.isVisible():
            self.loader.move(
                (self.content_widget.width() - 80) // 2,
                (self.content_widget.height() - 80) // 2
            )
    
    def _load_content(self):
        """İçeriği yükle"""
        if self.is_multi_file:
            self._load_multi_file()
        else:
            self._load_single_file()
        
        self.loader.hide()
    
    def _load_single_file(self):
        """Tek dosya"""
        code = self.snippet.get("code", "")
        language = self.snippet.get("language", "text")
        
        # Büyük dosyalarda highlighting kasıyor, direkt plain text göster
        if len(code) > 5000:
            self.txt_editor.setPlainText(code)
            return
        
        if PYGMENTS_AVAILABLE:
            try:
                lexer = get_lexer_by_name(language, stripall=True)
                formatter = HtmlFormatter(style='monokai', noclasses=True, nobackground=True)
                highlighted = highlight(code, lexer, formatter)
                self.txt_editor.setHtml(highlighted)
            except:
                self.txt_editor.setPlainText(code)
        else:
            self.txt_editor.setPlainText(code)
    
    def _load_multi_file(self):
        """Multi-file"""
        files = self.storage.get_snippet_files(self.snippet["id"])
        
        # Tek dosya text edit'i gizle
        self.txt_editor.hide()
        
        if not files:
            lbl = QLabel("⚠️ Dosya bulunamadı")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(lbl)
            return
        
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                background: #282c34;
            }
            QTabBar::tab {
                background: #343a40;
                color: #adb5bd;
                padding: 8px 16px;
                border: 1px solid #495057;
            }
            QTabBar::tab:selected {
                background: #282c34;
                color: white;
            }
        """)
        
        for file_data in files:
            txt = QTextEdit()
            txt.setReadOnly(True)
            txt.setFont(QFont("Consolas", 10))
            txt.setStyleSheet("background: #282c34; color: #abb2bf; border: none; padding: 10px;")
            
            content = file_data.get("content", "")
            language = file_data.get("language", "text")
            
            if PYGMENTS_AVAILABLE:
                try:
                    lexer = get_lexer_by_name(language, stripall=True)
                    formatter = HtmlFormatter(style='monokai', noclasses=True, nobackground=True)
                    highlighted = highlight(content, lexer, formatter)
                    txt.setHtml(highlighted)
                except:
                    txt.setPlainText(content)
            else:
                txt.setPlainText(content)
            
            tabs.addTab(txt, file_data.get("filename", "Untitled"))
        
        self.content_layout.addWidget(tabs)
