"""
Enhanced Snippet Widget - Multi-file support ve lazy loading
"""
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QFrame, QTabWidget, QProgressBar
)
from PySide6.QtGui import QFont, QCursor

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False


class SnippetWidget(QFrame):
    """Snippet kartı - lazy loading destekli"""
    
    on_copy_requested = Signal(str)  # code
    on_delete_requested = Signal(int)  # snippet_id
    on_favorite_toggled = Signal(int)  # snippet_id
    on_edit_requested = Signal(int)  # snippet_id
    
    def __init__(self, snippet: dict, storage, parent=None):
        super().__init__(parent)
        self.snippet = snippet
        self.snippet_id = snippet["id"]
        self.storage = storage
        self.content_loaded = False
        self.is_multi_file = bool(snippet.get("is_multi_file", 0))
        
        self.setObjectName("SnippetCard")
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            SnippetWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
            SnippetWidget:hover {
                border: 2px solid #4A90E2;
                background-color: white;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Başlık satırı
        header = QHBoxLayout()
        header.setSpacing(8)
        
        # Multi-file badge
        if self.is_multi_file:
            badge = QLabel("📁 Multi")
            badge.setStyleSheet("""
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)
            header.addWidget(badge)
        
        self.lbl_title = QLabel(snippet["title"])
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50;")
        header.addWidget(self.lbl_title, 1)
        
        # Dil etiketi
        if not self.is_multi_file:
            self.lbl_language = QLabel(snippet["language"].upper())
            self.lbl_language.setStyleSheet("""
                background-color: #4A90E2;
                color: white;
                padding: 3px 10px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)
            header.addWidget(self.lbl_language)
        
        # Favori butonu
        self.btn_favorite = QPushButton("⭐" if snippet.get("favorite") else "☆")
        self.btn_favorite.setFixedSize(28, 28)
        self.btn_favorite.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_favorite.clicked.connect(lambda: self.on_favorite_toggled.emit(self.snippet_id))
        self.btn_favorite.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #fff3cd;
                border-radius: 4px;
            }
        """)
        header.addWidget(self.btn_favorite)
        
        layout.addLayout(header)
        
        # Content container (lazy loaded)
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        
        # Loading indicator
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)  # Indeterminate
        self.loading_bar.setMaximumHeight(4)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #e9ecef;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4A90E2, stop:1 #667eea);
                border-radius: 2px;
            }
        """)
        self.content_layout.addWidget(self.loading_bar)
        
        # Placeholder text
        self.lbl_placeholder = QLabel("🔽 İçeriği görmek için tıklayın")
        self.lbl_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_placeholder.setStyleSheet("color: #6c757d; font-style: italic; padding: 20px;")
        self.content_layout.addWidget(self.lbl_placeholder)
        
        layout.addWidget(self.content_container)
        
        # Butonlar
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        
        self.btn_load = QPushButton("📄 Yükle")
        self.btn_load.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_load.clicked.connect(self._load_content)
        self.btn_load.setStyleSheet("""
            QPushButton {
                background: #4A90E2;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #357ABD;
            }
        """)
        btn_row.addWidget(self.btn_load)
        
        self.btn_copy = QPushButton("📋 Kopyala")
        self.btn_copy.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_copy.clicked.connect(self._copy_code)
        self.btn_copy.setEnabled(False)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover:enabled {
                background: #218838;
            }
            QPushButton:disabled {
                background: #95a5a6;
            }
        """)
        btn_row.addWidget(self.btn_copy)
        
        self.btn_edit = QPushButton("✏️ Düzenle")
        self.btn_edit.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_edit.clicked.connect(lambda: self.on_edit_requested.emit(self.snippet_id))
        self.btn_edit.setStyleSheet("""
            QPushButton {
                background: #ffc107;
                color: #212529;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e0a800;
            }
        """)
        btn_row.addWidget(self.btn_edit)
        
        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_delete.clicked.connect(lambda: self.on_delete_requested.emit(self.snippet_id))
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background: #dc3545;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #c82333;
            }
        """)
        btn_row.addWidget(self.btn_delete)
        
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        self.setFixedWidth(450)
    
    def _load_content(self):
        """İçeriği lazy load et"""
        if self.content_loaded:
            return
        
        self.loading_bar.show()
        self.lbl_placeholder.hide()
        self.btn_load.setEnabled(False)
        
        # Simüle loading (smooth UX için)
        QTimer.singleShot(300, self._do_load_content)
    
    def _do_load_content(self):
        """Gerçek yükleme işlemi"""
        try:
            # Loading bar'ı gizle
            self.loading_bar.hide()
            
            if self.is_multi_file:
                self._load_multi_file_content()
            else:
                self._load_single_file_content()
            
            self.content_loaded = True
            self.btn_copy.setEnabled(True)
            self.btn_load.setText("✓ Yüklendi")
            self.btn_load.setStyleSheet("""
                QPushButton {
                    background: #28a745;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                }
            """)
        
        except Exception as e:
            self.loading_bar.hide()
            self.lbl_placeholder.setText(f"❌ Yükleme hatası: {e}")
            self.lbl_placeholder.show()
    
    def _load_single_file_content(self):
        """Tek dosya snippet yükle"""
        code = self.snippet.get("code", "")
        language = self.snippet.get("language", "text")
        
        txt_code = QTextEdit()
        txt_code.setReadOnly(True)
        txt_code.setMaximumHeight(250)
        txt_code.setFont(QFont("Consolas", 10))
        txt_code.setStyleSheet("""
            QTextEdit {
                background: #282c34;
                color: #abb2bf;
                border: 1px solid #4b5263;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        # Syntax highlighting
        if PYGMENTS_AVAILABLE:
            try:
                lexer = get_lexer_by_name(language, stripall=True)
                formatter = HtmlFormatter(style='monokai', noclasses=True, nobackground=True)
                highlighted = highlight(code, lexer, formatter)
                txt_code.setHtml(highlighted)
            except:
                txt_code.setPlainText(code)
        else:
            txt_code.setPlainText(code)
        
        self.content_layout.addWidget(txt_code)
        self.code_widget = txt_code
    
    def _load_multi_file_content(self):
        """Multi-file snippet yükle (tab'lı)"""
        files = self.storage.get_snippet_files(self.snippet_id)
        
        if not files:
            self.lbl_placeholder.setText("⚠️ Dosya bulunamadı")
            self.lbl_placeholder.show()
            return
        
        # Tab widget oluştur
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background: #282c34;
            }
            QTabBar::tab {
                background: #343a40;
                color: #adb5bd;
                padding: 8px 16px;
                border: 1px solid #495057;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #282c34;
                color: white;
                border-bottom: 2px solid #4A90E2;
            }
            QTabBar::tab:hover {
                background: #495057;
            }
        """)
        
        for file_data in files:
            txt_code = QTextEdit()
            txt_code.setReadOnly(True)
            txt_code.setFont(QFont("Consolas", 10))
            txt_code.setStyleSheet("""
                QTextEdit {
                    background: #282c34;
                    color: #abb2bf;
                    border: none;
                    padding: 8px;
                }
            """)
            
            content = file_data.get("content", "")
            language = file_data.get("language", "text")
            
            # Syntax highlighting
            if PYGMENTS_AVAILABLE:
                try:
                    lexer = get_lexer_by_name(language, stripall=True)
                    formatter = HtmlFormatter(style='monokai', noclasses=True, nobackground=True)
                    highlighted = highlight(content, lexer, formatter)
                    txt_code.setHtml(highlighted)
                except:
                    txt_code.setPlainText(content)
            else:
                txt_code.setPlainText(content)
            
            # Tab ekle
            filename = file_data.get("filename", "Untitled")
            tabs.addTab(txt_code, filename)
        
        self.content_layout.addWidget(tabs)
        self.code_widget = tabs
    
    def _copy_code(self):
        """Kodu kopyala"""
        if not self.content_loaded:
            return
        
        if self.is_multi_file:
            # İlk tab'ın kodunu kopyala
            if isinstance(self.code_widget, QTabWidget):
                current_tab = self.code_widget.currentWidget()
                if isinstance(current_tab, QTextEdit):
                    code = current_tab.toPlainText()
                    self.on_copy_requested.emit(code)
        else:
            if isinstance(self.code_widget, QTextEdit):
                code = self.code_widget.toPlainText()
                self.on_copy_requested.emit(code)
    
    def _update_content(self):
        """İçeriği güncelle (favori değişimi için)"""
        self.btn_favorite.setText("⭐" if self.snippet.get("favorite") else "☆")
