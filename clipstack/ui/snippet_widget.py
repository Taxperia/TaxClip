"""
Snippet Widget - Kod parçacıklarını gösterir
Syntax highlighting ile
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QFrame
)
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import HtmlFormatter
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False


class SnippetWidget(QFrame):
    """Snippet kartı"""
    
    on_copy_requested = Signal(str)  # code
    on_delete_requested = Signal(int)  # snippet_id
    on_favorite_toggled = Signal(int)  # snippet_id
    on_edit_requested = Signal(int)  # snippet_id
    
    def __init__(self, snippet: dict, parent=None):
        super().__init__(parent)
        self.snippet = snippet
        self.snippet_id = snippet["id"]
        
        self.setObjectName("SnippetCard")
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setLineWidth(1)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Başlık satırı
        header = QHBoxLayout()
        header.setSpacing(8)
        
        self.lbl_title = QLabel(snippet["title"])
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(self.lbl_title, 1)
        
        # Dil etiketi
        self.lbl_language = QLabel(snippet["language"].upper())
        self.lbl_language.setStyleSheet("""
            background-color: #4A90E2;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
        """)
        header.addWidget(self.lbl_language)
        
        # Favori butonu
        self.btn_favorite = QPushButton("⭐" if snippet.get("favorite") else "☆")
        self.btn_favorite.setMaximumWidth(30)
        self.btn_favorite.clicked.connect(lambda: self.on_favorite_toggled.emit(self.snippet_id))
        header.addWidget(self.btn_favorite)
        
        layout.addLayout(header)
        
        # Kod alanı
        self.txt_code = QTextEdit()
        self.txt_code.setReadOnly(True)
        self.txt_code.setMaximumHeight(200)
        self.txt_code.setFont(QFont("Consolas", 10))
        
        # Syntax highlighting uygula
        if PYGMENTS_AVAILABLE:
            try:
                lexer = get_lexer_by_name(snippet["language"], stripall=True)
                formatter = HtmlFormatter(style='monokai', noclasses=True)
                highlighted = highlight(snippet["code"], lexer, formatter)
                self.txt_code.setHtml(highlighted)
            except Exception:
                self.txt_code.setPlainText(snippet["code"])
        else:
            self.txt_code.setPlainText(snippet["code"])
        
        layout.addWidget(self.txt_code)
        
        # Tags
        if snippet.get("tags"):
            self.lbl_tags = QLabel(f"🏷️ {snippet['tags']}")
            self.lbl_tags.setStyleSheet("font-size: 11px; color: #888;")
            layout.addWidget(self.lbl_tags)
        
        # Butonlar
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        
        self.btn_copy = QPushButton("📋 Kopyala")
        self.btn_copy.clicked.connect(lambda: self.on_copy_requested.emit(snippet["code"]))
        buttons.addWidget(self.btn_copy)
        
        self.btn_edit = QPushButton("✏️ Düzenle")
        self.btn_edit.clicked.connect(lambda: self.on_edit_requested.emit(self.snippet_id))
        buttons.addWidget(self.btn_edit)
        
        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.clicked.connect(lambda: self.on_delete_requested.emit(self.snippet_id))
        buttons.addWidget(self.btn_delete)
        
        buttons.addStretch()
        
        layout.addLayout(buttons)
    
    def _update_content(self):
        """Widget içeriğini güncelle"""
        snippet = self.snippet
        
        # Başlık güncelle
        self.lbl_title.setText(snippet["title"])
        
        # Dil etiketi güncelle
        self.lbl_language.setText(snippet["language"].upper())
        
        # Favori butonu güncelle
        self.btn_favorite.setText("⭐" if snippet.get("favorite") else "☆")
        
        # Kod alanı güncelle
        if PYGMENTS_AVAILABLE:
            try:
                lexer = get_lexer_by_name(snippet["language"], stripall=True)
                formatter = HtmlFormatter(style='monokai', noclasses=True)
                highlighted = highlight(snippet["code"], lexer, formatter)
                self.txt_code.setHtml(highlighted)
            except Exception:
                self.txt_code.setPlainText(snippet["code"])
        else:
            self.txt_code.setPlainText(snippet["code"])
        
        # Tags güncelle
        if hasattr(self, 'lbl_tags'):
            if snippet.get("tags"):
                self.lbl_tags.setText(f"🏷️ {snippet['tags']}")
                self.lbl_tags.setVisible(True)
            else:
                self.lbl_tags.setVisible(False)
