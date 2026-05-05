"""
Todo Card Widget - Her liste ayrı bir kart (copy card tarzı)
Bir kartta birden fazla todo item olabilir
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QCheckBox, QFrame, QLabel, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor
from datetime import datetime


class TodoItemRow(QWidget):
    """Bir todo satırı (checkbox + text)"""
    
    toggled = Signal(int, bool)  # todo_id, checked
    deleted = Signal(int)  # todo_id
    text_changed = Signal(int, str)  # todo_id, new_text
    
    def __init__(self, todo: dict, parent=None):
        super().__init__(parent)
        self.todo = todo
        self.todo_id = todo["id"]
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)
        
        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(bool(todo.get("completed", False)))
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.checkbox)
        
        # Text field
        self.txt_content = QLineEdit()
        self.txt_content.setText(todo.get("content", ""))
        self.txt_content.setFrame(False)
        self.txt_content.editingFinished.connect(self._on_text_edited)
        layout.addWidget(self.txt_content, 1)
        
        # Sil butonu
        self.btn_delete = QPushButton("✕")
        self.btn_delete.setFixedSize(24, 24)
        self.btn_delete.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #999;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #e74c3c;
                background: #fee;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.btn_delete)
        
        self._update_style()
    
    def _update_style(self):
        """Checkbox durumuna göre stil güncelle"""
        is_completed = self.checkbox.isChecked()
        
        if is_completed:
            # Tamamlanmış: üstü çizili, soluk
            self.txt_content.setStyleSheet("""
                QLineEdit {
                    text-decoration: line-through;
                    color: #999;
                    background: transparent;
                }
            """)
        else:
            # Aktif: normal
            self.txt_content.setStyleSheet("""
                QLineEdit {
                    color: #333;
                    background: transparent;
                }
            """)
    
    def _on_checkbox_changed(self):
        """Checkbox değişti"""
        is_checked = self.checkbox.isChecked()
        self._update_style()
        self.toggled.emit(self.todo_id, is_checked)
    
    def _on_text_edited(self):
        """Text değişti"""
        new_text = self.txt_content.text().strip()
        if new_text != self.todo.get("content", ""):
            self.text_changed.emit(self.todo_id, new_text)
    
    def _on_delete_clicked(self):
        """Sil butonuna tıklandı"""
        self.deleted.emit(self.todo_id)


class TodoCardWidget(QFrame):
    """Todo listesi kartı - copy card tarzında"""
    
    card_deleted = Signal(int)  # list_id
    todos_changed = Signal()  # Herhangi bir değişiklik
    
    def __init__(self, storage, list_todos: list, parent=None, list_name: str = None, list_id: int = None):
        super().__init__(parent)
        self.storage = storage
        self.list_todos = list_todos  # Bu listeye ait tüm todo'lar
        self.todo_rows = []
        self.list_name = list_name or "Liste"
        
        # List ID'yi ayarla
        if list_id is not None:
            self.list_id = list_id
        elif list_todos:
            self.list_id = list_todos[0].get("list_id", list_todos[0]["id"])
        else:
            self.list_id = 0
        
        # Tarih için
        if list_todos:
            created_at = list_todos[0].get("created_at", "")
        else:
            created_at = ""
        
        self._init_ui(created_at)
        self._load_todos()
        self._update_stats()
    
    def _init_ui(self, created_at: str):
        """UI oluştur"""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            TodoCardWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 8px;
            }
            TodoCardWidget:hover {
                border: 2px solid #3498db;
                background-color: #f0f8ff;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Üst bar: Liste adı + Tarih + Düzenle + Sil butonu
        top_bar = QHBoxLayout()
        
        # Liste adı etiketi
        self.lbl_list_name = QLabel(self.list_name)
        self.lbl_list_name.setStyleSheet("font-weight: bold; font-size: 12pt; color: #2c3e50;")
        top_bar.addWidget(self.lbl_list_name)
        
        # Tarih etiketi
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at)
                date_str = dt.strftime("%d.%m.%Y")
            except:
                date_str = created_at
        else:
            date_str = ""
        
        self.lbl_date = QLabel(date_str)
        self.lbl_date.setStyleSheet("color: #95a5a6; font-size: 9pt;")
        top_bar.addWidget(self.lbl_date)
        
        top_bar.addStretch()
        
        # Düzenle butonu
        self.btn_edit_card = QPushButton("✏️")
        self.btn_edit_card.setFixedSize(28, 28)
        self.btn_edit_card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_edit_card.clicked.connect(self._on_edit_card)
        self.btn_edit_card.setToolTip("Listeyi düzenle")
        self.btn_edit_card.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #3498db;
                color: white;
                border-radius: 4px;
            }
        """)
        top_bar.addWidget(self.btn_edit_card)
        
        # Kart sil butonu
        self.btn_delete_card = QPushButton("🗑️")
        self.btn_delete_card.setFixedSize(28, 28)
        self.btn_delete_card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_delete_card.clicked.connect(self._on_delete_card)
        self.btn_delete_card.setToolTip("Tüm listeyi sil")
        self.btn_delete_card.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #e74c3c;
                color: white;
                border-radius: 4px;
            }
        """)
        top_bar.addWidget(self.btn_delete_card)
        
        layout.addLayout(top_bar)
        
        # Todo satırları için container
        self.todos_container = QVBoxLayout()
        self.todos_container.setSpacing(4)
        layout.addLayout(self.todos_container)
        
        # Yeni todo ekle satırı
        add_row = QHBoxLayout()
        self.txt_new_todo = QLineEdit()
        self.txt_new_todo.setPlaceholderText("Yeni görev ekle...")
        self.txt_new_todo.setFrame(False)
        self.txt_new_todo.setStyleSheet("""
            QLineEdit {
                background: #f8f9fa;
                padding: 6px 8px;
                border-radius: 4px;
                border: 1px solid #e0e0e0;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
                background: white;
            }
        """)
        self.txt_new_todo.returnPressed.connect(self._add_new_todo)
        add_row.addWidget(self.txt_new_todo)
        
        self.btn_add = QPushButton("➕")
        self.btn_add.setFixedSize(28, 28)
        self.btn_add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_add.clicked.connect(self._add_new_todo)
        self.btn_add.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        add_row.addWidget(self.btn_add)
        
        layout.addLayout(add_row)
        
        # Alt bar: İstatistikler
        self.lbl_stats = QLabel("0 görev")
        self.lbl_stats.setStyleSheet("color: #95a5a6; font-size: 9pt;")
        layout.addWidget(self.lbl_stats)
        
        self.setFixedWidth(350)
    
    def _load_todos(self):
        """Todo satırlarını yükle"""
        # Eski satırları temizle
        for row in self.todo_rows:
            self.todos_container.removeWidget(row)
            row.deleteLater()
        self.todo_rows.clear()
        
        # Yeni satırları ekle
        for todo in self.list_todos:
            row = TodoItemRow(todo, self)
            row.toggled.connect(self._on_todo_toggled)
            row.deleted.connect(self._on_todo_deleted)
            row.text_changed.connect(self._on_todo_text_changed)
            
            self.todos_container.addWidget(row)
            self.todo_rows.append(row)
    
    def _update_stats(self):
        """İstatistikleri güncelle"""
        total = len(self.list_todos)
        completed = sum(1 for todo in self.list_todos if todo.get("completed"))
        
        if completed > 0:
            self.lbl_stats.setText(f"{total} görev ({completed} tamamlandı)")
        else:
            self.lbl_stats.setText(f"{total} görev")
    
    def _add_new_todo(self):
        """Yeni todo ekle"""
        text = self.txt_new_todo.text().strip()
        if not text:
            return
        
        # Veritabanına ekle
        todo_id = self.storage.add_todo(text)
        
        # Listeye ekle
        new_todo = {
            "id": todo_id,
            "content": text,
            "completed": False,
            "created_at": datetime.now().isoformat()
        }
        self.list_todos.append(new_todo)
        
        # UI'a ekle
        row = TodoItemRow(new_todo, self)
        row.toggled.connect(self._on_todo_toggled)
        row.deleted.connect(self._on_todo_deleted)
        row.text_changed.connect(self._on_todo_text_changed)
        self.todos_container.addWidget(row)
        self.todo_rows.append(row)
        
        # Text field'i temizle
        self.txt_new_todo.clear()
        
        self._update_stats()
        self.todos_changed.emit()
    
    def _on_todo_toggled(self, todo_id: int, checked: bool):
        """Todo checkbox değişti"""
        self.storage.update_todo(todo_id, completed=checked)
        
        # Liste verisini güncelle
        for todo in self.list_todos:
            if todo["id"] == todo_id:
                todo["completed"] = checked
                break
        
        self._update_stats()
        self.todos_changed.emit()
    
    def _on_todo_deleted(self, todo_id: int):
        """Todo silindi"""
        self.storage.delete_todo(todo_id)
        
        # Liste verisinden kaldır
        self.list_todos = [t for t in self.list_todos if t["id"] != todo_id]
        
        # UI'dan kaldır
        for row in self.todo_rows:
            if row.todo_id == todo_id:
                self.todos_container.removeWidget(row)
                self.todo_rows.remove(row)
                row.deleteLater()
                break
        
        # Eğer liste boşaldıysa kartı sil
        if not self.list_todos:
            self.card_deleted.emit(self.list_id)
            return
        
        self._update_stats()
        self.todos_changed.emit()
    
    def _on_todo_text_changed(self, todo_id: int, new_text: str):
        """Todo metni değişti"""
        if not new_text:
            return
        
        self.storage.update_todo(todo_id, content=new_text)
        
        # Liste verisini güncelle
        for todo in self.list_todos:
            if todo["id"] == todo_id:
                todo["content"] = new_text
                break
        
        self.todos_changed.emit()
    
    def _on_edit_card(self):
        """Listeyi düzenle - modal aç"""
        from .todo_modal import TodoModal
        
        modal = TodoModal(self.list_id, self.storage, self, list_name=self.list_name)
        modal.exec()
        
        # Modal kapandıktan sonra verileri yenile
        self._refresh_from_db()
        self.todos_changed.emit()
    
    def _refresh_from_db(self):
        """Veritabanından verileri yenile"""
        try:
            # list_id'ye göre todo'ları çek
            self.list_todos = self.storage.get_todos_by_list(self.list_id)
            
            # Liste adını güncelle
            todo_list = self.storage.get_todo_list_by_id(self.list_id)
            if todo_list:
                self.list_name = todo_list.get("name", "Liste")
                self.lbl_list_name.setText(self.list_name)
            
            self._load_todos()
            self._update_stats()
        except Exception as e:
            print(f"[TODO] Refresh hatası: {e}")
    
    def _on_delete_card(self):
        """Tüm kartı sil"""
        reply = QMessageBox.question(
            self,
            "Listeyi Sil",
            f"Bu listedeki {len(self.list_todos)} görevi silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Tüm todo'ları sil
            for todo in self.list_todos:
                self.storage.delete_todo(todo["id"])
            
            self.card_deleted.emit(self.list_id)
