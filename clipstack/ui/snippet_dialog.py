"""
Snippet Ekleme/Düzenleme Dialog'u
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QComboBox, QPushButton, QLabel
)
from PySide6.QtGui import QFont


# Popüler programlama dilleri
LANGUAGES = [
    "python", "javascript", "typescript", "java", "c", "cpp", "csharp",
    "go", "rust", "php", "ruby", "swift", "kotlin", "dart",
    "html", "css", "scss", "sql", "bash", "powershell",
    "json", "xml", "yaml", "markdown", "text"
]


class SnippetDialog(QDialog):
    """Snippet ekleme/düzenleme dialog'u"""
    
    def __init__(self, parent=None, snippet=None):
        super().__init__(parent)
        self.snippet = snippet
        self.setWindowTitle("Snippet Düzenle" if snippet else "Yeni Snippet")
        self.resize(700, 500)
        
        layout = QVBoxLayout(self)
        
        # Form
        form = QFormLayout()
        form.setSpacing(10)
        
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Snippet başlığı")
        if snippet:
            self.txt_title.setText(snippet.get("title", ""))
        form.addRow("Başlık:", self.txt_title)
        
        self.cmb_language = QComboBox()
        for lang in LANGUAGES:
            self.cmb_language.addItem(lang.upper(), lang)
        if snippet:
            idx = self.cmb_language.findData(snippet.get("language", "python"))
            if idx >= 0:
                self.cmb_language.setCurrentIndex(idx)
        form.addRow("Dil:", self.cmb_language)
        
        self.txt_tags = QLineEdit()
        self.txt_tags.setPlaceholderText("Etiketler (virgülle ayırın)")
        if snippet:
            self.txt_tags.setText(snippet.get("tags", ""))
        form.addRow("Etiketler:", self.txt_tags)
        
        layout.addLayout(form)
        
        # Kod alanı
        lbl_code = QLabel("Kod:")
        lbl_code.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_code)
        
        self.txt_code = QTextEdit()
        self.txt_code.setFont(QFont("Consolas", 11))
        self.txt_code.setPlaceholderText("Kodunuzu buraya yazın...")
        if snippet:
            self.txt_code.setPlainText(snippet.get("code", ""))
        layout.addWidget(self.txt_code)
        
        # Butonlar
        buttons = QHBoxLayout()
        
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.clicked.connect(self.accept)
        self.btn_save.setDefault(True)
        buttons.addWidget(self.btn_save)
        
        self.btn_cancel = QPushButton("❌ İptal")
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_cancel)
        
        buttons.addStretch()
        
        layout.addLayout(buttons)
    
    def get_data(self) -> dict:
        """Dialog verilerini al"""
        return {
            "title": self.txt_title.text().strip(),
            "code": self.txt_code.toPlainText(),
            "language": self.cmb_language.currentData(),
            "tags": self.txt_tags.text().strip()
        }
