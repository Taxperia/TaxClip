"""
Todo Card Widget v2 - ItemWidget tarzı 260x160 format
"""
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QToolButton, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from ..utils import resource_path, svg_icon


CARD_W = 260
CARD_H = 160


class TodoCardWidgetV2(QFrame):
    """Todo liste kartı - 260x160 format"""
    
    delete_requested = Signal(int)  # list_id
    
    def __init__(self, list_id: int, list_data: dict, storage, parent=None):
        super().__init__(parent)
        self.list_id = list_id
        self.storage = storage
        self.list_data = dict(list_data or {})
        
        self.setObjectName("TodoCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(CARD_W, CARD_H)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Başlık
        self.title_lbl = QLabel(self.list_data.get("name", "Todo Listesi"))
        self.title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color: white;")
        layout.addWidget(self.title_lbl)
        
        # Todo items preview (max 3)
        self.items_container = QFrame()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(4)
        layout.addWidget(self.items_container)
        
        layout.addStretch()
        
        # Load items
        self._load_items()
        
        # Hover overlay
        self.hover_overlay = QWidget(self)
        self.hover_overlay.setObjectName("HoverHighlight")
        self.hover_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hover_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hover_overlay.setStyleSheet("background-color: rgba(0,0,0,0.10); border-radius: 12px;")
        self.hover_overlay.hide()
        
        # Hover toolbar - notlar gibi üstte ortalı
        self.toolbar = QWidget(self)
        self.toolbar.setObjectName("HoverToolbar")
        self.toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.toolbar.setStyleSheet("background-color: rgba(0,0,0,0.22); border-top-left-radius: 12px; border-top-right-radius: 12px;")
        self.toolbar.hide()
        
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(6, 4, 6, 4)
        toolbar_layout.setSpacing(6)
        
        # Görüntüle butonu
        self.btn_expand = QToolButton()
        try:
            self.btn_expand.setIcon(svg_icon("assets/icons/expand.svg"))
        except:
            self.btn_expand.setText("👁️")
        self.btn_expand.setAutoRaise(True)
        self.btn_expand.setStyleSheet("QToolButton { color: white; }")
        self.btn_expand.setToolTip("Görüntüle")
        self.btn_expand.clicked.connect(self._expand_list)
        toolbar_layout.addWidget(self.btn_expand)

        # Düzenle butonu
        self.btn_edit = QToolButton()
        try:
            self.btn_edit.setIcon(svg_icon("assets/icons/edit.svg"))
        except:
            self.btn_edit.setText("✏️")
        self.btn_edit.setAutoRaise(True)
        self.btn_edit.setStyleSheet("QToolButton { color: white; }")
        self.btn_edit.setToolTip("Düzenle")
        self.btn_edit.clicked.connect(self._edit_list)
        toolbar_layout.addWidget(self.btn_edit)
        
        # Sil butonu
        self.btn_delete = QToolButton()
        try:
            self.btn_delete.setIcon(svg_icon("assets/icons/delete.svg"))
        except:
            self.btn_delete.setText("🗑️")
        self.btn_delete.setAutoRaise(True)
        self.btn_delete.setStyleSheet("QToolButton { color: white; }")
        self.btn_delete.setToolTip("Sil")
        self.btn_delete.clicked.connect(self._delete_list)
        toolbar_layout.addWidget(self.btn_delete)
    
    def _load_items(self):
        """Load todos (max 3 preview)"""
        # Clear existing
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        todos = self.storage.get_todos_by_list(self.list_id)
        
        # Show max 3
        for i, todo in enumerate(todos[:3]):
            checkbox = QCheckBox(self._shorten(todo.get("content", ""), 30))
            checkbox.setFont(QFont("Segoe UI", 9))
            checkbox.setChecked(bool(todo.get("completed", False)))
            todo_id = todo.get("id")
            checkbox.stateChanged.connect(lambda state, tid=todo_id: self._toggle_todo(tid, state))
            
            if todo.get("completed"):
                checkbox.setStyleSheet("""
                    QCheckBox {
                        color: #888;
                        text-decoration: line-through;
                    }
                    QCheckBox::indicator {
                        width: 16px;
                        height: 16px;
                        border: 2px solid #888;
                        border-radius: 3px;
                        background: #28a745;
                    }
                """)
            else:
                checkbox.setStyleSheet("""
                    QCheckBox {
                        color: white;
                    }
                    QCheckBox::indicator {
                        width: 16px;
                        height: 16px;
                        border: 2px solid white;
                        border-radius: 3px;
                        background: transparent;
                    }
                """)
            
            self.items_layout.addWidget(checkbox)
        
        # Show "..." if more items
        if len(todos) > 3:
            more_lbl = QLabel(f"... +{len(todos) - 3} daha")
            more_lbl.setFont(QFont("Segoe UI", 8))
            more_lbl.setStyleSheet("color: #aaa; font-style: italic;")
            self.items_layout.addWidget(more_lbl)
    
    def _shorten(self, text: str, max_len: int) -> str:
        """Metni kısalt"""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."
    
    def _toggle_todo(self, todo_id: int, state: int):
        """Todo durumunu değiştir"""
        try:
            completed = (state == Qt.CheckState.Checked.value)
            self.storage.toggle_todo(todo_id)
            self._load_items()  # Refresh görünümü
        except Exception as e:
            print(f"Toggle todo error: {e}")
    
    def _expand_list(self):
        """Liste detayını göster (modal)"""
        from clipstack.ui.todo_modal import TodoModal
        
        dialog = TodoModal(self.list_id, self.storage, self)
        if dialog.exec():
            self._refresh_from_storage()

    def _edit_list(self):
        """Listeyi düzenle."""
        self._expand_list()

    def _refresh_from_storage(self):
        """Liste adını ve preview içeriğini veritabanından yenile."""
        list_data = self.storage.get_todo_list_by_id(self.list_id)
        if list_data:
            self.list_data = dict(list_data)
            self.title_lbl.setText(self.list_data.get("name", "Todo Listesi"))
        self._load_items()
    
    def _delete_list(self):
        """Liste sil"""
        reply = QMessageBox.question(
            self, "Liste Sil",
            f"'{self.title_lbl.text()}' listesini silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.storage.delete_todo_list(self.list_id)
                self.delete_requested.emit(self.list_id)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Silme hatası: {e}")
    
    def enterEvent(self, event):
        """Hover başlangıç"""
        self.hover_overlay.setGeometry(self.rect())
        self.hover_overlay.show()
        # Üstte tam genişlik, küçük yükseklik
        self.toolbar.setGeometry(0, 0, self.width(), 32)
        self.toolbar.show()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hover bitiş"""
        self.hover_overlay.hide()
        self.toolbar.hide()
        super().leaveEvent(event)
