"""
Todo List Widget - Yapılacaklar listesi
Checkbox ile işaretlenebilir görevler
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
    QLineEdit, QPushButton, QFrame, QLabel, QScrollArea
)
from PySide6.QtGui import QFont
from datetime import datetime


class TodoItemWidget(QFrame):
    """Tek bir todo öğesi"""
    
    toggled = Signal(int, bool)  # todo_id, completed
    deleted = Signal(int)  # todo_id
    text_changed = Signal(int, str)  # todo_id, new_text
    
    def __init__(self, todo: dict, parent=None):
        super().__init__(parent)
        self.todo = todo
        self.todo_id = todo["id"]
        
        self.setObjectName("TodoItem")
        self.setFrameStyle(QFrame.StyledPanel)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(bool(todo.get("completed", False)))
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.checkbox)
        
        # Text (eğer tamamlanmışsa üstü çizili)
        self.txt_content = QLineEdit()
        self.txt_content.setText(todo.get("content", ""))
        self.txt_content.setFrame(False)
        self.txt_content.editingFinished.connect(self._on_text_edited)
        
        # Tamamlanmış görünümü
        self._update_style()
        
        layout.addWidget(self.txt_content, 1)
        
        # Sil butonu
        self.btn_delete = QPushButton("🗑️")
        self.btn_delete.setMaximumWidth(30)
        self.btn_delete.setFlat(True)
        self.btn_delete.clicked.connect(lambda: self.deleted.emit(self.todo_id))
        layout.addWidget(self.btn_delete)
    
    def _on_checkbox_changed(self, state):
        """Checkbox değiştiğinde"""
        completed = state == Qt.Checked
        self.todo["completed"] = completed
        self._update_style()
        self.toggled.emit(self.todo_id, completed)
    
    def _on_text_edited(self):
        """Metin düzenlendiğinde"""
        new_text = self.txt_content.text().strip()
        if new_text != self.todo.get("content", ""):
            self.todo["content"] = new_text
            self.text_changed.emit(self.todo_id, new_text)
    
    def _update_style(self):
        """Tamamlanmış/tamamlanmamış görünümü"""
        if self.todo.get("completed", False):
            font = self.txt_content.font()
            font.setStrikeOut(True)
            self.txt_content.setFont(font)
            self.txt_content.setStyleSheet("color: #888;")
        else:
            font = self.txt_content.font()
            font.setStrikeOut(False)
            self.txt_content.setFont(font)
            self.txt_content.setStyleSheet("")


class TodoListWidget(QWidget):
    """Yapılacaklar listesi yöneticisi"""
    
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.todo_widgets = []
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Üst bar - yeni todo ekle
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(8, 8, 8, 8)
        top_bar.setSpacing(8)
        
        self.txt_new_todo = QLineEdit()
        self.txt_new_todo.setPlaceholderText("Yeni görev ekle...")
        self.txt_new_todo.returnPressed.connect(self._add_todo)
        top_bar.addWidget(self.txt_new_todo, 1)
        
        self.btn_add = QPushButton("➕ Ekle")
        self.btn_add.clicked.connect(self._add_todo)
        top_bar.addWidget(self.btn_add)
        
        layout.addLayout(top_bar)
        
        # İstatistikler
        self.lbl_stats = QLabel()
        self.lbl_stats.setStyleSheet("padding: 4px 8px; color: #666; font-size: 11px;")
        layout.addWidget(self.lbl_stats)
        
        # Filtre butonları
        filter_bar = QHBoxLayout()
        filter_bar.setContentsMargins(8, 4, 8, 4)
        filter_bar.setSpacing(4)
        
        self.btn_all = QPushButton("Tümü")
        self.btn_all.setCheckable(True)
        self.btn_all.setChecked(True)
        self.btn_all.clicked.connect(lambda: self._set_filter("all"))
        filter_bar.addWidget(self.btn_all)
        
        self.btn_active = QPushButton("Aktif")
        self.btn_active.setCheckable(True)
        self.btn_active.clicked.connect(lambda: self._set_filter("active"))
        filter_bar.addWidget(self.btn_active)
        
        self.btn_completed = QPushButton("Tamamlanan")
        self.btn_completed.setCheckable(True)
        self.btn_completed.clicked.connect(lambda: self._set_filter("completed"))
        filter_bar.addWidget(self.btn_completed)
        
        filter_bar.addStretch()
        
        self.btn_clear_completed = QPushButton("🗑️ Tamamlananları Sil")
        self.btn_clear_completed.clicked.connect(self._clear_completed)
        filter_bar.addWidget(self.btn_clear_completed)
        
        layout.addLayout(filter_bar)
        
        # Todo listesi (scroll)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.container = QWidget()
        self.todo_layout = QVBoxLayout(self.container)
        self.todo_layout.setContentsMargins(0, 0, 0, 0)
        self.todo_layout.setSpacing(2)
        self.todo_layout.addStretch()
        
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)
        
        # Filtre durumu
        self.current_filter = "all"
        
        # Todo'ları yükle
        self._load_todos()
    
    def _load_todos(self):
        """Veritabanından todo'ları yükle"""
        try:
            todos = self.storage.list_todos()
            for todo in todos:
                self._add_todo_widget(todo)
            self._update_stats()
        except Exception as e:
            print(f"[TODO] Yükleme hatası: {e}")
    
    def _add_todo(self):
        """Yeni todo ekle"""
        text = self.txt_new_todo.text().strip()
        if not text:
            return
        
        try:
            todo_id = self.storage.add_todo(text)
            todo = self.storage.get_todo(todo_id)
            if todo:
                self._add_todo_widget(todo)
                self.txt_new_todo.clear()
                self._update_stats()
        except Exception as e:
            print(f"[TODO] Ekleme hatası: {e}")
    
    def _add_todo_widget(self, todo: dict):
        """Todo widget'ı ekle"""
        widget = TodoItemWidget(todo, self.container)
        widget.toggled.connect(self._on_todo_toggled)
        widget.deleted.connect(self._on_todo_deleted)
        widget.text_changed.connect(self._on_todo_text_changed)
        
        # Layout'a ekle (stretch'den önce)
        insert_at = max(0, self.todo_layout.count() - 1)
        self.todo_layout.insertWidget(insert_at, widget)
        
        self.todo_widgets.append(widget)
        self._apply_filter()
    
    def _on_todo_toggled(self, todo_id: int, completed: bool):
        """Todo tamamlandı/iptal edildi"""
        try:
            self.storage.update_todo(todo_id, completed=completed)
            self._update_stats()
            self._apply_filter()
        except Exception as e:
            print(f"[TODO] Toggle hatası: {e}")
    
    def _on_todo_deleted(self, todo_id: int):
        """Todo silindi"""
        try:
            self.storage.delete_todo(todo_id)
            
            # Widget'ı bul ve sil
            widget = next((w for w in self.todo_widgets if w.todo_id == todo_id), None)
            if widget:
                self.todo_layout.removeWidget(widget)
                self.todo_widgets.remove(widget)
                widget.setParent(None)
                widget.deleteLater()
            
            self._update_stats()
        except Exception as e:
            print(f"[TODO] Silme hatası: {e}")
    
    def _on_todo_text_changed(self, todo_id: int, new_text: str):
        """Todo metni değişti"""
        try:
            self.storage.update_todo(todo_id, content=new_text)
        except Exception as e:
            print(f"[TODO] Güncelleme hatası: {e}")
    
    def _set_filter(self, filter_type: str):
        """Filtre değiştir"""
        self.current_filter = filter_type
        
        # Butonları güncelle
        self.btn_all.setChecked(filter_type == "all")
        self.btn_active.setChecked(filter_type == "active")
        self.btn_completed.setChecked(filter_type == "completed")
        
        self._apply_filter()
    
    def _apply_filter(self):
        """Mevcut filtreyi uygula"""
        for widget in self.todo_widgets:
            completed = widget.todo.get("completed", False)
            
            if self.current_filter == "all":
                widget.setVisible(True)
            elif self.current_filter == "active":
                widget.setVisible(not completed)
            elif self.current_filter == "completed":
                widget.setVisible(completed)
    
    def _clear_completed(self):
        """Tamamlanan todo'ları sil"""
        completed_widgets = [w for w in self.todo_widgets if w.todo.get("completed", False)]
        
        for widget in completed_widgets:
            self._on_todo_deleted(widget.todo_id)
    
    def _update_stats(self):
        """İstatistikleri güncelle"""
        total = len(self.todo_widgets)
        completed = sum(1 for w in self.todo_widgets if w.todo.get("completed", False))
        active = total - completed
        
        self.lbl_stats.setText(f"Toplam: {total} | Aktif: {active} | Tamamlanan: {completed}")
