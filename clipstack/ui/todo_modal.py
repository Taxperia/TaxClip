"""
Todo Modal - Todo listesi düzenleme
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QFrame, QScrollArea, QWidget, QMessageBox, QToolButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from ..utils import resource_path, svg_icon


class TodoItemRow(QWidget):
    """Tek todo satırı"""
    
    def __init__(self, todo: dict, storage, parent=None):
        super().__init__(parent)
        self.todo = todo
        self.todo_id = todo["id"]
        self.storage = storage
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        
        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(bool(todo.get("completed", False)))
        self.checkbox.stateChanged.connect(self._on_toggle)
        layout.addWidget(self.checkbox)
        
        # Text
        self.txt = QLineEdit(todo.get("content", ""))
        self.txt.setFrame(False)
        self.txt.editingFinished.connect(self._on_text_changed)
        layout.addWidget(self.txt, 1)
        
        # Sil
        btn_delete = QToolButton()
        try:
            btn_delete.setIcon(svg_icon("assets/icons/delete.svg"))
        except:
            btn_delete.setText("🗑️")
        btn_delete.setFixedSize(24, 24)
        btn_delete.setAutoRaise(True)
        btn_delete.setToolTip("Sil")
        btn_delete.clicked.connect(self._on_delete)
        btn_delete.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
            }
            QToolButton:hover {
                background: rgba(255,255,255,0.1);
                border-radius: 4px;
            }
        """)
        layout.addWidget(btn_delete)
        
        self._update_style()
    
    def _update_style(self):
        """Stil güncelle"""
        if self.checkbox.isChecked():
            self.txt.setStyleSheet("""
                QLineEdit {
                    color: #888;
                    text-decoration: line-through;
                    background: transparent;
                }
            """)
            self.checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 2px solid #888;
                    border-radius: 3px;
                    background: #28a745;
                }
            """)
        else:
            self.txt.setStyleSheet("""
                QLineEdit {
                    color: white;
                    background: transparent;
                }
            """)
            self.checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 2px solid white;
                    border-radius: 3px;
                    background: transparent;
                }
            """)
    
    def _on_toggle(self):
        """Toggle"""
        self.storage.update_todo_status(self.todo_id, self.checkbox.isChecked())
        self._update_style()
    
    def _on_text_changed(self):
        """Text değişti"""
        new_text = self.txt.text().strip()
        if new_text and new_text != self.todo.get("content", ""):
            self.storage.update_todo_content(self.todo_id, new_text)
    
    def _on_delete(self):
        """Sil"""
        self.storage.delete_todo(self.todo_id)
        self.deleteLater()


class TodoModal(QDialog):
    """Todo listesi modal'ı"""
    
    def __init__(self, list_id: int, storage, parent=None, list_name: str = None):
        super().__init__(parent)
        self.list_id = list_id
        self.storage = storage
        
        if list_name is None:
            list_data = storage.get_todo_list_by_id(list_id)
            list_name = list_data.get("name", "Todo Listesi") if list_data else "Todo Listesi"
        
        self.current_list_name = list_name
        
        self.setWindowTitle(list_name)
        self.setModal(True)
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Başlık
        header = QHBoxLayout()
        
        self.title_lbl = QLabel(list_name)
        self.title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.addWidget(self.title_lbl)
        
        header.addStretch()
        
        btn_edit_name = QPushButton("✏️ Adı Düzenle")
        btn_edit_name.clicked.connect(self._edit_name)
        header.addWidget(btn_edit_name)
        
        layout.addLayout(header)
        
        # Yeni todo input
        input_layout = QHBoxLayout()
        
        self.new_todo_input = QLineEdit()
        self.new_todo_input.setPlaceholderText("Yeni görev ekle...")
        self.new_todo_input.returnPressed.connect(self._add_todo)
        input_layout.addWidget(self.new_todo_input)
        
        btn_add = QPushButton("➕ Ekle")
        btn_add.clicked.connect(self._add_todo)
        input_layout.addWidget(btn_add)
        
        layout.addLayout(input_layout)
        
        # Scroll area for todos
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.todos_container = QWidget()
        self.todos_layout = QVBoxLayout(self.todos_container)
        self.todos_layout.setContentsMargins(0, 10, 0, 10)
        self.todos_layout.setSpacing(8)
        self.todos_layout.addStretch()
        
        scroll.setWidget(self.todos_container)
        layout.addWidget(scroll)
        
        # Butonlar
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        
        layout.addLayout(btn_row)
        
        # Load todos
        self._load_todos()
    
    def _load_todos(self):
        """Load todos"""
        # Clear
        while self.todos_layout.count() > 1:  # Keep stretch
            item = self.todos_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        todos = self.storage.get_todos_by_list(self.list_id)
        
        for todo in todos:
            row = TodoItemRow(todo, self.storage, self)
            self.todos_layout.insertWidget(self.todos_layout.count() - 1, row)
    
    def _add_todo(self):
        """Yeni todo ekle"""
        text = self.new_todo_input.text().strip()
        if not text:
            return
        
        try:
            self.storage.add_todo(self.list_id, text)
            self.new_todo_input.clear()
            self._load_todos()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Ekleme hatası: {e}")
    
    def _edit_name(self):
        """Liste adını düzenle"""
        from PySide6.QtWidgets import QInputDialog
        
        new_name, ok = QInputDialog.getText(
            self, "Liste Adını Düzenle",
            "Yeni ad:",
            text=self.title_lbl.text()
        )
        
        if ok and new_name.strip():
            self.storage.update_todo_list_name(self.list_id, new_name.strip())
            self.title_lbl.setText(new_name.strip())
            self.setWindowTitle(new_name.strip())
