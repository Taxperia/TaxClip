"""
Enhanced Snippet Card Widget - ItemWidget tarzı tasarım
"""
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QFrame, QTabWidget, QToolButton
)
from PySide6.QtGui import QFont, QCursor
from ..utils import resource_path, svg_icon

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False


class SnippetCardWidget(QFrame):
    """Snippet kartı - ItemWidget tarzı"""
    
    on_copy_requested = Signal(str)
    on_delete_requested = Signal(int)
    on_favorite_toggled = Signal(int)
    on_edit_requested = Signal(int)
    
    CARD_W = 260
    CARD_H = 160
    
    def __init__(self, snippet: dict, storage, parent=None):
        super().__init__(parent)
        self.snippet = snippet
        self.snippet_id = snippet["id"]
        self.storage = storage
        self.content_loaded = False
        self.is_multi_file = bool(snippet.get("is_multi_file", 0))
        
        self.setObjectName("ItemCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(self.CARD_W, self.CARD_H)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        
        # Üst kısım: Başlık
        top = QHBoxLayout()
        top.setSpacing(4)
        
        # Multi-file badge
        if self.is_multi_file:
            badge = QLabel("📁")
            badge.setStyleSheet("font-size: 14px;")
            top.addWidget(badge)
        
        self.lbl_title = QLabel(self._shorten(snippet["title"], 30))
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 11px;")
        top.addWidget(self.lbl_title, 1)
        
        layout.addLayout(top)
        
        # Dil etiketi
        if not self.is_multi_file:
            lang_label = QLabel(snippet["language"].upper())
            lang_label.setStyleSheet("""
                background: #4A90E2;
                color: white;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 9px;
                font-weight: bold;
            """)
            lang_label.setMaximumWidth(60)
            layout.addWidget(lang_label)
        
        # Preview - kod satırları görünsün
        self.lbl_preview = QLabel()
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.lbl_preview.setWordWrap(True)
        self.lbl_preview.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_preview.setStyleSheet("color: #666; font-size: 9px; font-family: Consolas;")
        
        if not self.is_multi_file:
            code = snippet.get("code", "")
            # İlk 80 karakter veya 2 satır
            lines = code.split('\n')[:2]
            preview_text = '\n'.join(lines)
            if len(preview_text) > 80:
                preview_text = preview_text[:80] + "..."
            elif len(code.split('\n')) > 2:
                preview_text += "\n..."
            self.lbl_preview.setText(preview_text if preview_text else "(boş)")
        else:
            self.lbl_preview.setText("🗂️ Multi-file snippet")
        
        layout.addWidget(self.lbl_preview, 1)
        
        # Alt bar: tarih (note_widget gibi)
        self.bottom = QHBoxLayout()
        self.bottom.setContentsMargins(0, 0, 0, 0)
        self.bottom.setSpacing(6)
        
        created_at = snippet.get("created_at", "")
        # Tarih format: "2024-11-15 10:30" -> "15 Kas 10:30"
        date_str = created_at[:16] if len(created_at) >= 16 else created_at
        self.lbl_meta = QLabel(date_str)
        self.lbl_meta.setObjectName("MetaLabel")
        self.bottom.addWidget(self.lbl_meta, 1)
        
        # Favori ikonu
        if snippet.get("favorite"):
            self.lbl_favorite = QLabel("⭐")
            self.lbl_favorite.setStyleSheet("font-size: 12px;")
            self.bottom.addWidget(self.lbl_favorite)
        
        layout.addLayout(self.bottom)
        
        # Hover overlay
        self.hover_overlay = QWidget(self)
        self.hover_overlay.setObjectName("HoverHighlight")
        self.hover_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hover_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hover_overlay.setStyleSheet("background-color: rgba(0,0,0,0.10); border-radius: 12px;")
        self.hover_overlay.hide()
        
        # Hover toolbar
        self.toolbar = QWidget(self)
        self.toolbar.setObjectName("HoverToolbar")
        self.toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.toolbar.setStyleSheet("background-color: rgba(0,0,0,0.22); border-top-left-radius: 12px; border-top-right-radius: 12px;")
        self.toolbar.hide()
        
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(6, 4, 6, 4)
        toolbar_layout.setSpacing(6)
        
        # Copy butonu
        self.btn_copy = QToolButton()
        try:
            self.btn_copy.setIcon(svg_icon("assets/icons/copy.svg"))
        except:
            self.btn_copy.setText("📋")
        self.btn_copy.setAutoRaise(True)
        self.btn_copy.setToolTip("Kopyala")
        self.btn_copy.clicked.connect(self._copy_code)
        toolbar_layout.addWidget(self.btn_copy)
        
        # Expand butonu
        self.btn_expand = QToolButton()
        try:
            self.btn_expand.setIcon(svg_icon("assets/icons/expand.svg"))
        except:
            self.btn_expand.setText("👁️")
        self.btn_expand.setAutoRaise(True)
        self.btn_expand.setToolTip("Görüntüle")
        self.btn_expand.clicked.connect(self._expand_content)
        toolbar_layout.addWidget(self.btn_expand)
        
        # VSCode butonu
        self.btn_vscode = QToolButton()
        try:
            self.btn_vscode.setIcon(svg_icon("assets/icons/vscode.svg"))
        except:
            self.btn_vscode.setText("VS")
        self.btn_vscode.setAutoRaise(True)
        self.btn_vscode.setToolTip("VSCode'da Aç")
        self.btn_vscode.clicked.connect(self._open_in_vscode)
        toolbar_layout.addWidget(self.btn_vscode)
        
        # Edit butonu
        self.btn_edit = QToolButton()
        try:
            self.btn_edit.setIcon(svg_icon("assets/icons/edit.svg"))
        except:
            self.btn_edit.setText("✏️")
        self.btn_edit.setAutoRaise(True)
        self.btn_edit.setToolTip("Düzenle")
        self.btn_edit.clicked.connect(lambda: self.on_edit_requested.emit(self.snippet_id))
        toolbar_layout.addWidget(self.btn_edit)
        
        # Delete butonu
        self.btn_delete = QToolButton()
        try:
            self.btn_delete.setIcon(svg_icon("assets/icons/delete.svg"))
        except:
            self.btn_delete.setText("🗑️")
        self.btn_delete.setAutoRaise(True)
        self.btn_delete.setToolTip("Sil")
        self.btn_delete.clicked.connect(lambda: self.on_delete_requested.emit(self.snippet_id))
        toolbar_layout.addWidget(self.btn_delete)
    
    def _shorten(self, text: str, max_len: int) -> str:
        """Metni kısalt"""
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text
    
    def _expand_content(self):
        """İçeriği modal'da göster"""
        from .snippet_modal import SnippetModal
        
        modal = SnippetModal(self.snippet, self.storage, self)
        modal.exec()
    
    def _copy_code(self):
        """Kodu kopyala"""
        if self.is_multi_file:
            files = self.storage.get_snippet_files(self.snippet_id)
            if files:
                code = files[0].get("content", "")
                self.on_copy_requested.emit(code)
        else:
            code = self.snippet.get("code", "")
            self.on_copy_requested.emit(code)
    
    def _open_in_vscode(self):
        """Kodu VSCode'da aç"""
        import tempfile
        import subprocess
        import os
        
        try:
            # Dil uzantısı mapping
            ext_map = {
                "python": ".py",
                "javascript": ".js",
                "typescript": ".ts",
                "java": ".java",
                "cpp": ".cpp",
                "c": ".c",
                "csharp": ".cs",
                "go": ".go",
                "rust": ".rs",
                "ruby": ".rb",
                "php": ".php",
                "swift": ".swift",
                "kotlin": ".kt",
                "html": ".html",
                "css": ".css",
                "json": ".json",
                "yaml": ".yaml",
                "xml": ".xml",
                "sql": ".sql",
                "shell": ".sh",
                "bash": ".sh",
                "powershell": ".ps1",
            }
            
            if self.is_multi_file:
                # Multi-file: geçici klasör oluştur
                files = self.storage.get_snippet_files(self.snippet_id)
                if files:
                    temp_dir = tempfile.mkdtemp(prefix="taxclip_snippet_")
                    for f in files:
                        filename = f.get("filename", "file.txt")
                        content = f.get("content", "")
                        file_path = os.path.join(temp_dir, filename)
                        with open(file_path, "w", encoding="utf-8") as fp:
                            fp.write(content)
                    subprocess.Popen(["code", temp_dir], shell=True)
            else:
                # Tek dosya
                lang = self.snippet.get("language", "txt").lower()
                ext = ext_map.get(lang, ".txt")
                title = self.snippet.get("title", "snippet")
                # Dosya adından geçersiz karakterleri kaldır
                safe_title = "".join(c for c in title if c.isalnum() or c in "._- ")[:30]
                
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=ext,
                    prefix=f"{safe_title}_",
                    delete=False,
                    encoding="utf-8"
                ) as f:
                    f.write(self.snippet.get("code", ""))
                    temp_path = f.name
                
                subprocess.Popen(["code", temp_path], shell=True)
        except Exception as e:
            print(f"VSCode açma hatası: {e}")
    
    def enterEvent(self, event):
        """Hover başlangıç"""
        self.hover_overlay.setGeometry(self.rect())
        self.hover_overlay.show()
        self.toolbar.setGeometry(0, 0, self.width(), 32)
        self.toolbar.show()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hover bitiş"""
        self.hover_overlay.hide()
        self.toolbar.hide()
        super().leaveEvent(event)
